from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from custom_components.ok.const import CONF_INCLUDE_RECEIPTS, CONNECTOR_STATUS_OPTIONS
from custom_components.ok.sensor import SENSOR_DESCRIPTIONS, OkSensor, async_setup_entry
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import EntityCategory

from .entity_helpers import EntitySetupEntry, EntityTestCoordinator, make_connector, make_document


def _description(key: str) -> Any:
    return next(item for item in SENSOR_DESCRIPTIONS if item.key == key)


def test_connector_status_sensor_attrs_and_device_info(tmp_path: Path) -> None:
    asyncio.run(_test_connector_status_sensor_attrs_and_device_info(tmp_path))


async def _test_connector_status_sensor_attrs_and_device_info(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        connector = coordinator.connector_refs[0]
        entity = OkSensor(coordinator, connector, _description("connector_status"))
        entity.hass = hass

        description = _description("connector_status")
        assert description.device_class is SensorDeviceClass.ENUM
        assert description.options == list(CONNECTOR_STATUS_OPTIONS)
        assert entity.unique_id == "OK-CHARGER-001_1_connector_status"
        assert entity.native_value == "available"
        assert entity.available is True
        assert entity.extra_state_attributes == {
            "charger_id": "OK-CHARGER-001",
            "connector_id": 1,
            "raw_status": "Available",
            "status_updated": "2026-06-14T12:00:00Z",
            "maximum_power_kw": 22,
        }
        assert entity.device_info["identifiers"] == {("ok", "OK-CHARGER-001")}
        assert entity.device_info["name"] == "Home Charger"
        assert entity.device_info["suggested_area"] == "Garage"
    finally:
        await hass.async_stop()


def test_entity_multi_connector_and_device_info_fallbacks(tmp_path: Path) -> None:
    asyncio.run(_test_entity_multi_connector_and_device_info_fallbacks(tmp_path))


async def _test_entity_multi_connector_and_device_info_fallbacks(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        connector = coordinator.connector_refs[0]
        coordinator.connector_refs.append(make_connector("OK-CHARGER-001", 2))

        connector_status = OkSensor(coordinator, connector, _description("connector_status"))
        connector_status.hass = hass

        assert connector_status.translation_key == "connector_status_connector"
        assert connector_status.translation_placeholders == {"connector_id": "1"}

        coordinator.connector_refs = [coordinator.connector_refs[1]]
        assert connector_status.connector is connector
        assert connector_status.available is False

        energy_price = OkSensor(coordinator, connector, _description("energy_price"))
        energy_price.hass = hass
        assert energy_price.available is True

        coordinator.data = None
        assert energy_price.available is False

        minimal = make_connector("MINIMAL", 1)
        minimal.station.clear()
        minimal.station.update(
            {
                "csIdentifier": "MINIMAL",
                "vendorName": 1,
                "name": "",
                "connectors": [{"connectorId": 1}],
            }
        )
        minimal.location.clear()
        fallback = OkSensor(coordinator, minimal, _description("connector_status"))

        assert fallback.device_info["manufacturer"] == "OK"
        assert fallback.device_info["name"] == "MINIMAL"
    finally:
        await hass.async_stop()


def test_connector_status_sensor_rejects_unknown_enum_state(tmp_path: Path) -> None:
    asyncio.run(_test_connector_status_sensor_rejects_unknown_enum_state(tmp_path))


async def _test_connector_status_sensor_rejects_unknown_enum_state(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        connector = coordinator.connector_refs[0]
        coordinator.station_status_documents[(connector.station_id, connector.connector_id)] = (
            make_document({"status": "VendorSpecific"})
        )
        entity = OkSensor(coordinator, connector, _description("connector_status"))
        entity.hass = hass

        assert entity.native_value is None
        assert entity.available is False
    finally:
        await hass.async_stop()


def test_connector_status_translations_cover_enum_options() -> None:
    expected_names = {
        "en": {
            "connector_status": "Status",
            "connector_status_connector": "Connector {connector_id} status",
            "connector_session_power": "Session power",
            "connector_session_power_connector": "Connector {connector_id} session power",
            "connector_session_energy": "Session energy",
            "connector_session_energy_connector": "Connector {connector_id} session energy",
            "schedule_start": "Schedule start",
            "schedule_start_connector": "Connector {connector_id} schedule start",
            "schedule_end": "Schedule end",
            "schedule_end_connector": "Connector {connector_id} schedule end",
            "schedule_duration": "Schedule duration",
            "schedule_duration_connector": "Connector {connector_id} schedule duration",
            "last_refresh": "Last refresh",
            "charger_last_refresh": "Last refresh",
        },
        "da": {
            "connector_status": "Status",
            "connector_status_connector": "Ladestik {connector_id} status",
            "connector_session_power": "Sessionseffekt",
            "connector_session_power_connector": "Ladestik {connector_id} sessionseffekt",
            "connector_session_energy": "Sessionsenergi",
            "connector_session_energy_connector": "Ladestik {connector_id} sessionsenergi",
            "schedule_start": "Ladeplan start",
            "schedule_start_connector": "Ladestik {connector_id} ladeplan start",
            "schedule_end": "Ladeplan slut",
            "schedule_end_connector": "Ladestik {connector_id} ladeplan slut",
            "schedule_duration": "Ladeplan varighed",
            "schedule_duration_connector": "Ladestik {connector_id} ladeplan varighed",
            "last_refresh": "Seneste opdatering",
            "charger_last_refresh": "Seneste opdatering",
        },
    }
    expected_attribute_keys = {
        "energy_price": {
            "charger_id",
            "unit",
            "currency",
            "region",
            "tomorrow_valid",
            "next_data_update",
            "today",
            "tomorrow",
            "raw_today",
            "raw_tomorrow",
            "today_min",
            "today_max",
            "today_mean",
            "tomorrow_min",
            "tomorrow_max",
            "tomorrow_mean",
            "use_cent",
            "prices",
            "product",
            "attribution",
        },
        "last_refresh": {
            "account_settings",
            "charger_overview",
            "energy_prices",
            "active_sessions",
            "charging_receipts",
            "trigger",
            "in_progress",
        },
        "charger_last_refresh": {
            "charger_status",
            "session_status",
            "session_receipt",
        },
        "connector_status": {
            "charger_id",
            "connector_id",
            "raw_status",
            "status_updated",
            "maximum_power_kw",
        },
        "connector_status_connector": {
            "charger_id",
            "connector_id",
            "raw_status",
            "status_updated",
            "maximum_power_kw",
        },
        "last_session_cost": {"no_price_reason"},
    }

    for language in ("en", "da"):
        translations = json.loads(
            Path(f"custom_components/ok/translations/{language}.json").read_text()
        )
        entity_translations = translations["entity"]["sensor"]
        assert (
            translations["device"]["account"]["name"]
            == {
                "en": "OK Account",
                "da": "OK-konto",
            }[language]
        )

        for key in ("connector_status", "connector_status_connector"):
            states = entity_translations[key]["state"]
            assert set(states) == set(CONNECTOR_STATUS_OPTIONS)
            assert all(states[status] for status in CONNECTOR_STATUS_OPTIONS)

        for key, name in expected_names[language].items():
            assert entity_translations[key]["name"] == name

        for key, attribute_keys in expected_attribute_keys.items():
            state_attributes = entity_translations[key]["state_attributes"]
            assert set(state_attributes) == attribute_keys
            assert all(attribute["name"] for attribute in state_attributes.values())


def test_charging_session_sensors_use_active_charging_status(tmp_path: Path) -> None:
    asyncio.run(_test_charging_session_sensors_use_active_charging_status(tmp_path))


async def _test_charging_session_sensors_use_active_charging_status(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        coordinator.active_charging = {"chargingToken": "charging-token"}
        connector = coordinator.connector_refs[0]

        power = OkSensor(coordinator, connector, _description("connector_session_power"))
        values = {
            "connector_session_power": power.native_value,
            "connector_session_energy": OkSensor(
                coordinator, connector, _description("connector_session_energy")
            ).native_value,
            "schedule_start": OkSensor(
                coordinator, connector, _description("schedule_start")
            ).native_value,
            "schedule_end": OkSensor(
                coordinator, connector, _description("schedule_end")
            ).native_value,
            "schedule_duration": OkSensor(
                coordinator, connector, _description("schedule_duration")
            ).native_value,
        }
        schedule_start = OkSensor(coordinator, connector, _description("schedule_start"))

        assert power.native_unit_of_measurement is UnitOfPower.KILO_WATT
        assert values["connector_session_power"] == 3.522
        assert values["connector_session_energy"] == 5.835
        assert values["schedule_start"] == datetime(2026, 6, 14, 15, 30, tzinfo=UTC)
        assert values["schedule_end"] == datetime(2026, 6, 14, 18, 0, tzinfo=UTC)
        assert values["schedule_duration"] == 9000
        assert schedule_start.extra_state_attributes == {}
        assert _description("schedule_duration").native_unit_of_measurement is UnitOfTime.SECONDS
        assert power.extra_state_attributes == {}

        coordinator.active_charging = None
        inactive_power = OkSensor(coordinator, connector, _description("connector_session_power"))
        inactive_power.hass = hass

        assert inactive_power.native_value is None
        assert inactive_power.available is False
    finally:
        await hass.async_stop()


def test_energy_price_sensor_exposes_compatible_attributes(tmp_path: Path) -> None:
    asyncio.run(_test_energy_price_sensor_exposes_compatible_attributes(tmp_path))


async def _test_energy_price_sensor_exposes_compatible_attributes(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        connector = coordinator.connector_refs[0]

        price = OkSensor(coordinator, connector, _description("energy_price"))
        price.hass = hass
        attrs = price.extra_state_attributes

        assert price.native_value == 1.25
        assert attrs["charger_id"] == "OK-CHARGER-001"
        assert attrs["unit"] == "kWh"
        assert attrs["currency"] == "DKK"
        assert attrs["region"] == "DK2"
        assert isinstance(attrs["tomorrow_valid"], bool)
        assert isinstance(attrs["raw_tomorrow"], list)
        assert attrs["prices"][0]["price"] == 1.25
        assert attrs["prices"][1]["price"] == 2.35
        assert "today_min" in attrs
        assert "today_max" in attrs
        assert attrs["product"] == "OK El Flex"
        assert attrs["attribution"] == "Data sourced from OK"
        assert "current_price" not in attrs
        assert "region_code" not in attrs
        assert "product_type" not in attrs
        assert "electricity_price_origin" not in attrs
    finally:
        await hass.async_stop()


def test_last_refresh_sensor(tmp_path: Path) -> None:
    asyncio.run(_test_last_refresh_sensor(tmp_path))


async def _test_last_refresh_sensor(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        connector = coordinator.connector_refs[0]
        entity = OkSensor(coordinator, connector, _description("last_refresh"))
        entity.hass = hass

        assert entity.unique_id == "1000001_last_refresh"
        assert entity.device_info["identifiers"] == {("ok", "account_1000001")}
        assert entity.device_info["entry_type"] is DeviceEntryType.SERVICE
        assert entity.device_info["manufacturer"] == "OK"
        assert entity.device_info["translation_key"] == "account"
        assert "name" not in entity.device_info
        assert entity.device_class is SensorDeviceClass.TIMESTAMP
        assert entity.entity_category is EntityCategory.DIAGNOSTIC
        assert entity.native_value == datetime(2026, 6, 14, 12, 0, tzinfo=UTC)
        assert entity.available is True
        assert entity.extra_state_attributes == {
            "account_settings": "2026-06-14T11:50:00+00:00",
            "charger_overview": "2026-06-14T11:55:00+00:00",
            "energy_prices": "2026-06-14T11:56:00+00:00",
            "active_sessions": "2026-06-14T11:57:00+00:00",
            "charging_receipts": "2026-06-14T11:58:00+00:00",
            "trigger": "automatic",
            "in_progress": False,
        }
        assert "charger_status" not in entity.extra_state_attributes
        assert "session_status" not in entity.extra_state_attributes
        assert "session_receipt" not in entity.extra_state_attributes
        assert "refresh" not in str(entity.extra_state_attributes).lower()

        coordinator.connector_refs = []

        assert entity.available is True

        coordinator.last_refresh = None

        assert entity.available is False
    finally:
        await hass.async_stop()


def test_charger_last_refresh_sensor(tmp_path: Path) -> None:
    asyncio.run(_test_charger_last_refresh_sensor(tmp_path))


async def _test_charger_last_refresh_sensor(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        connector = coordinator.connector_refs[0]
        entity = OkSensor(coordinator, connector, _description("charger_last_refresh"))
        entity.hass = hass

        assert entity.unique_id == "OK-CHARGER-001_charger_last_refresh"
        assert entity.device_info["identifiers"] == {("ok", "OK-CHARGER-001")}
        assert entity.device_info["name"] == "Home Charger"
        assert entity.device_class is SensorDeviceClass.TIMESTAMP
        assert entity.entity_category is EntityCategory.DIAGNOSTIC
        assert entity.native_value == datetime(2026, 6, 14, 11, 59, tzinfo=UTC)
        assert entity.available is True
        assert entity.extra_state_attributes == {
            "charger_status": "2026-06-14T11:59:00+00:00",
            "session_status": None,
            "session_receipt": None,
        }

        coordinator._charger_last_refresh = None

        assert entity.available is False
    finally:
        await hass.async_stop()


def test_last_session_sensor(tmp_path: Path) -> None:
    asyncio.run(_test_last_session_sensor(tmp_path))


async def _test_last_session_sensor(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        connector = coordinator.connector_refs[0]

        entities = {
            key: OkSensor(coordinator, connector, _description(key))
            for key in (
                "last_session_ended",
                "last_session_energy",
                "last_session_cost",
                "last_session_started",
                "last_session_duration",
            )
        }
        for entity in entities.values():
            entity.hass = hass

        assert entities["last_session_ended"].unique_id == "OK-CHARGER-001_last_session_ended"
        assert entities["last_session_ended"].native_value == datetime(
            2026, 6, 13, 22, 0, tzinfo=UTC
        )
        assert entities["last_session_ended"].extra_state_attributes == {}
        assert entities["last_session_energy"].native_value == 12.5
        assert entities["last_session_energy"].native_unit_of_measurement is (
            UnitOfEnergy.KILO_WATT_HOUR
        )
        assert entities["last_session_cost"].native_value == 17.67
        assert entities["last_session_cost"].native_unit_of_measurement == "DKK"
        assert entities["last_session_cost"].extra_state_attributes == {"no_price_reason": None}
        assert entities["last_session_started"].native_value == datetime(
            2026, 6, 13, 20, 0, tzinfo=UTC
        )
        assert entities["last_session_duration"].native_value == 7200
        assert entities["last_session_duration"].native_unit_of_measurement is UnitOfTime.SECONDS

        coordinator.receipt = None

        for entity in entities.values():
            assert entity.native_value is None
            assert entity.available is False
    finally:
        await hass.async_stop()


def test_last_session_sensors_are_option_gated(tmp_path: Path) -> None:
    asyncio.run(_test_last_session_sensors_are_option_gated(tmp_path))


async def _test_last_session_sensors_are_option_gated(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        entry = EntitySetupEntry(coordinator, options={CONF_INCLUDE_RECEIPTS: False})
        added: list[OkSensor] = []

        await async_setup_entry(hass, entry, added.extend)

        assert {entity.unique_id for entity in added} == {
            "OK-CHARGER-001_energy_price",
            "1000001_last_refresh",
            "OK-CHARGER-001_charger_last_refresh",
            "OK-CHARGER-001_1_connector_status",
            "OK-CHARGER-001_1_connector_session_power",
            "OK-CHARGER-001_1_connector_session_energy",
            "OK-CHARGER-001_1_schedule_start",
            "OK-CHARGER-001_1_schedule_end",
            "OK-CHARGER-001_1_schedule_duration",
        }
    finally:
        await hass.async_stop()


def test_sensor_setup_adds_new_connectors_once(tmp_path: Path) -> None:
    asyncio.run(_test_sensor_setup_adds_new_connectors_once(tmp_path))


async def _test_sensor_setup_adds_new_connectors_once(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        entry = EntitySetupEntry(coordinator)
        added: list[OkSensor] = []

        await async_setup_entry(hass, entry, added.extend)

        assert len(added) == len(SENSOR_DESCRIPTIONS)
        assert "OK-CHARGER-001_energy_price" in {entity.unique_id for entity in added}

        coordinator.connector_refs.append(make_connector("OK-CHARGER-001", 2))
        coordinator.listeners[0]()
        coordinator.listeners[0]()

        assert len(added) == len(SENSOR_DESCRIPTIONS) + 6
        assert "OK-CHARGER-001_2_connector_status" in {entity.unique_id for entity in added}

        coordinator.connector_refs.append(make_connector("EVB-P99999999", 1))
        coordinator.listeners[0]()

        assert len(added) == len(SENSOR_DESCRIPTIONS) * 2 + 5
        assert "EVB-P99999999_energy_price" in {entity.unique_id for entity in added}
    finally:
        await hass.async_stop()


def test_sensor_setup_adds_coordinator_scoped_without_connectors(tmp_path: Path) -> None:
    asyncio.run(_test_sensor_setup_adds_coordinator_scoped_without_connectors(tmp_path))


async def _test_sensor_setup_adds_coordinator_scoped_without_connectors(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        coordinator.connector_refs = []
        entry = EntitySetupEntry(coordinator)
        added: list[OkSensor] = []

        await async_setup_entry(hass, entry, added.extend)

        assert [entity.unique_id for entity in added] == ["1000001_last_refresh"]
        assert added[0].device_info["identifiers"] == {("ok", "account_1000001")}
    finally:
        await hass.async_stop()
