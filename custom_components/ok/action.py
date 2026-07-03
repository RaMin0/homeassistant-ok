from __future__ import annotations

from collections.abc import Awaitable, Mapping
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .api import (
    OkApiError,
    OkAuthenticationError,
    OkCommandError,
    OkConfigurationError,
    OkPermissionDeniedError,
)
from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_KNOWN_COMMAND_ERROR_TRANSLATIONS = {
    "featuredisabled": "command_feature_disabled",
    "maximumfailuresexceeded": "command_receipt_unavailable",
    "pollingfailed": "command_receipt_unavailable",
    "updatebeforeaction": "command_update_before_action",
    "updatescheduleoffinishedcharge": "command_update_schedule_finished_charge",
}


async def async_call_ok_api(
    api_call: Awaitable[Any],
    *,
    hass: HomeAssistant | None = None,
    entry: ConfigEntry[Any] | None = None,
) -> Any:
    """Call an OK API action and raise Home Assistant translated errors."""
    try:
        return await api_call
    except OkConfigurationError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="api_configuration_error",
            translation_placeholders={"reason": _api_error_message(err)},
        ) from err
    except (OkAuthenticationError, OkPermissionDeniedError) as err:
        if hass is not None and entry is not None:
            entry.async_start_reauth(hass)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="api_authentication_error",
            translation_placeholders={"reason": _api_error_message(err)},
        ) from err
    except OkCommandError as err:
        translation_key = _command_error_translation_key(err)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key or "command_failed",
            translation_placeholders=(
                {}
                if translation_key is not None
                else {"reason": err.error_description or _api_error_message(err)}
            ),
        ) from err
    except OkApiError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="api_error",
            translation_placeholders={"reason": _api_error_message(err)},
        ) from err


def active_charging_token(charging: Mapping[str, Any] | None) -> str | None:
    """Return the OK charging token used by charging action endpoints."""
    if charging is None:
        return None
    token = charging.get("chargingToken")
    return token if isinstance(token, str) and token else None


def require_active_charging_token(charging: Mapping[str, Any] | None) -> str:
    """Return an active charging token or raise a translated Home Assistant error."""
    token = active_charging_token(charging)
    if token is not None:
        return token
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="active_charging_not_found",
    )


def charging_command_tokens(response: object) -> tuple[str | None, str | None]:
    """Return action and realtime tokens returned by an OK charging command."""
    if not isinstance(response, Mapping):
        return None, None
    charging_token = response.get("chargingToken")
    firestore_token = response.get("firestoreToken")
    return (
        charging_token if isinstance(charging_token, str) and charging_token else None,
        firestore_token if isinstance(firestore_token, str) and firestore_token else None,
    )


def validate_command_response(response: object) -> None:
    """Validate the OK command response shape used by charger control actions."""
    if not isinstance(response, Mapping):
        return

    result = response.get("result")
    has_error_fields = (
        response.get("errorcode") is not None or response.get("errordescription") is not None
    )
    if result == "Success" or (result is None and not has_error_fields):
        return

    description = response.get("errordescription") or result or response.get("errorcode")
    if translation_key := _known_command_error_translation_key(description):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
        )
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="command_failed",
        translation_placeholders={"reason": str(description)},
    )


def _command_error_translation_key(err: OkCommandError) -> str | None:
    return (
        _known_command_error_translation_key(err.error_description)
        or _known_command_error_translation_key(err.result)
        or _known_command_error_translation_key(err.error_code)
    )


def _known_command_error_translation_key(value: object) -> str | None:
    if value is None:
        return None
    normalized = "".join(char for char in str(value).casefold() if char.isalnum())
    return _KNOWN_COMMAND_ERROR_TRANSLATIONS.get(normalized)


def _api_error_message(err: OkApiError) -> str:
    return str(err) or err.__class__.__name__
