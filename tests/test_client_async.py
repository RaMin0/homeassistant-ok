from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from api import (
    AsyncOkApiClient,
    OkCommandError,
    OkConfigurationError,
    OkConnectionError,
    OkTimeoutError,
)


def test_async_client_supports_service_data_and_status_methods() -> None:
    async def scenario() -> None:
        responses = [
            {
                "RegistrerDeviceResult": {
                    "DeviceId": "device-id",
                    "DeviceFriendlyId": "FRIEND",
                }
            },
            {"LogIndResult": {"LogIndToken": "login-token"}},
            {
                "HentDeviceOpsaetningResult": {
                    "DeviceId": "device-id",
                    "DeviceFriendlyId": "FRIEND",
                    "Bruger": {"LogIndToken": "settings-token"},
                }
            },
        ]

        async def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            url = str(request.url)
            if path.startswith("/service/"):
                body = json.loads(request.content)
                assert "hmac" in body
                return httpx.Response(200, json=responses.pop(0))

            if path.startswith("/api/"):
                assert request.headers["OK-App-DeviceId"] == "device-id"
                assert request.headers["OK-App-Hmac-Timestamp"] == "456"

            if path.endswith("/location/all"):
                return httpx.Response(200, json=[{"locationId": "loc"}])
            if url.endswith("/dayAheadPrices/station%2Fid"):
                return httpx.Response(
                    200,
                    json={"prices": [{"applicableTime": "2025-01-01T00:00:00Z"}]},
                )
            if path.endswith("/setAutostart"):
                return httpx.Response(200, content=b"")
            if path.endswith("/restart"):
                return httpx.Response(200, content=b"")
            if path.endswith("/get-current-chargings"):
                return httpx.Response(
                    200,
                    json={
                        "current_charging": [
                            {
                                "charging_station_id": "OK-CHARGER-001",
                                "connector_id": 1,
                                "location_identifier": "loc",
                                "charging_token": "token",
                                "charging_transaction_type": "Scheduled",
                                "schedules": [
                                    {
                                        "from": "2025-01-01T01:00:00+00:00",
                                        "to": None,
                                    }
                                ],
                                "initiated_at": "2025-01-01T00:30:00+00:00",
                            }
                        ]
                    },
                )
            if path.endswith("/start"):
                return httpx.Response(200, json={"result": "Success", "chargingToken": "token"})
            if path.endswith("/schedule-charging"):
                body = json.loads(request.content)
                assert body == {
                    "charging-station-id": "OK-CHARGER-001",
                    "charging-token": "token",
                    "from": "2025-01-01T01:00:00+00:00",
                    "to": "2025-01-01T02:00:00+00:00",
                }
                return httpx.Response(
                    200,
                    json={"charging-token": "token", "firestore-token": "token"},
                )
            if path.endswith("/schedule/token"):
                return httpx.Response(200, json={})
            if path.endswith("/stop"):
                return httpx.Response(200, json={})
            if path.endswith("/receipts"):
                return httpx.Response(200, json=[{"chargingStationId": "station-id", "kWh": 1.2}])
            if path.endswith("/quickReceipt/token"):
                return httpx.Response(200, json={"chargingStationId": "station-id", "kWh": 1.2})
            if path.endswith("/ChargingStations/Status/Connectors/station__1"):
                return httpx.Response(
                    200,
                    json={
                        "fields": {
                            "status": {"stringValue": "Charging"},
                            "connectorId": {"integerValue": "1"},
                        }
                    },
                )
            if path.endswith("/RemoteTransactions/token"):
                return httpx.Response(
                    200,
                    json={"fields": {"status": {"stringValue": "Charging"}}},
                )
            raise AssertionError(f"unexpected path {path}")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            async with AsyncOkApiClient(
                app_secret="SECRET",
                http_client=http_client,
                timestamp_provider=lambda: 456,
            ) as client:
                registered = await client.register_device(os_device_token="os-token", app_id="APP")
                logged_in = await client.login("user@example.test", "password")
                settings = await client.get_device_settings()
                stations = await client.get_stations()
                prices = await client.get_station_prices("station/id")
                auto_start = await client.set_station_auto_start("station-id", False)
                restarted = await client.restart_station("station-id")
                chargings = await client.get_chargings()
                started = await client.start_charging(
                    charging_station_id="station-id", connector_id=1
                )
                scheduled = await client.schedule_charging(
                    charging_station_id="station-id",
                    connector_id=1,
                    scheduled_start="2025-01-01T01:00:00+00:00",
                    scheduled_end="2025-01-01T02:00:00+00:00",
                )
                updated = await client.update_charging_schedule(
                    "token",
                    charging_station_id="OK-CHARGER-001",
                    scheduled_start="2025-01-01T01:00:00+00:00",
                    scheduled_end="2025-01-01T02:00:00+00:00",
                )
                cancelled = await client.cancel_charging_schedule("token")
                stopped = await client.stop_charging("token")
                receipts = await client.get_charging_receipts()
                receipt = await client.get_charging_receipt("token")
                station_status = await client.get_charging_station_status("station", 1)
                charging_status = await client.get_charging_status("token")

        assert registered["RegistrerDeviceResult"]["DeviceId"] == "device-id"
        assert logged_in["LogIndResult"]["LogIndToken"] == "login-token"
        assert settings["HentDeviceOpsaetningResult"]["Bruger"]["LogIndToken"] == "settings-token"
        assert stations[0]["locationId"] == "loc"
        assert prices["prices"][0]["applicableTime"] == "2025-01-01T00:00:00Z"
        assert auto_start == {}
        assert restarted == {}
        assert chargings[0]["csIdentifier"] == "OK-CHARGER-001"
        assert chargings[0]["connectorId"] == 1
        assert chargings[0]["locationId"] == "loc"
        assert chargings[0]["chargingToken"] == "token"
        assert chargings[0]["firestoreToken"] == "token"
        assert chargings[0]["chargingTransactionType"] == "Scheduled"
        assert chargings[0]["schedules"][0]["scheduledStart"] == "2025-01-01T01:00:00+00:00"
        assert chargings[0]["schedules"][0]["scheduledEnd"] is None
        assert started["result"] == "Success"
        assert scheduled["chargingToken"] == "token"
        assert updated["chargingToken"] == "token"
        assert updated["firestoreToken"] == "token"
        assert cancelled == {}
        assert stopped == {}
        assert receipts[0]["chargingStationId"] == "station-id"
        assert receipt["chargingStationId"] == "station-id"
        assert station_status.fields["connectorId"] == 1
        assert charging_status.fields["status"] == "Charging"

    asyncio.run(scenario())


def test_async_client_edge_errors_and_injected_client_lifecycle() -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("test must not perform HTTP requests")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = AsyncOkApiClient(
                app_id="APP",
                app_secret="SECRET",
                device_id="device-id",
                http_client=http_client,
            )

            with pytest.raises(OkConfigurationError, match="device_friendly_id"):
                await client.start_charging(charging_station_id="station-id", connector_id=1)

            await client.aclose()
            assert http_client.is_closed is False

    asyncio.run(scenario())


def test_async_command_failure_raises_typed_client_error() -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"result": "Rejected", "errorcode": 42, "errordescription": "busy"},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = AsyncOkApiClient(
                app_id="APP",
                app_secret="SECRET",
                device_id="device-id",
                http_client=http_client,
                timestamp_provider=lambda: 456,
            )
            client.config.device_friendly_id = "FRIEND"

            with pytest.raises(OkCommandError) as error:
                await client.start_charging(charging_station_id="station-id", connector_id=1)

        assert str(error.value) == "OK command failed: busy"
        assert error.value.error_code == 42

    asyncio.run(scenario())


def test_injected_async_client_receives_configured_timeout() -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            timeout = request.extensions["timeout"]
            assert timeout["connect"] == 7.0
            assert timeout["read"] == 7.0
            return httpx.Response(200, json=[])

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = AsyncOkApiClient(
                app_id="APP",
                app_secret="SECRET",
                device_id="device-id",
                timeout=7.0,
                http_client=http_client,
                timestamp_provider=lambda: 456,
            )

            assert await client.get_stations() == []

    asyncio.run(scenario())


def test_async_transport_errors_are_mapped_to_client_exceptions() -> None:
    async def scenario() -> None:
        async def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")

        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as (
            http_client
        ):
            client = AsyncOkApiClient(
                app_id="APP",
                app_secret="SECRET",
                device_id="device-id",
                http_client=http_client,
                timestamp_provider=lambda: 456,
            )
            with pytest.raises(OkTimeoutError):
                await client.get_stations()

        async def connection_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route")

        async with httpx.AsyncClient(transport=httpx.MockTransport(connection_handler)) as (
            http_client
        ):
            client = AsyncOkApiClient(
                app_id="APP",
                app_secret="SECRET",
                device_id="device-id",
                http_client=http_client,
                timestamp_provider=lambda: 456,
            )
            with pytest.raises(OkConnectionError):
                await client.get_stations()

    asyncio.run(scenario())
