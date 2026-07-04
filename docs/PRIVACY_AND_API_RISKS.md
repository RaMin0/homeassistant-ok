# Privacy And API Risks

This integration is unofficial and uses OK app APIs. It is not backed by a public OK Home Assistant
API contract.

## What The Integration Stores

Home Assistant stores the OK account details needed to authenticate through the config flow and make
future OK API requests. Runtime diagnostics redact known account, credential, token, app, charger,
and device identifiers.

The bundled OK app credential is part of the integration code so users do not need to discover or
enter app internals during setup. Treat it as an implementation detail of the unofficial API client,
not as a user secret.

## What Not To Share

Do not paste these into public issues, screenshots, logs, or discussions:

- Passwords or account credentials.
- Home Assistant `.storage` files.
- `secrets.yaml`.
- Raw access tokens, refresh tokens, Firebase tokens, or cookies.
- Unsanitized OK API captures.
- Charger IDs, device IDs, location IDs, addresses, or account identifiers unless redacted.

## Unofficial API Risk

OK can change, rotate, rate-limit, restrict, or block the private app API without notice. That can
affect login, charger discovery, realtime Firestore documents, schedule actions, charging controls,
energy prices, or receipt data.

When behavior changes, first compare Home Assistant with the OK app:

- If the OK app also fails, the issue may be an OK account, charger, or service problem.
- If the OK app still works but Home Assistant does not, open an **OK API behavior change** issue
  with integration version, Home Assistant version, redacted logs, and read-only reproduction steps.

## Diagnostics

Prefer Home Assistant diagnostics and the integration's diagnostic entities over raw captures. If
raw captures are required for development, sanitize them before sharing and keep them out of git.
