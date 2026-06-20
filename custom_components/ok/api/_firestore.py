from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import import_module
from typing import Any, Protocol, cast

from ._errors import OkConfigurationError
from ._models import FirestoreDocument, FirestoreWatchEvent, JsonObject, JsonValue

DEFAULT_FIRESTORE_PROJECT_ID = "knp-ok-app-prod"
DEFAULT_FIRESTORE_DATABASE = "(default)"
DEFAULT_STATUS_DOCUMENT_ROOT = "OK/Emsp"
_LOGGER = logging.getLogger(__name__)

FirestoreWatchCallback = Callable[[FirestoreWatchEvent], None]
type _QueuedFirestoreWatchEvent = FirestoreWatchEvent | None


class AsyncBlockingCallRunner(Protocol):
    """Run a blocking callable without blocking the current event loop."""

    def __call__[T](self, func: Callable[[], T]) -> Awaitable[T]: ...


@dataclass(slots=True)
class _AsyncFirestoreWatchState:
    closed: bool = False
    closing: bool = False


@dataclass(frozen=True, slots=True)
class FirestoreWatchSubscription:
    """Handle returned by a Firestore realtime watcher."""

    document_path: str
    _watch: object
    _owned_client: object | None = None
    _closed: bool = field(default=False, init=False)

    def unsubscribe(self) -> None:
        if self._closed:
            return
        unsubscribe = getattr(self._watch, "unsubscribe", None)
        try:
            if callable(unsubscribe):
                unsubscribe()
            try:
                _close_owned_firestore_client(self._owned_client)
            finally:
                object.__setattr__(self, "_closed", True)
        except Exception:
            _close_owned_firestore_client(self._owned_client)
            raise

    def close(self) -> None:
        self.unsubscribe()

    def __enter__(self) -> FirestoreWatchSubscription:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.unsubscribe()


@dataclass(slots=True)
class AsyncFirestoreWatchSubscription:
    """Async event-stream wrapper for a Firestore realtime watcher."""

    document_path: str
    _subscription: FirestoreWatchSubscription
    _run_blocking: AsyncBlockingCallRunner
    _queue: asyncio.Queue[_QueuedFirestoreWatchEvent] = field(repr=False)
    _state: _AsyncFirestoreWatchState = field(repr=False)

    def __aiter__(self) -> AsyncIterator[FirestoreWatchEvent]:
        return self

    async def __anext__(self) -> FirestoreWatchEvent:
        event = await self._queue.get()
        if event is None:
            raise StopAsyncIteration
        return event

    async def aclose(self) -> None:
        """Close the watcher without blocking the event loop."""
        if self._state.closed or self._state.closing:
            return
        self._state.closing = True
        try:
            await self._run_blocking(self._subscription.unsubscribe)
        except Exception:
            self._state.closing = False
            raise
        self._state.closed = True
        self._state.closing = False
        _enqueue_queued_event(self._queue, self._state, None, wake_closed=True)

    @property
    def closed(self) -> bool:
        """Return whether the watcher closed successfully."""
        return self._state.closed

    async def __aenter__(self) -> AsyncFirestoreWatchSubscription:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.aclose()


def charging_station_status_document_path(charging_station_id: str, connector_id: int) -> str:
    return (
        f"{DEFAULT_STATUS_DOCUMENT_ROOT}/ChargingStations/Status/Connectors/"
        f"{charging_station_id}__{connector_id}"
    )


def charging_transaction_document_path(charging_token: str) -> str:
    return f"{DEFAULT_STATUS_DOCUMENT_ROOT}/RemoteTransactions/{charging_token}"


def parse_nanoseconds_timestamp(value: str | int) -> str:
    nanoseconds = int(value)
    seconds, nanos = divmod(nanoseconds, 1_000_000_000)
    timestamp = datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=nanos // 1_000)
    return timestamp.isoformat().replace("+00:00", "Z")


def decode_firestore_value(value: Mapping[str, Any]) -> JsonValue:
    if "nullValue" in value:
        return None
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "integerValue" in value:
        return int(str(value["integerValue"]))
    if "doubleValue" in value:
        return float(str(value["doubleValue"]))
    if "timestampValue" in value:
        return str(value["timestampValue"])
    if "stringValue" in value:
        return str(value["stringValue"])
    if "bytesValue" in value:
        return str(value["bytesValue"])
    if "referenceValue" in value:
        return str(value["referenceValue"])
    if "geoPointValue" in value:
        point = value["geoPointValue"]
        if isinstance(point, Mapping):
            return {
                "latitude": float(str(point.get("latitude", 0))),
                "longitude": float(str(point.get("longitude", 0))),
            }
        return {}
    if "arrayValue" in value:
        array_value = value["arrayValue"]
        if not isinstance(array_value, Mapping):
            return []
        items = array_value.get("values", [])
        if not isinstance(items, list):
            return []
        return [
            decode_firestore_value(cast(Mapping[str, Any], item))
            for item in items
            if isinstance(item, Mapping)
        ]
    if "mapValue" in value:
        map_value = value["mapValue"]
        if not isinstance(map_value, Mapping):
            return {}
        fields = map_value.get("fields", {})
        if not isinstance(fields, Mapping):
            return {}
        return {
            str(key): decode_firestore_value(cast(Mapping[str, Any], nested))
            for key, nested in fields.items()
            if isinstance(nested, Mapping)
        }
    return {}


def decode_firestore_document(raw: Mapping[str, Any]) -> FirestoreDocument:
    fields_raw = raw.get("fields", {})
    fields: JsonObject = {}
    if isinstance(fields_raw, Mapping):
        fields = {
            str(key): decode_firestore_value(cast(Mapping[str, Any], value))
            for key, value in fields_raw.items()
            if isinstance(value, Mapping)
        }
    return FirestoreDocument(
        name=str(raw.get("name", "")),
        fields=fields,
        create_time=_optional_str(raw.get("createTime")),
        update_time=_optional_str(raw.get("updateTime")),
        raw=raw,
    )


def watch_firestore_document(
    document_path: str,
    callback: FirestoreWatchCallback,
    *,
    firestore_client: object | None = None,
    project_id: str = DEFAULT_FIRESTORE_PROJECT_ID,
    credentials: object | None = None,
) -> FirestoreWatchSubscription:
    """Watch a Firestore document with an optional injected client or credentials.

    When credentials are omitted, the default Google Firestore client is created with anonymous
    credentials because OK exposes these status documents for unauthenticated reads.
    """
    owned_client: object | None = None
    if firestore_client is None:
        client = _create_default_firestore_client(project_id=project_id, credentials=credentials)
        owned_client = client
    else:
        client = firestore_client
    document_method = getattr(client, "document", None)
    if not callable(document_method):
        _close_owned_firestore_client(owned_client)
        raise OkConfigurationError("firestore_client must provide a document(path) method")

    try:
        document_ref = document_method(document_path)
        on_snapshot = getattr(document_ref, "on_snapshot", None)
        if not callable(on_snapshot):
            raise OkConfigurationError(
                "firestore document reference must provide on_snapshot(callback)"
            )

        def _on_snapshot(
            snapshots: Sequence[object],
            changes: Sequence[object],
            read_time: object | None,
        ) -> None:
            snapshot = snapshots[0] if snapshots else None
            callback(_snapshot_to_event(snapshot, changes, read_time))

        watch = on_snapshot(_on_snapshot)
    except Exception:
        _close_owned_firestore_client(owned_client)
        raise
    return FirestoreWatchSubscription(
        document_path=document_path,
        _watch=watch,
        _owned_client=owned_client,
    )


async def async_watch_firestore_document(
    document_path: str,
    *,
    run_blocking: AsyncBlockingCallRunner | None = None,
    firestore_client: object | None = None,
    project_id: str = DEFAULT_FIRESTORE_PROJECT_ID,
    credentials: object | None = None,
    max_queue_size: int = 64,
) -> AsyncFirestoreWatchSubscription:
    """Watch a Firestore document as an async event stream.

    The async queue is bounded. If events arrive faster than Home Assistant can consume them, the
    oldest queued event is dropped so the stream converges to the newest Firestore state.
    """
    if max_queue_size < 1:
        raise ValueError("max_queue_size must be at least 1")
    loop = asyncio.get_running_loop()
    state = _AsyncFirestoreWatchState()
    queue: asyncio.Queue[_QueuedFirestoreWatchEvent] = asyncio.Queue(maxsize=max_queue_size)
    runner = run_blocking or _run_blocking_in_thread

    def callback(event: FirestoreWatchEvent) -> None:
        try:
            loop.call_soon_threadsafe(_enqueue_queued_event, queue, state, event)
        except RuntimeError:
            pass

    subscription = await runner(
        lambda: watch_firestore_document(
            document_path,
            callback,
            firestore_client=firestore_client,
            project_id=project_id,
            credentials=credentials,
        )
    )
    return AsyncFirestoreWatchSubscription(
        document_path=document_path,
        _subscription=subscription,
        _run_blocking=runner,
        _queue=queue,
        _state=state,
    )


async def _run_blocking_in_thread[T](func: Callable[[], T]) -> T:
    return await asyncio.to_thread(func)


def _enqueue_queued_event(
    queue: asyncio.Queue[_QueuedFirestoreWatchEvent],
    state: _AsyncFirestoreWatchState,
    event: _QueuedFirestoreWatchEvent,
    *,
    wake_closed: bool = False,
) -> None:
    if state.closed and not wake_closed:
        return
    if queue.full():
        try:
            queue.get_nowait()
            _LOGGER.debug("Dropped stale OK Firestore watch event because the queue is full")
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(event)


def _close_owned_firestore_client(client: object | None) -> None:
    if client is None:
        return
    close = getattr(client, "close", None)
    if callable(close):
        close()


def _create_default_firestore_client(*, project_id: str, credentials: object | None) -> object:
    try:
        firestore_module = import_module("google.cloud.firestore")
        credentials_module = import_module("google.auth.credentials")
    except ImportError as exc:
        raise OkConfigurationError(
            "Install the firebase extra or pass firestore_client= to use realtime watchers."
        ) from exc

    if credentials is None:
        credentials_cls = credentials_module.AnonymousCredentials
        credentials = credentials_cls()
    client_cls = firestore_module.Client
    return cast(object, client_cls(project=project_id, credentials=credentials))


def _snapshot_to_event(
    snapshot: object | None,
    changes: Sequence[object],
    read_time: object | None,
) -> FirestoreWatchEvent:
    if snapshot is None or not bool(getattr(snapshot, "exists", True)):
        return FirestoreWatchEvent(
            document=None, exists=False, read_time=read_time, changes=tuple(changes)
        )

    to_dict = getattr(snapshot, "to_dict", None)
    fields_obj = to_dict() if callable(to_dict) else {}
    fields = _json_safe(fields_obj)
    if not isinstance(fields, dict):
        fields = {}
    reference = getattr(snapshot, "reference", None)
    document_name = str(getattr(reference, "path", ""))
    return FirestoreWatchEvent(
        document=FirestoreDocument(
            name=document_name,
            fields=fields,
            create_time=_object_time(snapshot, "create_time"),
            update_time=_object_time(snapshot, "update_time"),
            raw=fields,
        ),
        exists=True,
        read_time=read_time,
        changes=tuple(changes),
    )


def _json_safe(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(nested) for key, nested in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    return str(value)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _object_time(obj: object, attr: str) -> str | None:
    value = getattr(obj, attr, None)
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)
