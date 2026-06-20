from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from custom_components.ok.api import OkAuthenticationError
from custom_components.ok.switch import (
    AUTO_START_SWITCH_DESCRIPTION,
    OkAutoStartSwitch,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory

from .entity_helpers import EntitySetupEntry, EntityTestCoordinator, make_connector


def test_auto_start_switch_controls_station(tmp_path: Path) -> None:
    asyncio.run(_test_auto_start_switch_controls_station(tmp_path))


async def _test_auto_start_switch_controls_station(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        connector = make_connector(auto_start=True)
        coordinator = EntityTestCoordinator(hass, connector)
        entity = OkAutoStartSwitch(coordinator, connector, AUTO_START_SWITCH_DESCRIPTION)
        entity.hass = hass

        assert entity.unique_id == "OK-CHARGER-001_auto_start"
        assert entity.is_on is True
        assert entity.available is True

        await entity.async_turn_off()
        await entity.async_turn_on()

        assert coordinator.client.auto_start_calls == [
            {"charging_station_id": "OK-CHARGER-001", "autostart": False},
            {"charging_station_id": "OK-CHARGER-001", "autostart": True},
        ]
        assert coordinator.refresh_count == 2

        coordinator.connector_refs[0] = make_connector(auto_start=False)

        assert entity.is_on is False

        coordinator.connector_refs[0] = make_connector(auto_start="yes")

        assert entity.is_on is None
        assert entity.available is True
    finally:
        await hass.async_stop()


def test_auto_start_switch_registry_defaults() -> None:
    assert AUTO_START_SWITCH_DESCRIPTION.entity_category is EntityCategory.CONFIG
    assert AUTO_START_SWITCH_DESCRIPTION.entity_registry_enabled_default is not False


def test_auto_start_switch_auth_error_starts_reauth(tmp_path: Path) -> None:
    asyncio.run(_test_auto_start_switch_auth_error_starts_reauth(tmp_path))


async def _test_auto_start_switch_auth_error_starts_reauth(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        connector = make_connector(auto_start=True)
        coordinator = EntityTestCoordinator(hass, connector)
        coordinator.client.error = OkAuthenticationError(
            "expired token",
            status_code=401,
            headers={},
            payload={},
        )
        entity = OkAutoStartSwitch(coordinator, connector, AUTO_START_SWITCH_DESCRIPTION)
        entity.hass = hass

        with pytest.raises(HomeAssistantError) as exc_info:
            await entity.async_turn_off()

        assert coordinator.entry.reauth_count == 1
        assert exc_info.value.translation_key == "api_authentication_error"
    finally:
        await hass.async_stop()


def test_switch_setup_adds_new_connectors_once(tmp_path: Path) -> None:
    asyncio.run(_test_switch_setup_adds_new_connectors_once(tmp_path))


async def _test_switch_setup_adds_new_connectors_once(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        entry = EntitySetupEntry(coordinator)
        added = []

        await async_setup_entry(hass, entry, added.extend)

        assert {entity.unique_id for entity in added} == {"OK-CHARGER-001_auto_start"}

        coordinator.connector_refs.append(make_connector("OK-CHARGER-001", 2))
        coordinator.listeners[0]()
        coordinator.listeners[0]()

        assert len(added) == 1

        coordinator.connector_refs.append(make_connector("EVB-P99999999", 1))
        coordinator.listeners[0]()

        assert len(added) == 2
        assert "EVB-P99999999_auto_start" in {entity.unique_id for entity in added}
    finally:
        await hass.async_stop()
