from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from custom_components.ok.api import (
    FirestoreDocument,
    OkAuthenticationError,
    OkRateLimitError,
    OkStatusError,
)
from custom_components.ok.const import DOMAIN
from custom_components.ok.coordinator import (
    OkData,
    OkDataUpdateCoordinator,
    _charging_connector_key,
    _charging_status_token,
    _document_status,
    _document_version,
    _finished_chargings,
    _merge_receipt,
    _nanoseconds_field,
    _parse_datetime,
    _realtime_watch_key_sort,
    _realtime_watch_keys,
    _realtime_watch_label,
    _receipt_identity,
    _retry_after,
    _single_connector_refresh_value,
    _timestamp_value,
)
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed


def test_coordinator_api_error_mapping_and_retry_after(tmp_path: Path) -> None:
    asyncio.run(_test_coordinator_api_error_mapping_and_retry_after(tmp_path))


async def _test_coordinator_api_error_mapping_and_retry_after(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    coordinator = OkDataUpdateCoordinator(hass, _entry(), SimpleNamespace())

    async def auth_error() -> None:
        raise OkAuthenticationError("bad auth", status_code=401, headers={}, payload={})

    async def rate_limit_without_header() -> None:
        raise OkRateLimitError("slow down", status_code=429, headers={}, payload={})

    async def rate_limit_with_header() -> None:
        raise OkRateLimitError(
            "slow down",
            status_code=429,
            headers={"Retry-After": "5"},
            payload={},
        )

    async def status_error() -> None:
        raise OkStatusError("server down", status_code=503, headers={}, payload={})

    async def optional_auth_error() -> None:
        raise OkAuthenticationError("bad auth", status_code=401, headers={}, payload={})

    async def optional_status_error() -> None:
        raise OkStatusError("server down", status_code=503, headers={}, payload={})

    try:
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._call_api(auth_error())
        with pytest.raises(UpdateFailed):
            await coordinator._call_api(rate_limit_without_header())
        with pytest.raises(UpdateFailed):
            await coordinator._call_api(rate_limit_with_header())
        with pytest.raises(UpdateFailed):
            await coordinator._call_api(status_error())
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._call_optional_api("optional", optional_auth_error, 0)
        assert await coordinator._call_optional_api("optional", optional_status_error, 0) is None
    finally:
        await hass.async_stop()


def test_coordinator_helper_edges() -> None:
    current = FirestoreDocument(
        "current", {"statusUpdated": "2026-01-01T00:00:00Z"}, None, None, {}
    )
    event_time = FirestoreDocument("event", {"statusEventTime": "42"}, None, None, {})
    no_time = FirestoreDocument("none", {"status": 1}, None, None, {})
    locations = (
        {
            "chargingStations": [
                {"csIdentifier": "charger", "connectors": [{"connectorId": 2}]},
                {"csIdentifier": "bad", "connectors": [{"connectorId": "not-a-number"}]},
                {"csIdentifier": "bool", "connectors": [{"connectorId": True}]},
                {"csIdentifier": 123, "connectors": [{"connectorId": 1}]},
                {"csIdentifier": "", "connectors": [{"connectorId": 1}]},
                {"csIdentifier": "missing-connectors"},
            ]
        },
        {"chargingStations": ["bad-station"]},
    )
    data = OkData(
        settings=None,
        locations=locations,
        current_chargings=({"firestoreToken": "token"}, {"firestoreToken": ""}),
    )

    assert _document_version(event_time) == (2, 42.0)
    assert _document_version(current)[0] == 1
    assert _document_version(no_time) == (0, 0)
    assert _document_status(no_time) is None
    assert _nanoseconds_field(True) is None
    assert _nanoseconds_field("bad") is None
    assert _timestamp_value("") is None
    assert _timestamp_value("bad") is None
    assert _timestamp_value("2026-01-01T00:00:00") == datetime(2026, 1, 1, tzinfo=UTC).timestamp()
    assert (
        _retry_after(
            OkRateLimitError("slow", status_code=429, headers={"retry-after": "bad"}, payload={})
        )
        is None
    )
    assert (
        _retry_after(
            OkRateLimitError("slow", status_code=429, headers={"retry-after": "9999"}, payload={})
        )
        == 3600
    )
    assert (
        _retry_after(
            OkRateLimitError(
                "slow",
                status_code=429,
                headers={"retry-after": format_datetime(datetime.now(UTC) + timedelta(hours=2))},
                payload={},
            )
        )
        == 3600
    )
    assert _parse_datetime("") is None
    assert _parse_datetime("bad") is None
    assert _parse_datetime("2026-01-01T00:00:00Z") == datetime(2026, 1, 1)
    assert _realtime_watch_key_sort(("charging", "token")) == (1, "token", 0)
    assert _realtime_watch_keys(data) == {
        ("station", "charger", 2),
        ("charging", "token"),
    }
    assert (
        _charging_status_token({"chargingToken": "command-token", "firestoreToken": "status-token"})
        == "status-token"
    )
    assert _realtime_watch_keys(
        OkData(
            settings=None,
            locations=(),
            current_chargings=(
                {"chargingToken": "command-token", "firestoreToken": "status-token"},
            ),
        )
    ) == {("charging", "status-token")}


def test_coordinator_helper_additional_edges() -> None:
    current = FirestoreDocument(
        "current",
        {"status": "Charging", "statusUpdated": "2026-01-01T00:00:00Z"},
        None,
        None,
        {},
    )
    older = FirestoreDocument(
        "older",
        {"status": "Available", "statusUpdated": "2025-01-01T00:00:00Z"},
        None,
        None,
        {},
    )
    newer = FirestoreDocument(
        "newer",
        {"status": "Available", "statusEventTime": 2},
        None,
        None,
        {},
    )
    receipt = {
        "chargingStationId": "charger",
        "chargingStart": "2026-01-01T00:00:00Z",
        "chargingEnd": "2026-01-01T01:00:00Z",
        "totalPriceInOere": 100,
    }
    replacement = {**receipt, "totalPriceInOere": 200}

    assert _document_status(None) is None
    assert _nanoseconds_field(42) == 42
    assert _charging_connector_key({"csIdentifier": "", "connectorId": 1}) is None
    assert _charging_connector_key({"csIdentifier": "charger", "connectorId": True}) is None
    assert _charging_connector_key({"csIdentifier": "charger", "connectorId": 0}) is None
    assert _charging_connector_key({"csIdentifier": "charger", "connectorId": 2}) == (
        "charger",
        2,
    )
    assert _finished_chargings(
        (
            {"chargingToken": "finished"},
            {"chargingToken": "active", "firestoreToken": "previous-status"},
            {"chargingToken": ""},
        ),
        ({"chargingToken": "active", "firestoreToken": "current-status"},),
    ) == ({"chargingToken": "finished"},)
    assert _receipt_identity({}) is None
    assert _receipt_identity(receipt) == (
        "charger",
        "2026-01-01T00:00:00Z",
        "2026-01-01T01:00:00Z",
    )
    assert _merge_receipt((), {"totalPriceInOere": 100}) == ({"totalPriceInOere": 100},)
    assert _merge_receipt((receipt,), replacement) == (replacement,)
    assert _realtime_watch_label(("station", "charger", 2)) == "charger connector 2"
    assert _realtime_watch_label(("charging", "token")) == "charging session"
    assert _single_connector_refresh_value({}) == {}
    assert _single_connector_refresh_value({1: "one"}) == "one"
    assert _single_connector_refresh_value({1: "one", 2: None}) == {"1": "one", "2": None}
    assert _document_version(newer) > _document_version(current)
    assert _document_version(older) < _document_version(current)


def _entry() -> SimpleNamespace:
    return SimpleNamespace(
        async_on_unload=lambda callback: None,
        domain=DOMAIN,
        data={CONF_EMAIL: "user@example.test"},
        entry_id="test",
        options={},
        state=config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
        unique_id="1000001",
    )
