from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .coordinator import OkConnectorRef, OkDataUpdateCoordinator


def charging_field(
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
    return parse_datetime(charging_field(coordinator, connector, "scheduledStart"))


def schedule_end(
    coordinator: OkDataUpdateCoordinator,
    connector: OkConnectorRef,
) -> datetime | None:
    """Return the current schedule end for a charger connector."""
    return parse_datetime(charging_field(coordinator, connector, "scheduledEnd"))


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
