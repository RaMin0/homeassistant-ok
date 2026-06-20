from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import OkConfigEntry
from .const import LEGACY_REDACT_CONFIG_KEYS, REDACT_CONFIG_KEYS


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: OkConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for an OK config entry."""
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data
    return {
        "entry": async_redact_data(
            dict(entry.data),
            REDACT_CONFIG_KEYS | LEGACY_REDACT_CONFIG_KEYS,
        ),
        "options": dict(entry.options),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "locations": len(data.locations) if data else 0,
            "chargers": len({connector.station_id for connector in coordinator.connectors()}),
            "connectors": len(coordinator.connectors()),
            "current_chargings": len(data.current_chargings) if data else 0,
            "receipts": len(data.receipts) if data else 0,
        },
    }
