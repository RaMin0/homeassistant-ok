from __future__ import annotations

import json
from pathlib import Path

from custom_components.ok.button import BUTTON_DESCRIPTIONS
from custom_components.ok.sensor import SENSOR_DESCRIPTIONS
from custom_components.ok.switch import SWITCH_DESCRIPTIONS


def test_icons_cover_all_entities() -> None:
    assert _description_icon_keys("sensor") == _sensor_icon_keys()
    assert _description_icon_keys("button") == _button_icon_keys()
    assert _description_icon_keys("switch") == {
        item.translation_key for item in SWITCH_DESCRIPTIONS
    }


def _description_icon_keys(platform: str) -> set[str]:
    icons = json.loads(Path("custom_components/ok/icons.json").read_text())["entity"][platform]
    return set(icons)


def _sensor_icon_keys() -> set[str]:
    keys: set[str] = set()
    for description in SENSOR_DESCRIPTIONS:
        keys.add(description.translation_key)
        if description.connector_scoped:
            keys.add(f"{description.translation_key}_connector")
    return keys


def _button_icon_keys() -> set[str]:
    keys: set[str] = set()
    for description in BUTTON_DESCRIPTIONS:
        keys.add(description.translation_key)
        if description.connector_scoped:
            keys.add(f"{description.translation_key}_connector")
    return keys
