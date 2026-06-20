from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
from custom_components.ok.api import (
    OkApiClient,
    OkCommandError,
    OkConfigurationError,
    OkConnectionError,
    OkRateLimitError,
    OkResponseError,
    OkServerError,
    OkStatusError,
    OkTimeoutError,
)
from custom_components.ok.api._client import OkApiConfig, _error_message, _request_id
from custom_components.ok.api._signing import SHA_1, SHA_256, generate_signature
from custom_components.ok.api._version import __version__


def test_service_flow_signs_payloads_and_stores_session_state() -> None:
    requests: list[httpx.Request] = []
    bodies: list[dict[str, object]] = []
    responses = [
        {
            "RegistrerDeviceResult": {
                "DeviceId": "device-id",
                "DeviceFriendlyId": "FRIEND",
            }
        },
        {"LogIndResult": {"LogIndToken": "login-token"}},
        {
            "HentDeviceOpsaetningResult": {
                "DeviceId": "device-id-2",
                "DeviceFriendlyId": "FRIEND2",
                "Bruger": {"LogIndToken": "settings-token"},
            }
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        bodies.append(body)
        return httpx.Response(200, json=responses.pop(0))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OkApiClient(app_secret="SECRET", http_client=http_client)
        registered = client.register_device(os_device_token="os-token", app_id="APP")
        logged_in = client.login("user@example.test", "password")
        settings = client.get_device_settings()

    assert registered["RegistrerDeviceResult"]["DeviceId"] == "device-id"
    assert logged_in["LogIndResult"]["LogIndToken"] == "login-token"
    assert settings["HentDeviceOpsaetningResult"]["Bruger"]["LogIndToken"] == "settings-token"
    assert client.config.app_id == "APP"
    assert client.config.device_id == "device-id-2"
    assert client.config.device_friendly_id == "FRIEND2"
    assert client.config.login_token == "settings-token"
    assert [request.url.path for request in requests] == [
        "/service/okappservice.svc/v1/RegistrerDevice",
        "/service/okappservice.svc/v1/LogInd",
        "/service/okappservice.svc/v1/HentDeviceOpsaetning",
    ]
    for body in bodies:
        unsigned = {key: value for key, value in body.items() if key != "hmac"}
        assert body["hmac"] == generate_signature("APP", "SECRET", unsigned, algorithm=SHA_1)


def test_data_methods_use_timestamp_hmac_headers_and_expected_paths() -> None:
    seen: list[tuple[str, str, dict[str, object] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, body))
        assert request.headers["OK-App-DeviceId"] == "device-id"
        assert request.headers["OK-App-Hmac-Timestamp"] == "123"
        assert request.headers["OK-App-Hmac-Signature"] == generate_signature(
            "APP",
            "SECRET",
            {"deviceId": "device-id", "timestamp": 123},
            algorithm=SHA_256,
        )
        path = request.url.path
        if path.endswith("/location/all"):
            return httpx.Response(
                200,
                json=[
                    {
                        "locationId": "loc",
                        "chargingStations": [
                            {"csIdentifier": "station-id", "connectors": [{"connectorId": 1}]}
                        ],
                    }
                ],
            )
        if path.endswith("/dayAheadPrices/station-id"):
            return httpx.Response(
                200, json={"prices": [{"applicableTime": "2025-01-01T00:00:00Z"}]}
            )
        if path.endswith("/setAutostart"):
            return httpx.Response(200, content=b"")
        if path.endswith("/restart"):
            return httpx.Response(200, content=b"")
        if path.endswith("/currentChargings"):
            return httpx.Response(200, json=[{"chargingToken": "token"}])
        if path.endswith("/start"):
            return httpx.Response(200, json={"result": "Success", "chargingToken": "token"})
        if path.endswith("/schedule/token"):
            return httpx.Response(200, json={})
        if path.endswith("/stop"):
            return httpx.Response(200, json={})
        if path.endswith("/receipts"):
            return httpx.Response(200, json=[{"chargingStationId": "station-id", "kWh": 1.2}])
        if path.endswith("/quickReceipt/token"):
            return httpx.Response(200, json={"chargingStationId": "station-id", "kWh": 1.2})
        raise AssertionError(f"unexpected path {path}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OkApiClient(
            app_id="APP",
            app_secret="SECRET",
            device_id="device-id",
            http_client=http_client,
            timestamp_provider=lambda: 123,
        )
        client.config.device_friendly_id = "FRIEND"
        assert client.get_stations()[0]["locationId"] == "loc"
        assert client.get_station_prices("station-id")["prices"][0]["applicableTime"]
        assert client.set_station_auto_start("station-id", False) == {}
        assert client.restart_station("station-id") == {}
        assert client.get_chargings()[0]["chargingToken"] == "token"
        assert (
            client.start_charging(charging_station_id="station-id", connector_id=1)["result"]
            == "Success"
        )
        assert (
            client.schedule_charging(
                charging_station_id="station-id",
                connector_id=1,
                scheduled_start=datetime(2025, 1, 1, 1, tzinfo=UTC),
                scheduled_end=datetime(2025, 1, 1, 2, tzinfo=UTC),
            )["chargingToken"]
            == "token"
        )
        assert (
            client.update_charging_schedule(
                "token",
                scheduled_start="2025-01-01T01:00:00+00:00",
                scheduled_end="2025-01-01T02:00:00+00:00",
            )
            == {}
        )
        assert client.cancel_charging_schedule("token") == {}
        assert client.stop_charging("token") == {}
        assert client.get_charging_receipts()[0]["chargingStationId"] == "station-id"
        assert client.get_charging_receipt("token")["chargingStationId"] == "station-id"

    assert (
        "POST",
        "/api/v2/HomeChargingStation/setAutostart",
        {"chargingStationId": "station-id", "autostart": False},
    ) in seen
    assert (
        "POST",
        "/api/v2/HomeChargingStation/restart",
        {"chargingStationIdentifier": "station-id"},
    ) in seen


def test_status_methods_decode_firestore_documents() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/ChargingStations/Status/Connectors/station__1")
        return httpx.Response(
            200,
            json={
                "name": (
                    "projects/p/databases/(default)/documents/OK/Emsp/"
                    "ChargingStations/Status/Connectors/station__1"
                ),
                "fields": {
                    "status": {"stringValue": "Charging"},
                    "connectorId": {"integerValue": "1"},
                    "powerInW": {"integerValue": "3522"},
                    "statusUpdated": {"timestampValue": "2025-06-05T12:10:12Z"},
                },
                "createTime": "2025-01-01T00:00:00Z",
                "updateTime": "2025-01-01T01:00:00Z",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OkApiClient(http_client=http_client)
        document = client.get_charging_station_status("station", 1)

    assert document.fields["status"] == "Charging"
    assert document.fields["connectorId"] == 1
    assert document.fields["powerInW"] == 3522
    assert document.update_time == "2025-01-01T01:00:00Z"


def test_status_error_preserves_payload_and_status_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"errordescription": "Start af ladestander fejlede", "result": "Failed"},
            headers={"trace-id": "trace-123"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OkApiClient(
            app_id="APP",
            app_secret="SECRET",
            device_id="device-id",
            http_client=http_client,
            timestamp_provider=lambda: 123,
        )
        client.config.device_friendly_id = "FRIEND"
        with pytest.raises(OkStatusError) as error:
            client.schedule_charging(
                charging_station_id="station-id",
                connector_id=1,
                scheduled_start="2025-01-01T01:00:00+00:00",
                scheduled_end="2025-01-01T02:00:00+00:00",
            )

    assert error.value.status_code == 400
    assert error.value.request_id == "trace-123"
    assert error.value.payload == {
        "errordescription": "Start af ladestander fejlede",
        "result": "Failed",
    }


def test_command_failure_raises_typed_client_error() -> None:
    responses = [
        {"result": "Rejected", "errorcode": 42, "errordescription": "busy"},
        {"errorcode": 43, "errordescription": "still busy"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=responses.pop(0),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OkApiClient(
            app_id="APP",
            app_secret="SECRET",
            device_id="device-id",
            http_client=http_client,
            timestamp_provider=lambda: 123,
        )
        client.config.device_friendly_id = "FRIEND"

        with pytest.raises(OkCommandError) as error:
            client.start_charging(charging_station_id="station-id", connector_id=1)
        with pytest.raises(OkCommandError) as error_without_result:
            client.start_charging(charging_station_id="station-id", connector_id=1)

    assert str(error.value) == "OK command failed: busy"
    assert error.value.error_code == 42
    assert error.value.error_description == "busy"
    assert error.value.payload["result"] == "Rejected"
    assert str(error_without_result.value) == "OK command failed: still busy"
    assert error_without_result.value.error_code == 43


def test_missing_friendly_device_id_is_explicit() -> None:
    client = OkApiClient(app_id="APP", app_secret="SECRET", device_id="device-id")

    with pytest.raises(OkConfigurationError):
        client.start_charging(charging_station_id="station-id", connector_id=1)


def test_missing_required_configuration_is_explicit() -> None:
    with pytest.raises(OkConfigurationError, match="app_id"):
        OkApiClient(app_secret="SECRET", device_id="device-id").get_stations()

    with pytest.raises(OkConfigurationError, match="app_secret"):
        OkApiClient(app_id="APP", device_id="device-id").get_stations()

    with pytest.raises(OkConfigurationError, match="device_id"):
        OkApiClient(app_id="APP", app_secret="SECRET").get_stations()

    with pytest.raises(OkConfigurationError, match="app_secret"):
        OkApiClient().register_device(app_id="APP")


def test_config_from_env_and_owned_context_manager() -> None:
    assert OkApiConfig().app_version == __version__
    assert OkApiConfig.from_env({}).app_version == __version__
    assert "SECRET" not in repr(OkApiConfig(app_secret="SECRET", login_token="token"))
    assert "token" not in repr(OkApiConfig(app_secret="SECRET", login_token="token"))

    config = OkApiConfig.from_env(
        {
            "OK_APP_ID": "APP",
            "OK_APP_SECRET": "SECRET",
            "OK_DEVICE_ID": "device-id",
            "OK_DEVICE_FRIENDLY_ID": "FRIEND",
            "OK_LOGIN_TOKEN": "token",
            "OK_SERVICE_URL": "https://service.example.test",
            "OK_DATA_URL": "https://data.example.test",
            "OK_STATUS_URL": "https://status.example.test",
            "OK_APP_PLATFORM": "Tests",
            "OK_APP_VERSION": "1.2.3",
        }
    )

    assert config.app_id == "APP"
    assert config.service_url == "https://service.example.test"
    assert config.app_platform == "Tests"
    with OkApiClient(config=config) as client:
        assert client.config.device_friendly_id == "FRIEND"


def test_response_state_storage_ignores_unexpected_shapes() -> None:
    client = OkApiClient(app_id="APP", app_secret="SECRET")

    client._store_register_response({"RegistrerDeviceResult": {"DeviceId": 1}})
    client._store_login_response({"LogIndResult": {"LogIndToken": 1}})
    client._store_device_settings_response({"HentDeviceOpsaetningResult": []})
    client._store_device_settings_response(
        {
            "HentDeviceOpsaetningResult": {
                "DeviceId": 2,
                "DeviceFriendlyId": 3,
                "Bruger": {"LogIndToken": 4},
            }
        }
    )

    assert client.config.device_id is None
    assert client.config.device_friendly_id is None
    assert client.config.login_token is None


def test_injected_sync_client_is_not_closed_by_wrapper() -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(204))) as (
        http_client
    ):
        client = OkApiClient(http_client=http_client)
        client.close()

        assert http_client.is_closed is False


def test_injected_sync_client_receives_configured_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        timeout = request.extensions["timeout"]
        assert timeout["connect"] == 7.0
        assert timeout["read"] == 7.0
        return httpx.Response(200, json=[])

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OkApiClient(
            app_id="APP",
            app_secret="SECRET",
            device_id="device-id",
            timeout=7.0,
            http_client=http_client,
            timestamp_provider=lambda: 123,
        )

        assert client.get_stations() == []


def test_transport_errors_are_mapped_to_client_exceptions() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    with httpx.Client(transport=httpx.MockTransport(timeout_handler)) as http_client:
        client = OkApiClient(
            app_id="APP",
            app_secret="SECRET",
            device_id="device-id",
            http_client=http_client,
            timestamp_provider=lambda: 123,
        )
        with pytest.raises(OkTimeoutError) as error:
            client.get_stations()
    assert str(error.value) == "timed out"

    def blank_timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("")

    with httpx.Client(transport=httpx.MockTransport(blank_timeout_handler)) as http_client:
        client = OkApiClient(
            app_id="APP",
            app_secret="SECRET",
            device_id="device-id",
            http_client=http_client,
            timestamp_provider=lambda: 123,
        )
        with pytest.raises(OkTimeoutError) as error:
            client.get_stations()
    assert str(error.value) == "OK API request timed out"

    def connection_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with httpx.Client(transport=httpx.MockTransport(connection_handler)) as http_client:
        client = OkApiClient(
            app_id="APP",
            app_secret="SECRET",
            device_id="device-id",
            http_client=http_client,
            timestamp_provider=lambda: 123,
        )
        with pytest.raises(OkConnectionError):
            client.get_stations()


def test_invalid_json_response_raises_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json", headers={"trace-id": "json-trace"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OkApiClient(http_client=http_client)
        with pytest.raises(OkResponseError) as error:
            client.get_charging_status("token")

    assert error.value.status_code == 200
    assert error.value.body == "not-json"
    assert error.value.request_id == "json-trace"


def test_unexpected_json_shapes_raise_response_error() -> None:
    responses = [
        {"not": "a list"},
        ["not", "objects"],
        [],
    ]
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json=responses.pop(0),
            headers={"trace-id": f"shape-trace-{request_count}"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OkApiClient(
            app_id="APP",
            app_secret="SECRET",
            device_id="device-id",
            http_client=http_client,
            timestamp_provider=lambda: 123,
        )

        with pytest.raises(OkResponseError, match="get_stations") as error:
            client.get_stations()
        assert error.value.status_code == 200
        assert error.value.request_id == "shape-trace-1"
        assert error.value.payload == {"not": "a list"}
        with pytest.raises(OkResponseError, match="get_stations"):
            client.get_stations()
        with pytest.raises(OkResponseError, match="get_station_prices"):
            client.get_station_prices("station-id")


def test_missing_service_wrapper_keys_raise_response_error() -> None:
    responses = [
        {},
        {"LogIndResult": []},
        {"HentDeviceOpsaetningResult": None},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses.pop(0))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OkApiClient(
            app_id="APP",
            app_secret="SECRET",
            device_id="device-id",
            http_client=http_client,
            timestamp_provider=lambda: 123,
        )

        with pytest.raises(OkResponseError, match="register_device"):
            client.register_device(app_id="APP")
        with pytest.raises(OkResponseError, match="login"):
            client.login("user@example.test", "password")
        with pytest.raises(OkResponseError, match="get_device_settings"):
            client.get_device_settings()


def test_server_error_and_text_error_payloads_are_mapped() -> None:
    def server_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream failed")

    with httpx.Client(transport=httpx.MockTransport(server_handler)) as http_client:
        client = OkApiClient(http_client=http_client)
        with pytest.raises(OkServerError) as error:
            client.get_charging_status("token")

    assert error.value.status_code == 500
    assert error.value.payload == "upstream failed"


def test_error_message_and_request_id_edge_cases() -> None:
    assert _error_message(400, {"ErrorCode": 123}) == (
        "OK API request failed with HTTP 400: ErrorCode=123"
    )
    assert _error_message(400, {"status": "bad"}) == (
        "OK API request failed with HTTP 400: status=bad"
    )
    assert _error_message(400, {}) == "OK API request failed with HTTP 400"
    assert _error_message(500, "secret raw body") == (
        "OK API request failed with HTTP 500: text response body"
    )
    assert (
        OkRateLimitError(
            "slow", status_code=429, headers={"Retry-After": "12"}, payload={}
        ).retry_after
        == 12
    )
    http_date_retry_after = OkRateLimitError(
        "slow",
        status_code=429,
        headers={"Retry-After": format_datetime(datetime.now(UTC) + timedelta(seconds=120))},
        payload={},
    ).retry_after
    assert http_date_retry_after is not None
    assert 0 < http_date_retry_after <= 120
    assert (
        OkRateLimitError(
            "slow",
            status_code=429,
            headers={"Retry-After": format_datetime(datetime.now(UTC) - timedelta(seconds=1))},
            payload={},
        ).retry_after
        == 0
    )
    assert _request_id({"x-request-id": "request-1"}) == "request-1"
    assert _request_id({"traceparent": "trace-1"}) == "trace-1"
    assert _request_id({}) is None
