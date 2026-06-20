from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, __version__
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.httpx_client import get_async_client

from .api import (
    AsyncOkApiClient,
    DeviceSettingsResponse,
    OkApiConfig,
    OkApiError,
    OkStatusError,
)
from .const import (
    APP_PLATFORM,
    APP_SECRET,
    CONF_APP_ID,
    CONF_DEVICE_FRIENDLY_ID,
    CONF_DEVICE_ID,
    CONF_INCLUDE_RECEIPTS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class OkValidationResult:
    title: str
    unique_id: str
    data: dict[str, Any]


class OkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg,misc]
    """Handle an OK config flow."""

    VERSION = 1
    MINOR_VERSION = 3

    def __init__(self) -> None:
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                result = await _validate_login(self.hass, user_input)
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception while validating OK credentials")
                errors["base"] = "unknown"
            else:
                if _matching_entry_for_result(self.hass, result):
                    return self.async_abort(reason="already_configured")
                await self.async_set_unique_id(result.unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=result.title, data=result.data)

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauthentication."""
        entry_id = self.context.get("entry_id")
        if not isinstance(entry_id, str):
            return self.async_abort(reason="unknown")
        self._reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Confirm reauthentication."""
        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(self._reauth_entry.data)
            data.update(user_input)
            try:
                result = await _validate_login(self.hass, data)
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception while reauthenticating OK")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(result.unique_id)
                if not _entry_matches_result(self._reauth_entry, result):
                    errors["base"] = "wrong_account"
                else:
                    if _unique_id_owned_by_other(self.hass, self._reauth_entry, result.unique_id):
                        return self.async_abort(reason="already_configured")
                    return self.async_update_reload_and_abort(
                        self._reauth_entry,
                        title=result.title,
                        data=result.data,
                        reason="reauth_successful",
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_reauth_schema(self._reauth_entry.data),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle entry reconfiguration."""
        entry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(entry.data)
            data.update(user_input)
            try:
                result = await _validate_login(self.hass, data)
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception while reconfiguring OK")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(result.unique_id)
                if not _entry_matches_result(entry, result):
                    errors["base"] = "wrong_account"
                else:
                    if _unique_id_owned_by_other(self.hass, entry, result.unique_id):
                        return self.async_abort(reason="already_configured")
                    return self.async_update_reload_and_abort(
                        entry,
                        title=result.title,
                        data=result.data,
                        reason="reconfigure_successful",
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_reauth_schema(entry.data),
            errors=errors,
        )

    @staticmethod
    @callback  # type: ignore[untyped-decorator]
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OkOptionsFlowHandler()


class OkOptionsFlowHandler(config_entries.OptionsFlow):  # type: ignore[misc]
    """Handle OK options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_INCLUDE_RECEIPTS: user_input[CONF_INCLUDE_RECEIPTS]},
            )
        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INCLUDE_RECEIPTS,
                        default=options.get(CONF_INCLUDE_RECEIPTS, True),
                    ): selector.BooleanSelector(),
                }
            ),
        )


async def _validate_login(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> OkValidationResult:
    config = OkApiConfig(
        app_id=data.get(CONF_APP_ID),
        app_secret=APP_SECRET,
        device_id=data.get(CONF_DEVICE_ID),
        device_friendly_id=data.get(CONF_DEVICE_FRIENDLY_ID),
        app_platform=APP_PLATFORM,
        app_version=__version__,
    )
    client = AsyncOkApiClient(config=config, http_client=get_async_client(hass))
    try:
        if not config.app_id or not config.device_id:
            await client.register_device(app_id=config.app_id)
        await client.login(data[CONF_EMAIL], data[CONF_PASSWORD])
        settings = await client.get_device_settings()
    except OkStatusError as err:
        if err.status_code in (400, 401, 403):
            raise InvalidAuthError from err
        raise CannotConnectError from err
    except OkApiError as err:
        raise CannotConnectError from err

    result = settings.get("HentDeviceOpsaetningResult", {})
    user = result.get("Bruger", {})
    account_id = _account_id(settings)
    title = _title(user, data[CONF_EMAIL])
    return OkValidationResult(
        title=title,
        unique_id=account_id,
        data={
            CONF_EMAIL: data[CONF_EMAIL],
            CONF_APP_ID: client.config.app_id,
            CONF_DEVICE_ID: client.config.device_id,
            CONF_DEVICE_FRIENDLY_ID: client.config.device_friendly_id,
        },
    )


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
            ),
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


def _reauth_schema(data: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL, default=data.get(CONF_EMAIL)): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
            ),
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


def _account_id(settings: DeviceSettingsResponse) -> str:
    result = settings.get("HentDeviceOpsaetningResult", {})
    user = result.get("Bruger", {})
    account_id = user.get("Brugernr")
    if account_id is not None:
        return str(account_id)
    raise CannotConnectError


def _entry_matches_result(
    entry: config_entries.ConfigEntry,
    result: OkValidationResult,
) -> bool:
    """Return whether a validation result belongs to an existing entry."""
    if entry.unique_id == result.unique_id:
        return True

    # Older pre-release entries could use the registered app device id as unique id.
    # That id is not account-scoped, so only accept it for the same configured email.
    entry_device_id = entry.data.get(CONF_DEVICE_ID)
    if entry.unique_id != entry_device_id:
        return False
    entry_email = entry.data.get(CONF_EMAIL)
    result_email = result.data.get(CONF_EMAIL)
    return (
        isinstance(entry_email, str)
        and isinstance(result_email, str)
        and entry_email.casefold() == result_email.casefold()
    )


def _matching_entry_for_result(
    hass: HomeAssistant,
    result: OkValidationResult,
) -> config_entries.ConfigEntry | None:
    """Return the configured entry matching a validated OK account."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if _entry_matches_result(entry, result):
            return entry
    return None


def _unique_id_owned_by_other(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    unique_id: str,
) -> bool:
    """Return whether another OK entry already owns a unique id."""
    for existing_entry in hass.config_entries.async_entries(DOMAIN):
        if existing_entry.entry_id != entry.entry_id and existing_entry.unique_id == unique_id:
            return True
    return False


def _title(user: Mapping[str, Any], email: str) -> str:
    return f"OK ({email})"


class CannotConnectError(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuthError(Exception):
    """Error to indicate invalid auth."""
