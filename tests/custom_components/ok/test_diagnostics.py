from __future__ import annotations

from types import SimpleNamespace

from custom_components.ok.const import (
    CONF_APP_ID,
    CONF_DEVICE_FRIENDLY_ID,
    CONF_DEVICE_ID,
)
from custom_components.ok.diagnostics import async_get_config_entry_diagnostics
from homeassistant.const import CONF_EMAIL


async def test_diagnostics_redacts_config_entry_data() -> None:
    coordinator = SimpleNamespace(
        data=SimpleNamespace(locations=(), current_chargings=(), receipts=()),
        last_update_success=True,
        connectors=lambda: (),
    )
    entry = SimpleNamespace(
        data={
            CONF_APP_ID: "app-id",
            CONF_DEVICE_ID: "device-id",
            CONF_DEVICE_FRIENDLY_ID: "friendly",
            "login_token": "legacy-token",
            CONF_EMAIL: "user@example.test",
        },
        options={},
        runtime_data=SimpleNamespace(coordinator=coordinator),
    )

    diagnostics = await async_get_config_entry_diagnostics(SimpleNamespace(), entry)

    assert diagnostics["entry"] == {
        CONF_APP_ID: "**REDACTED**",
        CONF_DEVICE_ID: "**REDACTED**",
        CONF_DEVICE_FRIENDLY_ID: "**REDACTED**",
        "login_token": "**REDACTED**",
        CONF_EMAIL: "**REDACTED**",
    }
    assert diagnostics["options"] == {}
    assert diagnostics["coordinator"]["chargers"] == 0
    assert diagnostics["coordinator"]["connectors"] == 0
