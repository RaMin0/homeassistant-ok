# Bundled OK API Client

The OK client currently lives inside the custom component at `custom_components/ok/api`. This is
intentional so HACS and manual installs ship the Home Assistant integration and API client as one
project.

Do not extract the client into a separate package unless that is the explicit task.

## Responsibilities

The bundled client owns OK protocol details:

- API URLs and endpoint paths.
- App registration and login requests.
- HMAC signing.
- Required OK headers.
- HTTP timeouts.
- Response shape validation.
- Typed response aliases and model helpers.
- OK exception classes.
- Firestore document paths and watch helper wrappers.
- Sync and async client APIs where currently implemented.

The Home Assistant integration owns Home Assistant behavior:

- Config flow, options, reauth, and reconfigure.
- Devices and entities.
- Services/actions and buttons.
- DataUpdateCoordinator refresh scheduling.
- Diagnostics and repairs.
- Translations and icons.
- Mapping OK exceptions to Home Assistant exceptions.

`custom_components/ok/api` must not import Home Assistant modules.

## Client Construction In Home Assistant

Home Assistant creates `AsyncOkApiClient` from `custom_components/ok/__init__.py`.

Rules:

- Use Home Assistant's shared `httpx.AsyncClient` from `homeassistant.helpers.httpx_client`.
- Use Home Assistant's version as the OK app version.
- Keep the OK mobile app secret as an integration constant in `const.py`.
- Do not expose the app secret in the config flow or options flow.
- Do not store passwords in config entries.
- Redact app/device/account identifiers and legacy tokens from diagnostics.

## Public Surface

The client public surface is exported from `custom_components/ok/api/__init__.py`. When changing
that surface:

- Keep imports side-effect free.
- Keep typed exports stable unless intentionally making a breaking change.
- Update tests that import from the package root.
- Update documentation when behavior or errors change.

## HTTP And Error Rules

Every request must have an explicit timeout through the client configuration or injected
transport. Do not add unbounded waits.

Map errors into the existing hierarchy:

- Authentication/permission failures must be distinguishable.
- Rate limits must preserve retry-after behavior when available.
- Transport timeouts and connection failures must not be collapsed into unrelated command errors.
- OK command payload failures should raise `OkCommandError`.
- Unexpected response shapes should raise `OkResponseError`.

Home Assistant-facing code should convert these into `ConfigEntryAuthFailed`, `UpdateFailed`,
`HomeAssistantError`, or `ServiceValidationError` depending on context.

## Firestore Wrapper Rules

Firestore realtime behavior is wrapped in the client package so Home Assistant code does not need
to know Firestore document path or subscription details.

Maintain these constraints:

- Watch setup and cleanup must be compatible with executor offloading by the integration.
- Watch callbacks must be safe to hand back to the Home Assistant event loop.
- The wrapper must remain testable without live Firebase or Google credentials.
- Do not hand-roll Firestore wire protocol behavior.
- If a future Firestore package provides a true async document watch API, evaluate it before
  replacing the current wrapper.

## Tests

Default tests must not call live OK, Firebase, or Google APIs.

Client tests should cover:

- Request construction and signing.
- Header and URL construction.
- Response parsing and validation.
- Error mapping.
- Timeout propagation.
- Sync and async transport behavior.
- Firestore path construction, timestamp parsing, watch callbacks, and cleanup behavior.

If live tests are ever added, they must be explicitly marked/gated and skipped by default.
