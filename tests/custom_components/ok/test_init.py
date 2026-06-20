from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any

import httpx
import pytest
from custom_components.ok.const import (
    APP_PLATFORM,
    APP_SECRET,
    CONF_APP_ID,
    CONF_DEVICE_FRIENDLY_ID,
    CONF_DEVICE_ID,
    PLATFORMS,
)
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntries, ConfigEntryState
from homeassistant.const import CONF_EMAIL, __version__
from homeassistant.core import HomeAssistant
from pytest import MonkeyPatch

from custom_components.ok import (
    OkRuntimeData,
    _async_update_listener,
    _client_from_entry,
    _loaded_entries,
    async_migrate_entry,
    async_remove_config_entry_device,
    async_setup_entry,
    async_unload_entry,
)


class FakeConfigEntries:
    def __init__(
        self,
        unload_result: bool = True,
        forward_error: BaseException | None = None,
    ) -> None:
        self.unload_result = unload_result
        self.forward_error = forward_error
        self.entries: list[Any] = []
        self.forwarded: list[tuple[Any, tuple[Any, ...]]] = []
        self.unloaded: list[tuple[Any, tuple[Any, ...]]] = []
        self.reloads: list[str] = []
        self.updated: list[tuple[Any, dict[str, Any]]] = []

    async def async_forward_entry_setups(self, entry: Any, platforms: tuple[Any, ...]) -> None:
        self.forwarded.append((entry, platforms))
        if self.forward_error is not None:
            raise self.forward_error

    async def async_unload_platforms(self, entry: Any, platforms: tuple[Any, ...]) -> bool:
        self.unloaded.append((entry, platforms))
        return self.unload_result

    async def async_reload(self, entry_id: str) -> None:
        self.reloads.append(entry_id)

    def async_entries(self, domain: str | None = None) -> list[Any]:
        return self.entries

    def async_update_entry(
        self,
        entry: Any,
        *,
        data: Mapping[str, Any],
        title: str | None = None,
        version: int | None = None,
        minor_version: int | None = None,
    ) -> bool:
        updated_data = dict(data)
        self.updated.append((entry, updated_data))
        entry.data = updated_data
        if title is not None:
            entry.title = title
        if version is not None:
            entry.version = version
        if minor_version is not None:
            entry.minor_version = minor_version
        return True


class FakeEntry:
    def __init__(self, update_listener_remover: Any = "remove-listener") -> None:
        self.entry_id = "test-entry"
        self.unique_id = "1000001"
        self.data: dict[str, Any] = {}
        self.options: dict[str, Any] = {}
        self.title = "OK"
        self.state = ConfigEntryState.NOT_LOADED
        self.unload_callbacks: list[Any] = []
        self.update_listener: Any = None
        self.update_listener_remover = update_listener_remover
        self.runtime_data: Any = None

    def add_update_listener(self, listener: Any) -> Any:
        self.update_listener = listener
        return self.update_listener_remover

    def async_on_unload(self, callback: Any) -> None:
        self.unload_callbacks.append(callback)


class FakeClient:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeCoordinator:
    def __init__(self, hass: Any, entry: Any, client: FakeClient) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.first_refresh_count = 0
        self.closed = False
        self.data = object()
        self.connector_refs = [SimpleNamespace(station_id="OK-CHARGER-001")]

    async def async_config_entry_first_refresh(self) -> None:
        self.first_refresh_count += 1

    def close_realtime_watches(self) -> None:
        self.closed = True

    async def async_close_realtime_watches(self) -> None:
        self.closed = True

    def connectors(self) -> tuple[Any, ...]:
        return tuple(self.connector_refs)


def test_setup_entry_builds_runtime_and_forwards_platforms(
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(_test_setup_entry_builds_runtime_and_forwards_platforms(monkeypatch))


async def _test_setup_entry_builds_runtime_and_forwards_platforms(
    monkeypatch: MonkeyPatch,
) -> None:
    import custom_components.ok.coordinator as coordinator_module

    import custom_components.ok as ok

    client = FakeClient()
    hass = SimpleNamespace(config_entries=FakeConfigEntries())
    entry = FakeEntry()
    entry.title = "OK (OK User)"
    entry.data = {
        "login_token": "legacy-token",
        CONF_APP_ID: "APP",
        CONF_EMAIL: "user@example.test",
    }

    monkeypatch.setattr(ok, "_client_from_entry", lambda hass, entry: client)
    monkeypatch.setattr(coordinator_module, "OkDataUpdateCoordinator", FakeCoordinator)

    assert await async_setup_entry(hass, entry) is True
    entry.state = ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, OkRuntimeData)
    assert entry.runtime_data.client is client
    assert isinstance(entry.runtime_data.coordinator, FakeCoordinator)
    assert entry.runtime_data.coordinator.first_refresh_count == 1
    assert hass.config_entries.forwarded == [(entry, PLATFORMS)]
    assert entry.unload_callbacks == ["remove-listener"]
    assert entry.update_listener is _async_update_listener
    assert "login_token" not in entry.data
    assert entry.title == "OK (user@example.test)"
    assert hass.config_entries.updated == [
        (entry, {CONF_APP_ID: "APP", CONF_EMAIL: "user@example.test"})
    ]


def test_migrate_entry_removes_legacy_login_token() -> None:
    asyncio.run(_test_migrate_entry_removes_legacy_login_token())


async def _test_migrate_entry_removes_legacy_login_token() -> None:
    hass = SimpleNamespace(config_entries=FakeConfigEntries())
    entry = FakeEntry()
    entry.title = "OK (OK User)"
    entry.data = {
        "login_token": "legacy-token",
        CONF_APP_ID: "APP",
        CONF_EMAIL: "user@example.test",
    }
    entry.version = 1
    entry.minor_version = 1

    assert await async_migrate_entry(hass, entry) is True
    assert entry.data == {CONF_APP_ID: "APP", CONF_EMAIL: "user@example.test"}
    assert entry.title == "OK (user@example.test)"
    assert hass.config_entries.updated == [
        (entry, {CONF_APP_ID: "APP", CONF_EMAIL: "user@example.test"})
    ]
    from custom_components.ok.config_flow import OkConfigFlow

    assert entry.version == OkConfigFlow.VERSION
    assert entry.minor_version == OkConfigFlow.MINOR_VERSION


def test_migrate_entry_refuses_future_versions() -> None:
    asyncio.run(_test_migrate_entry_refuses_future_versions())


async def _test_migrate_entry_refuses_future_versions() -> None:
    hass = SimpleNamespace(config_entries=FakeConfigEntries())
    entry = FakeEntry()
    entry.data = {"login_token": "legacy-token", CONF_APP_ID: "APP"}
    entry.version = 99
    entry.minor_version = 0

    assert await async_migrate_entry(hass, entry) is False
    assert entry.data == {"login_token": "legacy-token", CONF_APP_ID: "APP"}
    assert hass.config_entries.updated == []

    entry.version = 1
    entry.minor_version = 99

    assert await async_migrate_entry(hass, entry) is False
    assert entry.data == {"login_token": "legacy-token", CONF_APP_ID: "APP"}
    assert hass.config_entries.updated == []


def test_home_assistant_triggered_migration_removes_legacy_login_token(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(
        _test_home_assistant_triggered_migration_removes_legacy_login_token(tmp_path, monkeypatch)
    )


async def _test_home_assistant_triggered_migration_removes_legacy_login_token(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    import custom_components.ok.config_flow  # noqa: F401
    from custom_components.ok.config_flow import OkConfigFlow

    import custom_components.ok as ok

    class Integration:
        async def async_get_component(self) -> object:
            return ok

    async def async_get_integration(hass: HomeAssistant, domain: str) -> Integration:
        assert domain == "ok"
        return Integration()

    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain="ok",
        title="OK",
        unique_id="1000001",
        data={
            "login_token": "legacy-token",
            CONF_APP_ID: "APP",
            CONF_EMAIL: "user@example.test",
        },
        options={},
        source=config_entries.SOURCE_USER,
        discovery_keys=MappingProxyType({}),
        subentries_data=(),
    )
    hass.config_entries._entries[entry.entry_id] = entry
    monkeypatch.setattr("homeassistant.loader.async_get_integration", async_get_integration)

    try:
        assert await entry.async_migrate(hass) is True
        assert entry.data == {CONF_APP_ID: "APP", CONF_EMAIL: "user@example.test"}
        assert entry.title == "OK (user@example.test)"
        assert entry.version == OkConfigFlow.VERSION
        assert entry.minor_version == OkConfigFlow.MINOR_VERSION
    finally:
        await hass.async_stop()


def test_client_from_entry_uses_bundled_client_and_runtime_constants(
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(_test_client_from_entry_uses_bundled_client_and_runtime_constants(monkeypatch))


async def _test_client_from_entry_uses_bundled_client_and_runtime_constants(
    monkeypatch: MonkeyPatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("test must not perform HTTP requests")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        monkeypatch.setattr(
            "homeassistant.helpers.httpx_client.get_async_client",
            lambda hass: http_client,
        )
        client = _client_from_entry(
            SimpleNamespace(),
            SimpleNamespace(
                data={
                    CONF_APP_ID: "APP",
                    CONF_DEVICE_ID: "device-id",
                    CONF_DEVICE_FRIENDLY_ID: "friendly-id",
                }
            ),
        )

        assert client.config.app_id == "APP"
        assert client.config.app_secret == APP_SECRET
        assert client.config.device_id == "device-id"
        assert client.config.device_friendly_id == "friendly-id"
        assert client.config.login_token is None
        assert client.config.app_platform == APP_PLATFORM
        assert client.config.app_version == __version__


def test_setup_entry_cleans_up_when_platform_forwarding_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(_test_setup_entry_cleans_up_when_platform_forwarding_fails(monkeypatch))


async def _test_setup_entry_cleans_up_when_platform_forwarding_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    import custom_components.ok.coordinator as coordinator_module

    import custom_components.ok as ok

    client = FakeClient()
    coordinator: FakeCoordinator | None = None
    listener_removed_count = 0

    def remove_listener() -> None:
        nonlocal listener_removed_count
        listener_removed_count += 1

    def build_coordinator(hass: Any, entry: Any, client: FakeClient) -> FakeCoordinator:
        nonlocal coordinator
        coordinator = FakeCoordinator(hass, entry, client)
        return coordinator

    forward_error = RuntimeError("platform setup failed")
    config_entries = FakeConfigEntries(forward_error=forward_error)
    hass = SimpleNamespace(config_entries=config_entries)
    entry = FakeEntry(update_listener_remover=remove_listener)
    config_entries.entries = [entry]

    monkeypatch.setattr(ok, "_client_from_entry", lambda hass, entry: client)
    monkeypatch.setattr(coordinator_module, "OkDataUpdateCoordinator", build_coordinator)

    with pytest.raises(RuntimeError, match="platform setup failed"):
        await async_setup_entry(hass, entry)

    assert coordinator is not None
    assert coordinator.first_refresh_count == 1
    assert hass.config_entries.forwarded == [(entry, PLATFORMS)]
    assert listener_removed_count == 1
    assert entry.unload_callbacks == []
    for callback in entry.unload_callbacks:
        callback()
    assert listener_removed_count == 1
    assert coordinator.closed is True
    assert client.closed is True
    assert not hasattr(entry, "runtime_data")
    entry.state = ConfigEntryState.LOADED
    assert _loaded_entries(hass) == []


def test_setup_entry_cleans_up_when_platform_forwarding_is_cancelled(
    monkeypatch: MonkeyPatch,
) -> None:
    asyncio.run(_test_setup_entry_cleans_up_when_platform_forwarding_is_cancelled(monkeypatch))


async def _test_setup_entry_cleans_up_when_platform_forwarding_is_cancelled(
    monkeypatch: MonkeyPatch,
) -> None:
    import custom_components.ok.coordinator as coordinator_module

    import custom_components.ok as ok

    client = FakeClient()
    coordinator: FakeCoordinator | None = None

    def build_coordinator(hass: Any, entry: Any, client: FakeClient) -> FakeCoordinator:
        nonlocal coordinator
        coordinator = FakeCoordinator(hass, entry, client)
        return coordinator

    config_entries = FakeConfigEntries(forward_error=asyncio.CancelledError())
    hass = SimpleNamespace(config_entries=config_entries)
    entry = FakeEntry(update_listener_remover=lambda: None)
    config_entries.entries = [entry]

    monkeypatch.setattr(ok, "_client_from_entry", lambda hass, entry: client)
    monkeypatch.setattr(coordinator_module, "OkDataUpdateCoordinator", build_coordinator)

    with pytest.raises(asyncio.CancelledError):
        await async_setup_entry(hass, entry)

    assert coordinator is not None
    assert coordinator.closed is True
    assert client.closed is True
    assert not hasattr(entry, "runtime_data")
    entry.state = ConfigEntryState.LOADED
    assert _loaded_entries(hass) == []


def test_unload_entry_closes_runtime_only_after_platforms_unload() -> None:
    asyncio.run(_test_unload_entry_closes_runtime_only_after_platforms_unload())


async def _test_unload_entry_closes_runtime_only_after_platforms_unload() -> None:
    hass = SimpleNamespace(config_entries=FakeConfigEntries(unload_result=True))
    entry = FakeEntry()
    client = FakeClient()
    coordinator = FakeCoordinator(hass, entry, client)
    entry.runtime_data = OkRuntimeData(client=client, coordinator=coordinator)

    assert await async_unload_entry(hass, entry) is True
    assert hass.config_entries.unloaded == [(entry, PLATFORMS)]
    assert coordinator.closed is True
    assert client.closed is True

    hass = SimpleNamespace(config_entries=FakeConfigEntries(unload_result=False))
    entry = FakeEntry()
    client = FakeClient()
    coordinator = FakeCoordinator(hass, entry, client)
    entry.runtime_data = OkRuntimeData(client=client, coordinator=coordinator)

    assert await async_unload_entry(hass, entry) is False
    assert coordinator.closed is False
    assert client.closed is False


def test_update_listener_and_device_removal() -> None:
    asyncio.run(_test_update_listener_and_device_removal())


async def _test_update_listener_and_device_removal() -> None:
    hass = SimpleNamespace(config_entries=FakeConfigEntries())
    entry = FakeEntry()
    entry.runtime_data = OkRuntimeData(
        client=FakeClient(),
        coordinator=FakeCoordinator(hass, entry, FakeClient()),
    )

    await _async_update_listener(hass, entry)

    assert hass.config_entries.reloads == ["test-entry"]
    assert (
        await async_remove_config_entry_device(
            hass,
            entry,
            SimpleNamespace(identifiers={("ok", "OK-CHARGER-001")}),
        )
        is False
    )
    assert (
        await async_remove_config_entry_device(
            hass,
            entry,
            SimpleNamespace(identifiers={("ok", "account_1000001")}),
        )
        is False
    )
    assert (
        await async_remove_config_entry_device(
            hass,
            entry,
            SimpleNamespace(identifiers={("ok", "STALE-CHARGER")}),
        )
        is True
    )
    assert (
        await async_remove_config_entry_device(
            hass,
            entry,
            SimpleNamespace(identifiers={("other", "DEVICE")}),
        )
        is True
    )
