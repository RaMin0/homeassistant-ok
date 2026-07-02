from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

from .api import CurrentCharging
from .coordinator import OkConnectorRef, OkDataUpdateCoordinator

_SCHEDULE_START_KEYS = ("scheduledStart", "from", "start", "startTime")
_SCHEDULE_END_KEYS = ("scheduledEnd", "to", "end", "endTime")


def charging_status_field(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
    key: str,
) -> Any:
    """Return a field from the active charging status document."""
    charging = coordinator.active_charging_for(connector.station_id, connector.connector_id)
    document = coordinator.charging_status_for(charging)
    if document is None:
        return None
    return document.fields.get(key)


def schedule_start(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> datetime | None:
    """Return the current schedule start for a charger connector."""
    return parse_datetime(_schedule_start_value(coordinator, connector))


def schedule_end(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> datetime | None:
    """Return the current schedule end for a charger connector."""
    return parse_datetime(_schedule_end_value(coordinator, connector))


def schedule_duration(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> int | None:
    """Return the current schedule duration in seconds."""
    return duration_seconds(
        schedule_start(coordinator, connector), schedule_end(coordinator, connector)
    )


def duration_seconds(start: datetime | None, end: datetime | None) -> int | None:
    """Return a non-negative duration in whole seconds."""
    if start is None or end is None:
        return None
    duration = end - start
    if duration.total_seconds() < 0:
        return None
    return round(duration.total_seconds())


def _schedule_start_value(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> Any:
    return _schedule_value(coordinator, connector, _SCHEDULE_START_KEYS)


def _schedule_end_value(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> Any:
    return _schedule_value(coordinator, connector, _SCHEDULE_END_KEYS)


def _schedule_value(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
    keys: tuple[str, ...],
) -> Any:
    source = _schedule_source(coordinator, connector)
    if source is None:
        return None
    value, found = _schedule_mapping_field(source, keys)
    if found:
        return value
    return None


def _schedule_source(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> Mapping[str, Any] | None:
    charging = coordinator.active_charging_for(connector.station_id, connector.connector_id)
    document = coordinator.charging_status_for(charging)
    schedule = _first_schedule(charging)
    document_fields = cast(Mapping[str, Any], document.fields) if document is not None else None

    if (
        document_fields is not None
        and _has_schedule_start(document_fields)
        and _document_schedule_event_is_newer_than_current_chargings(coordinator, charging)
    ):
        return document_fields

    if schedule is not None and _has_schedule_start(schedule):
        return schedule

    if document_fields is not None and _has_schedule_start(document_fields):
        return document_fields
    return None


def _has_schedule_start(source: Mapping[str, Any]) -> bool:
    return _schedule_mapping_field(source, _SCHEDULE_START_KEYS)[1]


def _document_schedule_event_is_newer_than_current_chargings(
    coordinator: OkDataUpdateCoordinator,
    charging: CurrentCharging | None,
) -> bool:
    schedule_event_at = coordinator.charging_schedule_event_at(charging)
    if schedule_event_at is None:
        return False
    current_chargings_snapshot_at = coordinator.current_chargings_snapshot_at
    if current_chargings_snapshot_at is None:
        return True
    return schedule_event_at > current_chargings_snapshot_at


def _schedule_mapping_field(
    source: Mapping[str, Any],
    keys: tuple[str, ...],
) -> tuple[Any, bool]:
    for key in keys:
        if key in source:
            return source[key], True
    return None, False


def _first_schedule(charging: CurrentCharging | None) -> Mapping[str, Any] | None:
    if charging is None:
        return None
    schedules = charging.get("schedules")
    if not isinstance(schedules, list) or not schedules:
        return None
    schedule: object = schedules[0]
    return schedule if isinstance(schedule, Mapping) else None


def parse_datetime(value: Any) -> datetime | None:
    """Parse an OK datetime value as UTC."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
