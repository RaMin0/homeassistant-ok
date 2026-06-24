# Architecture

This repository is a HACS-compatible Home Assistant custom integration for OK home charging. The
integration wraps OK app APIs through a bundled client and exposes Home Assistant entities,
actions, diagnostics, and a script blueprint.

## Layout

- `custom_components/ok/__init__.py`: config entry setup/unload, service/action registration,
  runtime data creation, legacy config cleanup, and service target validation.
- `custom_components/ok/config_flow.py`: UI setup, reauth, reconfigure, and options flow.
- `custom_components/ok/coordinator.py`: shared data coordinator, polling cadences, Firestore
  watcher synchronization, freshness windows, backoff, force refresh, and stale-device cleanup.
- `custom_components/ok/entity.py`: common entity base, device info, availability, and
  multi-connector translation handling.
- `custom_components/ok/sensor.py`: price, status, session, schedule, last-session, and refresh
  diagnostics sensors.
- `custom_components/ok/button.py`: start, stop, cancel schedule, restart, and force refresh
  buttons.
- `custom_components/ok/switch.py`: auto start switch.
- `custom_components/ok/action.py`: shared action helpers and OK error mapping.
- `custom_components/ok/api`: bundled OK API client and Firestore watch helpers.
- `custom_components/ok/translations`: English and Danish translations.
- `custom_components/ok/icons.json`: entity icons and state icons.
- `blueprints/script/ok/schedule_charging.yaml`: script blueprint for schedule charging.
- `tests`: hermetic unit tests for the integration and bundled client.

## Runtime Data

`async_setup_entry` creates:

- `AsyncOkApiClient`, configured from the config entry and Home Assistant's shared
  `httpx.AsyncClient`.
- `OkDataUpdateCoordinator`, which owns all shared data and refresh behavior.
- `OkRuntimeData`, stored on `ConfigEntry.runtime_data`.

Do not store clients, coordinators, or other runtime-only objects in `ConfigEntry.data` or
`ConfigEntry.options`.

## Device Model

The integration exposes:

- An account-level service device using translation key `account`, displayed as `OK Account`.
- One Home Assistant device per OK charger, identified by the OK charger/station identifier.

Connector-specific entities are attached to the charger device. The connector ID is part of the
unique ID for connector-scoped entities.

For a single-connector charger, connector labels are omitted from entity names. For
multi-connector chargers, connector-scoped translations include the connector ID.

## Data Sources

The coordinator combines REST-backed OK app endpoints with Firestore realtime documents:

- Account settings are fetched during setup.
- Charger/location metadata is refreshed roughly every 30 minutes.
- Energy prices are refreshed roughly every 30 minutes per charger.
- Current charging sessions are refreshed every 60 seconds while active and every 5 minutes when
  idle.
- Full receipt lists are fetched on setup, force refresh, and roughly every 12 hours when
  last-session entities are enabled.
- Quick receipt data is fetched for known sessions after they finish.
- Connector status and charging-session status prefer Firestore realtime watches, with HTTP
  snapshot fallback when watches are unavailable, failed, missing, or force refresh is requested.

## Realtime Firestore Watches

The target Firestore package exposes synchronous document watch behavior. To keep Home Assistant
safe:

- Watch subscription setup and cleanup are offloaded through Home Assistant's executor.
- Watch callbacks schedule work back onto Home Assistant's event loop.
- Watch failures use bounded retry/backoff.
- A repair issue is created when realtime updates cannot start because Firestore runtime support is
  missing or misconfigured. Transient watcher failures retry with bounded backoff instead.

Do not move sync Firestore watch work onto the event loop.

## Refresh And Backoff

The coordinator uses freshness windows per source to avoid unnecessary OK API traffic. Force
refresh bypasses those windows and also asks for HTTP snapshots of realtime-backed status.

Rate-limited optional endpoints reuse cached data and set endpoint-specific backoff. Required
setup/update failures are mapped to Home Assistant `UpdateFailed` or `ConfigEntryAuthFailed` as
appropriate.

## Services And Buttons

Services/actions target OK entities, not raw charger or connector IDs. The selected entity must
belong to the OK integration and expose `charger_id` and `connector_id` attributes.

Control buttons call the same OK client operations as services and then request an operational
refresh. The auto start switch requests a charger metadata refresh. The force refresh button bypasses
freshness windows and requests a full coordinator refresh, including HTTP snapshots for
realtime-backed status.

## Translations And Icons

User-visible strings belong in both:

- `custom_components/ok/translations/en.json`
- `custom_components/ok/translations/da.json`

Relevant icons belong in `custom_components/ok/icons.json`.

When adding or renaming an entity, service, exception, option, attribute, repair, or device
translation key, update translations, icons, tests, docs, and stale-entity expectations together.
