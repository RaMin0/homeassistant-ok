from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from custom_components.ok.api import (
    AsyncOkApiClient,
    OkApiClient,
    OkConfigurationError,
    parse_nanoseconds_timestamp,
)
from custom_components.ok.api._firestore import (
    charging_transaction_document_path,
    decode_firestore_document,
    decode_firestore_value,
    watch_firestore_document,
)


def test_decode_firestore_document_supports_collection_value_types() -> None:
    document = decode_firestore_document(
        {
            "name": "documents/OK/Emsp/RemoteTransactions/token",
            "fields": {
                "status": {"stringValue": "Charging"},
                "chargeInWh": {"integerValue": "5835"},
                "enabled": {"booleanValue": True},
                "nested": {"mapValue": {"fields": {"k": {"stringValue": "v"}}}},
                "items": {
                    "arrayValue": {"values": [{"integerValue": "1"}, {"stringValue": "two"}]}
                },
            },
            "createTime": "2025-01-01T00:00:00Z",
        }
    )

    assert document.fields == {
        "status": "Charging",
        "chargeInWh": 5835,
        "enabled": True,
        "nested": {"k": "v"},
        "items": [1, "two"],
    }
    assert parse_nanoseconds_timestamp("1749471851000000000") == "2025-06-09T12:24:11Z"


def test_decode_firestore_value_handles_edge_shapes() -> None:
    assert decode_firestore_value({"nullValue": None}) is None
    assert decode_firestore_value({"doubleValue": "1.25"}) == 1.25
    assert decode_firestore_value({"timestampValue": "2025-01-01T00:00:00Z"})
    assert decode_firestore_value({"bytesValue": "abc"}) == "abc"
    assert decode_firestore_value({"referenceValue": "documents/OK/Emsp"}) == "documents/OK/Emsp"
    assert decode_firestore_value({"geoPointValue": {"latitude": 55.0, "longitude": 12.0}}) == {
        "latitude": 55.0,
        "longitude": 12.0,
    }
    assert decode_firestore_value({"geoPointValue": "bad"}) == {}
    assert decode_firestore_value({"arrayValue": "bad"}) == []
    assert decode_firestore_value({"arrayValue": {"values": "bad"}}) == []
    assert decode_firestore_value({"mapValue": "bad"}) == {}
    assert decode_firestore_value({"mapValue": {"fields": "bad"}}) == {}
    assert decode_firestore_value({"unknownValue": "bad"}) == {}
    assert decode_firestore_document({"fields": []}).fields == {}
    assert charging_transaction_document_path("token") == "OK/Emsp/RemoteTransactions/token"


def test_realtime_watcher_uses_firestore_document_path_and_decodes_snapshot() -> None:
    events = []

    @dataclass
    class Reference:
        path: str

    class Snapshot:
        exists = True
        reference = Reference("OK/Emsp/ChargingStations/Status/Connectors/station__1")
        create_time = None
        update_time = datetime(2025, 1, 1, tzinfo=UTC)

        def to_dict(self) -> dict[str, object]:
            return {
                "status": "Charging",
                "powerInW": 3522,
                "updated": datetime(2025, 1, 1, tzinfo=UTC),
                "items": (1, "two"),
                "custom": object(),
            }

    class Watch:
        unsubscribed = False

        def unsubscribe(self) -> None:
            self.unsubscribed = True

    class DocumentReference:
        def __init__(self) -> None:
            self.watch = Watch()

        def on_snapshot(self, callback: object) -> Watch:
            assert callable(callback)
            callback([Snapshot()], ["change"], "read-time")
            return self.watch

    class FirestoreClient:
        def __init__(self) -> None:
            self.path = ""
            self.reference = DocumentReference()

        def document(self, path: str) -> DocumentReference:
            self.path = path
            return self.reference

    firestore_client = FirestoreClient()
    client = OkApiClient()

    subscription = client.watch_charging_station_status(
        "station",
        1,
        events.append,
        firestore_client=firestore_client,
    )
    with subscription:
        pass
    subscription.close()
    subscription.unsubscribe()

    assert firestore_client.path == "OK/Emsp/ChargingStations/Status/Connectors/station__1"
    assert events[0].exists is True
    assert events[0].document is not None
    assert events[0].document.fields["status"] == "Charging"
    assert events[0].document.fields["items"] == [1, "two"]
    assert events[0].document.update_time == "2025-01-01T00:00:00+00:00"
    assert firestore_client.reference.watch.unsubscribed is True


def test_realtime_watcher_reports_deleted_or_missing_snapshots() -> None:
    events = []

    class Watch:
        def unsubscribe(self) -> None:
            pass

    class DocumentReference:
        def on_snapshot(self, callback: object) -> Watch:
            assert callable(callback)
            callback([], [], None)
            return Watch()

    class FirestoreClient:
        def document(self, path: str) -> DocumentReference:
            assert path == "OK/Emsp/RemoteTransactions/token"
            return DocumentReference()

    client = OkApiClient()
    client.watch_charging_status("token", events.append, firestore_client=FirestoreClient())

    assert events[0].exists is False
    assert events[0].document is None


def test_realtime_watcher_closes_owned_firestore_client(monkeypatch) -> None:
    import custom_components.ok.api._firestore as firestore_module

    events = []

    class Watch:
        unsubscribe_count = 0

        def unsubscribe(self) -> None:
            self.unsubscribe_count += 1

    class DocumentReference:
        def __init__(self) -> None:
            self.watch = Watch()

        def on_snapshot(self, callback: object) -> Watch:
            assert callable(callback)
            return self.watch

    class FirestoreClient:
        closed = False

        def __init__(self) -> None:
            self.reference = DocumentReference()

        def document(self, path: str) -> DocumentReference:
            assert path == "path"
            return self.reference

        def close(self) -> None:
            self.closed = True

    firestore_client = FirestoreClient()
    monkeypatch.setattr(
        firestore_module,
        "_create_default_firestore_client",
        lambda *, project_id, credentials: firestore_client,
    )

    subscription = watch_firestore_document("path", events.append)
    subscription.unsubscribe()
    subscription.unsubscribe()

    assert firestore_client.closed is True
    assert firestore_client.reference.watch.unsubscribe_count == 1


def test_realtime_watcher_closes_owned_firestore_client_after_setup_failure(
    monkeypatch,
) -> None:
    import custom_components.ok.api._firestore as firestore_module

    class FirestoreClient:
        closed = False

        def document(self, path: str) -> object:
            return object()

        def close(self) -> None:
            self.closed = True

    firestore_client = FirestoreClient()
    monkeypatch.setattr(
        firestore_module,
        "_create_default_firestore_client",
        lambda *, project_id, credentials: firestore_client,
    )

    with pytest.raises(OkConfigurationError, match="on_snapshot"):
        watch_firestore_document("path", lambda event: None)

    assert firestore_client.closed is True


def test_async_realtime_watcher_wraps_sync_firestore_subscription() -> None:
    asyncio.run(_test_async_realtime_watcher_wraps_sync_firestore_subscription())


async def _test_async_realtime_watcher_wraps_sync_firestore_subscription() -> None:
    runner_calls = 0

    @dataclass
    class Reference:
        path: str

    class Snapshot:
        def __init__(self, status: str) -> None:
            self.status = status
            self.exists = True
            self.reference = Reference("OK/Emsp/RemoteTransactions/token")
            self.create_time = None
            self.update_time = datetime(2025, 1, 1, tzinfo=UTC)

        def to_dict(self) -> dict[str, object]:
            return {"status": self.status}

    class Watch:
        unsubscribed = False

        def unsubscribe(self) -> None:
            self.unsubscribed = True

    class DocumentReference:
        def __init__(self) -> None:
            self.watch = Watch()

        def on_snapshot(self, callback: object) -> Watch:
            assert callable(callback)
            callback([Snapshot("Preparing")], [], "read-time")
            callback([Snapshot("Charging")], [], "read-time")
            return self.watch

    class FirestoreClient:
        def __init__(self) -> None:
            self.reference = DocumentReference()

        def document(self, path: str) -> DocumentReference:
            assert path == "OK/Emsp/RemoteTransactions/token"
            return self.reference

    async def run_blocking[T](func: Callable[[], T]) -> T:
        nonlocal runner_calls
        runner_calls += 1
        return func()

    firestore_client = FirestoreClient()
    async with AsyncOkApiClient(blocking_call_runner=run_blocking) as client:
        subscription = await client.watch_charging_status(
            "token",
            firestore_client=firestore_client,
            max_queue_size=1,
        )
        event = await asyncio.wait_for(subscription.__anext__(), timeout=1)
        await subscription.aclose()

        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(subscription.__anext__(), timeout=1)

    assert subscription.document_path == "OK/Emsp/RemoteTransactions/token"
    assert event.exists is True
    assert event.document is not None
    assert event.document.fields["status"] == "Charging"
    assert firestore_client.reference.watch.unsubscribed is True
    assert runner_calls == 2


def test_async_realtime_watcher_can_retry_failed_close() -> None:
    asyncio.run(_test_async_realtime_watcher_can_retry_failed_close())


async def _test_async_realtime_watcher_can_retry_failed_close() -> None:
    @dataclass
    class Reference:
        path: str

    class Snapshot:
        exists = True
        reference = Reference("OK/Emsp/RemoteTransactions/token")
        create_time = None
        update_time = None

        def to_dict(self) -> dict[str, object]:
            return {"status": "Charging"}

    class Watch:
        unsubscribe_count = 0

        def unsubscribe(self) -> None:
            self.unsubscribe_count += 1
            if self.unsubscribe_count == 1:
                raise RuntimeError("temporary close failure")

    class DocumentReference:
        def __init__(self) -> None:
            self.watch = Watch()
            self.callback: object | None = None

        def on_snapshot(self, callback: object) -> Watch:
            assert callable(callback)
            self.callback = callback
            return self.watch

    class FirestoreClient:
        def __init__(self) -> None:
            self.reference = DocumentReference()

        def document(self, path: str) -> DocumentReference:
            return self.reference

    async def run_blocking[T](func: Callable[[], T]) -> T:
        return func()

    firestore_client = FirestoreClient()
    async with AsyncOkApiClient(blocking_call_runner=run_blocking) as client:
        subscription = await client.watch_charging_status(
            "token",
            firestore_client=firestore_client,
        )

        with pytest.raises(RuntimeError, match="temporary close failure"):
            await subscription.aclose()
        assert subscription.closed is False

        callback = firestore_client.reference.callback
        assert callable(callback)
        callback([Snapshot()], [], "read-time")
        event = await asyncio.wait_for(subscription.__anext__(), timeout=1)
        assert event.document is not None
        assert event.document.fields["status"] == "Charging"

        await subscription.aclose()

    assert subscription.closed is True
    assert firestore_client.reference.watch.unsubscribe_count == 2


def test_async_realtime_watcher_rejects_unbounded_queue() -> None:
    asyncio.run(_test_async_realtime_watcher_rejects_unbounded_queue())


async def _test_async_realtime_watcher_rejects_unbounded_queue() -> None:
    async with AsyncOkApiClient() as client:
        with pytest.raises(ValueError, match="max_queue_size"):
            await client.watch_charging_status(
                "token",
                firestore_client=object(),
                max_queue_size=0,
            )


def test_async_realtime_watcher_supports_async_context_manager_and_iteration() -> None:
    asyncio.run(_test_async_realtime_watcher_supports_async_context_manager_and_iteration())


async def _test_async_realtime_watcher_supports_async_context_manager_and_iteration() -> None:
    @dataclass
    class Reference:
        path: str

    class Snapshot:
        exists = True
        reference = Reference("OK/Emsp/RemoteTransactions/token")
        create_time = None
        update_time = None

        def to_dict(self) -> dict[str, object]:
            return {"status": "Charging"}

    class Watch:
        unsubscribed = False

        def unsubscribe(self) -> None:
            self.unsubscribed = True

    class DocumentReference:
        def __init__(self) -> None:
            self.watch = Watch()

        def on_snapshot(self, callback: object) -> Watch:
            assert callable(callback)
            callback([Snapshot()], [], "read-time")
            return self.watch

    class FirestoreClient:
        def __init__(self) -> None:
            self.reference = DocumentReference()

        def document(self, path: str) -> DocumentReference:
            return self.reference

    async def run_blocking[T](func: Callable[[], T]) -> T:
        return func()

    firestore_client = FirestoreClient()
    async with AsyncOkApiClient(blocking_call_runner=run_blocking) as client:
        async with await client.watch_charging_status(
            "token",
            firestore_client=firestore_client,
        ) as subscription:
            async for event in subscription:
                assert event.document is not None
                assert event.document.fields["status"] == "Charging"
                break
        await subscription.aclose()

    assert subscription.closed is True
    assert firestore_client.reference.watch.unsubscribed is True


def test_realtime_watcher_validates_firestore_client_shape() -> None:
    with pytest.raises(OkConfigurationError, match="document"):
        watch_firestore_document("path", lambda event: None, firestore_client=object())

    class MissingOnSnapshotClient:
        def document(self, path: str) -> object:
            return object()

    with pytest.raises(OkConfigurationError, match="on_snapshot"):
        watch_firestore_document(
            "path", lambda event: None, firestore_client=MissingOnSnapshotClient()
        )


def test_realtime_watcher_requires_optional_dependency_by_default(monkeypatch) -> None:
    import custom_components.ok.api._firestore as firestore_module

    def import_module(name: str) -> object:
        raise ImportError(name)

    monkeypatch.setattr(firestore_module, "import_module", import_module)

    with pytest.raises(OkConfigurationError, match="firebase"):
        watch_firestore_document("path", lambda event: None)
