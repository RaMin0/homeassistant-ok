<div align="center">
  <img src="custom_components/ok/brand/logo.png" alt="OK logo" width="180">

  <h1>OK for Home Assistant</h1>

  <p>
    <strong>OK home charging, realtime charger status, and Danish energy prices in Home Assistant.</strong>
  </p>

  <p>
    <a href="https://github.com/RaMin0/homeassistant-ok/releases">
      <img alt="GitHub release" src="https://img.shields.io/github/v/release/RaMin0/homeassistant-ok?style=for-the-badge">
    </a>
    <a href="https://github.com/RaMin0/homeassistant-ok/actions/workflows/validate.yml">
      <img alt="Validation status" src="https://img.shields.io/github/actions/workflow/status/RaMin0/homeassistant-ok/validate.yml?branch=main&style=for-the-badge&label=validate">
    </a>
    <a href="https://hacs.xyz">
      <img alt="HACS custom repository" src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge&logo=homeassistant&logoColor=white">
    </a>
    <a href="https://github.com/RaMin0/homeassistant-ok/blob/main/LICENSE">
      <img alt="License" src="https://img.shields.io/github/license/RaMin0/homeassistant-ok?style=for-the-badge">
    </a>
  </p>

  <p>
    <img alt="Home Assistant 2025.12.5+" src="https://img.shields.io/badge/Home%20Assistant-2025.12.5%2B-18BCF2.svg?style=for-the-badge&logo=homeassistant&logoColor=white">
    <img alt="Python 3.13+" src="https://img.shields.io/badge/Python-3.13%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white">
    <img alt="Quality Gold+" src="https://img.shields.io/badge/Quality-Gold%2B-f2c94c.svg?style=for-the-badge">
  </p>

  <p>
    <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=RaMin0&repository=homeassistant-ok&category=integration">
      <img alt="Open this repository in HACS" src="https://my.home-assistant.io/badges/hacs_repository.svg">
    </a>
    <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2FRaMin0%2Fhomeassistant-ok%2Fmain%2Fblueprints%2Fscript%2Fok%2Fschedule_charging.yaml">
      <img alt="Import the schedule charging blueprint" src="https://my.home-assistant.io/badges/blueprint_import.svg">
    </a>
  </p>
</div>

## ✨ What It Adds

| Area | Capability |
| --- | --- |
| ⚡ Charger status | Realtime connector and charging-session status from OK's Firestore updates when available. |
| 🔋 Charging session | Current power, total energy, schedule start/end/duration, and optional last-session data. |
| 💰 Energy prices | Denmark electricity price sensor with `energidataservice`-style attributes for cards and automations. |
| 🎛️ Controls | Start, stop, schedule, update schedule, cancel schedule, restart charger, and auto start actions. |
| 🧰 Maintenance | Force refresh button and diagnostic last-refresh entities for account and charger API polling. |
| 🧾 Privacy | Diagnostics redact account, app, device, and legacy token values. |

The integration talks to OK's app APIs through the bundled client in
`custom_components/ok/api`, so HACS/manual installs publish the Home Assistant component and
API client as one project. The bundled client is not distributed as a separate Python package.

## ✅ Supported Setup

- Home Assistant `2025.12.5` is the supported floor. CI also tests the current Home Assistant
  `stable` container image.
- Python `3.13.2+`.
- OK account credentials that work in the OK app.
- OK home chargers returned by the OK app APIs.
- Denmark electricity prices returned by OK for the configured charger.

Public OK fast chargers and non-home-charging products are not a target for this integration.

## 🏅 Quality Status

This project is currently maintained as a **Gold+ HACS/custom integration**. The remaining
Platinum/Core-readiness work is tracked in [ROADMAP.md](ROADMAP.md). Maintainer release and HACS
publishing steps are tracked in [PUBLISHING.md](PUBLISHING.md).

## ⚠️ Known Limitations

- This is an unofficial community project. It is not affiliated with, endorsed by, sponsored by,
  or supported by OK a.m.b.a.
- OK names, logos, and trademarks belong to OK a.m.b.a. They are used only to identify the service
  this integration connects to.
- This integration uses OK app APIs that are not a public Home Assistant API contract. OK may
  change, rotate, rate-limit, restrict, or block API behavior without notice, and the integration
  may stop working until updated.
- The integration is Denmark-focused and built around OK home charging accounts and chargers.
  Public OK fast chargers and non-home-charging products are outside the current scope.
- Realtime charger updates depend on OK's Firestore documents and the Python Firestore watcher.
  If watcher startup fails, Home Assistant creates a repair issue and the integration continues
  with polling.
- Polling is split by data type and uses internal freshness windows/backoff to reduce the risk of
  OK API rate limits. The force refresh button bypasses those windows and should be used
  sparingly.
- The OK API client is intentionally bundled inside `custom_components/ok/api` for now so HACS
  installs the integration as one project.
- Local brand assets are included for HACS and Home Assistant `2026.3+`. Home Assistant `2025.12.x`
  does not serve local custom-integration brand assets, so frontend branding on that floor requires
  the OK brand assets to exist in the Home Assistant brands repository.

## 🚀 Installation

### HACS

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=RaMin0&repository=homeassistant-ok&category=integration)

1. Open the HACS button above, or add this repository as a custom HACS integration repository.
2. Install `OK`.
3. Restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration** and search for `OK`.

HACS installs the files, but it does not configure the integration for you. Setup still happens
through Home Assistant's integration UI after restart.

### Manual

1. Copy `custom_components/ok` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration** and search for `OK`.

## ⚙️ Setup

The config flow asks for:

- **Email**: the email address used for the OK app.
- **Password**: the OK app password. It is used to register/authenticate a Home Assistant
  app device and is not stored in the config entry after setup.

The integration stores the email address and OK app/device identifiers in the config entry. The
password is only used during setup/reauthentication and is not stored. Stored account and device
values are redacted from diagnostics.

## 🔧 Options

- **Energy price entities**: fetches OK energy prices and creates the price sensors compatible
  with energy price cards.
- **Last session entities**: fetches charging receipts and creates the optional last-session
  sensors. Disable this if you do not use last-session data or want to reduce API calls.
- **Control buttons**: creates the start charging, stop charging, cancel schedule, and restart
  button entities. The service actions remain available for automations.
- **Advanced > Realtime updates**: uses Firestore realtime watchers for charger and active
  charging session status. Disable this to use polled HTTP snapshot updates instead.

Polling cadence is managed by the integration. Connector and charging status use realtime
Firestore watches when that option is enabled and available. Slow-changing REST data is refreshed
on separate internal cadences to reduce OK cloud API traffic: charger metadata and prices are
refreshed roughly every 30 minutes, current charging sessions are refreshed more often while a
session is active and less often while idle, and the full receipt list is only used as an
infrequent backfill. When a known charging session ends, the integration uses OK's quick receipt
endpoint for that session token.

## 🧭 Discovery

Home Assistant network discovery is not used. OK chargers are account-owned cloud resources, so
the integration discovers chargers after login by reading the charger list returned for the
configured OK account.

New chargers/connectors returned by OK are added automatically on later refreshes. Charger devices
that disappear from repeated complete non-empty charger lists are removed from the device registry;
empty charger responses are treated conservatively and do not remove existing devices.

## 🧩 Entities

### Primary Entities

- Energy price sensor compatible with `energidataservice`-style attributes:
  `today`, `tomorrow`, `raw_today`, `raw_tomorrow`, `tomorrow_valid`, `prices`, `currency`,
  `region`, and summary attributes.
- Connector status sensor with status timestamp and maximum-power attributes.
- Auto start switch.
- Session power, session energy, schedule start, schedule end, and schedule duration sensors
  scoped per connector.
- Optional last-session entities with receipt summary data, when last-session entities are
  enabled.

### Config And Maintenance Entities

- Restart button.
- Force refresh button that bypasses internal freshness windows and polls all REST-backed data,
  including the HTTP snapshot endpoints that mirror Firestore realtime status. The button is
  unavailable while a refresh is already running.
- Last refresh diagnostic sensor with per-endpoint timestamp attributes for the last successful API
  poll.

## ▶️ Actions

All actions use an OK entity as the target, so automations do not need raw charger or connector
IDs.

- `ok.start_charging`
- `ok.stop_charging`
- `ok.schedule_charging`
- `ok.update_charging_schedule`
- `ok.cancel_charging_schedule`
- `ok.restart`
- `ok.set_auto_start`

For schedule actions, Home Assistant datetime selectors can be used. Naive datetimes are
interpreted in the Home Assistant local timezone before being sent to OK.

## 🕒 Schedule Script Blueprint

The repository includes a script blueprint for creating a reusable schedule button/script:
`blueprints/script/ok/schedule_charging.yaml`.

To use it, import or copy the blueprint into Home Assistant:

- **Import from URL**: In Home Assistant, go to **Settings > Automations & scenes > Blueprints**,
  choose **Import blueprint**, and use the raw GitHub URL for
  `blueprints/script/ok/schedule_charging.yaml`.
- **One-click import**:

  [![Open your Home Assistant instance and show the blueprint import dialog with this blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2FRaMin0%2Fhomeassistant-ok%2Fmain%2Fblueprints%2Fscript%2Fok%2Fschedule_charging.yaml)
- **Manual copy**: Copy the file to
  `config/blueprints/script/ok/schedule_charging.yaml`, then reload scripts/blueprints or restart
  Home Assistant.

The one-click import flow still imports from a URL. If you want to avoid GitHub/repository URLs,
use the manual copy method; Home Assistant will load the local blueprint from
`config/blueprints/script/ok/schedule_charging.yaml`.

Create a new script from the blueprint, select the OK connector status sensor once, then call that
script from a dashboard button. The script exposes `scheduled_start` and `scheduled_end` fields, so
Home Assistant can prompt for the schedule window when the script is run.

The integration does not create scripts automatically and does not modify `scripts.yaml`.

Equivalent script action:

```yaml
sequence:
  - action: ok.schedule_charging
    data:
      entity_id: sensor.charger_connector_status
      scheduled_start: "2026-06-17T23:00:00"
      scheduled_end: "2026-06-18T06:00:00"
```

## ⚡ Realtime Updates

Connector and charging status use OK's Firestore document watch support. The required Firestore
Python packages are installed by the integration manifest. If a watcher cannot be started because
the environment is missing required Firestore runtime configuration, realtime updates are disabled
and the integration continues with polling.

Home Assistant also creates a repair issue explaining why realtime updates could not be started.
That repair issue is non-fixable because there is no user-editable integration setting that can
repair missing Firestore runtime support. Transient watcher startup failures are retried with
bounded backoff.

Polling remains active because some data, such as charger discovery, price windows, active
charging sessions, receipts, and watcher recovery, is not fully covered by the realtime documents.

The target `google-cloud-firestore` version does not implement async document watchers, so the
integration creates Firestore watch subscriptions in Home Assistant's executor, schedules received
events back onto the event loop, and offloads watcher cleanup during unload. The main OK HTTP API
client is async and uses Home Assistant's shared `httpx` client.

## 📊 Example Lovelace Price Chart

Use the integration's energy price sensor entity in ApexCharts. The exact entity ID depends on your
charger name. This example uses a 34-hour rolling window with a one-hour left offset, matching the
local dashboard copy.

```yaml
type: custom:apexcharts-card
graph_span: 34h
span:
  start: hour
  offset: "-1h"
series:
  - entity: sensor.charger_energy_price
    type: column
    data_generator: |
      var today = entity.attributes.raw_today.map((row) => {
        return [new Date(row["hour"]).getTime(), row["price"]];
      });
      if (entity.attributes.tomorrow_valid) {
        var tomorrow = entity.attributes.raw_tomorrow.map((row) => {
          return [new Date(row["hour"]).getTime(), row["price"]];
        });
        return today.concat(tomorrow);
      }
      return today;
```

## 🔒 Diagnostics And Privacy

Diagnostics redact the email address, OK app IDs, device IDs, device friendly IDs, and any legacy
login-token values found in older config entries. Do not publish Home Assistant storage files,
`.envrc`, `.env`, `secrets.yaml`, or unsanitized API captures.

The OK mobile app secret is intentionally bundled as an integration constant. It is a shared
application credential used to register and sign OK app requests, not a user-specific secret. OK can
rotate or block that credential, which would require an integration update. User passwords are only
used during setup or reauthentication, and OK device/session identifiers remain redacted from
diagnostics.

If publishing a fork, sanitize credential-like values and keep local API captures out of the public
repository.

## 🧯 Troubleshooting

- If setup fails with invalid credentials, confirm the same credentials work in the OK app.
- If entities are unavailable, check the integration logs for connection, authentication, or
  Firestore watcher messages.
- If status updates are delayed, confirm realtime dependencies are installed and polling is still
  enabled. The integration will still fall back to polling when realtime setup fails.
- If schedule/stop actions fail, make sure the selected entity belongs to the target OK connector
  and that there is an active charging session or schedule when required.

## 🗑️ Removal

1. Delete the OK integration entry from **Settings > Devices & services**.
2. Restart Home Assistant if you manually installed the custom component and want to remove files.
3. Delete `custom_components/ok` for manual installs, or uninstall through HACS.

Removing the integration entry removes the stored OK app/device identifiers from Home Assistant's
config entry storage.

## 🛠️ Local Development

Use Docker for validation to avoid relying on host Python or host packages.

The canonical validation commands are in [docs/VALIDATION.md](docs/VALIDATION.md). Use the
target Home Assistant gate before merging integration, client, test, CI, or release changes, and
use the stable Home Assistant gate before public release prep.

The default tests are hermetic. They use mocked `httpx` transports and fake Firestore watcher
objects. No tests require live OK, Firebase, or Google credentials.

The development Home Assistant instance is documented in [docker/README.md](docker/README.md) and
targets Home Assistant `2025.12.5`.
