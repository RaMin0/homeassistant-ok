from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from homeassistant.components.datetime import DateTimeEntity, DateTimeEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import OkConfigEntry
from .action import active_charging_token, async_call_ok_api
from .const import DOMAIN
from .coordinator import OkConnectorRef, OkDataUpdateCoordinator
from .entity import OkEntity
from .schedule import schedule_end, schedule_start

type ScheduleBoundary = Literal["start", "end"]

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OkDateTimeEntityDescription(DateTimeEntityDescription):  # type: ignore[misc]
    value_fn: Callable[[OkDataUpdateCoordinator, OkConnectorRef], datetime | None]
    boundary: ScheduleBoundary


DATETIME_DESCRIPTIONS = (
    OkDateTimeEntityDescription(
        key="schedule_from",
        translation_key="schedule_from",
        value_fn=schedule_start,
        boundary="start",
    ),
    OkDateTimeEntityDescription(
        key="schedule_to",
        translation_key="schedule_to",
        value_fn=schedule_end,
        boundary="end",
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
        entities: list[OkScheduleDateTime] = []
        for connector in coordinator.connectors():
            for description in DATETIME_DESCRIPTIONS:
                unique_id = _unique_id(connector, description.key)
                if unique_id in known:
                    continue
                known.add(unique_id)
                entities.append(OkScheduleDateTime(coordinator, connector, description))
        if entities:
            async_add_entities(entities)

    async_add_ok_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_ok_entities))


class OkScheduleDateTime(OkEntity, DateTimeEntity):  # type: ignore[misc]
    entity_description: OkDateTimeEntityDescription

    def __init__(
        self,
        coordinator: OkDataUpdateCoordinator,
        connector: OkConnectorRef,
        description: OkDateTimeEntityDescription,
    ) -> None:
        super().__init__(coordinator, connector)
        self.entity_description = description
        self._attr_unique_id = _unique_id(connector, description.key)
        self._set_multi_connector_translation(description.translation_key)

    @property
    def native_value(self) -> datetime | None:
        return self.entity_description.value_fn(self.coordinator, self.connector)

    async def async_set_value(self, value: datetime) -> None:
        scheduled_start: datetime | None = _schedule_datetime(self.hass, value)
        scheduled_end: datetime | None = schedule_end(self.coordinator, self.connector)
        if self.entity_description.boundary == "end":
            scheduled_start = schedule_start(self.coordinator, self.connector)
            scheduled_end = _schedule_datetime(self.hass, value)

        if scheduled_start is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schedule_window_missing",
            )
        if scheduled_end is not None and scheduled_end <= scheduled_start:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_schedule_window",
            )

        token = active_charging_token(
            self.coordinator.active_charging_for(self.station_id, self.connector_id)
        )
        if token is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="active_charging_not_found",
            )

        await async_call_ok_api(
            self.coordinator.client.update_charging_schedule(
                token,
                charging_station_id=self.station_id,
                scheduled_start=scheduled_start.isoformat(),
                scheduled_end=scheduled_end.isoformat() if scheduled_end is not None else None,
            ),
            hass=self.hass,
            entry=self.coordinator.entry,
        )
        await self.coordinator.async_request_operational_refresh()


def _unique_id(connector: OkConnectorRef, key: str) -> str:
    return f"{connector.station_id}_{connector.connector_id}_{key}"


def _schedule_datetime(hass: HomeAssistant, value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        time_zone = dt_util.get_time_zone(hass.config.time_zone) or dt_util.DEFAULT_TIME_ZONE
        return value.replace(tzinfo=time_zone)
    return value
