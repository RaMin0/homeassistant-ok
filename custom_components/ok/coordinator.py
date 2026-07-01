from __future__ import annotations

import logging
from asyncio import CancelledError, Lock, Task, TimerHandle, current_task, gather
from collections import deque
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from inspect import isawaitable, signature
from time import monotonic
from typing import Any, Literal, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AsyncFirestoreWatchSubscription,
    AsyncOkApiClient,
    ChargingLocation,
    ChargingReceipt,
    CurrentCharging,
    DeviceSettingsResponse,
    FirestoreDocument,
    FirestoreWatchEvent,
    OkAuthenticationError,
    OkConfigurationError,
    OkConnectionError,
    OkPermissionDeniedError,
    OkRateLimitError,
    OkResponseError,
    OkStatusError,
    OkTimeoutError,
    StationPricesResponse,
)
from .const import (
    CONF_ENABLE_ENERGY_PRICES,
    CONF_ENABLE_REALTIME_UPDATES,
    CONF_INCLUDE_RECEIPTS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_COORDINATOR_HEARTBEAT = timedelta(seconds=60)
_STATIONS_REFRESH_INTERVAL = timedelta(minutes=30)
_PRICE_REFRESH_INTERVAL = timedelta(minutes=30)
_ACTIVE_CHARGINGS_REFRESH_INTERVAL = timedelta(seconds=60)
_IDLE_CHARGINGS_REFRESH_INTERVAL = timedelta(minutes=5)
_RECEIPTS_REFRESH_INTERVAL = timedelta(hours=12)
_RATE_LIMIT_BACKOFF_FALLBACK = 300
_REALTIME_REFRESH_DELAY = 5
_REALTIME_WATCH_RETRY_BASE_DELAY = 15
_REALTIME_WATCH_RETRY_MAX_DELAY = 300
_REALTIME_WATCH_ISSUE_ID = "realtime_updates_unavailable"
_STALE_DEVICE_REMOVE_THRESHOLD = 3
type RefreshTrigger = Literal[
    "automatic",
    "force_refresh",
    "service_action",
    "realtime_reconcile",
    "setup",
]
_SOURCE_ACCOUNT_SETTINGS = "account_settings"
_SOURCE_STATIONS = "stations"
_SOURCE_PRICES = "prices"
_SOURCE_CHARGINGS = "chargings"
_SOURCE_RECEIPTS = "receipts"
_REFRESH_TRIGGER_AUTOMATIC: RefreshTrigger = "automatic"
_REFRESH_TRIGGER_FORCE: RefreshTrigger = "force_refresh"
_REFRESH_TRIGGER_SERVICE_ACTION: RefreshTrigger = "service_action"
_REFRESH_TRIGGER_REALTIME_RECONCILE: RefreshTrigger = "realtime_reconcile"
_REFRESH_TRIGGER_SETUP: RefreshTrigger = "setup"
_ACCOUNT_POLL_ATTRIBUTE_SOURCES = (
    ("account_settings", _SOURCE_ACCOUNT_SETTINGS),
    ("charger_overview", _SOURCE_STATIONS),
    ("energy_prices", _SOURCE_PRICES),
    ("active_sessions", _SOURCE_CHARGINGS),
    ("charging_receipts", _SOURCE_RECEIPTS),
)
_POLL_TRIGGER_ATTRIBUTE_VALUES: Mapping[RefreshTrigger, str] = {
    _REFRESH_TRIGGER_AUTOMATIC: "automatic",
    _REFRESH_TRIGGER_FORCE: "manual",
    _REFRESH_TRIGGER_SERVICE_ACTION: "service_action",
    _REFRESH_TRIGGER_REALTIME_RECONCILE: "realtime_reconcile",
    _REFRESH_TRIGGER_SETUP: "setup",
}

type _RealtimeWatchKey = tuple[Literal["charging"], str] | tuple[Literal["station"], str, int]


@dataclass(frozen=True, slots=True)
class _RealtimeWatchFailure:
    attempts: int
    retry_at: float


@dataclass(slots=True)
class _RealtimeWatchHandle:
    key: _RealtimeWatchKey
    subscription: AsyncFirestoreWatchSubscription
    task: Task[None]


@dataclass(frozen=True, slots=True)
class OkConnectorRef:
    location: Mapping[str, Any]
    station: Mapping[str, Any]
    connector: Mapping[str, Any]

    @property
    def station_id(self) -> str:
        value = self.station.get("csIdentifier")
        return value if isinstance(value, str) and value else ""

    @property
    def connector_id(self) -> int:
        value = self.connector.get("connectorId")
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        return 0


@dataclass(frozen=True, slots=True)
class OkData:
    settings: DeviceSettingsResponse | None
    locations: tuple[ChargingLocation, ...]
    prices: dict[str, StationPricesResponse] = field(default_factory=dict)
    station_status: dict[tuple[str, int], FirestoreDocument] = field(default_factory=dict)
    current_chargings: tuple[CurrentCharging, ...] = ()
    charging_status: dict[str, FirestoreDocument] = field(default_factory=dict)
    receipts: tuple[ChargingReceipt, ...] = ()


class OkDataUpdateCoordinator(DataUpdateCoordinator[OkData]):  # type: ignore[misc]
    """Coordinate OK API polling."""

    settings: DeviceSettingsResponse | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AsyncOkApiClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=_COORDINATOR_HEARTBEAT,
            always_update=False,
        )
        self.client = client
        self.entry = entry
        self._refresh_lock = Lock()
        self._refresh_in_progress = False
        self._explicit_refreshes_pending = 0
        self._refresh_triggers: deque[RefreshTrigger] = deque()
        self._last_refresh_trigger: RefreshTrigger | None = None
        self._refresh_generation = 0
        self._force_full_refresh_pending = False
        self._last_refresh: dict[str, float] = {}
        self._last_refresh_wall: dict[str, datetime] = {}
        self._endpoint_backoff_until: dict[str, float] = {}
        self._force_stations_refresh = False
        self._force_prices_refresh = False
        self._force_chargings_refresh = False
        self._force_receipts_refresh = False
        self._force_realtime_snapshots = False
        self._quick_receipt_tokens: set[str] = set()
        self._realtime_watch_handles: dict[_RealtimeWatchKey, _RealtimeWatchHandle] = {}
        self._realtime_watch_failures: dict[_RealtimeWatchKey, _RealtimeWatchFailure] = {}
        self._realtime_watches_unavailable = False
        self._api_unavailable_logged = False
        self._realtime_refresh_handle: TimerHandle | None = None
        self._realtime_retry_handle: TimerHandle | None = None
        self._realtime_refresh_task: Task[None] | None = None
        self._missing_device_refreshes: dict[str, int] = {}
        self._closing_realtime_watches = False

    async def _async_setup(self) -> None:
        now = monotonic()
        self.settings = await self._call_api(self.client.get_device_settings())
        self._mark_refreshed(_SOURCE_ACCOUNT_SETTINGS, now)
        self._queue_refresh_trigger(_REFRESH_TRIGGER_SETUP)

    @property
    def _energy_prices_enabled(self) -> bool:
        return self.entry.options.get(CONF_ENABLE_ENERGY_PRICES, True) is not False

    @property
    def _realtime_updates_enabled(self) -> bool:
        return self.entry.options.get(CONF_ENABLE_REALTIME_UPDATES, True) is not False

    async def _async_update_data(self) -> OkData:
        async with self._refresh_lock:
            self._set_refresh_active(True)
            try:
                return await self._async_update_data_locked()
            finally:
                self._set_refresh_active(False)

    async def _async_update_data_locked(self) -> OkData:
        now = monotonic()
        refresh_generation = self._refresh_generation
        refresh_trigger = self._next_refresh_trigger()
        previous = self.data
        locations = await self._async_locations(now)
        prices = await self._async_prices(locations, now)
        station_status = self._station_status_from_cache(locations)
        for connector_ref in _iter_connectors(locations):
            station_id = connector_ref.station_id
            connector_id = connector_ref.connector_id
            if station_id and connector_id:
                key = (station_id, connector_id)
                if self._should_fetch_realtime_snapshot(("station", station_id, connector_id), key):
                    document = await self._call_api(
                        self.client.get_charging_station_status(station_id, connector_id)
                    )
                    self._mark_refreshed(
                        _connector_status_source(station_id, connector_id),
                        now,
                    )
                    station_status[key] = _newest_document(station_status.get(key), document)

        current_chargings = await self._async_current_chargings(now)
        charging_status = self._charging_status_from_cache(current_chargings)
        for charging in current_chargings:
            token = _charging_status_token(charging)
            if token is not None:
                if self._should_fetch_realtime_snapshot(("charging", token), token):
                    document = await self._call_api(self.client.get_charging_status(token))
                    if (connector_key := _charging_connector_key(charging)) is not None:
                        self._mark_refreshed(
                            _session_status_source(*connector_key),
                            now,
                        )
                    charging_status[token] = _newest_document(charging_status.get(token), document)
        self._force_realtime_snapshots = False

        receipts = await self._async_receipts(previous, current_chargings, now)

        data = OkData(
            settings=self.settings,
            locations=locations,
            prices=prices,
            station_status=station_status,
            current_chargings=current_chargings,
            charging_status=charging_status,
            receipts=receipts,
        )
        await self._async_remove_stale_devices(data)
        self._log_api_recovered_once()
        await self._async_sync_realtime_watches(data)
        if self._refresh_generation != refresh_generation:
            self._last_refresh_trigger = refresh_trigger
        return data

    async def _async_locations(self, now: float) -> tuple[ChargingLocation, ...]:
        if (
            self.data is None
            or self._force_stations_refresh
            or self._is_due(_SOURCE_STATIONS, _STATIONS_REFRESH_INTERVAL, now)
        ):
            locations = tuple(await self._call_api(self.client.get_stations()))
            self._mark_refreshed(_SOURCE_STATIONS, now)
            self._force_stations_refresh = False
            return locations
        return cast(OkData, self.data).locations

    async def _async_prices(
        self,
        locations: tuple[ChargingLocation, ...],
        now: float,
    ) -> dict[str, StationPricesResponse]:
        if not self._energy_prices_enabled:
            self._force_prices_refresh = False
            return {}

        station_ids = {
            connector.station_id
            for connector in _iter_connectors(locations)
            if connector.station_id
        }
        prices: dict[str, StationPricesResponse] = {}
        if self.data is not None:
            prices.update(
                {
                    station_id: response
                    for station_id, response in self.data.prices.items()
                    if station_id in station_ids
                }
            )

        for station_id in station_ids:
            source = _price_source(station_id)
            if (
                station_id in prices
                and not self._force_prices_refresh
                and not self._is_due(source, _PRICE_REFRESH_INTERVAL, now)
            ):
                continue

            async def get_station_prices(station_id: str = station_id) -> StationPricesResponse:
                return await self.client.get_station_prices(station_id)

            response = await self._call_optional_api(
                source,
                get_station_prices,
                now,
            )
            if response is None:
                continue
            prices[station_id] = response
            self._mark_refreshed(source, now)
            self._mark_refreshed(_SOURCE_PRICES, now)
        self._force_prices_refresh = False
        return prices

    async def _async_current_chargings(self, now: float) -> tuple[CurrentCharging, ...]:
        interval = (
            _ACTIVE_CHARGINGS_REFRESH_INTERVAL
            if self.data is not None and self.data.current_chargings
            else _IDLE_CHARGINGS_REFRESH_INTERVAL
        )
        if (
            self.data is None
            or self._force_chargings_refresh
            or self._is_due(_SOURCE_CHARGINGS, interval, now)
        ):
            current_chargings = tuple(await self._call_api(self.client.get_chargings()))
            self._mark_refreshed(_SOURCE_CHARGINGS, now)
            self._force_chargings_refresh = False
            return current_chargings
        return cast(OkData, self.data).current_chargings

    async def _async_receipts(
        self,
        previous: OkData | None,
        current_chargings: tuple[CurrentCharging, ...],
        now: float,
    ) -> tuple[ChargingReceipt, ...]:
        if self.entry.options.get(CONF_INCLUDE_RECEIPTS, True) is False:
            self._force_receipts_refresh = False
            return ()

        receipts = previous.receipts if previous is not None else ()
        if (
            previous is None
            or self._force_receipts_refresh
            or self._is_due(_SOURCE_RECEIPTS, _RECEIPTS_REFRESH_INTERVAL, now)
        ):
            response = await self._call_optional_api(
                _SOURCE_RECEIPTS,
                self.client.get_charging_receipts,
                now,
            )
            if response is not None:
                receipts = tuple(response)
                self._mark_refreshed(_SOURCE_RECEIPTS, now)
            self._force_receipts_refresh = False
            return receipts

        for charging in _finished_chargings(previous.current_chargings, current_chargings):
            token = _charging_token(charging)
            if token is None or token in self._quick_receipt_tokens:
                continue
            charging_token = token

            async def get_charging_receipt(token: str = charging_token) -> ChargingReceipt:
                return await self.client.get_charging_receipt(token)

            receipt = await self._call_optional_api(
                _quick_receipt_source(charging_token),
                get_charging_receipt,
                now,
            )
            if receipt is None:
                continue
            receipt = _normalize_quick_receipt(receipt)
            receipts = _merge_receipt(receipts, receipt)
            self._quick_receipt_tokens.add(charging_token)
            station_id = receipt.get("chargingStationId") or charging.get("csIdentifier")
            if isinstance(station_id, str) and station_id:
                self._mark_refreshed(_session_receipt_source(station_id), now)
        return receipts

    def _is_due(self, source: str, interval: timedelta, now: float) -> bool:
        refreshed_at = self._last_refresh.get(source)
        return refreshed_at is None or now - refreshed_at >= interval.total_seconds()

    def _mark_refreshed(self, source: str, now: float) -> None:
        self._last_refresh[source] = now
        self._last_refresh_wall[source] = datetime.now(UTC)
        self._refresh_generation += 1

    async def _call_optional_api[T](
        self,
        source: str,
        api_call: Callable[[], Awaitable[T]],
        now: float,
    ) -> T | None:
        if self._is_backing_off(source, now):
            return None
        try:
            return await api_call()
        except (OkAuthenticationError, OkPermissionDeniedError) as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except OkRateLimitError as err:
            retry_at = self._record_rate_limit_backoff(source, err, now)
            _LOGGER.info(
                "OK API endpoint %s is rate limited; reusing cached data for %s seconds",
                source,
                round(retry_at - now),
            )
        except (OkConnectionError, OkTimeoutError, OkResponseError, OkStatusError) as err:
            _LOGGER.debug("OK optional API endpoint %s failed: %s", source, err)
        return None

    def _is_backing_off(self, source: str, now: float) -> bool:
        retry_at = self._endpoint_backoff_until.get(source)
        if retry_at is None:
            return False
        if retry_at <= now:
            self._endpoint_backoff_until.pop(source, None)
            return False
        return True

    def _record_rate_limit_backoff(
        self,
        source: str,
        err: OkRateLimitError,
        now: float,
    ) -> float:
        delay = _retry_after(err) or _RATE_LIMIT_BACKOFF_FALLBACK
        retry_at = now + delay
        self._endpoint_backoff_until[source] = retry_at
        return retry_at

    def next_price_update_for(self, station_id: str) -> datetime | None:
        refreshed_at = self._last_refresh_wall.get(_price_source(station_id))
        if refreshed_at is None:
            return None
        return refreshed_at + _PRICE_REFRESH_INTERVAL

    async def async_request_operational_refresh(self) -> None:
        """Request a refresh of data that can change after charging actions."""
        await self._async_refresh_with_trigger(
            _REFRESH_TRIGGER_SERVICE_ACTION,
            lambda: setattr(self, "_force_chargings_refresh", True),
        )

    async def async_request_station_refresh(self) -> None:
        """Request a refresh of charger metadata."""
        await self._async_refresh_with_trigger(
            _REFRESH_TRIGGER_SERVICE_ACTION,
            lambda: setattr(self, "_force_stations_refresh", True),
        )

    async def async_force_full_refresh(self) -> None:
        """Force all REST-backed data sources to refresh."""
        if self._force_full_refresh_pending:
            return
        self._force_full_refresh_pending = True
        try:
            await self._async_refresh_with_trigger(
                _REFRESH_TRIGGER_FORCE,
                self._prepare_force_full_refresh,
            )
        finally:
            self._force_full_refresh_pending = False

    def _prepare_force_full_refresh(self) -> None:
        self._force_stations_refresh = True
        self._force_prices_refresh = True
        self._force_chargings_refresh = True
        self._force_receipts_refresh = True
        self._force_realtime_snapshots = True

    async def _async_refresh_with_trigger(
        self,
        trigger: RefreshTrigger,
        prepare_refresh: Callable[[], None] | None = None,
    ) -> None:
        self._queue_refresh_trigger(trigger)
        self._change_explicit_refreshes_pending(1)
        try:
            if prepare_refresh is not None:
                async with self._refresh_lock:
                    prepare_refresh()
            await self.async_refresh()
        finally:
            self._change_explicit_refreshes_pending(-1)

    def _queue_refresh_trigger(self, trigger: RefreshTrigger) -> None:
        self._refresh_triggers.append(trigger)

    def _next_refresh_trigger(self) -> RefreshTrigger:
        if self._refresh_triggers:
            return self._refresh_triggers.popleft()
        return _REFRESH_TRIGGER_AUTOMATIC

    @property
    def refresh_in_progress(self) -> bool:
        return self._refresh_in_progress or self._explicit_refreshes_pending > 0

    def _set_refresh_active(self, in_progress: bool) -> None:
        previous = self.refresh_in_progress
        self._refresh_in_progress = in_progress
        self._notify_refresh_state_change(previous)

    def _change_explicit_refreshes_pending(self, delta: int) -> None:
        previous = self.refresh_in_progress
        self._explicit_refreshes_pending = max(0, self._explicit_refreshes_pending + delta)
        self._notify_refresh_state_change(previous)

    def _notify_refresh_state_change(self, previous: bool) -> None:
        if self.refresh_in_progress != previous:
            self.async_update_listeners()

    @property
    def last_refresh(self) -> datetime | None:
        refresh_times = [
            refreshed_at
            for _, source in _ACCOUNT_POLL_ATTRIBUTE_SOURCES
            if (refreshed_at := self._last_refresh_wall.get(source)) is not None
        ]
        if not refresh_times:
            return None
        return max(refresh_times)

    @property
    def poll_attributes(self) -> Mapping[str, Any]:
        return {
            **{
                attribute: refreshed_at.isoformat() if refreshed_at is not None else None
                for attribute, source in _ACCOUNT_POLL_ATTRIBUTE_SOURCES
                for refreshed_at in (self._last_refresh_wall.get(source),)
            },
            "trigger": (
                _POLL_TRIGGER_ATTRIBUTE_VALUES[self._last_refresh_trigger]
                if self._last_refresh_trigger is not None
                else None
            ),
            "in_progress": self.refresh_in_progress,
        }

    def charger_last_refresh(self, station_id: str) -> datetime | None:
        refresh_times = [
            refreshed_at
            for source in self._charger_poll_attribute_sources(station_id)
            if (refreshed_at := self._last_refresh_wall.get(source)) is not None
        ]
        if not refresh_times:
            return None
        return max(refresh_times)

    def charger_poll_attributes(self, station_id: str) -> Mapping[str, Any]:
        connectors = sorted(
            (connector for connector in self.connectors() if connector.station_id == station_id),
            key=lambda connector: connector.connector_id,
        )
        charger_status = {
            connector.connector_id: self._poll_attribute(
                _connector_status_source(station_id, connector.connector_id)
            )
            for connector in connectors
        }
        session_status = {
            connector.connector_id: self._poll_attribute(
                _session_status_source(station_id, connector.connector_id)
            )
            for connector in connectors
        }
        return {
            "charger_status": _single_connector_refresh_value(charger_status),
            "session_status": _single_connector_refresh_value(session_status),
            "session_receipt": self._poll_attribute(_session_receipt_source(station_id)),
        }

    def _charger_poll_attribute_sources(self, station_id: str) -> Iterable[str]:
        connectors = sorted(
            (connector for connector in self.connectors() if connector.station_id == station_id),
            key=lambda connector: connector.connector_id,
        )
        for connector in connectors:
            yield _connector_status_source(
                station_id,
                connector.connector_id,
            )
            yield _session_status_source(
                station_id,
                connector.connector_id,
            )
        yield _session_receipt_source(station_id)

    def _poll_attribute(self, source: str) -> str | None:
        refreshed_at = self._last_refresh_wall.get(source)
        return refreshed_at.isoformat() if refreshed_at is not None else None

    def _station_status_from_cache(
        self,
        locations: tuple[ChargingLocation, ...],
    ) -> dict[tuple[str, int], FirestoreDocument]:
        if self.data is None:
            return {}
        desired = {
            (connector.station_id, connector.connector_id)
            for connector in _iter_connectors(locations)
            if connector.station_id and connector.connector_id
        }
        return {
            key: document for key, document in self.data.station_status.items() if key in desired
        }

    def _charging_status_from_cache(
        self,
        current_chargings: tuple[CurrentCharging, ...],
    ) -> dict[str, FirestoreDocument]:
        if self.data is None:
            return {}
        desired = {
            token
            for charging in current_chargings
            if (token := _charging_status_token(charging)) is not None
        }
        return {
            token: document
            for token, document in self.data.charging_status.items()
            if token in desired
        }

    def _should_fetch_realtime_snapshot(
        self,
        watch_key: _RealtimeWatchKey,
        cache_key: tuple[str, int] | str,
    ) -> bool:
        """Return whether a Firestore document needs a polled snapshot fallback."""
        if self._force_realtime_snapshots:
            return True
        if not self._realtime_updates_enabled:
            return True
        if self._realtime_watches_unavailable:
            return True
        if watch_key in self._realtime_watch_failures:
            return True
        if watch_key in self._realtime_watch_handles:
            return False
        if self.data is None:
            return True
        if watch_key[0] == "station":
            return cache_key not in self.data.station_status
        return cache_key not in self.data.charging_status

    async def _call_api(self, api_call: Any) -> Any:
        try:
            return await api_call
        except (OkAuthenticationError, OkPermissionDeniedError) as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except OkRateLimitError as err:
            self._log_api_unavailable_once(err)
            retry_after = _retry_after(err)
            if retry_after is None:
                raise UpdateFailed(str(err)) from err
            raise UpdateFailed(str(err), retry_after=retry_after) from err
        except (OkConnectionError, OkTimeoutError, OkResponseError, OkStatusError) as err:
            self._log_api_unavailable_once(err)
            raise UpdateFailed(str(err)) from err

    def _log_api_unavailable_once(self, err: Exception) -> None:
        if self._api_unavailable_logged:
            return
        self._api_unavailable_logged = True
        _LOGGER.info("OK API became unavailable: %s", err)

    def _log_api_recovered_once(self) -> None:
        if not self._api_unavailable_logged:
            return
        self._api_unavailable_logged = False
        _LOGGER.info("OK API became available again")

    async def _async_remove_stale_devices(self, data: OkData) -> None:
        """Remove OK charger devices that disappeared from the complete charger list."""
        from homeassistant.helpers import device_registry as dr

        charger_identifiers = {
            (DOMAIN, connector.station_id)
            for connector in _iter_connectors(data.locations)
            if connector.station_id
        }
        if not charger_identifiers:
            return
        current_identifiers = set(charger_identifiers)
        account_id = self.entry.unique_id or self.entry.entry_id
        current_identifiers.add((DOMAIN, f"account_{account_id}"))
        device_registry = await _async_get_device_registry(self.hass)
        for device in dr.async_entries_for_config_entry(device_registry, self.entry.entry_id):
            ok_identifiers = {
                identifier for identifier in device.identifiers if identifier[0] == DOMAIN
            }
            if not ok_identifiers:
                continue
            if not ok_identifiers.isdisjoint(current_identifiers):
                self._missing_device_refreshes.pop(device.id, None)
                continue
            missing_count = self._missing_device_refreshes.get(device.id, 0) + 1
            self._missing_device_refreshes[device.id] = missing_count
            if missing_count >= _STALE_DEVICE_REMOVE_THRESHOLD:
                device_registry.async_remove_device(device.id)
                self._missing_device_refreshes.pop(device.id, None)

    def connectors(self) -> tuple[OkConnectorRef, ...]:
        data = cast(OkData | None, self.data)
        if data is None:
            return ()
        return tuple(_iter_connectors(data.locations))

    def station_status_for(self, station_id: str, connector_id: int) -> FirestoreDocument | None:
        data = cast(OkData | None, self.data)
        if data is None:
            return None
        return data.station_status.get((station_id, connector_id))

    def active_charging_for(self, station_id: str, connector_id: int) -> CurrentCharging | None:
        data = cast(OkData | None, self.data)
        if data is None:
            return None
        for charging in data.current_chargings:
            if (
                charging.get("csIdentifier") == station_id
                and charging.get("connectorId") == connector_id
            ):
                return charging
        return None

    def charging_status_for(self, charging: CurrentCharging | None) -> FirestoreDocument | None:
        data = cast(OkData | None, self.data)
        if data is None or charging is None:
            return None
        token = _charging_status_token(charging)
        if token is None:
            return None
        return data.charging_status.get(token)

    def prices_for(self, station_id: str) -> StationPricesResponse | None:
        data = cast(OkData | None, self.data)
        if data is None:
            return None
        return data.prices.get(station_id)

    def last_receipt_for(self, station_id: str) -> ChargingReceipt | None:
        data = cast(OkData | None, self.data)
        if data is None:
            return None
        receipts = [item for item in data.receipts if item.get("chargingStationId") == station_id]
        if not receipts:
            return None
        return max(
            receipts,
            key=lambda item: _parse_datetime(item.get("chargingEnd")) or datetime.min,
        )

    def close_realtime_watches(self) -> None:
        """Schedule active Firestore realtime subscriptions to close."""
        self._closing_realtime_watches = True
        self._cancel_realtime_refresh()
        self._cancel_realtime_retry()
        self._cancel_realtime_refresh_task()
        for handle in self._drain_realtime_watch_handles():
            handle.task.cancel()
            self.hass.async_create_task(handle.subscription.aclose())
        self._realtime_watch_failures.clear()

    async def async_close_realtime_watches(self) -> None:
        """Close active Firestore realtime subscriptions without blocking the event loop."""
        self._closing_realtime_watches = True
        self._cancel_realtime_refresh()
        self._cancel_realtime_retry()
        await self._async_cancel_realtime_refresh_task()
        await self._async_close_realtime_watch_handles(self._drain_realtime_watch_handles())
        self._realtime_watch_failures.clear()

    async def _async_sync_realtime_watches(self, data: OkData) -> None:
        """Keep Firestore realtime watchers aligned with current coordinator data."""
        if not self._realtime_updates_enabled:
            self._cancel_realtime_refresh()
            self._cancel_realtime_retry()
            await self._async_cancel_realtime_refresh_task()
            await self._async_close_realtime_watch_handles(self._drain_realtime_watch_handles())
            self._realtime_watch_failures.clear()
            if self._realtime_watches_unavailable:
                self._async_delete_realtime_unavailable_issue()
            self._realtime_watches_unavailable = False
            return

        if self._realtime_watches_unavailable or self._closing_realtime_watches:
            return

        desired = _realtime_watch_keys(data)
        stale_handles = [
            self._realtime_watch_handles.pop(key)
            for key in set(self._realtime_watch_handles) - desired
        ]
        for key in set(self._realtime_watch_failures) - desired:
            self._realtime_watch_failures.pop(key, None)
        await self._async_close_realtime_watch_handles(stale_handles)

        now = monotonic()
        for key in sorted(
            desired - set(self._realtime_watch_handles),
            key=_realtime_watch_key_sort,
        ):
            if self._realtime_watches_unavailable:
                return
            failure = self._realtime_watch_failures.get(key)
            if failure is not None and failure.retry_at > now:
                continue
            await self._async_subscribe_realtime_watch(key)

    async def _async_subscribe_realtime_watch(self, key: _RealtimeWatchKey) -> None:
        if (
            not self._realtime_updates_enabled
            or self._realtime_watches_unavailable
            or self._closing_realtime_watches
        ):
            return
        try:
            subscription = await self._async_create_realtime_subscription(key)
        except OkConfigurationError as err:
            self._realtime_watches_unavailable = True
            await self.async_close_realtime_watches()
            self._async_create_realtime_unavailable_issue(err)
            _LOGGER.info("OK Firestore realtime updates are unavailable: %s", err)
            return
        except Exception as err:
            failure = self._record_realtime_watch_failure(key)
            log_level = logging.INFO if failure.attempts == 1 else logging.DEBUG
            if _LOGGER.isEnabledFor(log_level):
                _LOGGER.log(
                    log_level,
                    (
                        "OK Firestore realtime watcher for %s became unavailable: %s. "
                        "Retrying in %s seconds"
                    ),
                    _realtime_watch_label(key),
                    err,
                    round(failure.retry_at - monotonic()),
                )
            self._schedule_realtime_watch_retry(failure.retry_at)
            return
        if self._closing_realtime_watches:
            await self._async_close_realtime_subscription(key, subscription)
            return
        task = self.hass.async_create_background_task(
            self._async_consume_realtime_watch(key, subscription),
            name=f"OK realtime watcher {self.entry.entry_id} {key}",
        )
        self._realtime_watch_handles[key] = _RealtimeWatchHandle(
            key=key,
            subscription=subscription,
            task=task,
        )
        self._async_delete_realtime_unavailable_issue()
        if self._realtime_watch_failures.pop(key, None) is not None:
            _LOGGER.info(
                "OK Firestore realtime watcher for %s recovered",
                _realtime_watch_label(key),
            )

    def _async_create_realtime_unavailable_issue(self, err: OkConfigurationError) -> None:
        from homeassistant.helpers import issue_registry as ir

        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._realtime_watch_issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=_REALTIME_WATCH_ISSUE_ID,
            translation_placeholders={"reason": str(err) or err.__class__.__name__},
        )

    def _async_delete_realtime_unavailable_issue(self) -> None:
        from homeassistant.helpers import issue_registry as ir

        ir.async_delete_issue(self.hass, DOMAIN, self._realtime_watch_issue_id)

    @property
    def _realtime_watch_issue_id(self) -> str:
        return f"{_REALTIME_WATCH_ISSUE_ID}_{self.entry.entry_id}"

    def _record_realtime_watch_failure(self, key: _RealtimeWatchKey) -> _RealtimeWatchFailure:
        previous = self._realtime_watch_failures.get(key)
        attempts = 1 if previous is None else previous.attempts + 1
        delay = min(
            _REALTIME_WATCH_RETRY_MAX_DELAY,
            _REALTIME_WATCH_RETRY_BASE_DELAY * 2 ** (attempts - 1),
        )
        failure = _RealtimeWatchFailure(attempts=attempts, retry_at=monotonic() + delay)
        self._realtime_watch_failures[key] = failure
        return failure

    def _schedule_realtime_watch_retry(self, retry_at: float) -> None:
        if (
            self._realtime_retry_handle is not None
            and self._realtime_retry_handle.when() <= retry_at
        ):
            return
        self._cancel_realtime_retry()
        delay = max(0, retry_at - monotonic())
        self._realtime_retry_handle = self.hass.loop.call_later(delay, self._request_realtime_retry)

    def _cancel_realtime_retry(self) -> None:
        if self._realtime_retry_handle is None:
            return
        self._realtime_retry_handle.cancel()
        self._realtime_retry_handle = None

    def _request_realtime_retry(self) -> None:
        self._realtime_retry_handle = None
        if not self._realtime_updates_enabled:
            return
        self._create_realtime_refresh_task("retry")

    async def _async_create_realtime_subscription(
        self,
        key: _RealtimeWatchKey,
    ) -> AsyncFirestoreWatchSubscription:
        if key[0] == "station":
            _, station_id, connector_id = key
            return await self.client.watch_charging_station_status(
                station_id,
                connector_id,
            )

        _, charging_token = key
        return await self.client.watch_charging_status(charging_token)

    def _drain_realtime_watch_handles(self) -> tuple[_RealtimeWatchHandle, ...]:
        handles = tuple(self._realtime_watch_handles.values())
        self._realtime_watch_handles.clear()
        return handles

    async def _async_close_realtime_watch_handles(
        self,
        handles: Iterable[_RealtimeWatchHandle],
    ) -> None:
        handles = tuple(handles)
        if not handles:
            return
        for handle in handles:
            handle.task.cancel()
        await gather(
            *(
                self._async_close_realtime_subscription(handle.key, handle.subscription)
                for handle in handles
            ),
            return_exceptions=True,
        )
        await gather(*(handle.task for handle in handles), return_exceptions=True)

    async def _async_close_realtime_subscription(
        self,
        key: _RealtimeWatchKey,
        subscription: AsyncFirestoreWatchSubscription,
    ) -> None:
        try:
            await subscription.aclose()
        except Exception as err:
            _LOGGER.warning(
                "Failed to close OK Firestore realtime watcher for %s: %s",
                _realtime_watch_label(key),
                err,
            )

    async def _async_consume_realtime_watch(
        self,
        key: _RealtimeWatchKey,
        subscription: AsyncFirestoreWatchSubscription,
    ) -> None:
        try:
            async for event in subscription:
                if key[0] == "station":
                    _, station_id, connector_id = key
                    self._handle_station_status_event(station_id, connector_id, event)
                    continue
                _, charging_token = key
                self._handle_charging_status_event(charging_token, event)
        except CancelledError:
            raise
        except Exception as err:
            if (
                not self._closing_realtime_watches
                and self._realtime_watch_handles.get(key, None) is not None
            ):
                self._realtime_watch_handles.pop(key, None)
                await self._async_close_realtime_subscription(key, subscription)
                failure = self._record_realtime_watch_failure(key)
                _LOGGER.info(
                    "OK Firestore realtime watcher for %s stopped: %s. Retrying in %s seconds",
                    _realtime_watch_label(key),
                    err,
                    round(failure.retry_at - monotonic()),
                )
                self._schedule_realtime_watch_retry(failure.retry_at)

    def _handle_station_status_event(
        self,
        station_id: str,
        connector_id: int,
        event: FirestoreWatchEvent,
    ) -> None:
        if self.data is None:
            return

        key = (station_id, connector_id)
        station_status = dict(self.data.station_status)
        previous = station_status.get(key)
        document = event.document
        if not event.exists or document is None:
            self._force_chargings_refresh = True
            self._schedule_refresh_after_realtime_event()
            return

        document = _newest_document(previous, document)
        if document is previous:
            return
        station_status[key] = document

        if station_status == self.data.station_status:
            return

        self._mark_refreshed(_connector_status_source(station_id, connector_id), monotonic())
        self.async_set_updated_data(replace(self.data, station_status=station_status))
        if _status_changed(previous, document):
            self._force_chargings_refresh = True
            self._schedule_refresh_after_realtime_event()

    def _handle_charging_status_event(
        self,
        charging_token: str,
        event: FirestoreWatchEvent,
    ) -> None:
        if self.data is None:
            return

        charging_status = dict(self.data.charging_status)
        previous = charging_status.get(charging_token)
        document = event.document
        if not event.exists or document is None:
            self._force_chargings_refresh = True
            self._schedule_refresh_after_realtime_event()
            return

        document = _newest_document(previous, document)
        if document is previous:
            return
        charging_status[charging_token] = document

        if charging_status == self.data.charging_status:
            return

        charging = self._active_charging_for_token(charging_token)
        if charging is not None and (connector_key := _charging_connector_key(charging)):
            self._mark_refreshed(_session_status_source(*connector_key), monotonic())
        self.async_set_updated_data(replace(self.data, charging_status=charging_status))
        if _status_changed(previous, document):
            self._force_chargings_refresh = True
            self._schedule_refresh_after_realtime_event()

    def _active_charging_for_token(self, charging_token: str) -> CurrentCharging | None:
        data = cast(OkData | None, self.data)
        if data is None:
            return None
        for charging in data.current_chargings:
            if _charging_status_token(charging) == charging_token:
                return charging
        return None

    def _schedule_refresh_after_realtime_event(self) -> None:
        if not self._realtime_updates_enabled:
            return
        self._cancel_realtime_refresh()
        self._realtime_refresh_handle = self.hass.loop.call_later(
            _REALTIME_REFRESH_DELAY,
            self._request_realtime_refresh,
        )

    def _cancel_realtime_refresh(self) -> None:
        if self._realtime_refresh_handle is None:
            return
        self._realtime_refresh_handle.cancel()
        self._realtime_refresh_handle = None

    def _request_realtime_refresh(self) -> None:
        self._realtime_refresh_handle = None
        self._create_realtime_refresh_task("event")

    def _create_realtime_refresh_task(self, reason: str) -> None:
        if not self._realtime_updates_enabled or self._closing_realtime_watches:
            return
        task = self._realtime_refresh_task
        if task is not None and not task.done():
            return
        self._realtime_refresh_task = self.hass.async_create_background_task(
            self._async_request_realtime_refresh(),
            name=f"OK realtime {reason} refresh {self.entry.entry_id}",
        )
        self._realtime_refresh_task.add_done_callback(self._realtime_refresh_task_done)

    async def _async_request_realtime_refresh(self) -> None:
        if not self._realtime_updates_enabled or self._closing_realtime_watches:
            return
        await self._async_refresh_with_trigger(_REFRESH_TRIGGER_REALTIME_RECONCILE)

    def _realtime_refresh_task_done(self, task: Task[None]) -> None:
        if self._realtime_refresh_task is task:
            self._realtime_refresh_task = None
        if task.cancelled():
            return
        exception = task.exception()
        if exception is not None:
            _LOGGER.debug(
                "OK realtime refresh task failed",
                exc_info=(type(exception), exception, exception.__traceback__),
            )

    def _cancel_realtime_refresh_task(self) -> None:
        task = self._realtime_refresh_task
        if task is None:
            return
        task.cancel()
        self._realtime_refresh_task = None

    async def _async_cancel_realtime_refresh_task(self) -> None:
        task = self._realtime_refresh_task
        if task is None:
            return
        if task is current_task():
            self._realtime_refresh_task = None
            return
        self._cancel_realtime_refresh_task()
        await gather(task, return_exceptions=True)


def _iter_connectors(locations: Iterable[ChargingLocation]) -> Iterable[OkConnectorRef]:
    for location in locations:
        if not isinstance(location, Mapping):
            continue
        stations = location.get("chargingStations")
        if not isinstance(stations, list):
            continue
        for station in stations:
            if not isinstance(station, Mapping):
                continue
            connectors = station.get("connectors")
            if not isinstance(connectors, list):
                continue
            for connector in connectors:
                if not isinstance(connector, Mapping):
                    continue
                connector_ref = OkConnectorRef(
                    location=location,
                    station=station,
                    connector=connector,
                )
                if connector_ref.station_id and connector_ref.connector_id > 0:
                    yield connector_ref


async def _async_get_device_registry(hass: HomeAssistant) -> Any:
    """Return a loaded device registry across supported Home Assistant versions."""
    from homeassistant.helpers import device_registry as dr

    if dr.DATA_REGISTRY not in hass.data:
        async_setup = getattr(dr, "async_setup", None)
        if callable(async_setup):
            setup_result = async_setup(hass)
            if isawaitable(setup_result):
                await setup_result
        else:
            await dr.async_load(hass)
            return dr.async_get(hass)

    device_registry = dr.async_get(hass)
    if not hasattr(device_registry, "devices"):
        await _async_load_device_registry_instance(device_registry)

    async_wait_loaded = getattr(device_registry, "async_wait_loaded", None)
    if callable(async_wait_loaded):
        await async_wait_loaded()

    return device_registry


async def _async_load_device_registry_instance(device_registry: Any) -> None:
    """Load a partially initialized device registry instance."""
    async_load = device_registry.async_load
    if "load_empty" in signature(async_load).parameters:
        await async_load(load_empty=True)
    else:
        await async_load()


def _realtime_watch_keys(data: OkData) -> set[_RealtimeWatchKey]:
    keys: set[_RealtimeWatchKey] = set()
    for connector_ref in _iter_connectors(data.locations):
        if connector_ref.station_id and connector_ref.connector_id:
            keys.add(("station", connector_ref.station_id, connector_ref.connector_id))
    for charging in data.current_chargings:
        token = _charging_status_token(charging)
        if token:
            keys.add(("charging", token))
    return keys


def _realtime_watch_key_sort(key: _RealtimeWatchKey) -> tuple[int, str, int]:
    if key[0] == "station":
        _, station_id, connector_id = key
        return (0, station_id, connector_id)
    _, charging_token = key
    return (1, charging_token, 0)


def _realtime_watch_label(key: _RealtimeWatchKey) -> str:
    if key[0] == "station":
        return f"charger connector {key[2]}"
    return "charging session"


def _price_source(station_id: str) -> str:
    return f"prices:{station_id}"


def _single_connector_refresh_value(
    values: Mapping[int, str | None],
) -> str | None | dict[str, str | None]:
    if len(values) == 1:
        return next(iter(values.values()))
    return {str(connector_id): value for connector_id, value in values.items()}


def _connector_status_source(station_id: str, connector_id: int) -> str:
    return f"connector_status_snapshot:{station_id}:{connector_id}"


def _session_status_source(station_id: str, connector_id: int) -> str:
    return f"session_status_snapshot:{station_id}:{connector_id}"


def _session_receipt_source(station_id: str) -> str:
    return f"session_receipt:{station_id}"


def _quick_receipt_source(charging_token: str) -> str:
    return f"quick_receipt:{charging_token}"


def _charging_token(charging: CurrentCharging) -> str | None:
    token = charging.get("chargingToken") or charging.get("firestoreToken")
    return token if isinstance(token, str) and token else None


def _charging_status_token(charging: CurrentCharging) -> str | None:
    token = charging.get("firestoreToken") or charging.get("chargingToken")
    return token if isinstance(token, str) and token else None


def _charging_connector_key(charging: CurrentCharging) -> tuple[str, int] | None:
    station_id = charging.get("csIdentifier")
    connector_id = charging.get("connectorId")
    if not isinstance(station_id, str) or not station_id:
        return None
    if isinstance(connector_id, bool) or not isinstance(connector_id, int):
        return None
    if connector_id <= 0:
        return None
    return station_id, connector_id


def _finished_chargings(
    previous: tuple[CurrentCharging, ...],
    current: tuple[CurrentCharging, ...],
) -> tuple[CurrentCharging, ...]:
    current_tokens = {
        token for charging in current if (token := _charging_token(charging)) is not None
    }
    return tuple(
        charging
        for charging in previous
        if (token := _charging_token(charging)) is not None and token not in current_tokens
    )


def _merge_receipt(
    receipts: tuple[ChargingReceipt, ...],
    receipt: ChargingReceipt,
) -> tuple[ChargingReceipt, ...]:
    identity = _receipt_identity(receipt)
    if identity is None:
        return (*receipts, receipt)
    return (
        *(existing for existing in receipts if _receipt_identity(existing) != identity),
        receipt,
    )


def _receipt_identity(receipt: ChargingReceipt) -> tuple[str, str, str] | None:
    station_id = receipt.get("chargingStationId")
    started_at = receipt.get("chargingStart")
    ended_at = receipt.get("chargingEnd")
    if not (
        isinstance(station_id, str) and isinstance(started_at, str) and isinstance(ended_at, str)
    ):
        return None
    return (station_id, started_at, ended_at)


def _normalize_quick_receipt(receipt: ChargingReceipt) -> ChargingReceipt:
    """Convert quickReceipt's Wh energy field to the kWh used by full receipts."""
    energy_wh = _number_value(receipt.get("kWh"))
    if energy_wh is None:
        return receipt
    return {**receipt, "kWh": round(energy_wh / 1000, 3)}


def _number_value(value: object) -> float | None:
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


def _status_changed(
    previous: FirestoreDocument | None,
    current: FirestoreDocument | None,
) -> bool:
    return _document_status(previous) != _document_status(current)


def _document_status(document: FirestoreDocument | None) -> str | None:
    if document is None:
        return None
    value = document.fields.get("status")
    return value if isinstance(value, str) else None


def _newest_document(
    current: FirestoreDocument | None,
    candidate: FirestoreDocument,
) -> FirestoreDocument:
    if current is None:
        return candidate
    if _document_version(candidate) > _document_version(current):
        return candidate
    return current


def _document_version(document: FirestoreDocument) -> tuple[int, float]:
    nanoseconds = _nanoseconds_field(document.fields.get("statusEventTime"))
    if nanoseconds is not None:
        return (2, float(nanoseconds))

    timestamps = [
        _timestamp_value(document.fields.get("statusUpdated")),
        _timestamp_value(document.fields.get("powerUpdated")),
        _timestamp_value(document.update_time),
    ]
    values = [value for value in timestamps if value is not None]
    if values:
        return (1, max(values))
    return (0, 0)


def _nanoseconds_field(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _timestamp_value(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def _retry_after(error: OkRateLimitError) -> int | None:
    seconds = error.retry_after
    if seconds is None:
        return None
    return min(max(seconds, 60), 3600)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed
