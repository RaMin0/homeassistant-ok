from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import contextmanager
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any
from unittest.mock import patch

import custom_components.ok.config_flow  # noqa: F401
import pytest_asyncio
import voluptuous_serialize
from custom_components.ok.api import AsyncOkApiClient, OkConnectionError, OkStatusError
from custom_components.ok.config_flow import CannotConnectError, _account_id, _title
from custom_components.ok.const import (
    APP_SECRET,
    CONF_APP_ID,
    CONF_DEVICE_FRIENDLY_ID,
    CONF_DEVICE_ID,
    CONF_ENABLE_CONTROL_BUTTONS,
    CONF_ENABLE_ENERGY_PRICES,
    CONF_ENABLE_REALTIME_UPDATES,
    CONF_INCLUDE_RECEIPTS,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, __version__
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.loader import (
    DATA_COMPONENTS,
    DATA_CUSTOM_COMPONENTS,
    DATA_INTEGRATIONS,
    DATA_MISSING_PLATFORMS,
    DATA_PRELOAD_PLATFORMS,
)

from .conftest import load_fixture

type RegisterDeviceFn = Callable[[AsyncOkApiClient], Awaitable[dict[str, Any]]]
type LoginFn = Callable[[AsyncOkApiClient, str, str], Awaitable[dict[str, Any]]]
type SettingsFn = Callable[[AsyncOkApiClient], Awaitable[dict[str, Any]]]


@pytest_asyncio.fixture
async def hass(tmp_path: Path) -> AsyncIterator[HomeAssistant]:
    """Return a minimal Home Assistant instance with config entries initialized."""
    instance = HomeAssistant(str(tmp_path))
    instance.data[DATA_COMPONENTS] = {"ok.config_flow"}
    instance.data[DATA_CUSTOM_COMPONENTS] = {}
    instance.data[DATA_INTEGRATIONS] = {}
    instance.data[DATA_MISSING_PLATFORMS] = {}
    instance.data[DATA_PRELOAD_PLATFORMS] = set()
    instance.config_entries = ConfigEntries(instance, {})
    try:
        yield instance
    finally:
        await instance.async_stop()


async def test_user_flow_registers_device_and_creates_entry(hass: HomeAssistant) -> None:
    with _patch_validation(), patch("custom_components.ok.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_EMAIL: "user@example.test",
                CONF_PASSWORD: "secret",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OK (user@example.test)"
    assert "account_id" not in result["data"]
    assert result["data"][CONF_APP_ID] == "APP"
    assert "app_secret" not in result["data"]
    assert result["data"][CONF_DEVICE_ID] == "device-id-002"
    assert result["data"][CONF_DEVICE_FRIENDLY_ID] == "HAOK01"
    assert "login_token" not in result["data"]


async def test_user_flow_rejects_invalid_auth(hass: HomeAssistant) -> None:
    async def login_invalid(
        self: AsyncOkApiClient,
        email: str,
        password: str,
    ) -> dict[str, Any]:
        raise OkStatusError("invalid credentials", status_code=401, headers={}, payload={})

    with _patch_validation(login=login_invalid):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: "user@example.test", CONF_PASSWORD: "bad-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_handles_cannot_connect(hass: HomeAssistant) -> None:
    async def register_device_error(self: AsyncOkApiClient, **kwargs: Any) -> dict[str, Any]:
        raise OkConnectionError("timeout")

    with _patch_validation(register_device=register_device_error):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: "user@example.test", CONF_PASSWORD: "secret"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_requires_device_registration_fields(hass: HomeAssistant) -> None:
    for missing_field in (CONF_APP_ID, CONF_DEVICE_ID, CONF_DEVICE_FRIENDLY_ID):

        async def settings_missing_field(
            self: AsyncOkApiClient,
            *,
            field: str = missing_field,
        ) -> dict[str, Any]:
            self.config.app_id = None if field == CONF_APP_ID else "APP"
            self.config.device_id = None if field == CONF_DEVICE_ID else "device-id-002"
            self.config.device_friendly_id = None if field == CONF_DEVICE_FRIENDLY_ID else "HAOK01"
            return load_fixture("device_settings.json")

        with _patch_validation(settings=settings_missing_field):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data={CONF_EMAIL: "user@example.test", CONF_PASSWORD: "secret"},
            )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_handles_unexpected_validation_error(hass: HomeAssistant) -> None:
    async def register_device_error(self: AsyncOkApiClient, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("boom")

    with _patch_validation(register_device=register_device_error):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: "user@example.test", CONF_PASSWORD: "secret"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_aborts_duplicate_account(hass: HomeAssistant) -> None:
    _add_entry(hass, _mock_entry())

    with (
        _patch_validation(),
        patch(
            "homeassistant.loader.async_get_integration",
            return_value=SimpleNamespace(single_config_entry=False),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: "user@example.test", CONF_PASSWORD: "secret"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_aborts_duplicate_legacy_device_unique_id(
    hass: HomeAssistant,
) -> None:
    entry = _mock_entry(unique_id="device-id-002")
    _add_entry(hass, entry)

    with (
        _patch_validation(),
        patch(
            "homeassistant.loader.async_get_integration",
            return_value=SimpleNamespace(single_config_entry=False),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: "user@example.test", CONF_PASSWORD: "secret"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == "device-id-002"


async def test_reauth_updates_existing_entry(hass: HomeAssistant) -> None:
    entry = _mock_entry(legacy_login_token=True)
    _add_entry(hass, entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with _patch_validation(), patch("custom_components.ok.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.test", CONF_PASSWORD: "new-secret"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert "login_token" not in entry.data


async def test_reauth_rejects_wrong_account(hass: HomeAssistant) -> None:
    entry = _mock_entry()
    _add_entry(hass, entry)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )

    with _patch_validation(settings=_settings_for_account("other-account")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "other@example.test", CONF_PASSWORD: "secret"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_account"}


async def test_reauth_accepts_legacy_device_unique_id(hass: HomeAssistant) -> None:
    entry = _mock_entry(unique_id="device-id-002")
    _add_entry(hass, entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )

    with _patch_validation(), patch("custom_components.ok.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.test", CONF_PASSWORD: "new-secret"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.unique_id == "device-id-002"


async def test_reconfigure_rejects_wrong_account(hass: HomeAssistant) -> None:
    entry = _mock_entry()
    _add_entry(hass, entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        data=entry.data,
    )

    with _patch_validation(settings=_settings_for_account("other-account")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "other@example.test", CONF_PASSWORD: "secret"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_account"}


async def test_reauth_handles_missing_entry_and_validation_errors(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": "missing-entry"},
        data={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"

    entry = _mock_entry()
    _add_entry(hass, entry)
    for exception, expected in (
        (OkStatusError("invalid", status_code=401, headers={}, payload={}), "invalid_auth"),
        (OkConnectionError("timeout"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )

        async def login_error(
            self: AsyncOkApiClient,
            email: str,
            password: str,
            *,
            err: Exception = exception,
        ) -> dict[str, Any]:
            raise err

        with _patch_validation(login=login_error):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_EMAIL: "user@example.test", CONF_PASSWORD: "secret"},
            )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": expected}


async def test_reconfigure_updates_existing_entry(hass: HomeAssistant) -> None:
    entry = _mock_entry(legacy_login_token=True)
    _add_entry(hass, entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        data=entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with _patch_validation(), patch("custom_components.ok.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.test", CONF_PASSWORD: "new-secret"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert "login_token" not in entry.data


async def test_reconfigure_accepts_legacy_device_unique_id(hass: HomeAssistant) -> None:
    entry = _mock_entry(unique_id="device-id-002")
    _add_entry(hass, entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        data=entry.data,
    )

    with _patch_validation(), patch("custom_components.ok.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.test", CONF_PASSWORD: "new-secret"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "device-id-002"


async def test_reconfigure_handles_validation_errors(hass: HomeAssistant) -> None:
    entry = _mock_entry()
    _add_entry(hass, entry)

    for exception, expected in (
        (OkStatusError("invalid", status_code=401, headers={}, payload={}), "invalid_auth"),
        (OkConnectionError("timeout"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
            data=entry.data,
        )

        async def login_error(
            self: AsyncOkApiClient,
            email: str,
            password: str,
            *,
            err: Exception = exception,
        ) -> dict[str, Any]:
            raise err

        with _patch_validation(login=login_error):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_EMAIL: "user@example.test", CONF_PASSWORD: "secret"},
            )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": expected}


async def test_options_flow_updates_feature_toggles(hass: HomeAssistant) -> None:
    entry = _mock_entry()
    _add_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    defaults = result["data_schema"]({})
    assert defaults[CONF_ENABLE_ENERGY_PRICES] is True
    assert defaults[CONF_INCLUDE_RECEIPTS] is True
    assert defaults[CONF_ENABLE_CONTROL_BUTTONS] is True
    assert defaults["advanced"][CONF_ENABLE_REALTIME_UPDATES] is True
    serialized_schema = voluptuous_serialize.convert(
        result["data_schema"],
        custom_serializer=cv.custom_serializer,
    )
    advanced_section = next(item for item in serialized_schema if item["name"] == "advanced")
    assert advanced_section["default"] == {CONF_ENABLE_REALTIME_UPDATES: True}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENABLE_ENERGY_PRICES: False,
            CONF_INCLUDE_RECEIPTS: False,
            CONF_ENABLE_CONTROL_BUTTONS: False,
            "advanced": {CONF_ENABLE_REALTIME_UPDATES: False},
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_INCLUDE_RECEIPTS: False,
        CONF_ENABLE_REALTIME_UPDATES: False,
        CONF_ENABLE_CONTROL_BUTTONS: False,
        CONF_ENABLE_ENERGY_PRICES: False,
    }


async def test_options_flow_preserves_omitted_advanced_options(hass: HomeAssistant) -> None:
    entry = _mock_entry(options={CONF_ENABLE_REALTIME_UPDATES: False})
    _add_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENABLE_ENERGY_PRICES: True,
            CONF_INCLUDE_RECEIPTS: True,
            CONF_ENABLE_CONTROL_BUTTONS: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ENABLE_REALTIME_UPDATES] is False


def test_account_id_and_title_fallbacks() -> None:
    assert _account_id({"HentDeviceOpsaetningResult": {"Bruger": {"Brugernr": 1000001}}}) == (
        "1000001"
    )
    assert _title({"Navn": "OK User"}, "user@example.test") == "OK (user@example.test)"

    try:
        _account_id({"HentDeviceOpsaetningResult": {"DeviceId": "device-id"}})
    except CannotConnectError:
        pass
    else:
        raise AssertionError("missing account id should fail validation")


@contextmanager
def _patch_validation(
    *,
    register_device: RegisterDeviceFn | None = None,
    login: LoginFn | None = None,
    settings: SettingsFn | None = None,
):
    with (
        patch.object(AsyncOkApiClient, "register_device", register_device or _register_device),
        patch.object(AsyncOkApiClient, "login", login or _login),
        patch.object(AsyncOkApiClient, "get_device_settings", settings or _settings),
    ):
        yield


async def _register_device(self: AsyncOkApiClient, **kwargs: Any) -> dict[str, Any]:
    assert self.config.app_secret == APP_SECRET
    assert self.config.app_version == __version__
    self.config.app_id = "APP"
    self.config.device_id = "device-id"
    self.config.device_friendly_id = "FRIEND"
    return {
        "RegistrerDeviceResult": {
            "DeviceId": "device-id",
            "DeviceFriendlyId": "FRIEND",
        }
    }


async def _login(self: AsyncOkApiClient, email: str, password: str) -> dict[str, Any]:
    self.config.login_token = "login-token"
    return {"LogIndResult": {"LogIndToken": "login-token"}}


async def _settings(self: AsyncOkApiClient) -> dict[str, Any]:
    self.config.device_id = "device-id-002"
    self.config.device_friendly_id = "HAOK01"
    self.config.login_token = "settings-token"
    return load_fixture("device_settings.json")


def _settings_for_account(account_id: str) -> SettingsFn:
    async def settings(self: AsyncOkApiClient) -> dict[str, Any]:
        response = load_fixture("device_settings.json")
        response["HentDeviceOpsaetningResult"]["Bruger"]["Brugernr"] = account_id
        return response

    return settings


def _mock_entry(
    *,
    legacy_login_token: bool = False,
    unique_id: str = "1000001",
    options: dict[str, Any] | None = None,
) -> config_entries.ConfigEntry:
    data = {
        CONF_EMAIL: "user@example.test",
        CONF_APP_ID: "APP",
        CONF_DEVICE_ID: "device-id-002",
        CONF_DEVICE_FRIENDLY_ID: "HAOK01",
    }
    if legacy_login_token:
        data["login_token"] = "old-token"
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="OK (user@example.test)",
        unique_id=unique_id,
        data=data,
        options=options or {},
        source=config_entries.SOURCE_USER,
        discovery_keys=MappingProxyType({}),
        subentries_data=(),
    )


def _add_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> None:
    hass.config_entries._entries[entry.entry_id] = entry
