from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Self, cast
from urllib.parse import quote
from uuid import uuid4

import httpx

from ._errors import (
    OkCommandError,
    OkConfigurationError,
    OkConnectionError,
    OkResponseError,
    OkStatusError,
    OkTimeoutError,
    status_error_class,
)
from ._firestore import (
    DEFAULT_FIRESTORE_PROJECT_ID,
    AsyncBlockingCallRunner,
    AsyncFirestoreWatchSubscription,
    FirestoreWatchCallback,
    FirestoreWatchSubscription,
    async_watch_firestore_document,
    charging_station_status_document_path,
    charging_transaction_document_path,
    decode_firestore_document,
    watch_firestore_document,
)
from ._models import (
    ChargingCommandResponse,
    ChargingLocation,
    ChargingReceipt,
    CurrentCharging,
    DeviceSettingsResponse,
    FirestoreDocument,
    JsonObject,
    JsonValue,
    LoginResponse,
    RegisterDeviceResponse,
    StationPricesResponse,
)
from ._signing import SHA_1, SHA_256, generate_signature
from ._version import __version__

TimestampProvider = Callable[[], int]

DEFAULT_SERVICE_URL = "https://okappservice.ok.dk/service/okappservice.svc"
DEFAULT_DATA_URL = "https://appdata.emsp.ok.dk/api"
DEFAULT_STATUS_URL = (
    "https://firestore.googleapis.com/v1/projects/"
    "knp-ok-app-prod/databases/(default)/documents/OK/Emsp"
)
_MAX_ERROR_DETAIL_LENGTH = 200


@dataclass(frozen=True, slots=True)
class _OkApiResponse:
    payload: JsonValue
    status_code: int
    headers: Mapping[str, str]
    request_id: str | None


@dataclass(slots=True)
class OkApiConfig:
    """Runtime configuration for the OK API client."""

    app_id: str | None = None
    app_secret: str | None = field(default=None, repr=False)
    device_id: str | None = None
    device_friendly_id: str | None = None
    login_token: str | None = field(default=None, repr=False)
    service_url: str = DEFAULT_SERVICE_URL
    data_url: str = DEFAULT_DATA_URL
    status_url: str = DEFAULT_STATUS_URL
    app_platform: str = "HomeAssistant"
    app_version: str = __version__
    timeout: float | httpx.Timeout = 10.0
    user_agent: str = f"homeassistant-ok/{__version__}"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        source = env if env is not None else os.environ
        return cls(
            app_id=source.get("OK_APP_ID"),
            app_secret=source.get("OK_APP_SECRET"),
            device_id=source.get("OK_DEVICE_ID"),
            device_friendly_id=source.get("OK_DEVICE_FRIENDLY_ID"),
            login_token=source.get("OK_LOGIN_TOKEN"),
            service_url=source.get("OK_SERVICE_URL", DEFAULT_SERVICE_URL),
            data_url=source.get("OK_DATA_URL", DEFAULT_DATA_URL),
            status_url=source.get("OK_STATUS_URL", DEFAULT_STATUS_URL),
            app_platform=source.get("OK_APP_PLATFORM", "HomeAssistant"),
            app_version=source.get("OK_APP_VERSION", __version__),
        )


class _BaseOkApiClient:
    config: OkApiConfig
    _timestamp_provider: TimestampProvider

    def _require_app_credentials(self) -> tuple[str, str]:
        if not self.config.app_id:
            raise OkConfigurationError("app_id is required for signed OK API requests")
        if not self.config.app_secret:
            raise OkConfigurationError("app_secret is required for signed OK API requests")
        return self.config.app_id, self.config.app_secret

    def _require_app_secret(self) -> str:
        if not self.config.app_secret:
            raise OkConfigurationError("app_secret is required for signed OK API requests")
        return self.config.app_secret

    def _require_device_id(self) -> str:
        if not self.config.device_id:
            raise OkConfigurationError(
                "device_id is required; call register_device(), pass device_id=, "
                "or set OK_DEVICE_ID"
            )
        return self.config.device_id

    def _common_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": self.config.user_agent,
            "X-App-Platform": self.config.app_platform,
            "X-App-Version": self.config.app_version,
            "X-App-Configuration": "consumer",
        }

    def _service_payload(self, payload: Mapping[str, JsonValue]) -> JsonObject:
        app_id, app_secret = self._require_app_credentials()
        signed = dict(payload)
        signed["hmac"] = generate_signature(app_id, app_secret, payload, algorithm=SHA_1)
        return signed

    def _data_headers(self) -> dict[str, str]:
        app_id, app_secret = self._require_app_credentials()
        device_id = self._require_device_id()
        timestamp = self._timestamp_provider()
        signature = generate_signature(
            app_id,
            app_secret,
            {"deviceId": device_id, "timestamp": timestamp},
            algorithm=SHA_256,
        )
        headers = self._common_headers()
        headers.update(
            {
                "OK-App-DeviceId": device_id,
                "OK-App-Hmac-Timestamp": str(timestamp),
                "OK-App-Hmac-Signature": signature,
            }
        )
        return headers

    def _status_headers(self) -> dict[str, str]:
        return self._common_headers()

    def _new_register_payload(
        self,
        *,
        os_device_token: str | None,
        app_id: str | None,
    ) -> JsonObject:
        configured_app_id = app_id or self.config.app_id or str(uuid4()).upper()
        self.config.app_id = configured_app_id
        self._require_app_secret()
        return self._service_payload(
            {
                "osDeviceToken": os_device_token or str(uuid4()),
                "appId": configured_app_id,
            }
        )

    def _store_register_response(self, data: Mapping[str, Any]) -> None:
        result = data.get("RegistrerDeviceResult")
        if isinstance(result, Mapping):
            device_id = result.get("DeviceId")
            friendly_id = result.get("DeviceFriendlyId")
            if isinstance(device_id, str):
                self.config.device_id = device_id
            if isinstance(friendly_id, str):
                self.config.device_friendly_id = friendly_id

    def _store_login_response(self, data: Mapping[str, Any]) -> None:
        result = data.get("LogIndResult")
        if isinstance(result, Mapping):
            token = result.get("LogIndToken")
            if isinstance(token, str):
                self.config.login_token = token

    def _store_device_settings_response(self, data: Mapping[str, Any]) -> None:
        result = data.get("HentDeviceOpsaetningResult")
        if not isinstance(result, Mapping):
            return
        device_id = result.get("DeviceId")
        friendly_id = result.get("DeviceFriendlyId")
        if isinstance(device_id, str):
            self.config.device_id = device_id
        if isinstance(friendly_id, str):
            self.config.device_friendly_id = friendly_id
        user = result.get("Bruger")
        if isinstance(user, Mapping):
            token = user.get("LogIndToken")
            if isinstance(token, str):
                self.config.login_token = token

    def _format_datetime(self, value: datetime | str) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _join_url(self, base_url: str, path: str) -> str:
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    def _segment(self, value: str | int) -> str:
        return quote(str(value), safe="")

    def _checked_command_response(
        self,
        response: JsonValue | _OkApiResponse,
    ) -> JsonValue | _OkApiResponse:
        payload = _response_payload(response)
        if not isinstance(payload, Mapping):
            return response
        result = payload.get("result")
        has_error_fields = (
            payload.get("errorcode") is not None or payload.get("errordescription") is not None
        )
        if result == "Success" or (result is None and not has_error_fields):
            return payload

        description = payload.get("errordescription")
        reason = (
            str(description)
            if isinstance(description, str) and description
            else str(result or payload.get("errorcode") or "unknown error")
        )
        raise OkCommandError(
            f"OK command failed: {reason}",
            result=result,
            error_code=payload.get("errorcode"),
            error_description=reason,
            payload=payload,
        )

    def _expect_json_object(
        self, response: JsonValue | _OkApiResponse, endpoint: str
    ) -> JsonObject:
        payload = _response_payload(response)
        if not isinstance(payload, dict):
            raise _unexpected_response_error(endpoint, response)
        return payload

    def _expect_wrapped_json_object(
        self,
        response: JsonValue | _OkApiResponse,
        endpoint: str,
        wrapper_key: str,
    ) -> JsonObject:
        data = self._expect_json_object(response, endpoint)
        if not isinstance(data.get(wrapper_key), dict):
            raise _unexpected_response_error(endpoint, response)
        return data

    def _expect_json_object_list(
        self,
        response: JsonValue | _OkApiResponse,
        endpoint: str,
    ) -> list[JsonObject]:
        payload = _response_payload(response)
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise _unexpected_response_error(endpoint, response)
        return cast(list[JsonObject], payload)


class OkApiClient(_BaseOkApiClient):
    """Synchronous OK API client."""

    def __init__(
        self,
        *,
        config: OkApiConfig | None = None,
        app_id: str | None = None,
        app_secret: str | None = None,
        device_id: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        http_client: httpx.Client | None = None,
        timestamp_provider: TimestampProvider | None = None,
    ) -> None:
        base_config = config or OkApiConfig()
        self.config = replace(
            base_config,
            app_id=app_id if app_id is not None else base_config.app_id,
            app_secret=app_secret if app_secret is not None else base_config.app_secret,
            device_id=device_id if device_id is not None else base_config.device_id,
            timeout=timeout if timeout is not None else base_config.timeout,
        )
        self._timestamp_provider = timestamp_provider or (lambda: int(time.time()))
        self._client = http_client or httpx.Client(timeout=self.config.timeout)
        self._owns_client = http_client is None

    def __enter__(self) -> OkApiClient:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def watch_charging_station_status(
        self,
        charging_station_id: str,
        connector_id: int,
        callback: FirestoreWatchCallback,
        *,
        firestore_client: object | None = None,
        project_id: str = DEFAULT_FIRESTORE_PROJECT_ID,
        credentials: object | None = None,
    ) -> FirestoreWatchSubscription:
        document_path = charging_station_status_document_path(charging_station_id, connector_id)
        return watch_firestore_document(
            document_path,
            callback,
            firestore_client=firestore_client,
            project_id=project_id,
            credentials=credentials,
        )

    def watch_charging_status(
        self,
        charging_token: str,
        callback: FirestoreWatchCallback,
        *,
        firestore_client: object | None = None,
        project_id: str = DEFAULT_FIRESTORE_PROJECT_ID,
        credentials: object | None = None,
    ) -> FirestoreWatchSubscription:
        document_path = charging_transaction_document_path(charging_token)
        return watch_firestore_document(
            document_path,
            callback,
            firestore_client=firestore_client,
            project_id=project_id,
            credentials=credentials,
        )

    def register_device(
        self,
        *,
        os_device_token: str | None = None,
        app_id: str | None = None,
    ) -> RegisterDeviceResponse:
        payload = self._new_register_payload(os_device_token=os_device_token, app_id=app_id)
        data = self._expect_wrapped_json_object(
            self._service_post("v1/RegistrerDevice", payload),
            "register_device",
            "RegistrerDeviceResult",
        )
        self._store_register_response(data)
        return cast(RegisterDeviceResponse, data)

    def login(self, email: str, password: str, *, device_id: str | None = None) -> LoginResponse:
        payload = self._service_payload(
            {
                "emailadresse": email,
                "kodeord": password,
                "deviceId": device_id or self._require_device_id(),
            }
        )
        data = self._expect_wrapped_json_object(
            self._service_post("v1/LogInd", payload),
            "login",
            "LogIndResult",
        )
        self._store_login_response(data)
        return cast(LoginResponse, data)

    def get_device_settings(self, *, device_id: str | None = None) -> DeviceSettingsResponse:
        payload = self._service_payload({"deviceId": device_id or self._require_device_id()})
        data = self._expect_wrapped_json_object(
            self._service_post("v1/HentDeviceOpsaetning", payload),
            "get_device_settings",
            "HentDeviceOpsaetningResult",
        )
        self._store_device_settings_response(data)
        return cast(DeviceSettingsResponse, data)

    def get_stations(self) -> list[ChargingLocation]:
        return cast(
            list[ChargingLocation],
            self._expect_json_object_list(
                self._data_request("GET", "v3/HomeChargingStation/location/all"),
                "get_stations",
            ),
        )

    def get_station_prices(self, charging_station_id: str) -> StationPricesResponse:
        path = f"v3/HomeChargingStation/dayAheadPrices/{self._segment(charging_station_id)}"
        return cast(
            StationPricesResponse,
            self._expect_json_object(self._data_request("GET", path), "get_station_prices"),
        )

    def set_station_auto_start(self, charging_station_id: str, autostart: bool) -> JsonObject:
        return self._expect_json_object(
            self._checked_command_response(
                self._data_request(
                    "POST",
                    "v2/HomeChargingStation/setAutostart",
                    json_body={
                        "chargingStationId": charging_station_id,
                        "autostart": autostart,
                    },
                )
            ),
            "set_station_auto_start",
        )

    def restart_station(self, charging_station_id: str) -> JsonObject:
        return self._expect_json_object(
            self._checked_command_response(
                self._data_request(
                    "POST",
                    "v2/HomeChargingStation/restart",
                    json_body={"chargingStationIdentifier": charging_station_id},
                )
            ),
            "restart_station",
        )

    def get_chargings(self) -> list[CurrentCharging]:
        return cast(
            list[CurrentCharging],
            self._expect_json_object_list(
                self._data_request("GET", "v2/HomeChargingStation/currentChargings"),
                "get_chargings",
            ),
        )

    def start_charging(
        self,
        *,
        friendly_device_id: str | None = None,
        charging_station_id: str,
        connector_id: int,
    ) -> ChargingCommandResponse:
        payload: JsonObject = {
            "friendlyDeviceId": friendly_device_id or self._require_device_friendly_id(),
            "chargingStationId": charging_station_id,
            "connectorId": connector_id,
        }
        return cast(
            ChargingCommandResponse,
            self._expect_json_object(
                self._checked_command_response(
                    self._data_request("POST", "v2/HomeChargingStation/start", json_body=payload)
                ),
                "start_charging",
            ),
        )

    def schedule_charging(
        self,
        *,
        friendly_device_id: str | None = None,
        charging_station_id: str,
        connector_id: int,
        scheduled_start: datetime | str,
        scheduled_end: datetime | str,
    ) -> ChargingCommandResponse:
        payload: JsonObject = {
            "friendlyDeviceId": friendly_device_id or self._require_device_friendly_id(),
            "chargingStationId": charging_station_id,
            "connectorId": connector_id,
            "scheduledStart": self._format_datetime(scheduled_start),
            "scheduledEnd": self._format_datetime(scheduled_end),
        }
        return cast(
            ChargingCommandResponse,
            self._expect_json_object(
                self._checked_command_response(
                    self._data_request("POST", "v2/HomeChargingStation/start", json_body=payload)
                ),
                "schedule_charging",
            ),
        )

    def update_charging_schedule(
        self,
        charging_token: str,
        *,
        scheduled_start: datetime | str,
        scheduled_end: datetime | str,
    ) -> JsonObject:
        payload: JsonObject = {
            "scheduledStart": self._format_datetime(scheduled_start),
            "scheduledEnd": self._format_datetime(scheduled_end),
        }
        return self._expect_json_object(
            self._checked_command_response(
                self._data_request(
                    "PUT",
                    f"v2/HomeChargingStation/schedule/{self._segment(charging_token)}",
                    json_body=payload,
                )
            ),
            "update_charging_schedule",
        )

    def cancel_charging_schedule(self, charging_token: str) -> JsonObject:
        return self._expect_json_object(
            self._checked_command_response(
                self._data_request(
                    "DELETE",
                    f"v2/HomeChargingStation/schedule/{self._segment(charging_token)}",
                )
            ),
            "cancel_charging_schedule",
        )

    def stop_charging(self, charging_token: str) -> JsonObject:
        return self._expect_json_object(
            self._checked_command_response(
                self._data_request(
                    "POST",
                    "v2/HomeChargingStation/stop",
                    json_body={"chargingToken": charging_token},
                )
            ),
            "stop_charging",
        )

    def get_charging_receipts(self) -> list[ChargingReceipt]:
        return cast(
            list[ChargingReceipt],
            self._expect_json_object_list(
                self._data_request("GET", "v2/HomeChargingStation/receipts"),
                "get_charging_receipts",
            ),
        )

    def get_charging_receipt(self, charging_token: str) -> ChargingReceipt:
        path = f"v2/HomeChargingStation/quickReceipt/{self._segment(charging_token)}"
        return cast(
            ChargingReceipt,
            self._expect_json_object(self._data_request("GET", path), "get_charging_receipt"),
        )

    def get_charging_station_status(
        self,
        charging_station_id: str,
        connector_id: int,
    ) -> FirestoreDocument:
        path = (
            "ChargingStations/Status/Connectors/"
            f"{self._segment(f'{charging_station_id}__{connector_id}')}"
        )
        return decode_firestore_document(
            self._expect_json_object(self._status_request(path), "get_charging_station_status")
        )

    def get_charging_status(self, charging_token: str) -> FirestoreDocument:
        path = f"RemoteTransactions/{self._segment(charging_token)}"
        return decode_firestore_document(
            self._expect_json_object(self._status_request(path), "get_charging_status")
        )

    def _require_device_friendly_id(self) -> str:
        if not self.config.device_friendly_id:
            raise OkConfigurationError(
                "device_friendly_id is required; call register_device(), pass friendly_device_id=, "
                "or set OK_DEVICE_FRIENDLY_ID"
            )
        return self.config.device_friendly_id

    def _service_post(self, path: str, payload: Mapping[str, JsonValue]) -> _OkApiResponse:
        return self._request_json(
            "POST",
            self._join_url(self.config.service_url, path),
            headers=self._common_headers(),
            json_body=payload,
        )

    def _data_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, JsonValue] | None = None,
    ) -> _OkApiResponse:
        return self._request_json(
            method,
            self._join_url(self.config.data_url, path),
            headers=self._data_headers(),
            json_body=json_body,
        )

    def _status_request(self, path: str) -> _OkApiResponse:
        return self._request_json(
            "GET",
            self._join_url(self.config.status_url, path),
            headers=self._status_headers(),
        )

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, JsonValue] | None = None,
    ) -> _OkApiResponse:
        try:
            response = self._client.request(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=self.config.timeout,
            )
        except httpx.TimeoutException as exc:
            raise OkTimeoutError(_transport_error_message(exc, "OK API request timed out")) from exc
        except httpx.TransportError as exc:
            raise OkConnectionError(
                _transport_error_message(exc, "OK API connection failed")
            ) from exc
        return _parse_response(response)


class AsyncOkApiClient(_BaseOkApiClient):
    """Asynchronous OK API client."""

    def __init__(
        self,
        *,
        config: OkApiConfig | None = None,
        app_id: str | None = None,
        app_secret: str | None = None,
        device_id: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        http_client: httpx.AsyncClient | None = None,
        timestamp_provider: TimestampProvider | None = None,
        blocking_call_runner: AsyncBlockingCallRunner | None = None,
    ) -> None:
        base_config = config or OkApiConfig()
        self.config = replace(
            base_config,
            app_id=app_id if app_id is not None else base_config.app_id,
            app_secret=app_secret if app_secret is not None else base_config.app_secret,
            device_id=device_id if device_id is not None else base_config.device_id,
            timeout=timeout if timeout is not None else base_config.timeout,
        )
        self._timestamp_provider = timestamp_provider or (lambda: int(time.time()))
        self._client = http_client or httpx.AsyncClient(timeout=self.config.timeout)
        self._owns_client = http_client is None
        self._blocking_call_runner = blocking_call_runner

    async def __aenter__(self) -> AsyncOkApiClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def watch_charging_station_status(
        self,
        charging_station_id: str,
        connector_id: int,
        *,
        firestore_client: object | None = None,
        project_id: str = DEFAULT_FIRESTORE_PROJECT_ID,
        credentials: object | None = None,
        max_queue_size: int = 64,
    ) -> AsyncFirestoreWatchSubscription:
        document_path = charging_station_status_document_path(charging_station_id, connector_id)
        return await async_watch_firestore_document(
            document_path,
            run_blocking=self._blocking_call_runner,
            firestore_client=firestore_client,
            project_id=project_id,
            credentials=credentials,
            max_queue_size=max_queue_size,
        )

    async def watch_charging_status(
        self,
        charging_token: str,
        *,
        firestore_client: object | None = None,
        project_id: str = DEFAULT_FIRESTORE_PROJECT_ID,
        credentials: object | None = None,
        max_queue_size: int = 64,
    ) -> AsyncFirestoreWatchSubscription:
        document_path = charging_transaction_document_path(charging_token)
        return await async_watch_firestore_document(
            document_path,
            run_blocking=self._blocking_call_runner,
            firestore_client=firestore_client,
            project_id=project_id,
            credentials=credentials,
            max_queue_size=max_queue_size,
        )

    async def register_device(
        self,
        *,
        os_device_token: str | None = None,
        app_id: str | None = None,
    ) -> RegisterDeviceResponse:
        payload = self._new_register_payload(os_device_token=os_device_token, app_id=app_id)
        data = self._expect_wrapped_json_object(
            await self._service_post("v1/RegistrerDevice", payload),
            "register_device",
            "RegistrerDeviceResult",
        )
        self._store_register_response(data)
        return cast(RegisterDeviceResponse, data)

    async def login(
        self, email: str, password: str, *, device_id: str | None = None
    ) -> LoginResponse:
        payload = self._service_payload(
            {
                "emailadresse": email,
                "kodeord": password,
                "deviceId": device_id or self._require_device_id(),
            }
        )
        data = self._expect_wrapped_json_object(
            await self._service_post("v1/LogInd", payload),
            "login",
            "LogIndResult",
        )
        self._store_login_response(data)
        return cast(LoginResponse, data)

    async def get_device_settings(self, *, device_id: str | None = None) -> DeviceSettingsResponse:
        payload = self._service_payload({"deviceId": device_id or self._require_device_id()})
        data = self._expect_wrapped_json_object(
            await self._service_post("v1/HentDeviceOpsaetning", payload),
            "get_device_settings",
            "HentDeviceOpsaetningResult",
        )
        self._store_device_settings_response(data)
        return cast(DeviceSettingsResponse, data)

    async def get_stations(self) -> list[ChargingLocation]:
        return cast(
            list[ChargingLocation],
            self._expect_json_object_list(
                await self._data_request("GET", "v3/HomeChargingStation/location/all"),
                "get_stations",
            ),
        )

    async def get_station_prices(self, charging_station_id: str) -> StationPricesResponse:
        path = f"v3/HomeChargingStation/dayAheadPrices/{self._segment(charging_station_id)}"
        return cast(
            StationPricesResponse,
            self._expect_json_object(await self._data_request("GET", path), "get_station_prices"),
        )

    async def set_station_auto_start(self, charging_station_id: str, autostart: bool) -> JsonObject:
        return self._expect_json_object(
            self._checked_command_response(
                await self._data_request(
                    "POST",
                    "v2/HomeChargingStation/setAutostart",
                    json_body={
                        "chargingStationId": charging_station_id,
                        "autostart": autostart,
                    },
                )
            ),
            "set_station_auto_start",
        )

    async def restart_station(self, charging_station_id: str) -> JsonObject:
        return self._expect_json_object(
            self._checked_command_response(
                await self._data_request(
                    "POST",
                    "v2/HomeChargingStation/restart",
                    json_body={"chargingStationIdentifier": charging_station_id},
                )
            ),
            "restart_station",
        )

    async def get_chargings(self) -> list[CurrentCharging]:
        return cast(
            list[CurrentCharging],
            self._expect_json_object_list(
                await self._data_request("GET", "v2/HomeChargingStation/currentChargings"),
                "get_chargings",
            ),
        )

    async def start_charging(
        self,
        *,
        friendly_device_id: str | None = None,
        charging_station_id: str,
        connector_id: int,
    ) -> ChargingCommandResponse:
        payload: JsonObject = {
            "friendlyDeviceId": friendly_device_id or self._require_device_friendly_id(),
            "chargingStationId": charging_station_id,
            "connectorId": connector_id,
        }
        return cast(
            ChargingCommandResponse,
            self._expect_json_object(
                self._checked_command_response(
                    await self._data_request(
                        "POST",
                        "v2/HomeChargingStation/start",
                        json_body=payload,
                    )
                ),
                "start_charging",
            ),
        )

    async def schedule_charging(
        self,
        *,
        friendly_device_id: str | None = None,
        charging_station_id: str,
        connector_id: int,
        scheduled_start: datetime | str,
        scheduled_end: datetime | str,
    ) -> ChargingCommandResponse:
        payload: JsonObject = {
            "friendlyDeviceId": friendly_device_id or self._require_device_friendly_id(),
            "chargingStationId": charging_station_id,
            "connectorId": connector_id,
            "scheduledStart": self._format_datetime(scheduled_start),
            "scheduledEnd": self._format_datetime(scheduled_end),
        }
        return cast(
            ChargingCommandResponse,
            self._expect_json_object(
                self._checked_command_response(
                    await self._data_request(
                        "POST",
                        "v2/HomeChargingStation/start",
                        json_body=payload,
                    )
                ),
                "schedule_charging",
            ),
        )

    async def update_charging_schedule(
        self,
        charging_token: str,
        *,
        scheduled_start: datetime | str,
        scheduled_end: datetime | str,
    ) -> JsonObject:
        payload: JsonObject = {
            "scheduledStart": self._format_datetime(scheduled_start),
            "scheduledEnd": self._format_datetime(scheduled_end),
        }
        return self._expect_json_object(
            self._checked_command_response(
                await self._data_request(
                    "PUT",
                    f"v2/HomeChargingStation/schedule/{self._segment(charging_token)}",
                    json_body=payload,
                )
            ),
            "update_charging_schedule",
        )

    async def cancel_charging_schedule(self, charging_token: str) -> JsonObject:
        return self._expect_json_object(
            self._checked_command_response(
                await self._data_request(
                    "DELETE",
                    f"v2/HomeChargingStation/schedule/{self._segment(charging_token)}",
                )
            ),
            "cancel_charging_schedule",
        )

    async def stop_charging(self, charging_token: str) -> JsonObject:
        return self._expect_json_object(
            self._checked_command_response(
                await self._data_request(
                    "POST",
                    "v2/HomeChargingStation/stop",
                    json_body={"chargingToken": charging_token},
                )
            ),
            "stop_charging",
        )

    async def get_charging_receipts(self) -> list[ChargingReceipt]:
        return cast(
            list[ChargingReceipt],
            self._expect_json_object_list(
                await self._data_request("GET", "v2/HomeChargingStation/receipts"),
                "get_charging_receipts",
            ),
        )

    async def get_charging_receipt(self, charging_token: str) -> ChargingReceipt:
        path = f"v2/HomeChargingStation/quickReceipt/{self._segment(charging_token)}"
        return cast(
            ChargingReceipt,
            self._expect_json_object(
                await self._data_request("GET", path),
                "get_charging_receipt",
            ),
        )

    async def get_charging_station_status(
        self,
        charging_station_id: str,
        connector_id: int,
    ) -> FirestoreDocument:
        path = (
            "ChargingStations/Status/Connectors/"
            f"{self._segment(f'{charging_station_id}__{connector_id}')}"
        )
        return decode_firestore_document(
            self._expect_json_object(
                await self._status_request(path),
                "get_charging_station_status",
            )
        )

    async def get_charging_status(self, charging_token: str) -> FirestoreDocument:
        path = f"RemoteTransactions/{self._segment(charging_token)}"
        return decode_firestore_document(
            self._expect_json_object(await self._status_request(path), "get_charging_status")
        )

    def _require_device_friendly_id(self) -> str:
        if not self.config.device_friendly_id:
            raise OkConfigurationError(
                "device_friendly_id is required; call register_device(), pass friendly_device_id=, "
                "or set OK_DEVICE_FRIENDLY_ID"
            )
        return self.config.device_friendly_id

    async def _service_post(
        self,
        path: str,
        payload: Mapping[str, JsonValue],
    ) -> _OkApiResponse:
        return await self._request_json(
            "POST",
            self._join_url(self.config.service_url, path),
            headers=self._common_headers(),
            json_body=payload,
        )

    async def _data_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, JsonValue] | None = None,
    ) -> _OkApiResponse:
        return await self._request_json(
            method,
            self._join_url(self.config.data_url, path),
            headers=self._data_headers(),
            json_body=json_body,
        )

    async def _status_request(self, path: str) -> _OkApiResponse:
        return await self._request_json(
            "GET",
            self._join_url(self.config.status_url, path),
            headers=self._status_headers(),
        )

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, JsonValue] | None = None,
    ) -> _OkApiResponse:
        try:
            response = await self._client.request(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=self.config.timeout,
            )
        except httpx.TimeoutException as exc:
            raise OkTimeoutError(_transport_error_message(exc, "OK API request timed out")) from exc
        except httpx.TransportError as exc:
            raise OkConnectionError(
                _transport_error_message(exc, "OK API connection failed")
            ) from exc
        return _parse_response(response)


def _parse_response(response: httpx.Response) -> _OkApiResponse:
    if response.status_code >= 400:
        raise _status_error(response)
    request_id = _request_id(response.headers)
    if not response.content:
        return _OkApiResponse(
            payload={},
            status_code=response.status_code,
            headers=response.headers,
            request_id=request_id,
        )
    try:
        return _OkApiResponse(
            payload=cast(JsonValue, response.json()),
            status_code=response.status_code,
            headers=response.headers,
            request_id=request_id,
        )
    except ValueError as exc:
        raise OkResponseError(
            "OK API returned a non-JSON response body",
            status_code=response.status_code,
            headers=response.headers,
            body=response.text,
            request_id=request_id,
        ) from exc


def _response_payload(response: JsonValue | _OkApiResponse) -> JsonValue:
    if isinstance(response, _OkApiResponse):
        return response.payload
    return response


def _unexpected_response_error(
    endpoint: str,
    response: JsonValue | _OkApiResponse,
) -> OkResponseError:
    if isinstance(response, _OkApiResponse):
        return OkResponseError(
            f"OK API returned an unexpected {endpoint} response body",
            status_code=response.status_code,
            headers=response.headers,
            payload=response.payload,
            request_id=response.request_id,
        )
    return OkResponseError(
        f"OK API returned an unexpected {endpoint} response body",
        payload=response,
    )


def _transport_error_message(exc: Exception, fallback: str) -> str:
    return str(exc) or fallback


def _status_error(response: httpx.Response) -> OkStatusError:
    payload: JsonValue | str
    try:
        payload = cast(JsonValue, response.json())
    except ValueError:
        payload = response.text
    message = _error_message(response.status_code, payload)
    error_cls = status_error_class(response.status_code)
    return error_cls(
        message,
        status_code=response.status_code,
        headers=response.headers,
        payload=payload,
        request_id=_request_id(response.headers),
    )


def _error_message(status_code: int, payload: JsonValue | str) -> str:
    if isinstance(payload, Mapping):
        for key in ("ErrorDescription", "errordescription", "title", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return f"OK API request failed with HTTP {status_code}: {_safe_error_detail(value)}"
        for key in ("ErrorCode", "errorcode", "status"):
            value = payload.get(key)
            if value is not None:
                return (
                    f"OK API request failed with HTTP {status_code}: "
                    f"{key}={_safe_error_detail(str(value))}"
                )
    if isinstance(payload, str) and payload:
        return f"OK API request failed with HTTP {status_code}: text response body"
    return f"OK API request failed with HTTP {status_code}"


def _safe_error_detail(value: str) -> str:
    detail = " ".join(value.split())
    if len(detail) <= _MAX_ERROR_DETAIL_LENGTH:
        return detail
    return f"{detail[:_MAX_ERROR_DETAIL_LENGTH]}..."


def _request_id(headers: Mapping[str, str]) -> str | None:
    for key in ("x-request-id", "traceparent", "trace-id", "x-correlation-id"):
        value = headers.get(key)
        if value:
            return value
    return None
