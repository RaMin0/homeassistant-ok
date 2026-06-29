from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from homeassistant.core import callback
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
        self._ok_base_translation_key: str | None = None
        self.station_id = "" if coordinator_scoped else connector.station_id
        self.connector_id = 0 if coordinator_scoped else connector.connector_id

    @property
    def connector(self) -> OkConnectorRef:
        if self._coordinator_scoped:
            return self._connector
        coordinator = cast(OkDataUpdateCoordinator, self.coordinator)
        for connector in coordinator.connectors():
            if connector.station_id != self.station_id:
                continue
            if not self._connector_scoped or connector.connector_id == self.connector_id:
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
        vendor = _string(station.get("vendorName")) or _string(station.get("vendor")) or "OK"
        return DeviceInfo(
            identifiers={(DOMAIN, self.station_id)},
            manufacturer=vendor,
            model=_string(station.get("model")),
            name=_string(station.get("name")) or self.station_id,
            serial_number=_string(station.get("serialNumber")),
            sw_version=_string(station.get("firmwareVersion")),
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
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
        self._ok_base_translation_key = translation_key
        self._refresh_multi_connector_translation()

    def _refresh_multi_connector_translation(self) -> None:
        if self._ok_base_translation_key is None:
            return
        if not self._use_multi_connector_name():
            self._attr_translation_key = self._ok_base_translation_key
            self._attr_translation_placeholders = {}
            return
        self._attr_translation_key = f"{self._ok_base_translation_key}_connector"
        self._attr_translation_placeholders = {"connector_id": str(self.connector_id)}

    @callback  # type: ignore[untyped-decorator]
    def _handle_coordinator_update(self) -> None:
        self._refresh_multi_connector_translation()
        super()._handle_coordinator_update()


def _string(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
