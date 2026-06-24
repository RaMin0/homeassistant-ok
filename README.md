<div align="center">
  <img src="custom_components/ok/brand/logo.png" alt="OK logo" width="180">

  <h1>OK for Home Assistant</h1>

  <p>
    <strong>OK home charging controls, schedules, session data, and Danish electricity prices in Home Assistant, with realtime status when OK's Firestore updates are available.</strong>
  </p>

  <p>
    <a href="https://github.com/RaMin0/homeassistant-ok/releases"><img alt="GitHub release" src="https://img.shields.io/github/v/release/RaMin0/homeassistant-ok?style=for-the-badge"></a>
    <a href="https://github.com/RaMin0/homeassistant-ok/actions/workflows/validate.yml"><img alt="Validation status" src="https://img.shields.io/github/actions/workflow/status/RaMin0/homeassistant-ok/validate.yml?branch=main&style=for-the-badge&label=validate"></a>
    <a href="https://hacs.xyz"><img alt="HACS custom repository" src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge&logo=homeassistant&logoColor=white"></a>
    <a href="https://github.com/RaMin0/homeassistant-ok/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/RaMin0/homeassistant-ok?style=for-the-badge"></a>
  </p>

  <p>
    <img alt="Home Assistant 2025.12.5+" src="https://img.shields.io/badge/Home%20Assistant-2025.12.5%2B-18BCF2.svg?style=for-the-badge&logo=homeassistant&logoColor=white">
  </p>

  <p>
    <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=RaMin0&repository=homeassistant-ok&category=integration"><img alt="Open this repository in HACS" src="https://my.home-assistant.io/badges/hacs_repository.svg"></a>
    <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2FRaMin0%2Fhomeassistant-ok%2Fmain%2Fblueprints%2Fscript%2Fok%2Fschedule_charging.yaml"><img alt="Import the schedule charging blueprint" src="https://my.home-assistant.io/badges/blueprint_import.svg"></a>
  </p>

  <p>
    <a href="README.md">English</a> | <a href="README.da.md">Dansk</a>
  </p>
</div>

## ✨ What It Adds

| Area | Capability |
| --- | --- |
| ⚡ Charger status | Connector and charging-session status with Firestore realtime updates when available and polling fallback. |
| 🎛️ Controls | Start, stop, schedule, update schedule, cancel schedule, restart charger, and set auto start from Home Assistant. |
| 🔋 Session data | Current connector session power/energy, schedule timing, and optional last-session receipt data. |
| 💰 Energy prices | OK energy price data with a normalized `prices` timeline for charts and `energidataservice`-style compatibility attributes. |
| 🧰 Maintenance | Force refresh troubleshooting control and account/charger diagnostic refresh timestamps. |
| 🔒 Privacy | Diagnostics redact OK account, app, device, and legacy token identifiers. No custom telemetry is added. |

## 🤝 Works Well With

- [ApexCharts Card](https://github.com/RomRider/apexcharts-card), using the `prices` timeline
  attribute for hourly price charts.
- [energy_price_window](https://github.com/JBoye/energy_price_window) and
  `energidataservice`-style automations, using compatibility attributes exposed by the energy price
  sensor.
- Home Assistant scripts and dashboard buttons, using the bundled schedule charging script
  blueprint.

Usage examples for ApexCharts, compact charger controls, and the schedule blueprint are in
[docs/USAGE_EXAMPLES.md](docs/USAGE_EXAMPLES.md).

## ✅ Supported Setup

- Home Assistant `2025.12.5+`. CI also tests the current Home Assistant `stable` container image.
- OK account credentials that work in the OK app.
- An OK home charger returned by the OK app APIs.
- Danish electricity prices returned by OK for the configured charger.

Public OK fast chargers and non-home-charging products are outside the current scope.

## 🏅 Quality Status

This custom integration is maintained against internal **Gold+** quality guardrails for HACS/custom
integration use. This is not a Home Assistant Core integration and is not an official Home
Assistant quality-scale certification. Remaining Core/Platinum-readiness tradeoffs are tracked in
[ROADMAP.md](ROADMAP.md).

## ⚠️ Known Limitations

- This is an unofficial community project. It is not affiliated with, endorsed by, sponsored by, or
  supported by OK a.m.b.a.
- OK names, logos, and trademarks belong to OK a.m.b.a. They are used only to identify the service
  this integration connects to.
- This integration uses OK app APIs that are not a public Home Assistant API contract. OK may
  change, rotate, rate-limit, restrict, or block API behavior without notice.
- Realtime status depends on OK Firestore documents and watcher support. If realtime updates cannot
  start, the integration creates a non-fixable repair issue and continues with polling.
- Polling uses internal freshness windows and endpoint backoff to reduce OK API traffic. Force
  refresh bypasses those windows and should be used only as a troubleshooting control.
- The OK API client is intentionally bundled inside `custom_components/ok/api` for now so HACS and
  manual installs ship as one project.
- Local brand assets are included in the repository. Home Assistant versions that support local
  custom-integration brand files can serve them directly; older versions may still need OK assets in
  the Home Assistant brands repository for frontend branding.

## 🚀 Installation

### HACS

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=RaMin0&repository=homeassistant-ok&category=integration)

1. Open the HACS button above, or add this repository as a custom HACS integration repository.
2. Install `OK`.
3. Restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration** and search for `OK`.

This repository uses HACS release assets. Install a published release that includes `ok.zip`; do not
install from the default branch unless you are intentionally testing unreleased code.

HACS installs the files, but it does not configure the integration for you. Setup still happens
through Home Assistant's integration UI after restart.

### Manual

1. Copy `custom_components/ok` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration** and search for `OK`.

## ⚙️ Setup And Options

The config flow asks for the email and password used by the OK app. The password is used to register
and authenticate a Home Assistant app device, then discarded. The config entry stores the email
address and OK app/device identifiers needed for future API requests; those values are redacted from
diagnostics.

The options flow lets you disable optional surfaces:

- **Energy price entities**: fetch OK prices and create the energy price sensor.
- **Last session entities**: fetch charging receipts and create the optional last-session sensors.
- **Control buttons**: create start, stop, cancel schedule, and restart button entities. Restart is
  a config-category button and is disabled by default in the entity registry.
- **Advanced > Realtime updates**: use Firestore realtime watchers for connector and charging
  session status. Disable this to use polling only.

Polling cadence is managed by the integration. Charger metadata and prices refresh roughly every 30
minutes. Current charging sessions refresh more often while active and less often while idle. When
last-session entities are enabled, the full receipt list is fetched on setup, force refresh, and
roughly every 12 hours; quick receipt is used for known sessions after they finish.

## 🧩 Entities And Actions

The full entity model, scopes, defaults, attributes, and action target rules are documented in
[docs/ENTITY_MODEL.md](docs/ENTITY_MODEL.md).

At a high level, the integration creates an OK Account service device, one Home Assistant device per
OK charger, charger/connector entities for status and controls, optional receipt-backed last-session
entities, and account/charger diagnostic refresh sensors.

Actions take an OK connector status sensor `entity_id`, so automations do not need raw OK charger or
connector IDs. Schedule actions accept Home Assistant datetime selectors. Naive datetimes are
interpreted in the Home Assistant local timezone before being sent to OK.

## 🕒 Schedule Script Blueprint

The repository includes a script blueprint that can be called from a dashboard button to prompt for
a charging schedule window. Import, copy, dashboard usage, and equivalent script action examples are
documented in [docs/USAGE_EXAMPLES.md](docs/USAGE_EXAMPLES.md).

The My Home Assistant blueprint button at the top imports the blueprint from the current `main`
branch. If you want the exact blueprint from an installed release, copy it from the release source or
from your installed custom component checkout.

## ⚡ Realtime And Polling

Connector and charging-session status use OK Firestore document watches when realtime updates are
enabled and available. The integration currently consumes Firestore's sync `on_snapshot()` watcher
through an async wrapper so watch setup, events, and cleanup stay off Home Assistant's event loop.

Some data is not fully covered by realtime documents, including charger discovery, price windows,
active charging lists, receipts, and watcher recovery. Polling remains active for those sources.
The detailed behavior and fallback path are documented in
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#how-realtime-updates-work).

## 🔒 Support, Diagnostics, And Security

Before opening an issue, read [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) and use the
matching issue template. Include the OK integration version, Home Assistant version, install method,
redacted logs, and diagnostics when available.

Do not paste credentials, tokens, Home Assistant `.storage` files, `secrets.yaml`, databases, or
unsanitized API captures into public issues. Report vulnerabilities privately according to
[SECURITY.md](SECURITY.md). Only the latest published release is actively supported for security
fixes.

The OK mobile app secret is intentionally bundled as an integration constant. It is a shared
application credential used to register and sign OK app requests, not a user-specific secret. OK can
rotate or block that credential, which would require an integration update.

## 🗑️ Removal

1. Delete the OK integration entry from **Settings > Devices & services**.
2. Restart Home Assistant if you manually installed the custom component and want to remove files.
3. Delete `custom_components/ok` for manual installs, or uninstall through HACS.

Removing the integration entry removes the stored OK app/device identifiers from Home Assistant's
config entry storage.

## 🛠️ Development

Contributor guidance is in [CONTRIBUTING.md](CONTRIBUTING.md). Repository-specific automation and AI
agent rules are in [AGENTS.md](AGENTS.md). Docker validation is documented in
[docs/VALIDATION.md](docs/VALIDATION.md), and the local Home Assistant compose environment is
documented in [docker/README.md](docker/README.md).
