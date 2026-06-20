from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OkConfigEntry
from .action import async_call_ok_api
from .coordinator import OkConnectorRef, OkDataUpdateCoordinator
from .entity import OkEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OkSwitchEntityDescription(SwitchEntityDescription):  # type: ignore[misc]
    pass


AUTO_START_SWITCH_DESCRIPTION = OkSwitchEntityDescription(
    key="auto_start",
    translation_key="auto_start",
    entity_category=EntityCategory.CONFIG,
)
SWITCH_DESCRIPTIONS = (AUTO_START_SWITCH_DESCRIPTION,)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    known: set[str] = set()

    @callback  # type: ignore[untyped-decorator]
    def async_add_ok_entities() -> None:
        entities: list[SwitchEntity] = []
        for connector in coordinator.connectors():
            _add_entity(
                entities,
                known,
                OkAutoStartSwitch(coordinator, connector, AUTO_START_SWITCH_DESCRIPTION),
            )
        if entities:
            async_add_entities(entities)

    async_add_ok_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_ok_entities))


class OkAutoStartSwitch(OkEntity, SwitchEntity):  # type: ignore[misc]
    entity_description: OkSwitchEntityDescription

    def __init__(
        self,
        coordinator: OkDataUpdateCoordinator,
        connector: OkConnectorRef,
        description: OkSwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator, connector, connector_scoped=False)
        self.entity_description = description
        self._attr_unique_id = _unique_id(connector, description.key)

    @property
    def is_on(self) -> bool | None:
        value = self.connector.station.get("autoStart")
        return value if isinstance(value, bool) else None

    async def async_turn_on(self, **kwargs: object) -> None:
        await async_call_ok_api(
            self.coordinator.client.set_station_auto_start(self.station_id, True),
            hass=self.hass,
            entry=self.coordinator.entry,
        )
        await self.coordinator.async_request_station_refresh()

    async def async_turn_off(self, **kwargs: object) -> None:
        await async_call_ok_api(
            self.coordinator.client.set_station_auto_start(self.station_id, False),
            hass=self.hass,
            entry=self.coordinator.entry,
        )
        await self.coordinator.async_request_station_refresh()


def _add_entity(
    entities: list[SwitchEntity],
    known: set[str],
    entity: SwitchEntity,
) -> None:
    unique_id = entity.unique_id
    if unique_id is None or unique_id in known:
        return
    known.add(unique_id)
    entities.append(entity)


def _unique_id(connector: OkConnectorRef, key: str) -> str:
    return f"{connector.station_id}_{key}"
