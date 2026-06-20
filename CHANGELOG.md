# Changelog

<!-- version list -->

## v0.1.1 (2026-06-20)

### Bug Fixes

- Correct GitHub owner casing
  ([`1f5da74`](https://github.com/RaMin0/homeassistant-ok/commit/1f5da7477b573d3fb21da184c50b6da44119414d))

- Refine charger registry and blueprint defaults
  ([`6705dd4`](https://github.com/RaMin0/homeassistant-ok/commit/6705dd493949e4563b1c0cd098fc01c5337170c5))


## 0.1.0

- Initial public OK Home Assistant custom integration.
- Bundled OK API client.
- Config flow, reauth, options, diagnostics, services, sensors, switches, buttons, and
  Firestore realtime watcher support.
- Raise typed OK command errors for application-level command failures.
- Validate core API response shapes before returning typed client models.
- Pass configured timeouts to injected sync and async HTTP transports.
- Remove current config-entry persistence of login tokens and clean up legacy entries.
- Harden Firestore realtime watcher queue handling and document anonymous watcher credentials.
