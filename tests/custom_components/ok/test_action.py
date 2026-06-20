from __future__ import annotations

from typing import NoReturn

import pytest
from custom_components.ok.action import (
    active_charging_token,
    async_call_ok_api,
    require_active_charging_token,
    validate_command_response,
)
from custom_components.ok.api import (
    OkAuthenticationError,
    OkCommandError,
    OkConfigurationError,
    OkConnectionError,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


async def test_async_call_ok_api_translates_configuration_errors() -> None:
    async def call() -> NoReturn:
        raise OkConfigurationError("missing app id")

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_call_ok_api(call())

    assert exc_info.value.translation_domain == "ok"
    assert exc_info.value.translation_key == "api_configuration_error"
    assert exc_info.value.translation_placeholders == {"reason": "missing app id"}


async def test_async_call_ok_api_translates_api_errors() -> None:
    async def call() -> NoReturn:
        raise OkConnectionError("timeout")

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_call_ok_api(call())

    assert exc_info.value.translation_domain == "ok"
    assert exc_info.value.translation_key == "api_error"
    assert exc_info.value.translation_placeholders == {"reason": "timeout"}


async def test_async_call_ok_api_translates_command_errors() -> None:
    async def call() -> NoReturn:
        raise OkCommandError("OK command failed: busy", error_description="busy")

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_call_ok_api(call())

    assert exc_info.value.translation_domain == "ok"
    assert exc_info.value.translation_key == "command_failed"
    assert exc_info.value.translation_placeholders == {"reason": "busy"}


async def test_async_call_ok_api_starts_reauth_for_auth_errors() -> None:
    async def call() -> NoReturn:
        raise OkAuthenticationError("expired token", status_code=401, headers={}, payload={})

    class Entry:
        reauth_calls = 0

        def async_start_reauth(self, hass) -> None:
            self.reauth_calls += 1
            assert hass == "hass"

    entry = Entry()

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_call_ok_api(call(), hass="hass", entry=entry)  # type: ignore[arg-type]

    assert entry.reauth_calls == 1
    assert exc_info.value.translation_domain == "ok"
    assert exc_info.value.translation_key == "api_authentication_error"
    assert exc_info.value.translation_placeholders == {"reason": "expired token"}


def test_active_charging_token_prefers_charging_token() -> None:
    assert active_charging_token({"chargingToken": "charging", "firestoreToken": "firestore"})
    assert active_charging_token({"firestoreToken": "firestore"}) == "firestore"
    assert active_charging_token({}) is None


def test_require_active_charging_token_raises_translated_error() -> None:
    with pytest.raises(HomeAssistantError) as exc_info:
        require_active_charging_token(None)

    assert exc_info.value.translation_key == "active_charging_not_found"


def test_validate_command_response_accepts_success_and_rejects_failures() -> None:
    validate_command_response(None)
    validate_command_response({})
    validate_command_response({"result": "Success"})

    with pytest.raises(HomeAssistantError) as exc_info:
        validate_command_response({"result": "Rejected", "errordescription": "busy"})

    assert exc_info.value.translation_domain == "ok"
    assert exc_info.value.translation_key == "command_failed"
    assert exc_info.value.translation_placeholders == {"reason": "busy"}

    with pytest.raises(HomeAssistantError) as exc_info:
        validate_command_response({"errorcode": 42, "errordescription": "still busy"})

    assert exc_info.value.translation_key == "command_failed"
    assert exc_info.value.translation_placeholders == {"reason": "still busy"}
