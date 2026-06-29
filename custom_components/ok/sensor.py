from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import OkConfigEntry
from . import schedule as ok_schedule
from .const import (
    ATTR_CHARGER_ID,
    ATTR_CONNECTOR_ID,
    CONF_ENABLE_ENERGY_PRICES,
    CONF_INCLUDE_RECEIPTS,
    CONNECTOR_STATUS_BY_RAW_STATUS,
    CONNECTOR_STATUS_OPTIONS,
)
from .coordinator import OkConnectorRef, OkDataUpdateCoordinator
from .entity import OkEntity

type SensorValue = str | int | float | datetime | None

_charging_field = ok_schedule.charging_field
_duration_seconds = ok_schedule.duration_seconds
_parse_datetime = ok_schedule.parse_datetime
_schedule_duration = ok_schedule.schedule_duration

PARALLEL_UPDATES = 0
_COORDINATOR_CONNECTOR = OkConnectorRef(location={}, station={}, connector={})


@dataclass(frozen=True, kw_only=True)
class OkSensorEntityDescription(SensorEntityDescription):  # type: ignore[misc]
    value_fn: Callable[[OkDataUpdateCoordinator, OkConnectorRef], SensorValue]
    attrs_fn: Callable[[OkDataUpdateCoordinator, OkConnectorRef], Mapping[str, Any]] | None = None
    connector_scoped: bool = True
    coordinator_scoped: bool = False
    receipt_required: bool = False
    energy_price_required: bool = False


SENSOR_DESCRIPTIONS: tuple[OkSensorEntityDescription, ...] = (
    OkSensorEntityDescription(
        key="energy_price",
        translation_key="energy_price",
        native_unit_of_measurement="DKK/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        connector_scoped=False,
        energy_price_required=True,
        value_fn=lambda coordinator, connector: _current_price(coordinator, connector),
        attrs_fn=lambda coordinator, connector: _energy_price_attrs(coordinator, connector),
    ),
    OkSensorEntityDescription(
        key="last_refresh",
        translation_key="last_refresh",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        connector_scoped=False,
        coordinator_scoped=True,
        value_fn=lambda coordinator, connector: coordinator.last_refresh,
        attrs_fn=lambda coordinator, connector: coordinator.poll_attributes,
    ),
    OkSensorEntityDescription(
        key="charger_last_refresh",
        translation_key="charger_last_refresh",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        connector_scoped=False,
        value_fn=lambda coordinator, connector: coordinator.charger_last_refresh(
            connector.station_id
        ),
        attrs_fn=lambda coordinator, connector: coordinator.charger_poll_attributes(
            connector.station_id
        ),
    ),
    OkSensorEntityDescription(
        key="connector_status",
        translation_key="connector_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(CONNECTOR_STATUS_OPTIONS),
        value_fn=lambda coordinator, connector: _connector_status(coordinator, connector),
        attrs_fn=lambda coordinator, connector: _station_status_attrs(coordinator, connector),
    ),
    OkSensorEntityDescription(
        key="connector_session_power",
        translation_key="connector_session_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator, connector: _watts_to_kw(
            _charging_field(coordinator, connector, "powerInW")
        ),
    ),
    OkSensorEntityDescription(
        key="connector_session_energy",
        translation_key="connector_session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda coordinator, connector: _watt_hours_to_kwh(
            _charging_field(coordinator, connector, "chargeInWh")
        ),
    ),
    OkSensorEntityDescription(
        key="schedule_duration",
        translation_key="schedule_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda coordinator, connector: _schedule_duration(coordinator, connector),
    ),
    OkSensorEntityDescription(
        key="last_session_ended",
        translation_key="last_session_ended",
        device_class=SensorDeviceClass.TIMESTAMP,
        connector_scoped=False,
        receipt_required=True,
        value_fn=lambda coordinator, connector: _parse_datetime(
            _receipt_field(coordinator, connector, "chargingEnd")
        ),
    ),
    OkSensorEntityDescription(
        key="last_session_energy",
        translation_key="last_session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        connector_scoped=False,
        receipt_required=True,
        value_fn=lambda coordinator, connector: _number(
            _receipt_field(coordinator, connector, "kWh")
        ),
    ),
    OkSensorEntityDescription(
        key="last_session_cost",
        translation_key="last_session_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="DKK",
        connector_scoped=False,
        receipt_required=True,
        value_fn=lambda coordinator, connector: _ore_to_dkk(
            _receipt_field(coordinator, connector, "totalPriceInOere")
        ),
        attrs_fn=lambda coordinator, connector: _last_session_cost_attrs(coordinator, connector),
    ),
    OkSensorEntityDescription(
        key="last_session_started",
        translation_key="last_session_started",
        device_class=SensorDeviceClass.TIMESTAMP,
        connector_scoped=False,
        receipt_required=True,
        value_fn=lambda coordinator, connector: _parse_datetime(
            _receipt_field(coordinator, connector, "chargingStart")
        ),
    ),
    OkSensorEntityDescription(
        key="last_session_duration",
        translation_key="last_session_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        connector_scoped=False,
        receipt_required=True,
        value_fn=lambda coordinator, connector: _last_session_duration(coordinator, connector),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    known: set[str] = set()

    @callback  # type: ignore[untyped-decorator]
    def async_add_ok_entities() -> None:
        descriptions = _sensor_descriptions_for_entry(entry)
        entities: list[OkSensor] = []
        for description in descriptions:
            if not description.coordinator_scoped:
                continue
            unique_id = _unique_id(
                coordinator,
                _COORDINATOR_CONNECTOR,
                description.key,
                description.connector_scoped,
                description.coordinator_scoped,
            )
            if unique_id in known:
                continue
            known.add(unique_id)
            entities.append(OkSensor(coordinator, _COORDINATOR_CONNECTOR, description))
        for connector in coordinator.connectors():
            for description in descriptions:
                if description.coordinator_scoped:
                    continue
                unique_id = _unique_id(
                    coordinator,
                    connector,
                    description.key,
                    description.connector_scoped,
                    description.coordinator_scoped,
                )
                if unique_id in known:
                    continue
                known.add(unique_id)
                entities.append(OkSensor(coordinator, connector, description))
        if entities:
            async_add_entities(entities)

    async_add_ok_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_ok_entities))


def _sensor_descriptions_for_entry(entry: OkConfigEntry) -> tuple[OkSensorEntityDescription, ...]:
    descriptions = SENSOR_DESCRIPTIONS
    if entry.options.get(CONF_INCLUDE_RECEIPTS, True) is False:
        descriptions = tuple(
            description for description in descriptions if not description.receipt_required
        )
    if entry.options.get(CONF_ENABLE_ENERGY_PRICES, True) is False:
        descriptions = tuple(
            description for description in descriptions if not description.energy_price_required
        )
    return descriptions


class OkSensor(OkEntity, SensorEntity):  # type: ignore[misc]
    entity_description: OkSensorEntityDescription
    _unrecorded_attributes = frozenset(
        {
            "today",
            "tomorrow",
            "raw_today",
            "raw_tomorrow",
            "prices",
        }
    )

    def __init__(
        self,
        coordinator: OkDataUpdateCoordinator,
        connector: OkConnectorRef,
        description: OkSensorEntityDescription,
    ) -> None:
        super().__init__(
            coordinator,
            connector,
            connector_scoped=description.connector_scoped,
            coordinator_scoped=description.coordinator_scoped,
        )
        self.entity_description = description
        self._attr_unique_id = _unique_id(
            coordinator,
            connector,
            description.key,
            description.connector_scoped,
            description.coordinator_scoped,
        )
        self._set_multi_connector_translation(description.translation_key)

    @property
    def native_value(self) -> SensorValue:
        return self.entity_description.value_fn(self.coordinator, self.connector)

    @property
    def available(self) -> bool:
        return super().available

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        attrs = dict(super().extra_state_attributes)
        if self.entity_description.attrs_fn is not None:
            attrs.update(self.entity_description.attrs_fn(self.coordinator, self.connector))
        return attrs


def _unique_id(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
    key: str,
    connector_scoped: bool = True,
    coordinator_scoped: bool = False,
) -> str:
    if coordinator_scoped:
        config_unique_id = coordinator.entry.unique_id or coordinator.entry.entry_id
        return f"{config_unique_id}_{key}"
    if connector_scoped:
        return f"{connector.station_id}_{connector.connector_id}_{key}"
    return f"{connector.station_id}_{key}"


def _prices(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> list[dict[str, Any]]:
    response = coordinator.prices_for(connector.station_id)
    if response is None:
        return []
    return [dict(item) for item in response.get("prices", []) or []]


def _price_total(price: Mapping[str, Any]) -> float | None:
    values = [
        _number(price.get("electricityPriceIncludingVat")),
        _number(price.get("tariffIncludingVat")),
        _number(price.get("electricityTaxIncludingVat")),
    ]
    if any(value is None for value in values):
        return None
    return round(sum(value for value in values if value is not None) / 100, 3)


def _current_price(coordinator: OkDataUpdateCoordinator, connector: OkConnectorRef) -> float | None:
    current = _current_price_row(coordinator, connector)
    return _price_total(current) if current else None


def _current_price_row(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> Mapping[str, Any] | None:
    rows = sorted(
        _prices(coordinator, connector),
        key=lambda item: (
            _parse_datetime(item.get("applicableTime")) or datetime.min.replace(tzinfo=UTC)
        ),
    )
    if not rows:
        return None
    now = datetime.now(UTC)
    selected = rows[0]
    for row in rows:
        applicable = _parse_datetime(row.get("applicableTime"))
        if applicable is None:
            continue
        if applicable <= now:
            selected = row
            continue
        break
    return selected


def _energy_price_attrs(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> Mapping[str, Any]:
    response = coordinator.prices_for(connector.station_id) or {}
    rows = _price_rows(coordinator, connector)
    today = dt_util.now().date()
    tomorrow = today + timedelta(days=1)
    today_rows = _rows_for_date(rows, today)
    tomorrow_rows = _rows_for_date(rows, tomorrow)

    region_code = connector.location.get("electricityPriceZone")
    region = region_code if isinstance(region_code, str) and region_code else None
    next_update = coordinator.next_price_update_for(connector.station_id)
    tomorrow_valid = bool(tomorrow_rows)

    return {
        ATTR_CHARGER_ID: connector.station_id,
        "unit": "kWh",
        "currency": "DKK",
        "region": region,
        "tomorrow_valid": tomorrow_valid,
        "next_data_update": next_update.isoformat() if next_update is not None else None,
        "today": [item["price"] for item in today_rows],
        "tomorrow": [item["price"] for item in tomorrow_rows] if tomorrow_valid else None,
        "raw_today": _raw_price_rows(today_rows),
        "raw_tomorrow": _raw_price_rows(tomorrow_rows) if tomorrow_valid else [],
        "today_min": _specific_price("min", today_rows),
        "today_max": _specific_price("max", today_rows),
        "today_mean": _mean_price(today_rows),
        "tomorrow_min": _specific_price("min", tomorrow_rows) if tomorrow_valid else None,
        "tomorrow_max": _specific_price("max", tomorrow_rows) if tomorrow_valid else None,
        "tomorrow_mean": _mean_price(tomorrow_rows) if tomorrow_valid else None,
        "use_cent": False,
        "prices": _window_price_rows(rows),
        "product": response.get("productName"),
        "attribution": "Data sourced from OK",
    }


def _price_rows(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in sorted(
        _prices(coordinator, connector),
        key=lambda value: (
            _parse_datetime(value.get("applicableTime")) or datetime.max.replace(tzinfo=UTC)
        ),
    ):
        start = _parse_datetime(item.get("applicableTime"))
        price = _price_total(item)
        if start is None or price is None:
            continue
        rows.append({"hour": start, "price": price})
    return rows


def _rows_for_date(rows: list[dict[str, Any]], local_date: date) -> list[dict[str, Any]]:
    return [row for row in rows if dt_util.as_local(row["hour"]).date() == local_date]


def _raw_price_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "hour": row["hour"].isoformat(),
            "price": row["price"],
        }
        for row in rows
    ]


def _window_price_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prices: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        start = row["hour"]
        end = _price_row_end(rows, index)
        if end <= start:
            continue
        prices.append(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "price": row["price"],
            }
        )
    return prices


def _price_row_end(rows: list[dict[str, Any]], index: int) -> datetime:
    start = cast(datetime, rows[index]["hour"])
    if index + 1 < len(rows):
        next_start = cast(datetime, rows[index + 1]["hour"])
        if next_start > start:
            return next_start
    if index > 0:
        previous_start = cast(datetime, rows[index - 1]["hour"])
        slot = start - previous_start
        if slot.total_seconds() > 0:
            return start + slot
    return start + timedelta(hours=1)


def _specific_price(kind: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    if kind == "min":
        row = min(rows, key=lambda item: item["price"])
    else:
        row = max(rows, key=lambda item: item["price"])
    return {"hour": row["hour"].isoformat(), "price": row["price"]}


def _mean_price(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    return round(sum(cast(float, row["price"]) for row in rows) / len(rows), 3)


def _station_status_field(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
    key: str,
) -> Any:
    document = coordinator.station_status_for(connector.station_id, connector.connector_id)
    if document is None:
        return None
    return document.fields.get(key)


def _connector_status(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> str | None:
    status = _station_status_field(coordinator, connector, "status")
    if not isinstance(status, str):
        return None
    return CONNECTOR_STATUS_BY_RAW_STATUS.get(status)


def _station_status_attrs(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> Mapping[str, Any]:
    document = coordinator.station_status_for(connector.station_id, connector.connector_id)
    if document is None:
        return {}
    return {
        ATTR_CHARGER_ID: connector.station_id,
        ATTR_CONNECTOR_ID: connector.connector_id,
        "raw_status": document.fields.get("status"),
        "status_updated": document.fields.get("statusUpdated"),
        "maximum_power_kw": _number(connector.connector.get("power")),
    }


def _receipt_field(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
    key: str,
) -> Any:
    receipt = coordinator.last_receipt_for(connector.station_id)
    if receipt is None:
        return None
    return receipt.get(key)


def _last_session_cost_attrs(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> Mapping[str, Any]:
    if coordinator.last_receipt_for(connector.station_id) is None:
        return {}
    return {"no_price_reason": _receipt_field(coordinator, connector, "noPriceReason")}


def _last_session_duration(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> int | None:
    receipt = coordinator.last_receipt_for(connector.station_id)
    if receipt is None:
        return None
    started_at = _parse_datetime(receipt.get("chargingStart"))
    ended_at = _parse_datetime(receipt.get("chargingEnd"))
    return _duration_seconds(started_at, ended_at)


def _watt_hours_to_kwh(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(number / 1000, 3)


def _watts_to_kw(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(number / 1000, 3)


def _ore_to_dkk(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(number / 100, 3)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
