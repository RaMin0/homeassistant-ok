from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from custom_components.ok.api import OkAuthenticationError
from custom_components.ok.button import BUTTON_DESCRIPTIONS, OkButton, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import EntityCategory

from .entity_helpers import EntitySetupEntry, EntityTestCoordinator, make_connector


def _description(key: str):
    return next(item for item in BUTTON_DESCRIPTIONS if item.key == key)


def test_button_registry_defaults() -> None:
    assert _description("start_charging").entity_registry_enabled_default is not False
    assert _description("stop_charging").entity_registry_enabled_default is not False
    assert _description("force_refresh").entity_registry_enabled_default is not False
    assert _description("force_refresh").entity_category is EntityCategory.CONFIG
    assert _description("restart").entity_registry_enabled_default is False


def test_buttons_call_ok_api_actions(tmp_path: Path) -> None:
    asyncio.run(_test_buttons_call_ok_api_actions(tmp_path))


async def _test_buttons_call_ok_api_actions(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        coordinator.active_charging = {"chargingToken": "charging-token"}
        connector = coordinator.connector_refs[0]

        start = OkButton(coordinator, connector, _description("start_charging"))
        stop = OkButton(coordinator, connector, _description("stop_charging"))
        cancel = OkButton(coordinator, connector, _description("cancel_schedule"))
        restart = OkButton(coordinator, connector, _description("restart"))
        force_refresh = OkButton(coordinator, connector, _description("force_refresh"))
        for entity in (start, stop, cancel, restart, force_refresh):
            entity.hass = hass

        assert start.unique_id == "OK-CHARGER-001_1_start_charging"
        assert restart.unique_id == "OK-CHARGER-001_restart"
        assert force_refresh.unique_id == "1000001_force_refresh"
        assert force_refresh.device_info["identifiers"] == {("ok", "account_1000001")}
        assert force_refresh.device_info["entry_type"] is DeviceEntryType.SERVICE
        assert force_refresh.device_info["manufacturer"] == "OK"
        assert force_refresh.device_info["translation_key"] == "account"
        assert "name" not in force_refresh.device_info
        assert start.available is True
        assert stop.available is True
        assert cancel.available is True
        assert force_refresh.available is True

        await start.async_press()
        await stop.async_press()
        await cancel.async_press()
        await restart.async_press()
        await force_refresh.async_press()

        assert coordinator.client.start_calls == [
            {"charging_station_id": "OK-CHARGER-001", "connector_id": 1}
        ]
        assert coordinator.client.stop_calls == ["charging-token"]
        assert coordinator.client.cancel_calls == ["charging-token"]
        assert coordinator.client.restart_calls == ["OK-CHARGER-001"]
        assert coordinator.refresh_count == 5
        assert coordinator.force_full_refresh_count == 1

        coordinator.data = None
        assert start.available is False
    finally:
        await hass.async_stop()


def test_force_refresh_button_is_unavailable_during_refresh(tmp_path: Path) -> None:
    asyncio.run(_test_force_refresh_button_is_unavailable_during_refresh(tmp_path))


async def _test_force_refresh_button_is_unavailable_during_refresh(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        force_refresh = OkButton(
            coordinator,
            coordinator.connector_refs[0],
            _description("force_refresh"),
        )
        force_refresh.hass = hass

        assert force_refresh.available is True

        coordinator.refresh_in_progress = True

        assert force_refresh.available is False
    finally:
        await hass.async_stop()


def test_session_buttons_require_active_charging(tmp_path: Path) -> None:
    asyncio.run(_test_session_buttons_require_active_charging(tmp_path))


async def _test_session_buttons_require_active_charging(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        connector = coordinator.connector_refs[0]
        stop = OkButton(coordinator, connector, _description("stop_charging"))
        stop.hass = hass

        assert stop.available is False

        with pytest.raises(HomeAssistantError):
            await stop.async_press()
    finally:
        await hass.async_stop()


def test_button_auth_error_starts_reauth(tmp_path: Path) -> None:
    asyncio.run(_test_button_auth_error_starts_reauth(tmp_path))


async def _test_button_auth_error_starts_reauth(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        coordinator.client.error = OkAuthenticationError(
            "expired token",
            status_code=401,
            headers={},
            payload={},
        )
        start = OkButton(coordinator, coordinator.connector_refs[0], _description("start_charging"))
        start.hass = hass

        with pytest.raises(HomeAssistantError) as exc_info:
            await start.async_press()

        assert coordinator.entry.reauth_count == 1
        assert exc_info.value.translation_key == "api_authentication_error"
    finally:
        await hass.async_stop()


def test_button_setup_adds_new_connectors_once(tmp_path: Path) -> None:
    asyncio.run(_test_button_setup_adds_new_connectors_once(tmp_path))


async def _test_button_setup_adds_new_connectors_once(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        entry = EntitySetupEntry(coordinator)
        added: list[OkButton] = []

        await async_setup_entry(hass, entry, added.extend)

        assert len(added) == 5
        assert {entity.unique_id for entity in added} == {
            "OK-CHARGER-001_1_start_charging",
            "OK-CHARGER-001_1_stop_charging",
            "OK-CHARGER-001_1_cancel_schedule",
            "OK-CHARGER-001_restart",
            "1000001_force_refresh",
        }

        coordinator.connector_refs.append(make_connector("OK-CHARGER-001", 2))
        coordinator.listeners[0]()
        coordinator.listeners[0]()

        assert len(added) == 8
        assert "OK-CHARGER-001_2_start_charging" in {entity.unique_id for entity in added}
        assert [entity.unique_id for entity in added].count("OK-CHARGER-001_restart") == 1
        assert [entity.unique_id for entity in added].count("1000001_force_refresh") == 1

        coordinator.connector_refs.append(make_connector("EVB-P99999999", 1))
        coordinator.listeners[0]()

        assert len(added) == 12
        assert "EVB-P99999999_restart" in {entity.unique_id for entity in added}
        assert [entity.unique_id for entity in added].count("1000001_force_refresh") == 1
    finally:
        await hass.async_stop()


def test_button_setup_adds_coordinator_scoped_without_connectors(tmp_path: Path) -> None:
    asyncio.run(_test_button_setup_adds_coordinator_scoped_without_connectors(tmp_path))


async def _test_button_setup_adds_coordinator_scoped_without_connectors(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        coordinator.connector_refs = []
        entry = EntitySetupEntry(coordinator)
        added: list[OkButton] = []

        await async_setup_entry(hass, entry, added.extend)

        assert [entity.unique_id for entity in added] == ["1000001_force_refresh"]
        assert added[0].device_info["identifiers"] == {("ok", "account_1000001")}
    finally:
        await hass.async_stop()
