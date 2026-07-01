from __future__ import annotations

import asyncio
from pathlib import Path

from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.components.script.config import SCRIPT_ENTITY_SCHEMA
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.util.yaml.loader import load_yaml

ROOT = Path(__file__).resolve().parents[3]


def test_schedule_charging_script_blueprint(tmp_path: Path) -> None:
    asyncio.run(_test_schedule_charging_script_blueprint(tmp_path))


async def _test_schedule_charging_script_blueprint(tmp_path: Path) -> None:
    hass = HomeAssistant(str(tmp_path))
    previous_hass = cv._hass.hass
    cv._hass.hass = hass
    try:
        path = ROOT / "blueprints/script/ok/schedule_charging.yaml"
        blueprint = Blueprint(
            load_yaml(str(path)),
            path=str(path),
            expected_domain="script",
            schema=BLUEPRINT_SCHEMA,
        )
        substituted = BlueprintInputs(
            blueprint,
            {
                "use_blueprint": {
                    "path": str(path),
                    "input": {
                        "connector_status_entity": "sensor.charger_connector_status",
                    },
                }
            },
        ).async_substitute()

        SCRIPT_ENTITY_SCHEMA(substituted)

        assert substituted["icon"] == "mdi:battery-clock"
        with_end = substituted["sequence"][0]["choose"][0]["sequence"][0]
        without_end = substituted["sequence"][0]["default"][0]
        assert with_end["action"] == "ok.schedule_charging"
        assert with_end["target"]["entity_id"] == "sensor.charger_connector_status"
        assert with_end["data"]["scheduled_end"] == "{{ scheduled_end }}"
        assert without_end["action"] == "ok.schedule_charging"
        assert without_end["target"]["entity_id"] == "sensor.charger_connector_status"
        assert "scheduled_end" not in without_end["data"]
    finally:
        cv._hass.hass = previous_hass
        await hass.async_stop()
