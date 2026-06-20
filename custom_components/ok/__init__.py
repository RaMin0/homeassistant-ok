from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from homeassistant.const import CONF_EMAIL
from homeassistant.helpers import config_validation as cv

from .api import (
    AsyncOkApiClient,
    OkApiConfig,
)
from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

    from .coordinator import OkDataUpdateCoordinator


@dataclass(slots=True)
class OkRuntimeData:
    client: AsyncOkApiClient
    coordinator: OkDataUpdateCoordinator


@dataclass(slots=True)
class OkServiceTarget:
    entry: OkConfigEntry
    runtime: OkRuntimeData
    station_id: str
    connector_id: int


if TYPE_CHECKING:
    type OkConfigEntry = ConfigEntry[OkRuntimeData]
else:
    OkConfigEntry = Any

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_LEGACY_CONFIG_KEYS = {"login_token"}


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration-level OK services."""
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OkConfigEntry) -> bool:
    """Set up OK from a config entry."""
    from .const import PLATFORMS
    from .coordinator import OkDataUpdateCoordinator

    _update_legacy_config_entry(hass, entry)
    client = _client_from_entry(hass, entry)
    coordinator = OkDataUpdateCoordinator(hass, entry, client)
    remove_update_listener: Callable[[], None] | None = None
    runtime_data: OkRuntimeData | None = None
    try:
        await coordinator.async_config_entry_first_refresh()
        _cleanup_removed_or_disabled_entities(hass, entry)
        runtime_data = OkRuntimeData(client=client, coordinator=coordinator)
        entry.runtime_data = runtime_data
        remove_update_listener = entry.add_update_listener(_async_update_listener)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(remove_update_listener)
    except BaseException:
        if remove_update_listener is not None:
            remove_update_listener()
        await coordinator.async_close_realtime_watches()
        await client.aclose()
        if runtime_data is not None and getattr(entry, "runtime_data", None) is runtime_data:
            del entry.runtime_data
        raise
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: OkConfigEntry) -> bool:
    """Clean up legacy OK config entry data."""
    from .config_flow import OkConfigFlow

    if entry.version > OkConfigFlow.VERSION or (
        entry.version == OkConfigFlow.VERSION and entry.minor_version > OkConfigFlow.MINOR_VERSION
    ):
        return False

    hass.config_entries.async_update_entry(
        entry,
        data=_legacy_cleaned_data(entry.data),
        title=_entry_title_from_data(entry.data),
        version=OkConfigFlow.VERSION,
        minor_version=OkConfigFlow.MINOR_VERSION,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OkConfigEntry) -> bool:
    """Unload an OK config entry."""
    from .const import PLATFORMS

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.coordinator.async_close_realtime_watches()
        await entry.runtime_data.client.aclose()
    return bool(unload_ok)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: OkConfigEntry,
    device_entry: Any,
) -> bool:
    """Allow users to remove stale OK charger devices manually."""
    coordinator = entry.runtime_data.coordinator
    if coordinator.data is None:
        return False

    ok_identifiers = {
        identifier for identifier in device_entry.identifiers if identifier[0] == DOMAIN
    }
    if not ok_identifiers:
        return True

    current_identifiers = {
        (DOMAIN, connector.station_id)
        for connector in coordinator.connectors()
        if connector.station_id
    }
    account_id = entry.unique_id or entry.entry_id
    current_identifiers.add((DOMAIN, f"account_{account_id}"))
    return ok_identifiers.isdisjoint(current_identifiers)


async def _async_update_listener(hass: HomeAssistant, entry: OkConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _update_legacy_config_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = _legacy_cleaned_data(entry.data)
    title = _entry_title_from_data(data)
    if data == entry.data and entry.title == title:
        return
    hass.config_entries.async_update_entry(entry, data=data, title=title)


def _legacy_cleaned_data(data: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = dict(data)
    for key in _LEGACY_CONFIG_KEYS:
        cleaned.pop(key, None)
    return cleaned


def _entry_title_from_data(data: Mapping[str, Any]) -> str:
    email = data.get(CONF_EMAIL)
    if isinstance(email, str) and email:
        return f"OK ({email})"
    return "OK"


def _cleanup_removed_or_disabled_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove registry entries for entities that were removed or disabled."""
    from homeassistant.const import Platform
    from homeassistant.helpers import entity_registry as er

    from .button import BUTTON_DESCRIPTIONS
    from .const import (
        CONF_ENABLE_CONTROL_BUTTONS,
        CONF_ENABLE_ENERGY_PRICES,
        CONF_INCLUDE_RECEIPTS,
        DOMAIN,
    )
    from .sensor import SENSOR_DESCRIPTIONS

    disabled_keys: dict[str, set[str]] = {
        Platform.DATETIME.value: {"schedule_start", "schedule_end"},
        Platform.SENSOR.value: {"schedule_start", "schedule_end"},
    }
    if entry.options.get(CONF_INCLUDE_RECEIPTS, True) is False:
        disabled_keys[Platform.SENSOR.value].update(
            description.key for description in SENSOR_DESCRIPTIONS if description.receipt_required
        )
    if entry.options.get(CONF_ENABLE_ENERGY_PRICES, True) is False:
        disabled_keys.setdefault(Platform.SENSOR.value, set()).update(
            description.key
            for description in SENSOR_DESCRIPTIONS
            if description.energy_price_required
        )
    if entry.options.get(CONF_ENABLE_CONTROL_BUTTONS, True) is False:
        disabled_keys[Platform.BUTTON.value] = {
            description.key for description in BUTTON_DESCRIPTIONS if description.control_button
        }
    if not disabled_keys:
        return

    if not hasattr(hass, "data"):
        return
    registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registry_entry.platform != DOMAIN:
            continue
        entity_domain = registry_entry.entity_id.partition(".")[0]
        keys = disabled_keys.get(entity_domain)
        if keys is None or not _unique_id_ends_with_key(registry_entry.unique_id, keys):
            continue
        registry.async_remove(registry_entry.entity_id)


def _unique_id_ends_with_key(unique_id: str, keys: set[str]) -> bool:
    return any(unique_id == key or unique_id.endswith(f"_{key}") for key in keys)


def _client_from_entry(hass: HomeAssistant, entry: ConfigEntry) -> AsyncOkApiClient:
    from homeassistant.const import __version__
    from homeassistant.helpers.httpx_client import get_async_client

    from .const import (
        APP_PLATFORM,
        APP_SECRET,
        CONF_APP_ID,
        CONF_DEVICE_FRIENDLY_ID,
        CONF_DEVICE_ID,
    )

    config = OkApiConfig(
        app_id=entry.data.get(CONF_APP_ID),
        app_secret=APP_SECRET,
        device_id=entry.data.get(CONF_DEVICE_ID),
        device_friendly_id=entry.data.get(CONF_DEVICE_FRIENDLY_ID),
        app_platform=APP_PLATFORM,
        app_version=__version__,
    )

    async def run_blocking_call[T](func: Callable[[], T]) -> T:
        return cast(T, await hass.async_add_executor_job(func))

    return AsyncOkApiClient(
        config=config,
        http_client=get_async_client(hass),
        blocking_call_runner=run_blocking_call,
    )


def _register_services(hass: HomeAssistant) -> None:
    from .action import (
        async_call_ok_api,
        validate_command_response,
    )
    from .const import (
        ATTR_AUTOSTART,
        ATTR_SCHEDULED_END,
        ATTR_SCHEDULED_START,
        DOMAIN,
        SERVICE_CANCEL_CHARGING_SCHEDULE,
        SERVICE_RESTART,
        SERVICE_SCHEDULE_CHARGING,
        SERVICE_SET_AUTO_START,
        SERVICE_START_CHARGING,
        SERVICE_STOP_CHARGING,
        SERVICE_UPDATE_CHARGING_SCHEDULE,
    )

    async def start_charging(call: ServiceCall) -> None:
        target = _target_from_call(hass, call)
        response = await async_call_ok_api(
            target.runtime.client.start_charging(
                charging_station_id=target.station_id,
                connector_id=target.connector_id,
            ),
            hass=hass,
            entry=target.entry,
        )
        validate_command_response(response)
        await target.runtime.coordinator.async_request_operational_refresh()

    async def schedule_charging(call: ServiceCall) -> None:
        target = _target_from_call(hass, call)
        scheduled_start, scheduled_end = _schedule_window_from_call(hass, call)
        response = await async_call_ok_api(
            target.runtime.client.schedule_charging(
                charging_station_id=target.station_id,
                connector_id=target.connector_id,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
            ),
            hass=hass,
            entry=target.entry,
        )
        validate_command_response(response)
        await target.runtime.coordinator.async_request_operational_refresh()

    async def update_charging_schedule(call: ServiceCall) -> None:
        target = _target_from_call(hass, call)
        token = _active_charging_token(target)
        scheduled_start, scheduled_end = _schedule_window_from_call(hass, call)
        await async_call_ok_api(
            target.runtime.client.update_charging_schedule(
                token,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
            ),
            hass=hass,
            entry=target.entry,
        )
        await target.runtime.coordinator.async_request_operational_refresh()

    async def cancel_charging_schedule(call: ServiceCall) -> None:
        target = _target_from_call(hass, call)
        await async_call_ok_api(
            target.runtime.client.cancel_charging_schedule(_active_charging_token(target)),
            hass=hass,
            entry=target.entry,
        )
        await target.runtime.coordinator.async_request_operational_refresh()

    async def stop_charging(call: ServiceCall) -> None:
        target = _target_from_call(hass, call)
        await async_call_ok_api(
            target.runtime.client.stop_charging(_active_charging_token(target)),
            hass=hass,
            entry=target.entry,
        )
        await target.runtime.coordinator.async_request_operational_refresh()

    async def restart(call: ServiceCall) -> None:
        target = _target_from_call(hass, call)
        await async_call_ok_api(
            target.runtime.client.restart_station(target.station_id),
            hass=hass,
            entry=target.entry,
        )
        await target.runtime.coordinator.async_request_operational_refresh()

    async def set_auto_start(call: ServiceCall) -> None:
        target = _target_from_call(hass, call)
        await async_call_ok_api(
            target.runtime.client.set_station_auto_start(
                target.station_id,
                call.data[ATTR_AUTOSTART],
            ),
            hass=hass,
            entry=target.entry,
        )
        await target.runtime.coordinator.async_request_station_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_CHARGING,
        start_charging,
        schema=_entity_schema(),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCHEDULE_CHARGING,
        schedule_charging,
        schema=_entity_schema(
            {
                _vol().Required(ATTR_SCHEDULED_START): _cv().datetime,
                _vol().Required(ATTR_SCHEDULED_END): _cv().datetime,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_CHARGING_SCHEDULE,
        update_charging_schedule,
        schema=_entity_schema(
            {
                _vol().Required(ATTR_SCHEDULED_START): _cv().datetime,
                _vol().Required(ATTR_SCHEDULED_END): _cv().datetime,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_CHARGING_SCHEDULE,
        cancel_charging_schedule,
        schema=_entity_schema(),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_CHARGING,
        stop_charging,
        schema=_entity_schema(),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTART,
        restart,
        schema=_entity_schema(),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_AUTO_START,
        set_auto_start,
        schema=_entity_schema({_vol().Required(ATTR_AUTOSTART): _cv().boolean}),
    )


def _entry_from_entry_id(hass: HomeAssistant, entry_id: str) -> OkConfigEntry:
    from homeassistant.exceptions import ServiceValidationError

    from .const import DOMAIN

    for entry in _loaded_entries(hass):
        if entry.entry_id == entry_id:
            return entry
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="entry_not_loaded",
        translation_placeholders={"config_entry_id": entry_id},
    )


def _loaded_entries(hass: HomeAssistant) -> list[OkConfigEntry]:
    from homeassistant.config_entries import ConfigEntryState

    from .const import DOMAIN

    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED and hasattr(entry, "runtime_data")
    ]


def _target_from_call(hass: HomeAssistant, call: ServiceCall) -> OkServiceTarget:
    from homeassistant.const import ATTR_ENTITY_ID
    from homeassistant.exceptions import ServiceValidationError
    from homeassistant.helpers import entity_registry as er

    from .const import (
        ATTR_CHARGER_ID,
        ATTR_CONNECTOR_ID,
        DOMAIN,
    )

    entity_id = call.data[ATTR_ENTITY_ID]
    registry_entry = er.async_get(hass).async_get(entity_id)
    if registry_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={ATTR_ENTITY_ID: entity_id},
        )
    if registry_entry.platform != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_ok",
            translation_placeholders={ATTR_ENTITY_ID: entity_id},
        )
    if registry_entry.config_entry_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_missing_config_entry",
            translation_placeholders={ATTR_ENTITY_ID: entity_id},
        )
    entry = _entry_from_entry_id(hass, registry_entry.config_entry_id)
    runtime = cast(OkRuntimeData, entry.runtime_data)

    state = hass.states.get(entity_id)
    if state is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={ATTR_ENTITY_ID: entity_id},
        )

    station_id = state.attributes.get(ATTR_CHARGER_ID)
    connector_id = state.attributes.get(ATTR_CONNECTOR_ID)
    if not isinstance(station_id, str) or not station_id:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_missing_connector",
            translation_placeholders={ATTR_ENTITY_ID: entity_id},
        )
    try:
        connector_id = int(connector_id)
    except (TypeError, ValueError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_missing_connector",
            translation_placeholders={ATTR_ENTITY_ID: entity_id},
        ) from err
    if connector_id <= 0:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_missing_connector",
            translation_placeholders={ATTR_ENTITY_ID: entity_id},
        )

    if not any(
        connector.station_id == station_id and connector.connector_id == connector_id
        for connector in runtime.coordinator.connectors()
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="connector_not_found",
            translation_placeholders={ATTR_ENTITY_ID: entity_id},
        )

    return OkServiceTarget(
        entry=entry,
        runtime=runtime,
        station_id=station_id,
        connector_id=connector_id,
    )


def _active_charging_token(target: OkServiceTarget) -> str:
    from homeassistant.exceptions import ServiceValidationError

    from .action import active_charging_token
    from .const import DOMAIN

    charging = target.runtime.coordinator.active_charging_for(
        target.station_id,
        target.connector_id,
    )
    token = active_charging_token(charging)
    if token is not None:
        return token

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="active_charging_not_found",
    )


def _schedule_window_from_call(hass: HomeAssistant, call: ServiceCall) -> tuple[str, str]:
    from homeassistant.exceptions import ServiceValidationError

    from .const import ATTR_SCHEDULED_END, ATTR_SCHEDULED_START, DOMAIN

    scheduled_start = _schedule_datetime(hass, call.data[ATTR_SCHEDULED_START])
    scheduled_end = _schedule_datetime(hass, call.data[ATTR_SCHEDULED_END])
    if scheduled_end <= scheduled_start:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_schedule_window",
        )
    return (
        scheduled_start.isoformat(),
        scheduled_end.isoformat(),
    )


def _schedule_datetime(hass: HomeAssistant, value: datetime | str) -> datetime:
    from homeassistant.util import dt as dt_util

    if isinstance(value, str):
        value = cast(datetime, _cv().datetime(value))
    if value.tzinfo is None or value.utcoffset() is None:
        time_zone = dt_util.get_time_zone(hass.config.time_zone) or dt_util.DEFAULT_TIME_ZONE
        value = value.replace(tzinfo=time_zone)
    return value


def _entity_schema(extra: dict[Any, Any] | None = None) -> Any:
    from homeassistant.const import ATTR_ENTITY_ID

    fields: dict[Any, Any] = {_vol().Required(ATTR_ENTITY_ID): _cv().entity_id}
    if extra:
        fields.update(extra)
    return _vol().Schema(fields)


def _vol() -> Any:
    import voluptuous as vol

    return vol


def _cv() -> Any:
    from homeassistant.helpers import config_validation as cv

    return cv
