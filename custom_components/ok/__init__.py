from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .api import AsyncOkApiClient
    from .coordinator import OkDataUpdateCoordinator


@dataclass(slots=True)
class OkRuntimeData:
    client: AsyncOkApiClient
    coordinator: OkDataUpdateCoordinator


if TYPE_CHECKING:
    type OkConfigEntry = ConfigEntry[OkRuntimeData]
else:
    OkConfigEntry = Any


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: Any, config: dict[str, Any]) -> bool:
    """Set up integration-level OK services."""
    from ._integration import async_setup as _async_setup

    return await _async_setup(hass, config)


async def async_setup_entry(hass: Any, entry: OkConfigEntry) -> bool:
    """Set up OK from a config entry."""
    from ._integration import async_setup_entry as _async_setup_entry

    return await _async_setup_entry(hass, entry)


async def async_migrate_entry(hass: Any, entry: OkConfigEntry) -> bool:
    """Clean up legacy OK config entry data."""
    from ._integration import async_migrate_entry as _async_migrate_entry

    return await _async_migrate_entry(hass, entry)


async def async_unload_entry(hass: Any, entry: OkConfigEntry) -> bool:
    """Unload an OK config entry."""
    from ._integration import async_unload_entry as _async_unload_entry

    return await _async_unload_entry(hass, entry)


async def async_remove_config_entry_device(
    hass: Any,
    entry: OkConfigEntry,
    device_entry: Any,
) -> bool:
    """Allow users to remove stale OK charger devices manually."""
    from ._integration import async_remove_config_entry_device as _async_remove_device

    return await _async_remove_device(hass, entry, device_entry)
