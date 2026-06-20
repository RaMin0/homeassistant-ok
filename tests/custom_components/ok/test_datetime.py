from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from custom_components.ok.datetime import (
    DATETIME_DESCRIPTIONS,
    OkScheduleDateTime,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .entity_helpers import EntitySetupEntry, EntityTestCoordinator, make_connector


def _description(key: str) -> Any:
    return next(item for item in DATETIME_DESCRIPTIONS if item.key == key)


def test_schedule_datetime_entities_expose_current_schedule(tmp_path: Path) -> None:
    asyncio.run(_test_schedule_datetime_entities_expose_current_schedule(tmp_path))


async def _test_schedule_datetime_entities_expose_current_schedule(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        coordinator.active_charging = {"chargingToken": "charging-token"}
        connector = coordinator.connector_refs[0]

        schedule_from = OkScheduleDateTime(coordinator, connector, _description("schedule_from"))
        schedule_to = OkScheduleDateTime(coordinator, connector, _description("schedule_to"))
        schedule_from.hass = hass
        schedule_to.hass = hass

        assert schedule_from.unique_id == "OK-CHARGER-001_1_schedule_from"
        assert schedule_to.unique_id == "OK-CHARGER-001_1_schedule_to"
        assert schedule_from.translation_key == "schedule_from"
        assert schedule_from.native_value == datetime(2026, 6, 14, 15, 30, tzinfo=UTC)
        assert schedule_to.native_value == datetime(2026, 6, 14, 18, 0, tzinfo=UTC)
        assert schedule_from.available is True

        coordinator.active_charging = None

        assert schedule_from.native_value is None
        assert schedule_from.available is True

        coordinator.data = None

        assert schedule_from.available is False
    finally:
        await hass.async_stop()


def test_schedule_datetime_translations() -> None:
    expected_names = {
        "en": {
            "schedule_from": "Schedule from",
            "schedule_from_connector": "Connector {connector_id} schedule from",
            "schedule_to": "Schedule to",
            "schedule_to_connector": "Connector {connector_id} schedule to",
        },
        "da": {
            "schedule_from": "Ladeplan fra",
            "schedule_from_connector": "Ladestik {connector_id} ladeplan fra",
            "schedule_to": "Ladeplan til",
            "schedule_to_connector": "Ladestik {connector_id} ladeplan til",
        },
    }

    for language, names in expected_names.items():
        translations = json.loads(
            Path(f"custom_components/ok/translations/{language}.json").read_text()
        )
        datetime_translations = translations["entity"]["datetime"]
        assert set(datetime_translations) == set(names)
        for key, name in names.items():
            assert datetime_translations[key]["name"] == name


def test_schedule_datetime_entity_updates_schedule(tmp_path: Path) -> None:
    asyncio.run(_test_schedule_datetime_entity_updates_schedule(tmp_path))


async def _test_schedule_datetime_entity_updates_schedule(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        coordinator.active_charging = {"chargingToken": "charging-token"}
        connector = coordinator.connector_refs[0]

        schedule_from = OkScheduleDateTime(coordinator, connector, _description("schedule_from"))
        schedule_from.hass = hass
        await schedule_from.async_set_value(datetime(2026, 6, 14, 16, 0, tzinfo=UTC))

        schedule_to = OkScheduleDateTime(coordinator, connector, _description("schedule_to"))
        schedule_to.hass = hass
        await schedule_to.async_set_value(datetime(2026, 6, 14, 19, 0, tzinfo=UTC))

        assert coordinator.client.update_calls == [
            {
                "charging_token": "charging-token",
                "scheduled_start": "2026-06-14T16:00:00+00:00",
                "scheduled_end": "2026-06-14T18:00:00+00:00",
            },
            {
                "charging_token": "charging-token",
                "scheduled_start": "2026-06-14T15:30:00+00:00",
                "scheduled_end": "2026-06-14T19:00:00+00:00",
            },
        ]
        assert coordinator.refresh_count == 2
    finally:
        await hass.async_stop()


def test_schedule_datetime_entity_rejects_incomplete_schedule(tmp_path: Path) -> None:
    asyncio.run(_test_schedule_datetime_entity_rejects_incomplete_schedule(tmp_path))


async def _test_schedule_datetime_entity_rejects_incomplete_schedule(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        coordinator.active_charging = {"chargingToken": "charging-token"}
        connector = coordinator.connector_refs[0]
        coordinator.charging_status_documents["charging-token"].fields.pop("scheduledEnd")
        schedule_from = OkScheduleDateTime(coordinator, connector, _description("schedule_from"))
        schedule_from.hass = hass

        with pytest.raises(ServiceValidationError) as error:
            await schedule_from.async_set_value(datetime(2026, 6, 14, 16, 0, tzinfo=UTC))

        assert error.value.translation_key == "schedule_window_missing"
        assert coordinator.client.update_calls == []
    finally:
        await hass.async_stop()


def test_schedule_datetime_entity_rejects_invalid_schedule_window(tmp_path: Path) -> None:
    asyncio.run(_test_schedule_datetime_entity_rejects_invalid_schedule_window(tmp_path))


async def _test_schedule_datetime_entity_rejects_invalid_schedule_window(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        coordinator.active_charging = {"chargingToken": "charging-token"}
        connector = coordinator.connector_refs[0]
        schedule_to = OkScheduleDateTime(coordinator, connector, _description("schedule_to"))
        schedule_to.hass = hass

        with pytest.raises(ServiceValidationError) as error:
            await schedule_to.async_set_value(datetime(2026, 6, 14, 15, 0, tzinfo=UTC))

        assert error.value.translation_key == "invalid_schedule_window"
        assert coordinator.client.update_calls == []
    finally:
        await hass.async_stop()


def test_schedule_datetime_setup_adds_new_connectors_once(tmp_path: Path) -> None:
    asyncio.run(_test_schedule_datetime_setup_adds_new_connectors_once(tmp_path))


async def _test_schedule_datetime_setup_adds_new_connectors_once(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        entry = EntitySetupEntry(coordinator)
        added: list[OkScheduleDateTime] = []

        await async_setup_entry(hass, entry, added.extend)

        assert {entity.unique_id for entity in added} == {
            "OK-CHARGER-001_1_schedule_from",
            "OK-CHARGER-001_1_schedule_to",
        }

        coordinator.connector_refs.append(make_connector("OK-CHARGER-001", 2))
        coordinator.listeners[0]()
        coordinator.listeners[0]()

        assert len(added) == len(DATETIME_DESCRIPTIONS) * 2
        assert "OK-CHARGER-001_2_schedule_from" in {entity.unique_id for entity in added}

        coordinator.connector_refs.append(make_connector("EVB-P99999999", 1))
        coordinator.listeners[0]()

        assert len(added) == len(DATETIME_DESCRIPTIONS) * 3
        assert "EVB-P99999999_1_schedule_to" in {entity.unique_id for entity in added}
    finally:
        await hass.async_stop()
