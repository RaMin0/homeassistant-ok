# Troubleshooting

Use this page before opening an issue. Do not paste passwords, tokens, `.storage` files,
`secrets.yaml`, Home Assistant databases, or unsanitized OK API captures.

## Setup Fails

- Confirm the same email and password work in the OK mobile app.
- Confirm Home Assistant is running the supported minimum version from `hacs.json`.
- Check **Settings > System > Logs** for OK integration errors.
- If reauthentication starts, complete it from **Settings > Repairs** or the integration entry.

When opening a setup issue, include:

- OK integration version.
- Home Assistant version.
- Installation method: HACS custom repository, manual copy, or development checkout.
- The setup step where it failed.
- Redacted logs from the same startup or setup attempt.

## Entities Are Unavailable

- Check whether the OK account still has a home charger in the OK app.
- Reload the OK integration entry.
- Use the force refresh button only as a troubleshooting control to verify whether REST-backed data
  can still refresh.
- Check for authentication, connection, or Firestore watcher messages in the logs.

Unavailable entities usually mean one of these conditions:

- Home Assistant has no current OK data after startup.
- The OK app API did not return the charger/session data needed by that entity.
- The charger or connector was removed from the OK account.
- Authentication failed and reauthentication is needed.

## Realtime Updates Are Delayed

Connector and charging status use OK Firestore watches when realtime updates are enabled and the
watcher starts successfully. If Firestore runtime support is missing or misconfigured, Home
Assistant creates a non-fixable repair issue and the integration continues with polling. Transient
watcher failures retry with bounded backoff.

If updates look delayed:

- Confirm **Realtime updates** is enabled in the integration options.
- Check logs for Firestore watcher startup or retry messages.
- Confirm polling still updates the entity after a refresh cycle.
- Avoid repeatedly pressing force refresh; it bypasses freshness windows and can increase API load.
  Do not put it in recurring automations.

## Schedule, Stop, Update, Or Cancel Fails

Creating a schedule targets the selected connector and needs a valid future schedule window.
Updating, stopping, canceling, and editing the schedule datetime entities require OK to report an
active charging session or schedule for that connector.

- Select the OK connector status sensor for the correct connector.
- Confirm the OK app shows an active charging session or schedule.
- For schedule windows, scheduled end must be after scheduled start.
- Naive datetimes are interpreted in the Home Assistant local timezone.

## Known OK API Behavior

This integration is unofficial and uses OK app APIs, not a public Home Assistant API contract.
OK may change API behavior, rate limits, authentication, Firestore documents, or command responses
without notice.

When reporting a likely OK API behavior change:

- Use the **OK API behavior change** issue template.
- Include the integration version and Home Assistant version.
- Include redacted logs.
- Describe what still works in the OK app.
- Do not include app credentials, device IDs, raw tokens, or unsanitized API payloads.

## Debug Logging

Add temporary logging only while reproducing a problem, then remove it again.

```yaml
logger:
  logs:
    custom_components.ok: debug
```

Restart or reload logging, reproduce the issue, copy only the relevant redacted lines, then turn
debug logging off again.
