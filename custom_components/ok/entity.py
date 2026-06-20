from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OkConnectorRef, OkDataUpdateCoordinator


class OkEntity(CoordinatorEntity[OkDataUpdateCoordinator]):  # type: ignore[misc]
    """Base entity for OK charger entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OkDataUpdateCoordinator,
        connector: OkConnectorRef,
        *,
        connector_scoped: bool = True,
        coordinator_scoped: bool = False,
    ) -> None:
        super().__init__(coordinator)
        self._connector = connector
        self._connector_scoped = connector_scoped
        self._coordinator_scoped = coordinator_scoped
        self.station_id = "" if coordinator_scoped else connector.station_id
        self.connector_id = 0 if coordinator_scoped else connector.connector_id

    @property
    def connector(self) -> OkConnectorRef:
        coordinator = cast(OkDataUpdateCoordinator, self.coordinator)
        for connector in coordinator.connectors():
            if (
                connector.station_id == self.station_id
                and connector.connector_id == self.connector_id
            ):
                return connector
        return self._connector

    @property
    def device_info(self) -> DeviceInfo | None:
        if self._coordinator_scoped:
            coordinator = cast(OkDataUpdateCoordinator, self.coordinator)
            account_id = coordinator.entry.unique_id or coordinator.entry.entry_id
            return DeviceInfo(
                identifiers={(DOMAIN, f"account_{account_id}")},
                entry_type=DeviceEntryType.SERVICE,
                manufacturer="OK",
                translation_key="account",
            )
        station = self.connector.station
        location = self.connector.location
        vendor = _string(station.get("vendorName")) or _string(station.get("vendor")) or "OK"
        return DeviceInfo(
            identifiers={(DOMAIN, self.station_id)},
            manufacturer=vendor,
            model=_string(station.get("model")),
            name=_string(station.get("name")) or self.station_id,
            serial_number=_string(station.get("serialNumber")),
            sw_version=_string(station.get("firmwareVersion")),
            suggested_area=_string(location.get("name")),
        )

    @property
    def available(self) -> bool:
        coordinator = cast(OkDataUpdateCoordinator, self.coordinator)
        if coordinator.data is None:
            return False
        if self._coordinator_scoped:
            return True
        if not self._connector_scoped:
            return any(
                connector.station_id == self.station_id for connector in coordinator.connectors()
            )
        return any(
            connector.station_id == self.station_id and connector.connector_id == self.connector_id
            for connector in coordinator.connectors()
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {}

    def _use_multi_connector_name(self) -> bool:
        if self._coordinator_scoped or not self._connector_scoped:
            return False
        return (
            sum(
                1
                for connector in cast(OkDataUpdateCoordinator, self.coordinator).connectors()
                if connector.station_id == self.station_id
            )
            > 1
        )

    def _set_multi_connector_translation(self, translation_key: str | None) -> None:
        if translation_key is None or not self._use_multi_connector_name():
            return
        self._attr_translation_key = f"{translation_key}_connector"
        self._attr_translation_placeholders = {"connector_id": str(self.connector_id)}


def _string(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
