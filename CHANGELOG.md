# Changelog

<!-- version list -->

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
