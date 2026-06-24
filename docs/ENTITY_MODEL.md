# Entity Model

This document is the canonical guide for OK entity vocabulary, scopes, data sources, and defaults.
Home Assistant may generate entity IDs from translated names and device names, so example entity
IDs are illustrative. Stable identity comes from each entity's `unique_id`.

## Devices

| Device | Scope | Identifier | Notes |
| --- | --- | --- | --- |
| OK Account | Account/service | `ok:account_<config unique id or entry id>` | Translation key `account`; diagnostics and account-level refresh live here. |
| Charger | Physical charger | `ok:<station_id>` | Uses OK charger/station ID plus vendor/model/serial/firmware when available. The integration does not create or suggest Home Assistant areas. |

## Naming Rules

- Use `OK`, not `Ok`, in user-visible text.
- Use `charger` for the physical charger.
- Use `connector` for the charger's connector.
- Use `session` for an active or recent charging session.
- Use `last_session_*` for receipt-backed data from the most recent completed session.
- Use `schedule_*` for active schedule fields.
- Use `last_refresh` for diagnostics about API polling.
- Do not reintroduce `station` in user-visible names unless the OK API field itself is being
  described internally.

For one-connector chargers, connector-specific names omit "Connector". For multi-connector
chargers, translations use `Connector <ID>` placeholders.

## Entity Scopes

| Scope | Unique ID pattern | Device |
| --- | --- | --- |
| Account/coordinator-scoped | `<config unique id or entry id>_<key>` | OK Account |
| Charger-scoped | `<station_id>_<key>` | Charger |
| Connector-scoped | `<station_id>_<connector_id>_<key>` | Charger |

Connector ID must stay in connector-scoped unique IDs, even when the UI omits connector wording
for single-connector chargers.

## Entities

| Platform | Key | Scope | Default | Category | Main data source |
| --- | --- | --- | --- | --- | --- |
| Sensor | `energy_price` | Charger | Enabled | None | OK price REST endpoint for the charger. |
| Sensor | `last_refresh` | Account | Enabled | Diagnostic | Coordinator refresh timestamps. |
| Sensor | `charger_last_refresh` | Charger | Enabled | Diagnostic | Connector status/session snapshot and receipt refresh timestamps. |
| Sensor | `connector_status` | Connector | Enabled | None | Firestore charger status watch with HTTP snapshot fallback. |
| Sensor | `connector_session_power` | Connector | Enabled | None | Firestore charging-session status watch with HTTP snapshot fallback. |
| Sensor | `connector_session_energy` | Connector | Enabled | None | Firestore charging-session status watch with HTTP snapshot fallback. |
| Sensor | `schedule_duration` | Connector | Enabled | None | Derived from the active schedule start/end in the charging-session status document. |
| Sensor | `last_session_ended` | Charger | Option-controlled | None | Receipt list or quick receipt endpoint. |
| Sensor | `last_session_started` | Charger | Option-controlled | None | Receipt list or quick receipt endpoint. |
| Sensor | `last_session_duration` | Charger | Option-controlled | None | Derived from last receipt start/end. |
| Sensor | `last_session_energy` | Charger | Option-controlled | None | Receipt list or quick receipt endpoint. |
| Sensor | `last_session_cost` | Charger | Option-controlled | None | Receipt list or quick receipt endpoint. |
| DateTime | `schedule_from` | Connector | Enabled | None | Active schedule start from the charging-session status document; edits existing schedules. |
| DateTime | `schedule_to` | Connector | Enabled | None | Active schedule end from the charging-session status document; edits existing schedules. |
| Switch | `auto_start` | Charger | Enabled | Config | Charger metadata and set-auto-start command. |
| Button | `start_charging` | Connector | Enabled | None | OK start charging command. |
| Button | `stop_charging` | Connector | Enabled | None | OK stop charging command; requires active session token. |
| Button | `cancel_schedule` | Connector | Enabled | None | OK cancel schedule command; requires active session token. |
| Button | `restart` | Charger | Disabled | Config | OK restart charger command. |
| Button | `force_refresh` | Account | Enabled | Config | Coordinator force refresh; unavailable while refresh is running. |

`last_session_*` entities are created only when the `include_receipts` option is enabled. That
option is enabled by default in the config flow/options flow.

`schedule_from` and `schedule_to` are datetime entities, not sensors. Their state is empty until
OK reports an active schedule, and changing either value updates the existing schedule. Create a
new schedule with the `ok.schedule_charging` action or the schedule script blueprint.

## Important Attributes

### `energy_price`

Keep compatibility with `energidataservice`-style consumers and `energy_price_window`.

Attributes include:

- `charger_id`
- `unit`
- `currency`
- `region`
- `tomorrow_valid`
- `next_data_update`
- `today`
- `tomorrow`
- `raw_today`
- `raw_tomorrow`
- `today_min`
- `today_max`
- `today_mean`
- `tomorrow_min`
- `tomorrow_max`
- `tomorrow_mean`
- `use_cent`
- `prices`
- `product`
- `attribution`

Do not rename these lightly. Dashboard cards and external custom integrations can depend on them.

### `connector_status`

Attributes include:

- `charger_id`
- `connector_id`
- `raw_status`
- `status_updated`
- `maximum_power_kw`

The state is normalized from OCPP-style raw statuses into lower-case enum values defined in
`const.py`. Update constants, translations, and tests together when changing statuses.

### `last_session_cost`

Attributes include:

- `no_price_reason`

Keep `no_price_reason` as an attribute of cost rather than a separate entity unless the product
direction changes.

### `last_refresh`

Account-level diagnostic attributes:

- `account_settings`
- `charger_overview`
- `energy_prices`
- `active_sessions`
- `charging_receipts`
- `trigger`
- `in_progress`

These attributes are intentionally account-level. Charger-specific refresh timestamps belong on
`charger_last_refresh`.

### `charger_last_refresh`

Charger-level diagnostic attributes:

- `charger_status`
- `session_status`
- `session_receipt`

For multi-connector chargers, connector-specific refresh values may be represented by connector ID
in the attribute value.

## Services And Entity Targets

All services use `entity_id`, not raw charger IDs or connector IDs. The selected entity must be an
OK sensor with connector attributes:

- `ok.start_charging`
- `ok.stop_charging`
- `ok.schedule_charging`
- `ok.update_charging_schedule`
- `ok.cancel_charging_schedule`
- `ok.restart`
- `ok.set_auto_start`

Current service selectors target the connector status sensor because it is the most reliable
connector-specific entity for users to pick.

## Entity Changes Checklist

When adding, removing, or renaming an entity:

- Update the platform implementation.
- Update `custom_components/ok/translations/en.json`.
- Update `custom_components/ok/translations/da.json`.
- Update `custom_components/ok/icons.json`.
- Update tests.
- Update this document and README when user-facing behavior changes.
- Consider stale entities in developer Home Assistant instances. Permanent, tested registry cleanup
  is allowed when entities are removed or option-disabled; one-off developer cleanup workarounds do
  not belong in integration code.
