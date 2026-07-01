# Agent Guide

This file is the entrypoint for AI agents and automation working in this repository. Read it
before changing code, tests, documentation, CI, or release metadata.

## Project Snapshot

This repository contains a HACS-compatible Home Assistant custom integration for OK home
charging in Denmark.

- Home Assistant integration: `custom_components/ok`
- Bundled OK API client: `custom_components/ok/api`
- Script blueprint: `blueprints/script/ok/schedule_charging.yaml`
- Local Docker development environment: `docker-compose.yml` and `docker/README.md`
- Public release/versioning docs: `PUBLISHING.md`, `ROADMAP.md`, `CHANGELOG.md`

The OK API client intentionally stays bundled inside the custom component for now. Do not split
it into an external package unless the task explicitly asks for that work.

## Required Reading By Task

Always read these first:

- `README.md`
- `ROADMAP.md`
- `CONTRIBUTING.md`
- This file

Then read the focused document for the area you are touching:

- Integration architecture: `docs/ARCHITECTURE.md`
- Entity names, devices, attributes, defaults, and data sources: `docs/ENTITY_MODEL.md`
- Bundled OK client boundaries and API-wrapper rules: `docs/API_CLIENT.md`
- Validation commands and Docker workflow: `docs/VALIDATION.md`
- Repository invariants and public-release guardrails: `docs/REPO_INVARIANTS.md`
- Publishing steps: `PUBLISHING.md`

Before editing a platform file, also inspect its tests:

- `custom_components/ok/sensor.py` -> `tests/custom_components/ok/test_sensor*.py`
- `custom_components/ok/button.py` -> `tests/custom_components/ok/test_button.py`
- `custom_components/ok/switch.py` -> `tests/custom_components/ok/test_switch.py`
- `custom_components/ok/__init__.py` and `action.py` -> `tests/custom_components/ok/test_services.py`
- `custom_components/ok/coordinator.py` -> `tests/custom_components/ok/test_coordinator*.py`
- `custom_components/ok/api/*` -> `tests/test_client_*.py`, `tests/test_firestore.py`

## Non-Negotiables

- Do not call live OK APIs directly from development, tests, scripts, or CI.
- Keep default tests hermetic. Use fixtures, mocks, and local transports.
- Use Docker for Home Assistant runtime validation and compatibility checks.
- Do not depend on a host Home Assistant install.
- Do not commit Home Assistant runtime state from `docker/ha/config`.
- Do not commit `.env`, `.env.*`, `.envrc`, `secrets.yaml`, logs, databases, tokens, keys,
  unsanitized captures, or generated Python caches.
- Do not add one-off cleanup/workaround code for a single developer instance. If one-off cleanup is
  needed, run it separately and remove it. Permanent registry hygiene is allowed only when it is
  scoped, documented, and covered by tests.
- Keep OK uppercase in user-visible text.
- Keep English and Danish translations in sync for user-visible strings, entity names,
  attributes, services, exceptions, config flow text, and repairs.
- Keep HACS compatibility. Do not introduce Home Assistant Core-only packaging assumptions.
- Keep release versions synchronized across `pyproject.toml`,
  `custom_components/ok/manifest.json`, `custom_components/ok/api/_version.py`, and
  `CHANGELOG.md`. The release workflow commits those metadata changes to `main` before tagging
  and publishing a GitHub Release.

## Home Assistant Quality Bar

Treat this as a Gold+ custom integration with a path toward Platinum/Core quality.

Maintain these patterns:

- UI config flow only; no YAML setup.
- `ConfigEntry.runtime_data` owns runtime clients/coordinators.
- The coordinator owns shared polling, Firestore watcher synchronization, freshness windows,
  backoff, force refresh, and stale-device cleanup.
- Entities use `CoordinatorEntity`, stable unique IDs, device info, translated names, and
  appropriate device/entity classes.
- Actions target OK entities rather than raw charger or connector IDs.
- Diagnostics redact account, app, device, token, and other sensitive values.
- Realtime Firestore watch setup and cleanup must not block the Home Assistant event loop.
- Failed setup, unload, reload, reauth, options, service/action errors, and edge cases need tests.

The integration remains Gold+ rather than Platinum because the current Firestore watcher
dependency exposes sync watch behavior and the OK client is still bundled.

## Naming And Vocabulary

Use the current vocabulary consistently:

- Integration name: `OK`
- Account hub device translation: `OK Account`
- Charger device: the physical OK home charger
- Connector: a connector on a charger
- Connector-scoped session entities:
  - `connector_status`
  - `connector_session_power`
  - `connector_session_energy`
  - `schedule_duration`
- Connector-scoped schedule datetime controls:
  - `schedule_from`
  - `schedule_to`
- Last completed receipt/session entities use `last_session_*`.
- Diagnostics use `last_refresh` at account scope and `charger_last_refresh` at charger scope.

For chargers with one connector, the UI should avoid unnecessary "Connector" wording. For
multi-connector chargers, connector-specific translations include the connector ID.

## API Client Boundary

The bundled client under `custom_components/ok/api` owns:

- HTTP request construction, signing, timeout handling, and response validation.
- Typed response aliases/models.
- OK-specific exception classes.
- Firestore document path helpers and watch wrapper behavior.
- Sync and async client APIs where currently implemented.

The Home Assistant integration owns:

- Config flow, options, reauth, devices, entities, services/actions, diagnostics, repairs,
  translations, icons, and coordinator scheduling.
- Injecting Home Assistant's shared `httpx.AsyncClient`.
- Mapping OK client exceptions to Home Assistant setup, update, and service errors.

Do not import Home Assistant modules from `custom_components/ok/api`.

## Validation Expectations

For docs-only changes, inspect links and changed text. For code changes, run the relevant focused
tests and usually the full Docker gate in `docs/VALIDATION.md`.

Before public release work, run:

- Docker validation against Home Assistant `2025.12.5`.
- Docker validation against current Home Assistant `stable`.
- Brand image validation.
- Publish-surface audit for ignored runtime state, secrets, caches, and stale versions.

Report any validation that was skipped and why.

## Release Rules

Use Conventional Commit PR titles and squash merges:

- `fix:` -> patch release.
- `feat:` -> minor release.
- `feat!:`, `fix!:`, or `BREAKING CHANGE:` -> major release.
- `docs:`, `test:`, `ci:`, `chore:`, `refactor:`, `style:`, `build:`, `perf:`, and `revert:`
  do not release unless semantic-release rules change.

Do not publish to PyPI while the OK client remains bundled.

The release workflow keeps the built-in `GITHUB_TOKEN` read-only and uses the repository secret
`RELEASE_TOKEN` for write operations. `RELEASE_TOKEN` is a fine-grained personal access token scoped
only to `RaMin0/homeassistant-ok` with `Contents: Read and write`, allowing semantic-release to push
the release metadata commit, tag, GitHub Release, and `ok.zip` from the validated `main` workflow.

## When Unsure

Prefer a small, well-tested change that preserves existing Home Assistant behavior. If a change
touches entity IDs, unique IDs, device identifiers, option defaults, data retention, service
schemas, or release automation, stop and inspect the relevant docs and tests before editing.
