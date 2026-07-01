from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from custom_components.ok.api import OkAuthenticationError
from custom_components.ok.const import (
    ATTR_AUTOSTART,
    ATTR_SCHEDULED_END,
    ATTR_SCHEDULED_START,
    DOMAIN,
    SERVICE_CANCEL_CHARGING_SCHEDULE,
    SERVICE_RESTART,
    SERVICE_SCHEDULE_CHARGING,
    SERVICE_SET_AUTO_START,
    SERVICE_START_CHARGING,
    SERVICE_STOP_CHARGING,
    SERVICE_UPDATE_CHARGING_SCHEDULE,
)
from homeassistant.config_entries import ConfigEntries, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import DATA_DOMAIN_PLATFORM_ENTITIES
from pytest import MonkeyPatch

from custom_components.ok import OkRuntimeData, async_setup


class FakeServiceClient:
    def __init__(self) -> None:
        self.start_calls: list[dict[str, Any]] = []
        self.schedule_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []
        self.cancel_calls: list[str] = []
        self.stop_calls: list[str] = []
        self.restart_calls: list[str] = []
        self.auto_start_calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    async def start_charging(self, **kwargs: Any) -> dict[str, str]:
        self._raise_if_error()
        self.start_calls.append(kwargs)
        return {"result": "Success"}

    async def schedule_charging(self, **kwargs: Any) -> dict[str, str]:
        self._raise_if_error()
        self.schedule_calls.append(kwargs)
        return {"result": "Success"}

    async def update_charging_schedule(
        self,
        charging_token: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self._raise_if_error()
        self.update_calls.append({"charging_token": charging_token, **kwargs})
        return {}

    async def cancel_charging_schedule(self, charging_token: str) -> dict[str, Any]:
        self._raise_if_error()
        self.cancel_calls.append(charging_token)
        return {}

    async def stop_charging(self, charging_token: str) -> dict[str, Any]:
        self._raise_if_error()
        self.stop_calls.append(charging_token)
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


class FakeCoordinator:
    def __init__(self) -> None:
        self.refresh_count = 0
        self.connector_refs = (SimpleNamespace(station_id="OK-CHARGER-001", connector_id=1),)
        self.active_charging: dict[str, Any] | None = {
            "chargingToken": "charging-token",
            "firestoreToken": "firestore-token",
        }
        self.entry: Any = None

    async def async_request_refresh(self) -> None:
        self.refresh_count += 1

    async def async_request_operational_refresh(self) -> None:
        self.refresh_count += 1

    async def async_request_station_refresh(self) -> None:
        self.refresh_count += 1

    def connectors(self) -> tuple[SimpleNamespace, ...]:
        return self.connector_refs

    def active_charging_for(self, station_id: str, connector_id: int) -> dict[str, Any] | None:
        if station_id == "OK-CHARGER-001" and connector_id == 1:
            return self.active_charging
        return None


class FakeEntry:
    def __init__(self, client: FakeServiceClient, coordinator: FakeCoordinator) -> None:
        self.entry_id = "test-entry"
        self.state = ConfigEntryState.LOADED
        self.runtime_data = OkRuntimeData(client=client, coordinator=coordinator)
        self.reauth_count = 0

    def async_start_reauth(self, hass: HomeAssistant) -> None:
        self.reauth_count += 1


class FakeConnectorStatusEntity:
    entity_id = "sensor.charger_connector_status"
    available = True
    device_class = "enum"
    should_poll = False
    supported_features = 0

    def __init__(self, coordinator: FakeCoordinator) -> None:
        self.coordinator = coordinator
        self.connector = coordinator.connector_refs[0]
        self.context: Any = None

    def async_set_context(self, context: Any) -> None:
        self.context = context

    async def async_request_call(self, coro: Any) -> Any:
        return await coro


def test_schedule_charging_service_adds_local_timezone_to_naive_datetimes(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(
        _test_schedule_charging_service_adds_local_timezone_to_naive_datetimes(
            tmp_path, monkeypatch
        )
    )


async def _test_schedule_charging_service_adds_local_timezone_to_naive_datetimes(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeServiceClient()
    try:
        coordinator, _entry = await _setup_entry(hass, client, monkeypatch)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SCHEDULE_CHARGING,
            {
                ATTR_ENTITY_ID: "sensor.charger_connector_status",
                ATTR_SCHEDULED_START: "2026-06-14T15:30:00",
                ATTR_SCHEDULED_END: "2026-06-14T18:00:00",
            },
            blocking=True,
        )

        assert client.schedule_calls == []
        assert client.update_calls == [
            {
                "charging_token": "charging-token",
                "charging_station_id": "OK-CHARGER-001",
                "scheduled_start": "2026-06-14T15:30:00+02:00",
                "scheduled_end": "2026-06-14T18:00:00+02:00",
            }
        ]
        assert coordinator.refresh_count == 1
    finally:
        await hass.async_stop()


def test_schedule_services_preserve_explicit_timezone_offsets(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(_test_schedule_services_preserve_explicit_timezone_offsets(tmp_path, monkeypatch))


async def _test_schedule_services_preserve_explicit_timezone_offsets(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeServiceClient()
    try:
        coordinator, _entry = await _setup_entry(hass, client, monkeypatch)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SCHEDULE_CHARGING,
            {
                ATTR_ENTITY_ID: "sensor.charger_connector_status",
                ATTR_SCHEDULED_START: "2026-06-14T13:30:00+00:00",
                ATTR_SCHEDULED_END: "2026-06-14T16:00:00+00:00",
            },
            blocking=True,
        )
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CHARGING_SCHEDULE,
            {
                ATTR_ENTITY_ID: "sensor.charger_connector_status",
                ATTR_SCHEDULED_START: "2026-06-14T15:30:00",
                ATTR_SCHEDULED_END: "2026-06-14T18:00:00",
            },
            blocking=True,
        )

        assert client.update_calls == [
            {
                "charging_token": "charging-token",
                "charging_station_id": "OK-CHARGER-001",
                "scheduled_start": "2026-06-14T13:30:00+00:00",
                "scheduled_end": "2026-06-14T16:00:00+00:00",
            },
            {
                "charging_token": "charging-token",
                "charging_station_id": "OK-CHARGER-001",
                "scheduled_start": "2026-06-14T15:30:00+02:00",
                "scheduled_end": "2026-06-14T18:00:00+02:00",
            },
        ]
        assert client.schedule_calls == []
        assert coordinator.refresh_count == 2
    finally:
        await hass.async_stop()


def test_schedule_service_allows_start_only_existing_schedule(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(_test_schedule_service_allows_start_only_existing_schedule(tmp_path, monkeypatch))


async def _test_schedule_service_allows_start_only_existing_schedule(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeServiceClient()
    try:
        coordinator, _entry = await _setup_entry(hass, client, monkeypatch)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SCHEDULE_CHARGING,
            {
                ATTR_ENTITY_ID: "sensor.charger_connector_status",
                ATTR_SCHEDULED_START: "2026-06-14T15:30:00",
            },
            blocking=True,
        )

        assert client.update_calls == [
            {
                "charging_token": "charging-token",
                "charging_station_id": "OK-CHARGER-001",
                "scheduled_start": "2026-06-14T15:30:00+02:00",
                "scheduled_end": None,
            }
        ]
        assert client.schedule_calls == []
        assert coordinator.refresh_count == 1
    finally:
        await hass.async_stop()


def test_schedule_service_falls_back_to_start_when_no_active_token(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(
        _test_schedule_service_falls_back_to_start_when_no_active_token(tmp_path, monkeypatch)
    )


async def _test_schedule_service_falls_back_to_start_when_no_active_token(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeServiceClient()
    try:
        coordinator, _entry = await _setup_entry(hass, client, monkeypatch)
        coordinator.active_charging = None

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SCHEDULE_CHARGING,
            {
                ATTR_ENTITY_ID: "sensor.charger_connector_status",
                ATTR_SCHEDULED_START: "2026-06-14T15:30:00",
                ATTR_SCHEDULED_END: "2026-06-14T18:00:00",
            },
            blocking=True,
        )

        assert client.schedule_calls == [
            {
                "charging_station_id": "OK-CHARGER-001",
                "connector_id": 1,
                "scheduled_start": "2026-06-14T15:30:00+02:00",
                "scheduled_end": "2026-06-14T18:00:00+02:00",
            }
        ]
        assert client.update_calls == []
        assert coordinator.refresh_count == 1
    finally:
        await hass.async_stop()


def test_schedule_service_rejects_start_only_without_active_token(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(
        _test_schedule_service_rejects_start_only_without_active_token(tmp_path, monkeypatch)
    )


async def _test_schedule_service_rejects_start_only_without_active_token(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeServiceClient()
    try:
        coordinator, _entry = await _setup_entry(hass, client, monkeypatch)
        coordinator.active_charging = None

        with pytest.raises(ServiceValidationError) as error:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SCHEDULE_CHARGING,
                {
                    ATTR_ENTITY_ID: "sensor.charger_connector_status",
                    ATTR_SCHEDULED_START: "2026-06-14T15:30:00",
                },
                blocking=True,
            )

        assert error.value.translation_key == "active_charging_not_found"
        assert client.schedule_calls == []
        assert client.update_calls == []
        assert coordinator.refresh_count == 0
    finally:
        await hass.async_stop()


def test_schedule_services_reject_end_before_start(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(_test_schedule_services_reject_end_before_start(tmp_path, monkeypatch))


async def _test_schedule_services_reject_end_before_start(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeServiceClient()
    try:
        coordinator, _entry = await _setup_entry(hass, client, monkeypatch)

        with pytest.raises(ServiceValidationError) as error:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SCHEDULE_CHARGING,
                {
                    ATTR_ENTITY_ID: "sensor.charger_connector_status",
                    ATTR_SCHEDULED_START: "2026-06-14T18:00:00",
                    ATTR_SCHEDULED_END: "2026-06-14T15:30:00",
                },
                blocking=True,
            )

        assert error.value.translation_key == "invalid_schedule_window"
        assert client.schedule_calls == []
        assert coordinator.refresh_count == 0
    finally:
        await hass.async_stop()


def test_entity_services_resolve_connector_and_active_token(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(_test_entity_services_resolve_connector_and_active_token(tmp_path, monkeypatch))


async def _test_entity_services_resolve_connector_and_active_token(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeServiceClient()
    try:
        coordinator, _entry = await _setup_entry(hass, client, monkeypatch)

        for service, data in (
            (SERVICE_START_CHARGING, {}),
            (SERVICE_STOP_CHARGING, {}),
            (SERVICE_CANCEL_CHARGING_SCHEDULE, {}),
        ):
            await hass.services.async_call(
                DOMAIN,
                service,
                {ATTR_ENTITY_ID: "sensor.charger_connector_status", **data},
                blocking=True,
            )

        assert client.start_calls == [{"charging_station_id": "OK-CHARGER-001", "connector_id": 1}]
        assert client.stop_calls == ["charging-token"]
        assert client.cancel_calls == ["charging-token"]
        assert coordinator.refresh_count == 3
    finally:
        await hass.async_stop()


def test_charger_services_accept_device_targets(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(_test_charger_services_accept_device_targets(tmp_path, monkeypatch))


async def _test_charger_services_accept_device_targets(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeServiceClient()
    try:
        coordinator, _entry = await _setup_entry(hass, client, monkeypatch)
        _patch_device_registry(
            monkeypatch,
            SimpleNamespace(identifiers={(DOMAIN, "OK-CHARGER-001")}),
        )

        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESTART,
            {ATTR_DEVICE_ID: "device-1"},
            blocking=True,
        )
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_AUTO_START,
            {ATTR_DEVICE_ID: "device-1", ATTR_AUTOSTART: True},
            blocking=True,
        )

        assert client.restart_calls == ["OK-CHARGER-001"]
        assert client.auto_start_calls == [
            {"charging_station_id": "OK-CHARGER-001", "autostart": True}
        ]
        assert coordinator.refresh_count == 2
    finally:
        await hass.async_stop()


def test_entity_service_target_validation_errors(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(_test_entity_service_target_validation_errors(tmp_path, monkeypatch))


async def _test_entity_service_target_validation_errors(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeServiceClient()
    try:
        coordinator, _entry = await _setup_entry(hass, client, monkeypatch)

        entity = _registered_connector_entity(hass)
        entity.connector = SimpleNamespace(station_id="", connector_id=1)
        await _assert_service_validation_error(
            hass,
            SERVICE_START_CHARGING,
            "sensor.charger_connector_status",
            "entity_missing_connector",
        )

        entity.connector = SimpleNamespace(station_id="OK-CHARGER-001", connector_id=0)
        await _assert_service_validation_error(
            hass,
            SERVICE_START_CHARGING,
            "sensor.charger_connector_status",
            "entity_missing_connector",
        )

        entity.connector = SimpleNamespace(station_id="OTHER", connector_id=1)
        await _assert_service_validation_error(
            hass,
            SERVICE_START_CHARGING,
            "sensor.charger_connector_status",
            "connector_not_found",
        )

        entity.connector = coordinator.connector_refs[0]
        coordinator.active_charging = None
        await _assert_service_validation_error(
            hass,
            SERVICE_STOP_CHARGING,
            "sensor.charger_connector_status",
            "active_charging_not_found",
        )

        _patch_device_registry(monkeypatch, None)
        with pytest.raises(ServiceValidationError) as error:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESTART,
                {ATTR_DEVICE_ID: "missing-device"},
                blocking=True,
            )
        assert error.value.translation_key == "device_not_found"

        _patch_device_registry(monkeypatch, SimpleNamespace(identifiers={(DOMAIN, "account_1")}))
        with pytest.raises(ServiceValidationError) as error:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESTART,
                {ATTR_DEVICE_ID: "account-device"},
                blocking=True,
            )
        assert error.value.translation_key == "device_not_ok"
    finally:
        await hass.async_stop()


def test_service_auth_error_starts_reauth(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(_test_service_auth_error_starts_reauth(tmp_path, monkeypatch))


async def _test_service_auth_error_starts_reauth(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeServiceClient()
    client.error = OkAuthenticationError("expired token", status_code=401, headers={}, payload={})
    try:
        coordinator, entry = await _setup_entry(hass, client, monkeypatch)

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_START_CHARGING,
                {ATTR_ENTITY_ID: "sensor.charger_connector_status"},
                blocking=True,
            )

        assert coordinator.refresh_count == 0
        assert entry.reauth_count == 1
        assert exc_info.value.translation_key == "api_authentication_error"
    finally:
        await hass.async_stop()


async def _assert_service_validation_error(
    hass: HomeAssistant,
    service: str,
    entity_id: str,
    translation_key: str,
) -> None:
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert error.value.translation_key == translation_key


async def _setup_entry(
    hass: HomeAssistant,
    client: FakeServiceClient,
    monkeypatch: MonkeyPatch,
) -> tuple[FakeCoordinator, FakeEntry]:
    hass.config.time_zone = "Europe/Copenhagen"
    hass.config_entries = ConfigEntries(hass, {})
    coordinator = FakeCoordinator()
    entry = FakeEntry(client, coordinator)
    coordinator.entry = entry
    monkeypatch.setattr(hass.config_entries, "async_entries", lambda domain=None: [entry])
    entity = FakeConnectorStatusEntity(coordinator)
    hass.data.setdefault(DATA_DOMAIN_PLATFORM_ENTITIES, {})[(Platform.SENSOR.value, DOMAIN)] = {
        entity.entity_id: entity
    }
    await async_setup(hass, {})
    return coordinator, entry


def _registered_connector_entity(hass: HomeAssistant) -> FakeConnectorStatusEntity:
    entity = hass.data[DATA_DOMAIN_PLATFORM_ENTITIES][(Platform.SENSOR.value, DOMAIN)][
        "sensor.charger_connector_status"
    ]
    assert isinstance(entity, FakeConnectorStatusEntity)
    return entity


def _patch_device_registry(monkeypatch: MonkeyPatch, device_entry: Any) -> None:
    monkeypatch.setattr(
        dr,
        "async_get",
        lambda hass: SimpleNamespace(async_get=lambda device_id: device_entry),
    )
