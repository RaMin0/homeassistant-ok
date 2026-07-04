# Project Map

Use this map to keep public issues small, labeled consistently, and easy to turn into release notes.

## Milestones

- **Scheduling**: schedule controls, schedule blueprints, OK app schedule compatibility, and
  open-ended schedules.
- **Energy And Price Intelligence**: energy price, cost estimation, cheapest windows, and
  statistics-safe energy behavior.
- **Reliability And Diagnostics**: realtime watcher health, polling fallback, repairs, schema
  drift, and troubleshooting.
- **Publishing And HACS Quality**: release automation, HACS readiness, documentation, CI, and
  repository hygiene.

## Labels

- `api-change`: suspected OK app API, authentication, command, or Firestore document change.
- `realtime`: Firestore watcher or realtime update behavior.
- `scheduling`: charging schedule entities, actions, or blueprints.
- `energy-price`: energy price sensors, attributes, cards, or automations.
- `reliability`: retry, fallback, repair, diagnostics, or unavailable-state behavior.
- `setup`: config flow, reauthentication, install, reload, or startup issue.
- `release`: versioning, changelog, GitHub Release, or HACS release asset behavior.
- `privacy`: sensitive data handling, diagnostics redaction, or unofficial API risk.
- `tests`: unit, fixture, CI, hassfest, HACS, or validation coverage.
- `documentation`: README, docs, examples, or launch copy.
- `needs-info`: waiting for logs, diagnostics, versions, or reproduction details.
- `good-first-issue`: small, well-scoped contribution.

## Triage Defaults

- Ask for diagnostics and redacted logs before requesting raw API captures.
- For suspected OK API changes, ask whether the same behavior works in the OK app.
- Keep action-related repro steps read-only until a maintainer explicitly needs command behavior.
- Prefer one bug or enhancement per issue so Conventional Commit release notes remain readable.
