from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

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
    document = _charging_status_schedule(coordinator, connector)
    if document is not None:
        value, found = _schedule_mapping_field(document, _SCHEDULE_START_KEYS)
        if found:
            return value

    schedule = _first_schedule(coordinator, connector)
    if schedule is not None:
        value, found = _schedule_mapping_field(schedule, _SCHEDULE_START_KEYS)
        if found:
            return value
    return None


def _schedule_end_value(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> Any:
    document = _charging_status_schedule(coordinator, connector)
    schedule = _first_schedule(coordinator, connector)

    document_start: Any = None
    document_start_found = False
    if document is not None:
        document_start, document_start_found = _schedule_mapping_field(
            document, _SCHEDULE_START_KEYS
        )
        value, found = _schedule_mapping_field(document, _SCHEDULE_END_KEYS)
        if found:
            return value

    if document_start_found:
        if schedule is not None and _schedule_start_matches(document_start, schedule):
            value, found = _schedule_mapping_field(schedule, _SCHEDULE_END_KEYS)
            if found:
                return value
        return None

    if schedule is None:
        return None
    value, found = _schedule_mapping_field(schedule, _SCHEDULE_END_KEYS)
    if found:
        return value
    return None


def _charging_status_schedule(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> Mapping[str, Any] | None:
    charging = coordinator.active_charging_for(connector.station_id, connector.connector_id)
    document = coordinator.charging_status_for(charging)
    if document is None:
        return None
    return document.fields


def _schedule_mapping_field(
    source: Mapping[str, Any],
    keys: tuple[str, ...],
) -> tuple[Any, bool]:
    for key in keys:
        if key in source:
            return source[key], True
    return None, False


def _first_schedule(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> Mapping[str, Any] | None:
    charging = coordinator.active_charging_for(connector.station_id, connector.connector_id)
    if charging is None:
        return None
    schedules = charging.get("schedules")
    if not isinstance(schedules, list) or not schedules:
        return None
    schedule: object = schedules[0]
    return schedule if isinstance(schedule, Mapping) else None


def _schedule_start_matches(document_start: Any, schedule: Mapping[str, Any]) -> bool:
    schedule_start, found = _schedule_mapping_field(schedule, _SCHEDULE_START_KEYS)
    if not found:
        return False
    parsed_document_start = parse_datetime(document_start)
    parsed_schedule_start = parse_datetime(schedule_start)
    if parsed_document_start is not None and parsed_schedule_start is not None:
        return parsed_document_start == parsed_schedule_start
    return document_start == schedule_start


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
