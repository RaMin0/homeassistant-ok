from __future__ import annotations

from typing import Final

from homeassistant.const import CONF_EMAIL, Platform

DOMAIN: Final = "ok"

PLATFORMS: Final = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]

CONF_APP_ID: Final = "app_id"
CONF_DEVICE_FRIENDLY_ID: Final = "device_friendly_id"
CONF_DEVICE_ID: Final = "device_id"
CONF_INCLUDE_RECEIPTS: Final = "include_receipts"

ATTR_CHARGER_ID: Final = "charger_id"
ATTR_CONNECTOR_ID: Final = "connector_id"
ATTR_SCHEDULED_START: Final = "scheduled_start"
ATTR_SCHEDULED_END: Final = "scheduled_end"
ATTR_AUTOSTART: Final = "autostart"

SERVICE_CANCEL_CHARGING_SCHEDULE: Final = "cancel_charging_schedule"
SERVICE_RESTART: Final = "restart"
SERVICE_SCHEDULE_CHARGING: Final = "schedule_charging"
SERVICE_SET_AUTO_START: Final = "set_auto_start"
SERVICE_START_CHARGING: Final = "start_charging"
SERVICE_STOP_CHARGING: Final = "stop_charging"
SERVICE_UPDATE_CHARGING_SCHEDULE: Final = "update_charging_schedule"

APP_PLATFORM: Final = "HomeAssistant"
APP_SECRET: Final = "49BA6A36-956A-4444-8B7B-C04DD63D200F"  # noqa: S105

CONNECTOR_STATUS_AVAILABLE: Final = "available"
CONNECTOR_STATUS_PREPARING: Final = "preparing"
CONNECTOR_STATUS_CHARGING: Final = "charging"
CONNECTOR_STATUS_SUSPENDED_EVSE: Final = "suspended_evse"
CONNECTOR_STATUS_SUSPENDED_EV: Final = "suspended_ev"
CONNECTOR_STATUS_FINISHING: Final = "finishing"
CONNECTOR_STATUS_RESERVED: Final = "reserved"
CONNECTOR_STATUS_UNAVAILABLE: Final = "unavailable"
CONNECTOR_STATUS_FAULTED: Final = "faulted"

CONNECTOR_STATUS_OPTIONS: Final = (
    CONNECTOR_STATUS_AVAILABLE,
    CONNECTOR_STATUS_PREPARING,
    CONNECTOR_STATUS_CHARGING,
    CONNECTOR_STATUS_SUSPENDED_EVSE,
    CONNECTOR_STATUS_SUSPENDED_EV,
    CONNECTOR_STATUS_FINISHING,
    CONNECTOR_STATUS_RESERVED,
    CONNECTOR_STATUS_UNAVAILABLE,
    CONNECTOR_STATUS_FAULTED,
)

CONNECTOR_STATUS_BY_RAW_STATUS: Final = {
    "Available": CONNECTOR_STATUS_AVAILABLE,
    "Preparing": CONNECTOR_STATUS_PREPARING,
    "Charging": CONNECTOR_STATUS_CHARGING,
    "SuspendedEVSE": CONNECTOR_STATUS_SUSPENDED_EVSE,
    "SuspendedEV": CONNECTOR_STATUS_SUSPENDED_EV,
    "Finishing": CONNECTOR_STATUS_FINISHING,
    "Reserved": CONNECTOR_STATUS_RESERVED,
    "Unavailable": CONNECTOR_STATUS_UNAVAILABLE,
    "Faulted": CONNECTOR_STATUS_FAULTED,
}

REDACT_CONFIG_KEYS: Final = {
    CONF_EMAIL,
    CONF_APP_ID,
    CONF_DEVICE_FRIENDLY_ID,
    CONF_DEVICE_ID,
}
LEGACY_REDACT_CONFIG_KEYS: Final = {
    "login_token",
}
