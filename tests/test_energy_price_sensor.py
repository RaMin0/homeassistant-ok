from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from custom_components.ok.coordinator import OkConnectorRef
from custom_components.ok.sensor import _energy_price_attrs
from homeassistant.util import dt as dt_util


class FakeCoordinator:
    def __init__(self, prices: list[dict[str, Any]]) -> None:
        self._prices = prices

    def prices_for(self, station_id: str) -> dict[str, Any]:
        assert station_id == "OK-CHARGER-001"
        return {
            "prices": self._prices,
            "productName": "OK El Flex",
            "productType": 3,
            "electricityPriceOrigin": "DigitEl",
        }

    def next_price_update_for(self, station_id: str) -> datetime:
        assert station_id == "OK-CHARGER-001"
        return datetime(2026, 1, 1, tzinfo=UTC)


def test_energy_price_attrs_are_compatible_with_price_window_consumers() -> None:
    local_midnight = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
    prices = [_price_row(local_midnight + timedelta(hours=hour), 100 + hour) for hour in range(24)]
    prices.extend(
        _price_row(local_midnight + timedelta(days=1, hours=hour), 200 + hour) for hour in range(24)
    )
    connector = OkConnectorRef(
        location={"electricityPriceZone": "DK2"},
        station={"csIdentifier": "OK-CHARGER-001"},
        connector={"connectorId": 1},
    )

    attrs = _energy_price_attrs(FakeCoordinator(prices), connector)

    assert attrs["unit"] == "kWh"
    assert attrs["currency"] == "DKK"
    assert attrs["region"] == "DK2"
    assert attrs["charger_id"] == "OK-CHARGER-001"
    assert attrs["tomorrow_valid"] is True
    assert attrs["use_cent"] is False
    assert attrs["product"] == "OK El Flex"
    assert len(attrs["today"]) == 24
    assert len(attrs["tomorrow"]) == 24
    assert len(attrs["raw_today"]) == 24
    assert len(attrs["raw_tomorrow"]) == 24
    assert attrs["raw_today"][0] == {
        "hour": local_midnight.astimezone(UTC).isoformat(),
        "price": 1.0,
    }
    assert attrs["today_min"] == attrs["raw_today"][0]
    assert attrs["today_max"] == attrs["raw_today"][23]
    assert attrs["today_mean"] == 1.115
    assert len(attrs["prices"]) == 48
    assert attrs["prices"][0] == {
        "start": local_midnight.astimezone(UTC).isoformat(),
        "end": (local_midnight + timedelta(hours=1)).astimezone(UTC).isoformat(),
        "price": 1.0,
    }


def _price_row(hour: datetime, price_in_oere: int) -> dict[str, Any]:
    return {
        "applicableTime": hour.isoformat(),
        "electricityPriceIncludingVat": price_in_oere,
        "tariffIncludingVat": 0,
        "electricityTaxIncludingVat": 0,
    }
