# Repository Invariants

These rules preserve the quality and publishability of the integration.

## Public Repository Contents

Keep these out of git:

- `docker/ha/config`
- `.env`, `.env.*`, `.envrc`
- `secrets.yaml`
- Home Assistant `.storage`
- Home Assistant logs and databases
- HACS runtime files installed into local Home Assistant config
- Unsanitized OK API captures
- Python caches and coverage output
- Local AI/dev tooling under `.codex`

There is intentionally no `.env.example`. Supported setup is through Home Assistant's config flow,
and default tests use fixtures/mocks.

## HACS Compatibility

Keep:

- `hacs.json`
- `custom_components/ok/manifest.json`
- `custom_components/ok/brand/*`
- `custom_components/ok/translations/en.json`
- `custom_components/ok/translations/da.json`
- `custom_components/ok/icons.json`
- `blueprints/script/ok/schedule_charging.yaml`
- README installation instructions with My Home Assistant buttons

Do not introduce assumptions that only work for Home Assistant Core integrations.

The HACS validation workflow intentionally skips while the repository is private. HACS only
supports public GitHub repositories, so HACS validation must be re-run after the repository is made
public.

## Version Synchronization

The version must stay synchronized across:

- `pyproject.toml`
- `custom_components/ok/manifest.json`
- `custom_components/ok/api/_version.py`
- `CHANGELOG.md`

Semantic release is configured to update the first three and the changelog from the established
public release baseline.

The release workflow creates `ok.zip` from `custom_components/ok` and uploads it to the GitHub
Release. Do not include repository root files, Docker config, tests, docs, or local runtime state
in that archive. HACS `zip_release` metadata is enabled, so every public release users can install
from HACS must include a matching `ok.zip` asset.

## Tests And API Calls

- Default tests must never call live OK APIs.
- Default tests must never require Firebase, Google, or OK credentials.
- Any future live tests must be explicitly marked and skipped by default.
- Test fixtures must be sanitized and minimal.

## Temporary Workarounds

Do not add temporary cleanup code to integration setup, unload, coordinator refresh, or platform
setup. Developer-instance cleanup should be run separately and then removed.

Acceptable permanent cleanup behavior includes normal Home Assistant registry hygiene, such as
removing stale charger devices only after repeated complete charger lists show that they are gone.

## Entity And Device Stability

Be careful changing:

- Entity unique IDs.
- Device identifiers.
- Entity translation keys.
- Entity categories.
- Default enabled/disabled state.
- Unit of measurement.
- Device class/state class.
- Service schemas.
- Option defaults.

Changes in those areas can create stale entities, history changes, dashboard breakage, or
automation breakage.

## Translations

Keep English and Danish translations aligned for:

- Config flow.
- Options flow.
- Device names.
- Entity names.
- Entity attributes.
- Entity states.
- Services/actions.
- Exceptions.
- Repairs.

Attribute names are user-visible in Home Assistant and must be translated too.

## Firestore Realtime Safety

The Firestore watcher remains a Gold+ HACS-safe tradeoff:

- Sync watch setup/cleanup is offloaded.
- Events return to the Home Assistant loop safely.
- Failures retry with bounded backoff.
- Polling fallback remains available.

Do not block the event loop with Firestore watch operations.

## Publishing

Do not push, tag, publish, or submit to HACS default repositories unless explicitly asked.

When publishing is requested, follow `PUBLISHING.md`.
