from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping

from ._models import JsonValue

SignatureAlgorithm = str

SHA_1 = "sha1"
SHA_256 = "sha256"


def generate_signature(
    app_id: str,
    app_secret: str,
    payload: Mapping[str, JsonValue],
    *,
    algorithm: SignatureAlgorithm,
) -> str:
    """Generate the OK HMAC value used by OK app requests.

    The collection signs a JSON string made from key-sorted single-key objects,
    then escapes forward slashes to match JavaScript's post-processing step.
    """

    normalized = [{key: payload[key]} for key in sorted(payload)]
    serialized = json.dumps(normalized, ensure_ascii=False, separators=(",", ":")).replace(
        "/", r"\/"
    )
    digest = getattr(hashlib, algorithm)
    key = f"{app_secret}{app_id}".encode()
    return hmac.new(key, serialized.encode(), digest).hexdigest()


def add_hmac(
    payload: Mapping[str, JsonValue], *, app_id: str, app_secret: str
) -> dict[str, JsonValue]:
    signed = dict(payload)
    signed["hmac"] = generate_signature(app_id, app_secret, signed, algorithm=SHA_1)
    return signed
