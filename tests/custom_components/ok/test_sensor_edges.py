from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from custom_components.ok.sensor import (
    _current_price_row,
    _duration_seconds,
    _energy_price_attrs,
    _mean_price,
    _number,
    _parse_datetime,
    _price_row_end,
    _price_rows,
    _price_total,
    _prices,
    _specific_price,
    _window_price_rows,
)
from homeassistant.core import HomeAssistant

from .entity_helpers import EntityTestCoordinator


def test_price_helpers_handle_missing_and_irregular_data(tmp_path: Path) -> None:
    asyncio.run(_test_price_helpers_handle_missing_and_irregular_data(tmp_path))


async def _test_price_helpers_handle_missing_and_irregular_data(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        connector = coordinator.connector_refs[0]
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        coordinator.price_response = {
            "prices": [
                {"applicableTime": "", "electricityPriceIncludingVat": 100},
                {
                    "applicableTime": (now - timedelta(hours=2)).isoformat(),
                    "electricityPriceIncludingVat": 100,
                    "tariffIncludingVat": 20,
                    "electricityTaxIncludingVat": 5,
                },
                {
                    "applicableTime": (now + timedelta(hours=2)).isoformat(),
                    "electricityPriceIncludingVat": 200,
                    "tariffIncludingVat": 30,
                    "electricityTaxIncludingVat": 5,
                },
            ]
        }

        rows = _price_rows(coordinator, connector)

        assert _prices(coordinator, connector) == coordinator.price_response["prices"]
        assert _price_total({"electricityPriceIncludingVat": 100}) is None
        assert (
            _current_price_row(coordinator, connector)["applicableTime"]
            == (now - timedelta(hours=2)).isoformat()
        )
        assert len(rows) == 2
        assert _specific_price("min", rows)["price"] == 1.25
        assert _specific_price("max", rows)["price"] == 2.35
        assert _mean_price(rows) == 1.8
        assert _window_price_rows([{"hour": now, "price": 1.0}, {"hour": now, "price": 2.0}]) == [
            {
                "start": now.isoformat(),
                "end": (now + timedelta(hours=1)).isoformat(),
                "price": 1.0,
            },
            {
                "start": now.isoformat(),
                "end": (now + timedelta(hours=1)).isoformat(),
                "price": 2.0,
            },
        ]
        assert _price_row_end([{"hour": now, "price": 1.0}], 0) == now + timedelta(hours=1)
    finally:
        await hass.async_stop()


def test_price_attrs_handle_empty_price_response(tmp_path: Path) -> None:
    asyncio.run(_test_price_attrs_handle_empty_price_response(tmp_path))


async def _test_price_attrs_handle_empty_price_response(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        coordinator = EntityTestCoordinator(hass)
        connector = coordinator.connector_refs[0]
        coordinator.price_response = None

        attrs = _energy_price_attrs(coordinator, connector)

        assert _prices(coordinator, connector) == []
        assert _current_price_row(coordinator, connector) is None
        assert attrs["today"] == []
        assert attrs["tomorrow"] is None
        assert attrs["today_min"] is None
        assert attrs["today_max"] is None
        assert attrs["today_mean"] is None
        assert attrs["prices"] == []
        assert attrs["product"] is None
    finally:
        await hass.async_stop()


def test_numeric_and_datetime_helpers_handle_invalid_values() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2025, 1, 1, tzinfo=UTC)

    assert _duration_seconds(None, start) is None
    assert _duration_seconds(start, end) is None
    assert _number(True) is None
    assert _number("not-a-number") is None
    assert _number(object()) is None
    assert _parse_datetime("") is None
    assert _parse_datetime("not-a-date") is None
    assert _parse_datetime("2026-01-01T12:00:00") == datetime(2026, 1, 1, 12, tzinfo=UTC)
