from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from custom_components.ok.api import FirestoreDocument
from custom_components.ok.coordinator import OkConnectorRef
from homeassistant.core import HomeAssistant


def make_connector(
    station_id: str = "OK-CHARGER-001",
    connector_id: int = 1,
    *,
    auto_start: bool | str | None = True,
) -> OkConnectorRef:
    station: dict[str, Any] = {
        "csIdentifier": station_id,
        "name": "Home Charger",
        "serialNumber": "SERIAL-1",
        "model": "OK Pro",
        "firmwareVersion": "1.2.3",
        "vendorName": "OK",
        "connectors": [{"connectorId": connector_id, "power": 22}],
    }
    if auto_start is not None:
        station["autoStart"] = auto_start
    return OkConnectorRef(
        location={"name": "Garage", "electricityPriceZone": "DK2"},
        station=station,
        connector={"connectorId": connector_id, "power": 22, "type": "Type2"},
    )


def make_document(
    fields: dict[str, Any] | None = None,
    *,
    name: str = "documents/OK/Emsp/ChargingStations/Status/Connectors/OK-CHARGER-001__1",
    update_time: str = "2026-06-14T12:00:00Z",
) -> FirestoreDocument:
    return FirestoreDocument(
        name=name,
        fields=fields or {},
        create_time="2026-06-14T11:00:00Z",
        update_time=update_time,
        raw={},
    )


def make_price_response(now: datetime | None = None) -> dict[str, Any]:
    current_hour = (now or datetime.now(UTC)).replace(minute=0, second=0, microsecond=0)
    return {
        "productName": "OK El Flex",
        "productType": 42,
        "electricityPriceOrigin": "Nord Pool",
        "prices": [
            {
                "applicableTime": (current_hour - timedelta(hours=1)).isoformat(),
                "electricityPriceIncludingVat": 100,
                "tariffIncludingVat": 20,
                "electricityTaxIncludingVat": 5,
            },
            {
                "applicableTime": (current_hour + timedelta(hours=1)).isoformat(),
                "electricityPriceIncludingVat": 200,
                "tariffIncludingVat": 30,
                "electricityTaxIncludingVat": 5,
            },
        ],
    }


def make_active_charging(
    *,
    charging_token: str | None = None,
    scheduled_start: str | None = "2026-06-14T15:30:00Z",
    scheduled_end: str | None = "2026-06-14T18:00:00Z",
) -> dict[str, Any]:
    charging_token = charging_token or "charging-token"
    schedule: dict[str, Any] = {}
    if scheduled_start is not None:
        schedule["scheduledStart"] = scheduled_start
    if scheduled_end is not None:
        schedule["scheduledEnd"] = scheduled_end
    return {
        "csIdentifier": "OK-CHARGER-001",
        "connectorId": 1,
        "chargingToken": charging_token,
        "firestoreToken": charging_token,
        "schedules": [schedule],
    }


class EntityTestClient:
    def __init__(self) -> None:
        self.start_calls: list[dict[str, Any]] = []
        self.stop_calls: list[str] = []
        self.cancel_calls: list[str] = []
        self.restart_calls: list[str] = []
        self.auto_start_calls: list[dict[str, Any]] = []
        self.schedule_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    async def start_charging(self, **kwargs: Any) -> dict[str, str]:
        self._raise_if_error()
        self.start_calls.append(kwargs)
        return {"result": "Success"}

    async def schedule_charging(self, **kwargs: Any) -> dict[str, str]:
        self._raise_if_error()
        self.schedule_calls.append(kwargs)
        return {"result": "Success"}

    async def stop_charging(self, charging_token: str) -> dict[str, Any]:
        self._raise_if_error()
        self.stop_calls.append(charging_token)
        return {}

    async def cancel_charging_schedule(self, charging_token: str) -> dict[str, Any]:
        self._raise_if_error()
        self.cancel_calls.append(charging_token)
        return {}

    async def update_charging_schedule(
        self,
        charging_token: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self._raise_if_error()
        self.update_calls.append({"charging_token": charging_token, **kwargs})
        return {}

    async def restart_station(self, charging_station_id: str) -> dict[str, Any]:
        self._raise_if_error()
        self.restart_calls.append(charging_station_id)
        return {}

    async def set_station_auto_start(
        self,
        charging_station_id: str,
        autostart: bool,
    ) -> dict[str, Any]:
        self._raise_if_error()
        self.auto_start_calls.append(
            {"charging_station_id": charging_station_id, "autostart": autostart}
        )
        return {}

    def _raise_if_error(self) -> None:
        if self.error is not None:
            raise self.error


class EntityTestEntry:
    def __init__(self) -> None:
        self.entry_id = "test-entry"
        self.unique_id = "1000001"
        self.title = "OK (user@example.test)"
        self.reauth_count = 0

    def async_start_reauth(self, hass: HomeAssistant) -> None:
        self.reauth_count += 1


class EntityTestCoordinator:
    def __init__(
        self,
        hass: HomeAssistant,
        connector: OkConnectorRef | None = None,
    ) -> None:
        self.hass = hass
        self.entry = EntityTestEntry()
        self.client = EntityTestClient()
        self.data: object | None = object()
        self.last_update_success = True
        self.connector_refs = [connector or make_connector()]
        self.active_charging: dict[str, Any] | None = None
        self.refresh_count = 0
        self.force_full_refresh_count = 0
        self.refresh_in_progress = False
        self.last_refresh = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)
        self.current_chargings_snapshot_at = datetime(2026, 6, 14, 12, 5, tzinfo=UTC)
        self.charging_schedule_event_at_map: dict[str, datetime] = {}
        self.schedule_snapshots: dict[tuple[str, int], dict[str, Any] | None] = {}
        self.poll_attributes = {
            "account_settings": "2026-06-14T11:50:00+00:00",
            "charger_overview": "2026-06-14T11:55:00+00:00",
            "energy_prices": "2026-06-14T11:56:00+00:00",
            "active_sessions": "2026-06-14T11:57:00+00:00",
            "charging_receipts": "2026-06-14T11:58:00+00:00",
            "trigger": "automatic",
            "in_progress": False,
            "realtime_status": "active",
            "realtime_active_watchers": 2,
            "realtime_retrying_watchers": 0,
            "realtime_unavailable": False,
        }
        self.charger_poll_attrs = {
            "charger_status": "2026-06-14T11:59:00+00:00",
            "session_status": None,
            "session_receipt": None,
            "realtime_status": "active",
        }
        self._charger_last_refresh = datetime(2026, 6, 14, 11, 59, tzinfo=UTC)
        self.listeners: list[Any] = []
        self.station_status_documents: dict[tuple[str, int], FirestoreDocument] = {
            (
                self.connector_refs[0].station_id,
                self.connector_refs[0].connector_id,
            ): make_document(
                {
                    "status": "Available",
                    "statusUpdated": "2026-06-14T12:00:00Z",
                    "statusEventTime": "1718366400000000000",
                    "locationType": "home",
                    "geoZoneId": "zone-1",
                }
            )
        }
        self.charging_status_documents: dict[str, FirestoreDocument] = {
            "charging-token": make_document(
                {
                    "status": "Charging",
                    "statusUpdated": "2026-06-14T12:01:00Z",
                    "powerInW": 3522,
                    "chargeInWh": 5835,
                    "stopReason": None,
                    "paymentStatus": "Open",
                },
                name="documents/OK/Emsp/RemoteTransactions/charging-token",
            )
        }
        self.price_response = make_price_response()
        self.receipt: dict[str, Any] | None = {
            "chargingStationId": self.connector_refs[0].station_id,
            "kWh": 12.5,
            "chargingStart": "2026-06-13T20:00:00Z",
            "chargingEnd": "2026-06-13T22:00:00Z",
            "locationName": "Garage",
            "chargingStationName": "Home Charger",
            "totalPriceInOere": 1767,
            "noPriceReason": None,
        }

    def async_add_listener(self, update_callback: Any, context: Any = None) -> Any:
        self.listeners.append(update_callback)
        return lambda: None

    def connectors(self) -> tuple[OkConnectorRef, ...]:
        return tuple(self.connector_refs)

    def active_charging_for(self, station_id: str, connector_id: int) -> dict[str, Any] | None:
        if (
            self.active_charging is not None
            and station_id == self.connector_refs[0].station_id
            and connector_id == self.connector_refs[0].connector_id
        ):
            return self.active_charging
        return None

    def record_schedule_window(
        self,
        station_id: str,
        connector_id: int,
        scheduled_start: str,
        scheduled_end: str | None,
        *,
        charging_token: str | None = None,
        firestore_token: str | None = None,
    ) -> None:
        connector = self.connector_refs[0]
        if station_id != connector.station_id or connector_id != connector.connector_id:
            return
        schedule: dict[str, Any] = {"scheduledStart": scheduled_start}
        if scheduled_end is not None:
            schedule["scheduledEnd"] = scheduled_end
        self.active_charging = {
            **(self.active_charging or {}),
            "schedules": [schedule],
        }
        if charging_token is not None:
            self.active_charging["chargingToken"] = charging_token
        if firestore_token is not None:
            self.active_charging["firestoreToken"] = firestore_token
        self.schedule_snapshots[(station_id, connector_id)] = schedule

    async def async_record_schedule_window(
        self,
        station_id: str,
        connector_id: int,
        scheduled_start: str,
        scheduled_end: str | None,
        *,
        charging_token: str | None = None,
        firestore_token: str | None = None,
    ) -> None:
        self.record_schedule_window(
            station_id,
            connector_id,
            scheduled_start,
            scheduled_end,
            charging_token=charging_token,
            firestore_token=firestore_token,
        )

    def station_status_for(self, station_id: str, connector_id: int) -> FirestoreDocument | None:
        return self.station_status_documents.get((station_id, connector_id))

    def charging_status_for(self, charging: dict[str, Any] | None) -> FirestoreDocument | None:
        if charging is None:
            return None
        token = charging.get("firestoreToken") or charging.get("chargingToken")
        return self.charging_status_documents.get(token)

    def charging_schedule_event_at(self, charging: dict[str, Any] | None) -> datetime | None:
        if charging is None:
            return None
        token = charging.get("firestoreToken") or charging.get("chargingToken")
        return self.charging_schedule_event_at_map.get(token)

    def schedule_source_for(self, connector: OkConnectorRef) -> dict[str, Any] | None:
        snapshot = self.schedule_snapshots.get((connector.station_id, connector.connector_id))
        if snapshot is not None:
            return snapshot

        charging = self.active_charging_for(connector.station_id, connector.connector_id)
        document = self.charging_status_for(charging)
        document_fields = document.fields if document is not None else None
        if (
            charging is not None
            and self.charging_schedule_event_at(charging) is not None
            and document_fields is not None
            and "scheduledStart" in document_fields
        ):
            return document_fields

        schedule = _first_schedule(charging)
        if schedule is not None and "scheduledStart" in schedule:
            return schedule

        if document_fields is not None and "scheduledStart" in document_fields:
            return document_fields
        return None

    def prices_for(self, station_id: str) -> dict[str, Any] | None:
        if station_id == self.connector_refs[0].station_id:
            return self.price_response
        return None

    def next_price_update_for(self, station_id: str) -> datetime | None:
        if station_id == self.connector_refs[0].station_id:
            return datetime(2026, 6, 14, 13, 0, tzinfo=UTC)
        return None

    def last_receipt_for(self, station_id: str) -> dict[str, Any] | None:
        if self.receipt is not None and self.receipt.get("chargingStationId") == station_id:
            return self.receipt
        return None

    def charger_poll_attributes(self, station_id: str) -> dict[str, str | None]:
        if station_id == self.connector_refs[0].station_id:
            return self.charger_poll_attrs
        return {
            "charger_status": None,
            "session_status": None,
            "session_receipt": None,
            "realtime_status": None,
        }

    def charger_last_refresh(self, station_id: str) -> datetime | None:
        if station_id == self.connector_refs[0].station_id:
            return self._charger_last_refresh
        return None

    async def async_request_refresh(self) -> None:
        self.refresh_count += 1

    async def async_request_operational_refresh(self) -> None:
        self.refresh_count += 1

    async def async_request_station_refresh(self) -> None:
        self.refresh_count += 1

    async def async_force_full_refresh(self) -> None:
        self.refresh_count += 1
        self.force_full_refresh_count += 1


class EntitySetupEntry:
    def __init__(
        self,
        coordinator: EntityTestCoordinator,
        *,
        options: dict[str, Any] | None = None,
    ) -> None:
        self.runtime_data = SimpleNamespace(coordinator=coordinator)
        self.options = options or {}
        self.unload_callbacks: list[Any] = []

    def async_on_unload(self, callback: Any) -> None:
        self.unload_callbacks.append(callback)


def _first_schedule(charging: dict[str, Any] | None) -> dict[str, Any] | None:
    if charging is None:
        return None
    schedules = charging.get("schedules")
    if not isinstance(schedules, list) or not schedules:
        return None
    schedule = schedules[0]
    return schedule if isinstance(schedule, dict) else None
