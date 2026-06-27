from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest
from custom_components.ok.api import (
    FirestoreDocument,
    FirestoreWatchEvent,
    OkConfigurationError,
    OkConnectionError,
    OkRateLimitError,
)
from custom_components.ok.const import (
    CONF_ENABLE_ENERGY_PRICES,
    CONF_ENABLE_REALTIME_UPDATES,
    CONF_INCLUDE_RECEIPTS,
    DOMAIN,
)
from custom_components.ok.coordinator import (
    OkData,
    OkDataUpdateCoordinator,
    _async_get_device_registry,
    _price_source,
    _RealtimeWatchHandle,
)
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntries
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import load_fixture


class FakeSubscription:
    def __init__(self) -> None:
        self.unsubscribed = False
        self.unsubscribe_count = 0
        self._queue: asyncio.Queue[FirestoreWatchEvent | None] = asyncio.Queue()

    def unsubscribe(self) -> None:
        self.unsubscribe_count += 1
        self.unsubscribed = True

    async def aclose(self) -> None:
        self.unsubscribe()
        self._queue.put_nowait(None)

    def emit(self, event: FirestoreWatchEvent) -> None:
        self._queue.put_nowait(event)

    def __aiter__(self) -> FakeSubscription:
        return self

    async def __anext__(self) -> FirestoreWatchEvent:
        event = await self._queue.get()
        if event is None:
            raise StopAsyncIteration
        return event


class FakeOkClient:
    def __init__(self) -> None:
        self.station_status = "Charging"
        self.station_status_updated = "2025-06-09T12:24:11Z"
        self.connector_session_power_w = 3522
        self.charging_status_updated = "2025-06-05T12:10:12.702511Z"
        self.station_watch_configuration_error = False
        self.station_watch_failures = 0
        self.station_watch_attempts = 0
        self.station_watch_callbacks = {}
        self.charging_watch_callbacks = {}
        self.subscriptions: list[FakeSubscription] = []
        self.get_stations_error: Exception | None = None
        self.locations_response: list[dict[str, Any]] | None = None
        self.current_chargings_response: list[dict[str, Any]] | None = None
        self.station_calls = 0
        self.price_calls = 0
        self.chargings_calls = 0
        self.receipts_calls = 0
        self.quick_receipt_calls: list[str] = []
        self.station_status_calls = 0
        self.charging_status_calls = 0

    async def get_device_settings(self) -> dict[str, Any]:
        return load_fixture("device_settings.json")

    async def get_stations(self) -> list[dict[str, Any]]:
        self.station_calls += 1
        if self.get_stations_error is not None:
            raise self.get_stations_error
        if self.locations_response is not None:
            return self.locations_response
        return load_fixture("locations.json")

    async def get_station_prices(self, charging_station_id: str) -> dict[str, Any]:
        self.price_calls += 1
        assert charging_station_id == "OK-CHARGER-001"
        return load_fixture("prices.json")

    async def get_charging_station_status(
        self,
        charging_station_id: str,
        connector_id: int,
    ) -> FirestoreDocument:
        self.station_status_calls += 1
        assert charging_station_id == "OK-CHARGER-001"
        assert connector_id == 1
        return FirestoreDocument(
            name="documents/OK/Emsp/ChargingStations/Status/Connectors/OK-CHARGER-001__1",
            fields={
                "status": self.station_status,
                "chargingStationId": charging_station_id,
                "connectorId": connector_id,
                "statusUpdated": self.station_status_updated,
            },
            create_time="2023-09-15T09:39:51.473916Z",
            update_time="2025-06-09T12:24:12.161052Z",
            raw={},
        )

    async def get_chargings(self) -> list[dict[str, Any]]:
        self.chargings_calls += 1
        if self.current_chargings_response is not None:
            return self.current_chargings_response
        return load_fixture("current_chargings.json")

    async def get_charging_status(self, charging_token: str) -> FirestoreDocument:
        self.charging_status_calls += 1
        assert charging_token == "charging-token-001"
        return FirestoreDocument(
            name=f"documents/OK/Emsp/RemoteTransactions/{charging_token}",
            fields={
                "status": "Charging",
                "powerInW": self.connector_session_power_w,
                "chargeInWh": 5835,
                "scheduledStart": "2025-06-05T10:30:00Z",
                "scheduledEnd": "2025-06-05T13:00:00Z",
            },
            create_time="2025-06-04T23:04:23.378539Z",
            update_time=self.charging_status_updated,
            raw={},
        )

    async def get_charging_receipts(self) -> list[dict[str, Any]]:
        self.receipts_calls += 1
        return load_fixture("receipts.json")

    async def get_charging_receipt(self, charging_token: str) -> dict[str, Any]:
        self.quick_receipt_calls.append(charging_token)
        assert charging_token == "charging-token-001"
        return {
            "chargingStationId": "OK-CHARGER-001",
            "kWh": 11300,
            "chargingStart": "2025-06-05T10:00:00+00:00",
            "chargingEnd": "2025-06-05T12:00:00+00:00",
            "totalPriceInOere": 1900,
            "noPriceReason": None,
        }

    async def watch_charging_station_status(self, charging_station_id, connector_id):
        self.station_watch_attempts += 1
        if self.station_watch_configuration_error:
            raise OkConfigurationError("missing firestore credentials")
        if self.station_watch_attempts <= self.station_watch_failures:
            raise RuntimeError("watch failed")
        subscription = FakeSubscription()
        self.subscriptions.append(subscription)
        self.station_watch_callbacks[(charging_station_id, connector_id)] = subscription.emit
        return subscription

    async def watch_charging_status(self, charging_token):
        subscription = FakeSubscription()
        self.subscriptions.append(subscription)
        self.charging_watch_callbacks[charging_token] = subscription.emit
        return subscription


async def _async_load_device_registry(hass: HomeAssistant) -> None:
    await _async_get_device_registry(hass)


def test_device_registry_helper_loads_ha_2026_setup_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_test_device_registry_helper_loads_ha_2026_setup_registry(tmp_path, monkeypatch))


async def _test_device_registry_helper_loads_ha_2026_setup_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDeviceRegistry:
        devices: dict[str, object]
        load_empty: bool | None = None
        waited = False

        async def async_load(self, *, load_empty: bool = False) -> None:
            self.load_empty = load_empty
            self.devices = {}

        async def async_wait_loaded(self) -> None:
            self.waited = True

    registry = FakeDeviceRegistry()
    hass = HomeAssistant(str(tmp_path))

    def async_setup(fake_hass: HomeAssistant) -> None:
        fake_hass.data["fake_device_registry"] = registry

    def async_get(fake_hass: HomeAssistant) -> FakeDeviceRegistry:
        return fake_hass.data["fake_device_registry"]

    monkeypatch.setattr(dr, "DATA_REGISTRY", "fake_device_registry")
    monkeypatch.setattr(dr, "async_setup", async_setup, raising=False)
    monkeypatch.setattr(dr, "async_get", async_get)

    try:
        assert await _async_get_device_registry(hass) is registry
        assert registry.load_empty is True
        assert registry.waited is True
    finally:
        await hass.async_stop()


def test_coordinator_collects_ok_api_shaped_data(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_collects_ok_api_shaped_data(tmp_path))


async def _test_coordinator_collects_ok_api_shaped_data(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        assert len(coordinator.data.locations) == 1
        assert len(coordinator.connectors()) == 1
        assert coordinator.prices_for("OK-CHARGER-001")["productName"] == "OK El Flex"
        assert coordinator.station_status_for("OK-CHARGER-001", 1).fields["status"] == "Charging"
        active = coordinator.active_charging_for("OK-CHARGER-001", 1)
        assert active["chargingToken"] == "charging-token-001"
        assert coordinator.charging_status_for(active).fields["powerInW"] == 3522
        assert coordinator.last_receipt_for("OK-CHARGER-001")["totalPriceInOere"] == 1767
        assert ("OK-CHARGER-001", 1) in client.station_watch_callbacks
        assert "charging-token-001" in client.charging_watch_callbacks
    finally:
        await hass.async_stop()


def test_coordinator_skips_malformed_connectors(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_skips_malformed_connectors(tmp_path))


async def _test_coordinator_skips_malformed_connectors(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    client.locations_response = [
        {
            "chargingStations": [
                {"csIdentifier": 123, "connectors": [{"connectorId": 1}]},
                {"csIdentifier": "BAD-STRING", "connectors": [{"connectorId": "bad"}]},
                {"csIdentifier": "BAD-BOOL", "connectors": [{"connectorId": True}]},
                {"csIdentifier": "MISSING-CONNECTORS"},
            ]
        },
        {"chargingStations": ["bad-station"]},
    ]
    client.current_chargings_response = []
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.connectors() == ()
        assert client.price_calls == 0
        assert client.station_status_calls == 0
    finally:
        await hass.async_stop()


def test_coordinator_logs_api_outage_once_and_recovery(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    asyncio.run(_test_coordinator_logs_api_outage_once_and_recovery(tmp_path, caplog))


async def _test_coordinator_logs_api_outage_once_and_recovery(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    client.get_stations_error = OkConnectionError("network down")
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        caplog.set_level(logging.INFO, logger="custom_components.ok.coordinator")

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

        assert caplog.messages.count("OK API became unavailable: network down") == 1

        client.get_stations_error = None
        await coordinator._async_update_data()

        assert "OK API became available again" in caplog.messages
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_removes_stale_ok_devices(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_removes_stale_ok_devices(tmp_path))


async def _test_coordinator_removes_stale_ok_devices(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _config_entry()
    hass.config_entries = ConfigEntries(hass, {})
    hass.config_entries._entries[entry.entry_id] = entry
    await _async_load_device_registry(hass)
    device_registry = dr.async_get(hass)
    current_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "OK-CHARGER-001")},
        name="Home Charger",
    )
    account_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "account_1000001")},
        translation_key="account",
    )
    stale_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "STALE-CHARGER")},
        name="Old Charger",
    )
    other_domain_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("other", "STALE-CHARGER")},
        name="Other Device",
    )

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator._async_update_data()

        assert device_registry.async_get(current_device.id) is not None
        assert device_registry.async_get(account_device.id) is not None
        assert device_registry.async_get(stale_device.id) is not None
        assert device_registry.async_get(other_domain_device.id) is not None

        await coordinator._async_update_data()

        assert device_registry.async_get(current_device.id) is not None
        assert device_registry.async_get(account_device.id) is not None
        assert device_registry.async_get(stale_device.id) is not None
        assert device_registry.async_get(other_domain_device.id) is not None

        await coordinator._async_update_data()

        assert device_registry.async_get(current_device.id) is not None
        assert device_registry.async_get(account_device.id) is not None
        assert device_registry.async_get(stale_device.id) is None
        assert device_registry.async_get(other_domain_device.id) is not None
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_keeps_devices_when_charger_list_is_empty(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_keeps_devices_when_charger_list_is_empty(tmp_path))


async def _test_coordinator_keeps_devices_when_charger_list_is_empty(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    client.locations_response = []
    entry = _config_entry()
    hass.config_entries = ConfigEntries(hass, {})
    hass.config_entries._entries[entry.entry_id] = entry
    await _async_load_device_registry(hass)
    device_registry = dr.async_get(hass)
    existing_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "OK-CHARGER-001")},
        name="Home Charger",
    )

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        for _ in range(3):
            await coordinator._async_update_data()

        assert device_registry.async_get(existing_device.id) is not None
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_skips_receipts_when_option_is_disabled(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_skips_receipts_when_option_is_disabled(tmp_path))


async def _test_coordinator_skips_receipts_when_option_is_disabled(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()
    entry.options = {CONF_INCLUDE_RECEIPTS: False}

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        assert coordinator.data.receipts == ()
        assert coordinator.last_receipt_for("OK-CHARGER-001") is None
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_skips_energy_prices_when_option_is_disabled(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_skips_energy_prices_when_option_is_disabled(tmp_path))


async def _test_coordinator_skips_energy_prices_when_option_is_disabled(
    tmp_path: Path,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()
    entry.options = {CONF_ENABLE_ENERGY_PRICES: False}

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        assert coordinator.data.prices == {}
        assert coordinator.prices_for("OK-CHARGER-001") is None
        assert client.price_calls == 0

        await coordinator.async_force_full_refresh()

        assert client.price_calls == 0
        assert coordinator.poll_attributes["energy_prices"] is None
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_polls_status_snapshots_when_realtime_option_is_disabled(
    tmp_path: Path,
) -> None:
    asyncio.run(_test_coordinator_polls_status_snapshots_when_realtime_option_is_disabled(tmp_path))


async def _test_coordinator_polls_status_snapshots_when_realtime_option_is_disabled(
    tmp_path: Path,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()
    entry.options = {CONF_ENABLE_REALTIME_UPDATES: False}

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        assert client.station_status_calls == 1
        assert client.charging_status_calls == 1
        assert client.station_watch_attempts == 0
        assert client.station_watch_callbacks == {}
        assert client.charging_watch_callbacks == {}
        assert coordinator.station_status_for("OK-CHARGER-001", 1).fields["status"] == "Charging"

        client.station_status = "Available"
        client.station_status_updated = "2025-06-09T12:30:00Z"
        client.connector_session_power_w = 7200
        client.charging_status_updated = "2025-06-05T12:11:12.702511Z"
        await coordinator.async_request_refresh()

        assert client.station_status_calls == 2
        assert client.charging_status_calls == 2
        assert coordinator.station_status_for("OK-CHARGER-001", 1).fields["status"] == "Available"
        active = coordinator.active_charging_for("OK-CHARGER-001", 1)
        assert coordinator.charging_status_for(active).fields["powerInW"] == 7200
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_accessors_handle_missing_data(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_accessors_handle_missing_data(tmp_path))


async def _test_coordinator_accessors_handle_missing_data(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    coordinator = OkDataUpdateCoordinator(hass, _entry(), FakeOkClient())

    try:
        assert coordinator.last_refresh is None
        assert coordinator.charger_last_refresh("station") is None
        assert coordinator.charger_poll_attributes("station") == {
            "charger_status": {},
            "session_status": {},
            "session_receipt": None,
        }
        assert coordinator.poll_attributes == {
            "account_settings": None,
            "charger_overview": None,
            "energy_prices": None,
            "active_sessions": None,
            "charging_receipts": None,
            "trigger": None,
            "in_progress": False,
        }
        assert coordinator.connectors() == ()
        assert coordinator.station_status_for("station", 1) is None
        assert coordinator.active_charging_for("station", 1) is None
        assert coordinator.charging_status_for(None) is None
        assert coordinator.prices_for("station") is None
        assert coordinator.last_receipt_for("station") is None

        coordinator.async_set_updated_data(
            OkData(
                settings=None,
                locations=(),
                current_chargings=(
                    {"csIdentifier": "other", "connectorId": 1},
                    {"csIdentifier": "station", "connectorId": 1, "chargingToken": 5},
                ),
            )
        )

        charging = coordinator.active_charging_for("station", 1)
        assert charging == {"csIdentifier": "station", "connectorId": 1, "chargingToken": 5}
        assert coordinator.active_charging_for("missing", 1) is None
        assert coordinator.charging_status_for(charging) is None
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_backs_off_optional_rate_limited_prices(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_backs_off_optional_rate_limited_prices(tmp_path))


async def _test_coordinator_backs_off_optional_rate_limited_prices(tmp_path: Path) -> None:
    class RateLimitedPricesClient(FakeOkClient):
        async def get_station_prices(self, charging_station_id: str) -> dict[str, Any]:
            self.price_calls += 1
            raise OkRateLimitError(
                "slow down",
                status_code=429,
                headers={"Retry-After": "60"},
                payload={},
            )

    hass = HomeAssistant(str(tmp_path))
    client = RateLimitedPricesClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.prices_for("OK-CHARGER-001") is None
        assert coordinator.next_price_update_for("OK-CHARGER-001") is None
        assert client.price_calls == 1

        await coordinator.async_request_refresh()

        assert client.price_calls == 1

        coordinator._endpoint_backoff_until[_price_source("OK-CHARGER-001")] = 0
        await coordinator.async_force_full_refresh()

        assert client.price_calls == 2
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_applies_realtime_firestore_events(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_applies_realtime_firestore_events(tmp_path))


async def _test_coordinator_applies_realtime_firestore_events(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        client.station_status = "Available"
        client.station_watch_callbacks[("OK-CHARGER-001", 1)](
            FirestoreWatchEvent(
                document=FirestoreDocument(
                    name=("documents/OK/Emsp/ChargingStations/Status/Connectors/OK-CHARGER-001__1"),
                    fields={
                        "status": "Available",
                        "chargingStationId": "OK-CHARGER-001",
                        "connectorId": 1,
                        "statusUpdated": "2025-06-09T12:30:00Z",
                    },
                    create_time="2023-09-15T09:39:51.473916Z",
                    update_time="2025-06-09T12:30:01.000000Z",
                    raw={},
                ),
                exists=True,
            )
        )
        await hass.async_block_till_done()

        assert coordinator.station_status_for("OK-CHARGER-001", 1).fields["status"] == "Available"

        client.connector_session_power_w = 7200
        client.charging_watch_callbacks["charging-token-001"](
            FirestoreWatchEvent(
                document=FirestoreDocument(
                    name=("documents/OK/Emsp/RemoteTransactions/charging-token-001"),
                    fields={
                        "status": "Charging",
                        "powerInW": 7200,
                        "chargeInWh": 6000,
                        "scheduledStart": "2025-06-05T10:30:00Z",
                        "scheduledEnd": "2025-06-05T13:00:00Z",
                    },
                    create_time="2025-06-04T23:04:23.378539Z",
                    update_time="2025-06-05T12:11:12.702511Z",
                    raw={},
                ),
                exists=True,
            )
        )
        await hass.async_block_till_done()

        active = coordinator.active_charging_for("OK-CHARGER-001", 1)
        assert coordinator.charging_status_for(active).fields["powerInW"] == 7200

        await coordinator.async_close_realtime_watches()
        assert all(subscription.unsubscribed for subscription in client.subscriptions)
    finally:
        await hass.async_stop()


def test_coordinator_does_not_poll_realtime_status_after_snapshot_seed(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_does_not_poll_realtime_status_after_snapshot_seed(tmp_path))


async def _test_coordinator_does_not_poll_realtime_status_after_snapshot_seed(
    tmp_path: Path,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        assert client.station_status_calls == 1
        assert client.charging_status_calls == 1

        await coordinator.async_request_refresh()

        assert client.station_status_calls == 1
        assert client.charging_status_calls == 1
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_uses_endpoint_specific_refresh_cadence(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_uses_endpoint_specific_refresh_cadence(tmp_path))


async def _test_coordinator_uses_endpoint_specific_refresh_cadence(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        assert client.station_calls == 1
        assert client.price_calls == 1
        assert client.chargings_calls == 1
        assert client.receipts_calls == 1

        await coordinator.async_request_refresh()

        assert client.station_calls == 1
        assert client.price_calls == 1
        assert client.chargings_calls == 1
        assert client.receipts_calls == 1

        await coordinator.async_request_operational_refresh()

        assert client.station_calls == 1
        assert client.price_calls == 1
        assert client.chargings_calls == 2
        assert client.receipts_calls == 1

        await coordinator.async_request_station_refresh()

        assert client.station_calls == 2
        assert client.price_calls == 1
        assert client.chargings_calls == 2
        assert client.receipts_calls == 1
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_force_full_refresh_polls_all_sources(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_force_full_refresh_polls_all_sources(tmp_path))


async def _test_coordinator_force_full_refresh_polls_all_sources(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        await coordinator.async_force_full_refresh()

        assert client.station_calls == 2
        assert client.price_calls == 2
        assert client.chargings_calls == 2
        assert client.receipts_calls == 2
        assert client.station_status_calls == 2
        assert client.charging_status_calls == 2

        await coordinator.async_request_refresh()

        assert client.station_calls == 2
        assert client.price_calls == 2
        assert client.chargings_calls == 2
        assert client.receipts_calls == 2
        assert client.station_status_calls == 2
        assert client.charging_status_calls == 2
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_exposes_api_refresh_metadata(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_exposes_api_refresh_metadata(tmp_path))


async def _test_coordinator_exposes_api_refresh_metadata(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        attrs = coordinator.poll_attributes
        assert coordinator.last_refresh is not None
        assert set(attrs) == {
            "account_settings",
            "charger_overview",
            "energy_prices",
            "active_sessions",
            "charging_receipts",
            "trigger",
            "in_progress",
        }
        assert attrs["trigger"] == "setup"
        assert attrs["in_progress"] is False
        for attribute in (
            "account_settings",
            "charger_overview",
            "energy_prices",
            "active_sessions",
            "charging_receipts",
        ):
            assert isinstance(attrs[attribute], str)
        assert coordinator.charger_last_refresh("OK-CHARGER-001") is not None
        charger_attrs = coordinator.charger_poll_attributes("OK-CHARGER-001")
        assert isinstance(charger_attrs["charger_status"], str)
        assert isinstance(charger_attrs["session_status"], str)
        assert charger_attrs["session_receipt"] is None
        assert set(charger_attrs) == {"charger_status", "session_status", "session_receipt"}

        client.current_chargings_response = []
        await coordinator.async_request_operational_refresh()

        charger_attrs = coordinator.charger_poll_attributes("OK-CHARGER-001")
        assert isinstance(charger_attrs["session_receipt"], str)
        assert coordinator.poll_attributes["trigger"] == "service_action"

        await coordinator.async_force_full_refresh()

        assert coordinator.poll_attributes["trigger"] == "manual"

        assert coordinator.data is not None
        coordinator.data = replace(
            coordinator.data,
            locations=(
                {
                    "chargingStations": [
                        {
                            "csIdentifier": "OK-CHARGER-001",
                            "connectors": [{"connectorId": 1}, {"connectorId": 2}],
                        }
                    ]
                },
            ),
        )
        multi_connector_attrs = coordinator.charger_poll_attributes("OK-CHARGER-001")
        assert set(multi_connector_attrs) == {
            "charger_status",
            "session_status",
            "session_receipt",
        }
        assert isinstance(multi_connector_attrs["charger_status"], dict)
        assert isinstance(multi_connector_attrs["charger_status"]["1"], str)
        assert multi_connector_attrs["charger_status"]["2"] is None
        assert isinstance(multi_connector_attrs["session_status"], dict)
        assert isinstance(multi_connector_attrs["session_status"]["1"], str)
        assert multi_connector_attrs["session_status"]["2"] is None
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_serializes_refreshes_and_reports_progress(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_serializes_refreshes_and_reports_progress(tmp_path))


async def _test_coordinator_serializes_refreshes_and_reports_progress(tmp_path: Path) -> None:
    class SlowStationsClient(FakeOkClient):
        def __init__(self) -> None:
            super().__init__()
            self.active_station_calls = 0
            self.max_active_station_calls = 0
            self.station_call_started = asyncio.Event()
            self.release_station_call = asyncio.Event()

        async def get_stations(self) -> list[dict[str, Any]]:
            self.active_station_calls += 1
            self.max_active_station_calls = max(
                self.max_active_station_calls,
                self.active_station_calls,
            )
            self.station_call_started.set()
            await self.release_station_call.wait()
            try:
                return await super().get_stations()
            finally:
                self.active_station_calls -= 1

    hass = HomeAssistant(str(tmp_path))
    client = SlowStationsClient()
    entry = _entry()
    coordinator = OkDataUpdateCoordinator(hass, entry, client)
    refresh_states: list[bool] = []
    remove_listener = coordinator.async_add_listener(
        lambda: refresh_states.append(coordinator.refresh_in_progress)
    )

    try:
        first_refresh = asyncio.create_task(coordinator._async_update_data())
        await asyncio.wait_for(client.station_call_started.wait(), timeout=1)
        second_refresh = asyncio.create_task(coordinator._async_update_data())
        await asyncio.sleep(0)

        assert coordinator.refresh_in_progress is True
        assert refresh_states[0] is True
        assert client.max_active_station_calls == 1

        client.release_station_call.set()
        await asyncio.gather(first_refresh, second_refresh)

        assert client.max_active_station_calls == 1
        assert coordinator.refresh_in_progress is False
        assert refresh_states[-1] is False
    finally:
        remove_listener()
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_fetches_quick_receipt_for_known_finished_session(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_fetches_quick_receipt_for_known_finished_session(tmp_path))


async def _test_coordinator_fetches_quick_receipt_for_known_finished_session(
    tmp_path: Path,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        client.current_chargings_response = []
        await coordinator.async_request_operational_refresh()

        assert client.receipts_calls == 1
        assert client.quick_receipt_calls == ["charging-token-001"]
        receipt = coordinator.last_receipt_for("OK-CHARGER-001")
        assert receipt is not None
        assert receipt["kWh"] == 11.3
        assert receipt["totalPriceInOere"] == 1900

        await coordinator.async_request_operational_refresh()

        assert client.quick_receipt_calls == ["charging-token-001"]
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_polls_realtime_status_when_realtime_is_unavailable(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_polls_realtime_status_when_realtime_is_unavailable(tmp_path))


async def _test_coordinator_polls_realtime_status_when_realtime_is_unavailable(
    tmp_path: Path,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    client.station_watch_configuration_error = True
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator._realtime_watches_unavailable is True
        assert client.station_status_calls == 1
        assert client.charging_status_calls == 1

        await coordinator.async_request_refresh()

        assert client.station_status_calls == 2
        assert client.charging_status_calls == 2
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_keeps_newer_realtime_status_during_refresh(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_keeps_newer_realtime_status_during_refresh(tmp_path))


async def _test_coordinator_keeps_newer_realtime_status_during_refresh(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        client.station_watch_callbacks[("OK-CHARGER-001", 1)](
            FirestoreWatchEvent(
                document=FirestoreDocument(
                    name=("documents/OK/Emsp/ChargingStations/Status/Connectors/OK-CHARGER-001__1"),
                    fields={
                        "status": "Available",
                        "chargingStationId": "OK-CHARGER-001",
                        "connectorId": 1,
                        "statusUpdated": "2025-06-09T12:30:00Z",
                    },
                    create_time="2023-09-15T09:39:51.473916Z",
                    update_time="2025-06-09T12:30:01.000000Z",
                    raw={},
                ),
                exists=True,
            )
        )
        await hass.async_block_till_done()

        client.station_status = "Charging"
        client.station_status_updated = "2025-06-09T12:24:11Z"
        await coordinator.async_request_refresh()

        assert coordinator.station_status_for("OK-CHARGER-001", 1).fields["status"] == "Available"

        client.station_watch_callbacks[("OK-CHARGER-001", 1)](
            FirestoreWatchEvent(document=None, exists=False)
        )
        await hass.async_block_till_done()

        assert coordinator.station_status_for("OK-CHARGER-001", 1).fields["status"] == "Available"
        await coordinator.async_close_realtime_watches()
    finally:
        await hass.async_stop()


def test_coordinator_retries_failed_realtime_watch(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    asyncio.run(_test_coordinator_retries_failed_realtime_watch(tmp_path, caplog))


async def _test_coordinator_retries_failed_realtime_watch(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    client.station_watch_failures = 2
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        caplog.set_level(logging.INFO, logger="custom_components.ok.coordinator")
        await coordinator.async_config_entry_first_refresh()

        assert client.station_watch_attempts == 1
        assert ("OK-CHARGER-001", 1) not in client.station_watch_callbacks
        assert coordinator._realtime_watch_failures
        assert (
            caplog.messages.count(
                "OK Firestore realtime watcher for charger connector 1 became unavailable: "
                "watch failed. Retrying in 15 seconds"
            )
            == 1
        )
        retry_handle = coordinator._realtime_retry_handle
        assert retry_handle is not None
        coordinator._schedule_realtime_watch_retry(retry_handle.when() + 60)
        assert coordinator._realtime_retry_handle is retry_handle
        coordinator._cancel_realtime_retry()
        assert retry_handle.cancelled()

        failures = coordinator._realtime_watch_failures
        for key, failure in tuple(failures.items()):
            failures[key] = type(failure)(attempts=failure.attempts, retry_at=0)

        assert coordinator.data is not None
        await coordinator._async_sync_realtime_watches(coordinator.data)

        assert client.station_watch_attempts == 2
        assert ("OK-CHARGER-001", 1) not in client.station_watch_callbacks
        assert (
            caplog.messages.count(
                "OK Firestore realtime watcher for charger connector 1 became unavailable: "
                "watch failed. Retrying in 15 seconds"
            )
            == 1
        )
        assert coordinator._realtime_watch_failures

        failures = coordinator._realtime_watch_failures
        for key, failure in tuple(failures.items()):
            failures[key] = type(failure)(attempts=failure.attempts, retry_at=0)

        assert coordinator.data is not None
        await coordinator._async_sync_realtime_watches(coordinator.data)

        assert client.station_watch_attempts == 3
        assert ("OK-CHARGER-001", 1) in client.station_watch_callbacks
        assert not coordinator._realtime_watch_failures
        assert "OK Firestore realtime watcher for charger connector 1 recovered" in caplog.messages
        await coordinator.async_close_realtime_watches()
    finally:
        await hass.async_stop()


def test_coordinator_realtime_handler_edges(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_realtime_handler_edges(tmp_path))


async def _test_coordinator_realtime_handler_edges(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()

    try:
        empty_coordinator = OkDataUpdateCoordinator(hass, entry, client)
        empty_coordinator._handle_station_status_event(
            "OK-CHARGER-001",
            1,
            FirestoreWatchEvent(document=None, exists=False),
        )
        empty_coordinator._handle_charging_status_event(
            "charging-token-001",
            FirestoreWatchEvent(document=None, exists=False),
        )

        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()
        assert coordinator.data is not None

        previous_station = coordinator.station_status_for("OK-CHARGER-001", 1)
        assert previous_station is not None
        coordinator._handle_station_status_event(
            "OK-CHARGER-001",
            1,
            FirestoreWatchEvent(
                document=FirestoreDocument(
                    name=previous_station.name,
                    fields={"status": "Available", "statusUpdated": "2025-06-09T12:00:00Z"},
                    create_time=previous_station.create_time,
                    update_time="2025-06-09T12:00:00Z",
                    raw={},
                ),
                exists=True,
            ),
        )
        assert coordinator.station_status_for("OK-CHARGER-001", 1) is previous_station

        previous_charging = coordinator.charging_status_for(
            coordinator.active_charging_for("OK-CHARGER-001", 1)
        )
        assert previous_charging is not None
        coordinator._handle_charging_status_event(
            "charging-token-001",
            FirestoreWatchEvent(
                document=FirestoreDocument(
                    name=previous_charging.name,
                    fields={"status": "Charging", "powerInW": 1},
                    create_time=previous_charging.create_time,
                    update_time="2025-06-05T12:00:00Z",
                    raw={},
                ),
                exists=True,
            ),
        )
        assert (
            coordinator.charging_status_for(coordinator.active_charging_for("OK-CHARGER-001", 1))
            is previous_charging
        )

        coordinator._handle_charging_status_event(
            "charging-token-001",
            FirestoreWatchEvent(document=None, exists=False),
        )
        assert coordinator._realtime_refresh_handle is not None
        coordinator._cancel_realtime_refresh()
        assert coordinator._realtime_refresh_handle is None

        coordinator._realtime_watches_unavailable = True
        await coordinator._async_sync_realtime_watches(coordinator.data)
        await coordinator._async_subscribe_realtime_watch(("station", "OK-CHARGER-001", 1))
    finally:
        await empty_coordinator.async_close_realtime_watches()
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_removes_stale_realtime_watches(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_removes_stale_realtime_watches(tmp_path))


async def _test_coordinator_removes_stale_realtime_watches(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        charging_subscription = coordinator._realtime_watch_handles[
            ("charging", "charging-token-001")
        ].subscription
        station_subscription = coordinator._realtime_watch_handles[
            ("station", "OK-CHARGER-001", 1)
        ].subscription

        await coordinator._async_sync_realtime_watches(
            replace(coordinator.data, current_chargings=(), charging_status={})
        )

        assert charging_subscription.unsubscribed is True
        assert charging_subscription.unsubscribe_count == 1
        assert station_subscription.unsubscribed is False
        assert ("charging", "charging-token-001") not in coordinator._realtime_watch_handles
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_reports_unavailable_realtime_watch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    asyncio.run(_test_coordinator_reports_unavailable_realtime_watch(tmp_path, monkeypatch))


async def _test_coordinator_reports_unavailable_realtime_watch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from homeassistant.helpers import issue_registry as ir

    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    client.station_watch_configuration_error = True
    entry = _entry()
    created_issues: list[dict[str, Any]] = []

    def create_issue(hass_arg, domain, issue_id, **kwargs):
        created_issues.append(
            {
                "hass": hass_arg,
                "domain": domain,
                "issue_id": issue_id,
                **kwargs,
            }
        )

    monkeypatch.setattr(ir, "async_create_issue", create_issue)

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator._realtime_watches_unavailable is True
        assert coordinator._realtime_watch_handles == {}
        assert client.charging_watch_callbacks == {}
        assert created_issues[0]["domain"] == DOMAIN
        assert created_issues[0]["issue_id"] == "realtime_updates_unavailable_test"
        assert created_issues[0]["is_fixable"] is False
        assert created_issues[0]["translation_placeholders"] == {
            "reason": "missing firestore credentials"
        }
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_close_cancels_pending_realtime_refresh(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_close_cancels_pending_realtime_refresh(tmp_path))


def test_coordinator_sync_close_schedules_realtime_subscription_close(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_sync_close_schedules_realtime_subscription_close(tmp_path))


async def _test_coordinator_sync_close_schedules_realtime_subscription_close(
    tmp_path: Path,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    coordinator = OkDataUpdateCoordinator(hass, _entry(), FakeOkClient())
    subscription = FakeSubscription()
    task = asyncio.create_task(asyncio.sleep(60))
    coordinator._realtime_watch_handles[("station", "OK-CHARGER-001", 1)] = _RealtimeWatchHandle(
        key=("station", "OK-CHARGER-001", 1),
        subscription=subscription,
        task=task,
    )

    try:
        coordinator.close_realtime_watches()
        await hass.async_block_till_done()
        await asyncio.gather(task, return_exceptions=True)

        assert coordinator._realtime_watch_handles == {}
        assert coordinator._realtime_watch_failures == {}
        assert task.cancelled()
        assert subscription.unsubscribed is True
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


async def _test_coordinator_close_cancels_pending_realtime_refresh(tmp_path: Path) -> None:
    class SlowRefreshClient(FakeOkClient):
        def __init__(self) -> None:
            super().__init__()
            self.stations_started = asyncio.Event()
            self.release_stations = asyncio.Event()

        async def get_stations(self) -> list[dict[str, Any]]:
            self.stations_started.set()
            await self.release_stations.wait()
            return await super().get_stations()

    hass = HomeAssistant(str(tmp_path))
    client = SlowRefreshClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        coordinator._create_realtime_refresh_task("test")

        await asyncio.wait_for(client.stations_started.wait(), timeout=1)
        await coordinator.async_close_realtime_watches()
        client.release_stations.set()
        await hass.async_block_till_done()

        assert coordinator._realtime_refresh_task is None
        assert coordinator._realtime_watch_handles == {}
        assert client.subscriptions == []
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_closes_subscription_created_during_shutdown(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_closes_subscription_created_during_shutdown(tmp_path))


async def _test_coordinator_closes_subscription_created_during_shutdown(tmp_path: Path) -> None:
    class SlowWatchClient(FakeOkClient):
        def __init__(self) -> None:
            super().__init__()
            self.watch_started = asyncio.Event()
            self.release_watch = asyncio.Event()

        async def watch_charging_station_status(
            self,
            charging_station_id: str,
            connector_id: int,
        ) -> FakeSubscription:
            self.watch_started.set()
            await self.release_watch.wait()
            subscription = FakeSubscription()
            self.subscriptions.append(subscription)
            return subscription

    hass = HomeAssistant(str(tmp_path))
    client = SlowWatchClient()
    entry = _entry()

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        subscribe_task = asyncio.create_task(
            coordinator._async_subscribe_realtime_watch(("station", "OK-CHARGER-001", 1))
        )

        await asyncio.wait_for(client.watch_started.wait(), timeout=1)
        await coordinator.async_close_realtime_watches()
        client.release_watch.set()
        await subscribe_task

        assert coordinator._realtime_watch_handles == {}
        assert len(client.subscriptions) == 1
        assert client.subscriptions[0].unsubscribed is True
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_logs_late_subscription_close_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    asyncio.run(_test_coordinator_logs_late_subscription_close_failure(tmp_path, caplog))


async def _test_coordinator_logs_late_subscription_close_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingCloseSubscription(FakeSubscription):
        async def aclose(self) -> None:
            raise RuntimeError("late close failed")

    class SlowWatchClient(FakeOkClient):
        def __init__(self) -> None:
            super().__init__()
            self.watch_started = asyncio.Event()
            self.release_watch = asyncio.Event()

        async def watch_charging_station_status(
            self,
            charging_station_id: str,
            connector_id: int,
        ) -> FakeSubscription:
            self.watch_started.set()
            await self.release_watch.wait()
            subscription = FailingCloseSubscription()
            self.subscriptions.append(subscription)
            return subscription

    hass = HomeAssistant(str(tmp_path))
    client = SlowWatchClient()
    entry = _entry()
    caplog.set_level(logging.WARNING, logger="custom_components.ok.coordinator")

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        subscribe_task = asyncio.create_task(
            coordinator._async_subscribe_realtime_watch(("station", "OK-CHARGER-001", 1))
        )

        await asyncio.wait_for(client.watch_started.wait(), timeout=1)
        await coordinator.async_close_realtime_watches()
        client.release_watch.set()
        await subscribe_task

        assert "Failed to close OK Firestore realtime watcher for charger connector 1" in (
            caplog.text
        )
        assert coordinator._realtime_watch_handles == {}
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_realtime_config_error_during_refresh_does_not_self_cancel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(
        _test_coordinator_realtime_config_error_during_refresh_does_not_self_cancel(
            tmp_path,
            monkeypatch,
        )
    )


async def _test_coordinator_realtime_config_error_during_refresh_does_not_self_cancel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from homeassistant.helpers import issue_registry as ir

    hass = HomeAssistant(str(tmp_path))
    client = FakeOkClient()
    client.station_watch_configuration_error = True
    entry = _entry()
    created_issues: list[str] = []

    def create_issue(hass_arg, domain, issue_id, **kwargs):
        created_issues.append(issue_id)

    monkeypatch.setattr(ir, "async_create_issue", create_issue)

    try:
        coordinator = OkDataUpdateCoordinator(hass, entry, client)
        current = asyncio.current_task()
        assert current is not None
        coordinator._realtime_refresh_task = current

        await coordinator._async_subscribe_realtime_watch(("station", "OK-CHARGER-001", 1))

        assert coordinator._realtime_refresh_task is None
        assert coordinator._realtime_watches_unavailable is True
        assert coordinator._realtime_watch_handles == {}
        assert created_issues == ["realtime_updates_unavailable_test"]
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_retries_when_realtime_consumer_fails(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_retries_when_realtime_consumer_fails(tmp_path))


async def _test_coordinator_retries_when_realtime_consumer_fails(tmp_path: Path) -> None:
    class FailingSubscription:
        closed = False

        def __aiter__(self) -> FailingSubscription:
            return self

        async def __anext__(self) -> FirestoreWatchEvent:
            raise RuntimeError("stream failed")

        async def aclose(self) -> None:
            self.closed = True

    hass = HomeAssistant(str(tmp_path))
    coordinator = OkDataUpdateCoordinator(hass, _entry(), FakeOkClient())
    key = ("charging", "charging-token-001")
    placeholder_task = asyncio.create_task(asyncio.sleep(0))
    subscription = FailingSubscription()
    coordinator._realtime_watch_handles[key] = _RealtimeWatchHandle(
        key=key,
        subscription=subscription,
        task=placeholder_task,
    )

    try:
        await coordinator._async_consume_realtime_watch(key, subscription)

        assert key not in coordinator._realtime_watch_handles
        assert subscription.closed is True
        assert coordinator._realtime_watch_failures[key].attempts == 1
        assert coordinator._realtime_retry_handle is not None
    finally:
        coordinator._cancel_realtime_retry()
        placeholder_task.cancel()
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def test_coordinator_logs_realtime_watch_close_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    asyncio.run(_test_coordinator_logs_realtime_watch_close_failure(tmp_path, caplog))


async def _test_coordinator_logs_realtime_watch_close_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingCloseSubscription:
        async def aclose(self) -> None:
            raise RuntimeError("close failed")

    hass = HomeAssistant(str(tmp_path))
    coordinator = OkDataUpdateCoordinator(hass, _entry(), FakeOkClient())
    task = asyncio.create_task(asyncio.sleep(0))
    handle = _RealtimeWatchHandle(
        key=("station", "OK-CHARGER-001", 1),
        subscription=FailingCloseSubscription(),
        task=task,
    )
    caplog.set_level(logging.WARNING, logger="custom_components.ok.coordinator")

    try:
        await coordinator._async_close_realtime_watch_handles((handle,))

        assert "Failed to close OK Firestore realtime watcher for charger connector 1" in (
            caplog.text
        )
    finally:
        await coordinator.async_close_realtime_watches()
        await hass.async_stop()


def _entry() -> SimpleNamespace:
    return SimpleNamespace(
        async_on_unload=lambda callback: None,
        domain=DOMAIN,
        data={CONF_EMAIL: "user@example.test"},
        entry_id="test",
        options={},
        pref_disable_polling=False,
        state=config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
        unique_id="1000001",
    )


def _config_entry() -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="OK",
        unique_id="1000001",
        data={CONF_EMAIL: "user@example.test"},
        options={},
        source=config_entries.SOURCE_USER,
        discovery_keys=MappingProxyType({}),
        subentries_data=(),
    )
