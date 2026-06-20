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

        assert substituted["sequence"][0]["action"] == "ok.schedule_charging"
        assert substituted["sequence"][0]["data"]["entity_id"] == "sensor.charger_connector_status"
    finally:
        cv._hass.hass = previous_hass
        await hass.async_stop()
