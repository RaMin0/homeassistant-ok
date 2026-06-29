from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from custom_components.ok.const import (
    SERVICE_CANCEL_CHARGING_SCHEDULE,
    SERVICE_RESTART,
    SERVICE_SCHEDULE_CHARGING,
    SERVICE_SET_AUTO_START,
    SERVICE_START_CHARGING,
    SERVICE_STOP_CHARGING,
    SERVICE_UPDATE_CHARGING_SCHEDULE,
)


def test_service_entity_selectors_target_connector_status_sensor() -> None:
    services = _services_yaml()

    for service in (
        SERVICE_START_CHARGING,
        SERVICE_SCHEDULE_CHARGING,
        SERVICE_UPDATE_CHARGING_SCHEDULE,
        SERVICE_CANCEL_CHARGING_SCHEDULE,
        SERVICE_STOP_CHARGING,
    ):
        assert services[service]["target"]["entity"] == {
            "integration": "ok",
            "domain": "sensor",
            "device_class": "enum",
        }


def test_charger_level_service_selectors_target_chargers() -> None:
    services = _services_yaml()

    restart_fields = services[SERVICE_RESTART]["fields"]
    assert restart_fields["device_id"]["selector"]["device"] == {"integration": "ok"}
    assert "entity_id" not in restart_fields

    auto_start_fields = services[SERVICE_SET_AUTO_START]["fields"]
    assert auto_start_fields["device_id"]["selector"]["device"] == {"integration": "ok"}
    assert "entity_id" not in auto_start_fields


def _services_yaml() -> dict[str, Any]:
    path = Path("custom_components/ok/services.yaml")
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    return data
