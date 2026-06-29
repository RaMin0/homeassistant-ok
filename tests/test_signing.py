from __future__ import annotations

import hashlib
import hmac

from api._signing import SHA_1, SHA_256, add_hmac, generate_signature


def test_generate_signature_matches_ok_payload_shape() -> None:
    payload = {"timestamp": 123, "deviceId": "device/1"}

    signature = generate_signature("APP", "SECRET", payload, algorithm=SHA_256)

    serialized_like_ok_app = rb'[{"deviceId":"device\/1"},{"timestamp":123}]'
    expected = hmac.new(b"SECRETAPP", serialized_like_ok_app, hashlib.sha256).hexdigest()
    assert signature == expected


def test_generate_signature_supports_service_sha1() -> None:
    payload = {"appId": "APP", "osDeviceToken": "os-token"}

    signature = generate_signature("APP", "SECRET", payload, algorithm=SHA_1)

    assert len(signature) == 40
    assert (
        signature
        == hmac.new(
            b"SECRETAPP",
            b'[{"appId":"APP"},{"osDeviceToken":"os-token"}]',
            hashlib.sha1,
        ).hexdigest()
    )


def test_add_hmac_preserves_payload_and_adds_signature() -> None:
    signed = add_hmac({"appId": "APP"}, app_id="APP", app_secret="SECRET")

    assert signed["appId"] == "APP"
    assert signed["hmac"] == generate_signature(
        "APP",
        "SECRET",
        {"appId": "APP"},
        algorithm=SHA_1,
    )
