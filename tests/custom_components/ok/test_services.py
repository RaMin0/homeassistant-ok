from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from custom_components.ok.api import OkAuthenticationError
from custom_components.ok.const import (
    ATTR_AUTOSTART,
    ATTR_CHARGER_ID,
    ATTR_CONNECTOR_ID,
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
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
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
        self.active_charging: dict[str, Any] | None = {"chargingToken": "charging-token"}

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

        assert client.schedule_calls == [
            {
                "charging_station_id": "OK-CHARGER-001",
                "connector_id": 1,
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

        assert client.schedule_calls[0]["scheduled_start"] == "2026-06-14T13:30:00+00:00"
        assert client.schedule_calls[0]["scheduled_end"] == "2026-06-14T16:00:00+00:00"
        assert client.update_calls == [
            {
                "charging_token": "charging-token",
                "scheduled_start": "2026-06-14T15:30:00+02:00",
                "scheduled_end": "2026-06-14T18:00:00+02:00",
            }
        ]
        assert coordinator.refresh_count == 2
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
            (SERVICE_RESTART, {}),
            (SERVICE_SET_AUTO_START, {ATTR_AUTOSTART: False}),
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
        assert client.restart_calls == ["OK-CHARGER-001"]
        assert client.auto_start_calls == [
            {"charging_station_id": "OK-CHARGER-001", "autostart": False}
        ]
        assert coordinator.refresh_count == 5
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

        _patch_entity_registry(monkeypatch, None)
        await _assert_service_validation_error(
            hass,
            SERVICE_START_CHARGING,
            "sensor.unknown",
            "entity_not_found",
        )

        _patch_entity_registry(
            monkeypatch,
            SimpleNamespace(platform="sensor", config_entry_id="test-entry"),
        )
        await _assert_service_validation_error(
            hass,
            SERVICE_START_CHARGING,
            "sensor.charger_connector_status",
            "entity_not_ok",
        )

        _patch_entity_registry(
            monkeypatch,
            SimpleNamespace(platform=DOMAIN, config_entry_id=None),
        )
        await _assert_service_validation_error(
            hass,
            SERVICE_START_CHARGING,
            "sensor.charger_connector_status",
            "entity_missing_config_entry",
        )

        _patch_entity_registry(
            monkeypatch,
            SimpleNamespace(platform=DOMAIN, config_entry_id="missing-entry"),
        )
        await _assert_service_validation_error(
            hass,
            SERVICE_START_CHARGING,
            "sensor.charger_connector_status",
            "entry_not_loaded",
        )

        _patch_entity_registry(
            monkeypatch,
            SimpleNamespace(platform=DOMAIN, config_entry_id="test-entry"),
        )
        await _assert_service_validation_error(
            hass,
            SERVICE_START_CHARGING,
            "sensor.missing_state",
            "entity_not_found",
        )

        hass.states.async_set("sensor.missing_connector", "Available", {})
        await _assert_service_validation_error(
            hass,
            SERVICE_START_CHARGING,
            "sensor.missing_connector",
            "entity_missing_connector",
        )

        hass.states.async_set(
            "sensor.bad_connector",
            "Available",
            {ATTR_CHARGER_ID: "OK-CHARGER-001", ATTR_CONNECTOR_ID: 0},
        )
        await _assert_service_validation_error(
            hass,
            SERVICE_START_CHARGING,
            "sensor.bad_connector",
            "entity_missing_connector",
        )

        hass.states.async_set(
            "sensor.unknown_connector",
            "Available",
            {ATTR_CHARGER_ID: "OTHER", ATTR_CONNECTOR_ID: 1},
        )
        await _assert_service_validation_error(
            hass,
            SERVICE_START_CHARGING,
            "sensor.unknown_connector",
            "connector_not_found",
        )

        coordinator.active_charging = None
        await _assert_service_validation_error(
            hass,
            SERVICE_STOP_CHARGING,
            "sensor.charger_connector_status",
            "active_charging_not_found",
        )
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
    monkeypatch.setattr(hass.config_entries, "async_entries", lambda domain=None: [entry])
    _patch_entity_registry(
        monkeypatch,
        SimpleNamespace(
            platform=DOMAIN,
            config_entry_id="test-entry",
        ),
    )
    hass.states.async_set(
        "sensor.charger_connector_status",
        "Available",
        {
            ATTR_CHARGER_ID: "OK-CHARGER-001",
            ATTR_CONNECTOR_ID: 1,
        },
    )
    await async_setup(hass, {})
    return coordinator, entry


def _patch_entity_registry(monkeypatch: MonkeyPatch, registry_entry: Any) -> None:
    monkeypatch.setattr(
        er,
        "async_get",
        lambda hass: SimpleNamespace(async_get=lambda entity_id: registry_entry),
    )
