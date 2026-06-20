from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OkConfigEntry
from .action import (
    active_charging_token,
    async_call_ok_api,
    require_active_charging_token,
    validate_command_response,
)
from .const import CONF_ENABLE_CONTROL_BUTTONS
from .coordinator import OkConnectorRef, OkDataUpdateCoordinator
from .entity import OkEntity

PARALLEL_UPDATES = 1
_COORDINATOR_CONNECTOR = OkConnectorRef(location={}, station={}, connector={})


@dataclass(frozen=True, kw_only=True)
class OkButtonEntityDescription(ButtonEntityDescription):  # type: ignore[misc]
    press_fn: Callable[[OkButton], Awaitable[None]]
    available_fn: Callable[[OkButton], bool] | None = None
    connector_scoped: bool = True
    coordinator_scoped: bool = False
    control_button: bool = False


BUTTON_DESCRIPTIONS = (
    OkButtonEntityDescription(
        key="start_charging",
        translation_key="start_charging",
        control_button=True,
        press_fn=lambda entity: entity._async_start_charging(),
    ),
    OkButtonEntityDescription(
        key="stop_charging",
        translation_key="stop_charging",
        control_button=True,
        press_fn=lambda entity: entity._async_stop_charging(),
        available_fn=lambda entity: entity._active_token() is not None,
    ),
    OkButtonEntityDescription(
        key="cancel_schedule",
        translation_key="cancel_schedule",
        control_button=True,
        press_fn=lambda entity: entity._async_cancel_schedule(),
        available_fn=lambda entity: entity._active_token() is not None,
    ),
    OkButtonEntityDescription(
        key="restart",
        translation_key="restart",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        connector_scoped=False,
        control_button=True,
        press_fn=lambda entity: entity._async_restart(),
    ),
    OkButtonEntityDescription(
        key="force_refresh",
        translation_key="force_refresh",
        entity_category=EntityCategory.CONFIG,
        connector_scoped=False,
        coordinator_scoped=True,
        press_fn=lambda entity: entity._async_force_refresh(),
        available_fn=lambda entity: not entity.coordinator.refresh_in_progress,
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
        descriptions = _button_descriptions_for_entry(entry)
        entities: list[OkButton] = []
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
            entities.append(OkButton(coordinator, _COORDINATOR_CONNECTOR, description))
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
                entities.append(OkButton(coordinator, connector, description))
        if entities:
            async_add_entities(entities)

    async_add_ok_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_ok_entities))


def _button_descriptions_for_entry(entry: OkConfigEntry) -> tuple[OkButtonEntityDescription, ...]:
    if entry.options.get(CONF_ENABLE_CONTROL_BUTTONS, True) is not False:
        return BUTTON_DESCRIPTIONS
    return tuple(
        description for description in BUTTON_DESCRIPTIONS if not description.control_button
    )


class OkButton(OkEntity, ButtonEntity):  # type: ignore[misc]
    entity_description: OkButtonEntityDescription

    def __init__(
        self,
        coordinator: OkDataUpdateCoordinator,
        connector: OkConnectorRef,
        description: OkButtonEntityDescription,
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
    def available(self) -> bool:
        if not super().available:
            return False
        if self.entity_description.available_fn is None:
            return True
        return self.entity_description.available_fn(self)

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self)

    async def _async_start_charging(self) -> None:
        response = await async_call_ok_api(
            self.coordinator.client.start_charging(
                charging_station_id=self.station_id,
                connector_id=self.connector_id,
            ),
            hass=self.hass,
            entry=self.coordinator.entry,
        )
        validate_command_response(response)
        await self.coordinator.async_request_operational_refresh()

    async def _async_stop_charging(self) -> None:
        token = require_active_charging_token(
            self.coordinator.active_charging_for(self.station_id, self.connector_id)
        )
        await async_call_ok_api(
            self.coordinator.client.stop_charging(token),
            hass=self.hass,
            entry=self.coordinator.entry,
        )
        await self.coordinator.async_request_operational_refresh()

    async def _async_cancel_schedule(self) -> None:
        token = require_active_charging_token(
            self.coordinator.active_charging_for(self.station_id, self.connector_id)
        )
        await async_call_ok_api(
            self.coordinator.client.cancel_charging_schedule(token),
            hass=self.hass,
            entry=self.coordinator.entry,
        )
        await self.coordinator.async_request_operational_refresh()

    async def _async_restart(self) -> None:
        await async_call_ok_api(
            self.coordinator.client.restart_station(self.station_id),
            hass=self.hass,
            entry=self.coordinator.entry,
        )
        await self.coordinator.async_request_operational_refresh()

    async def _async_force_refresh(self) -> None:
        await self.coordinator.async_force_full_refresh()

    def _active_token(self) -> str | None:
        return active_charging_token(
            self.coordinator.active_charging_for(self.station_id, self.connector_id)
        )


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
