from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, NotRequired, TypedDict

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class RegisterDeviceResult(TypedDict, total=False):
    DeviceId: str
    DeviceFriendlyId: str
    FeatureFlagListe: list[str] | None


class RegisterDeviceResponse(TypedDict):
    RegistrerDeviceResult: RegisterDeviceResult


class CustomerAddress(TypedDict, total=False):
    KundeNavn: str
    KundeAdresseVejnavnOgHusnr: str
    KundeAdressePostnr: int
    KundeEmailadresse: str
    ErKundeAdresseRegistreret: bool


class LoginResult(TypedDict, total=False):
    Brugernr: int
    Emailadresse: str
    Navn: str
    ErValideret: bool
    ErValideringPaakraevet: bool
    LogIndToken: str
    KundeAdresse: CustomerAddress


class LoginResponse(TypedDict):
    LogIndResult: LoginResult


class DeviceSettingsResult(TypedDict, total=False):
    DeviceId: str
    DeviceFriendlyId: str
    FeatureFlagListe: list[str]
    Bruger: LoginResult


class DeviceSettingsResponse(TypedDict):
    HentDeviceOpsaetningResult: DeviceSettingsResult


class ChargingAddress(TypedDict, total=False):
    city: str
    postalCode: str
    road: str
    number: int
    letter: str


class ChargingConnector(TypedDict, total=False):
    connectorId: int
    power: int
    type: str


class ChargingStation(TypedDict, total=False):
    csIdentifier: str
    name: str
    serialNumber: str
    model: str
    firmwareVersion: str
    vendor: str
    vendorName: str
    autoStart: bool
    connectors: list[ChargingConnector]


class ChargingLocation(TypedDict, total=False):
    locationId: str
    latitude: float
    longitude: float
    name: str
    electricityPriceZone: str
    address: ChargingAddress
    chargingStations: list[ChargingStation]


class StationPrice(TypedDict, total=False):
    tariffIncludingVat: int
    electricityTaxIncludingVat: int
    electricityPriceIncludingVat: int
    vat: int
    applicableTime: str


class StationPricesResponse(TypedDict, total=False):
    prices: list[StationPrice]
    productType: int
    productName: str
    okProductNo: int
    electricityPriceOrigin: str


class CurrentCharging(TypedDict, total=False):
    csIdentifier: str
    connectorId: int
    locationId: str
    firestoreToken: str
    chargingToken: str


class ChargingCommandResponse(TypedDict, total=False):
    result: str
    firestoreToken: str
    chargingToken: str
    errorcode: NotRequired[int]
    errordescription: NotRequired[str]


class ChargingReceipt(TypedDict, total=False):
    chargingStationId: str
    kWh: float
    chargingStart: str
    chargingEnd: str
    locationName: str
    chargingStationName: str
    totalPriceInOere: int
    noPriceReason: str | None


@dataclass(frozen=True, slots=True)
class FirestoreDocument:
    """Decoded Firestore document returned by the OK status endpoints."""

    name: str
    fields: Mapping[str, JsonValue]
    create_time: str | None
    update_time: str | None
    raw: Mapping[str, Any] = field(repr=False)


@dataclass(frozen=True, slots=True)
class FirestoreWatchEvent:
    """Document event delivered by a Firestore realtime watcher."""

    document: FirestoreDocument | None
    exists: bool
    read_time: object | None = field(default=None, repr=False)
    changes: tuple[object, ...] = field(default_factory=tuple, repr=False)
