from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import ceil
from typing import Any


class OkApiError(Exception):
    """Base exception for all OK API client failures."""


class OkConfigurationError(OkApiError):
    """Raised when required client configuration is missing."""


class OkConnectionError(OkApiError):
    """Raised when the transport cannot connect to the API."""


class OkTimeoutError(OkConnectionError):
    """Raised when a request exceeds its timeout."""


class OkResponseError(OkApiError):
    """Raised when the API returns an invalid or unsupported response body."""

    def __init__(
        self, message: str, *, status_code: int | None = None, body: str | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class OkCommandError(OkApiError):
    """Raised when an OK command endpoint returns an application-level failure."""

    def __init__(
        self,
        message: str,
        *,
        result: object | None = None,
        error_code: object | None = None,
        error_description: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.result = result
        self.error_code = error_code
        self.error_description = error_description
        self.payload = dict(payload or {})


class OkStatusError(OkApiError):
    """Raised for non-2xx HTTP responses."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        headers: Mapping[str, str],
        payload: Any,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.headers = dict(headers)
        self.payload = payload
        self.request_id = request_id


class OkAuthenticationError(OkStatusError):
    """Raised for authentication failures."""


class OkPermissionDeniedError(OkStatusError):
    """Raised for authorization failures."""


class OkNotFoundError(OkStatusError):
    """Raised when the requested resource does not exist."""


class OkConflictError(OkStatusError):
    """Raised for conflict responses."""


class OkRateLimitError(OkStatusError):
    """Raised when the API reports a rate-limit response."""

    @property
    def retry_after(self) -> int | None:
        """Return the Retry-After header in seconds when the API supplied one."""
        value = self.headers.get("Retry-After") or self.headers.get("retry-after")
        if value is None:
            return None
        value = value.strip()
        try:
            seconds = int(value)
        except ValueError:
            pass
        else:
            if seconds < 0:
                return None
            return seconds

        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        seconds = ceil((retry_at - datetime.now(UTC)).total_seconds())
        if seconds < 0:
            return 0
        return seconds


class OkServerError(OkStatusError):
    """Raised for upstream server errors."""


STATUS_ERROR_BY_CODE: dict[int, type[OkStatusError]] = {
    401: OkAuthenticationError,
    403: OkPermissionDeniedError,
    404: OkNotFoundError,
    409: OkConflictError,
    429: OkRateLimitError,
}


def status_error_class(status_code: int) -> type[OkStatusError]:
    if status_code >= 500:
        return OkServerError
    return STATUS_ERROR_BY_CODE.get(status_code, OkStatusError)
