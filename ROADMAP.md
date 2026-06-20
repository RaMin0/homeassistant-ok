# Roadmap

This document tracks the planned direction for the OK Home Assistant integration. It is
intentionally separate from the README: the README stays focused on installation and use,
while this file captures quality targets, known architectural tradeoffs, and future work.

## Current Status

The integration is currently treated as **Gold+ for HACS/custom integration use**.

What that means:

- The Home Assistant integration follows the Gold-level expectations that are practical for a
  HACS custom integration: UI config flow, runtime data, diagnostics, repairs, translated
  entities and exceptions, entity/device hygiene, unload cleanup, and broad hermetic tests.
- The bundled OK client is intentionally kept inside `custom_components/ok/api` so HACS and
  manual installs publish a single project for now.
- The OK HTTP API client is async and uses Home Assistant's shared `httpx` client.
- Firestore realtime watches are safe for Home Assistant's event loop because subscription
  setup and cleanup are offloaded through Home Assistant's executor, and events are handed
  back to the event loop.

Why this is not called Platinum yet:

- Home Assistant Platinum expects an async dependency.
- The target `google-cloud-firestore` package does not currently expose an async document
  watch API equivalent to sync `DocumentReference.on_snapshot()`.
- The current Firestore watcher design is stable and HACS-safe, but it still wraps a sync
  watch implementation.
- The OK client is not yet an external package, which would be expected for a Core-quality
  API-wrapper integration.

## Quality Target

Keep the integration at **Gold+** until the remaining Platinum conditions can be met without
reducing stability or making HACS installation worse.

Gold+ guardrails:

- Keep all default tests hermetic. Do not require live OK, Firebase, or Google credentials.
- Keep realtime Firestore watch work off the event loop.
- Keep setup, unload, reload, and failed setup cleanup covered by tests.
- Keep compatibility with the currently supported Home Assistant and Python versions.
- Keep the bundled client importable from the integration without adding host-specific setup
  requirements.

## Future Plan

### 1. HACS Release Readiness

Goal: make the current Gold+ integration easy to install, debug, and maintain.

Planned work:

- Keep README install, setup, options, actions, troubleshooting, and removal docs current.
- Add release notes discipline in `CHANGELOG.md`.
- Validate HACS metadata and brand assets before public releases.
- Keep Docker validation for the target Home Assistant version and latest supported version.
- Avoid live API calls in CI by default.

### 2. Extract The OK Client

Goal: move the OK API wrapper into its own package while keeping this integration small and
focused on Home Assistant behavior.

Planned work:

- Create a separate typed Python package for the OK client.
- Preserve the current async HTTP API surface and explicit lifecycle handling.
- Preserve hermetic tests for signing, request construction, response parsing, and error
  mapping.
- Keep Home Assistant using an injected `httpx.AsyncClient` or compatible injected transport.
- Add a migration plan for this repo so HACS installs depend on a released client package
  instead of bundled source.

This is a step toward Platinum, but it does not by itself solve the Firestore watch issue.

### 3. Resolve Realtime Firestore Async Strategy

Goal: make realtime updates compatible with Platinum's async dependency expectation.

Acceptable future options:

- Use a future `google-cloud-firestore` release if it adds a real async document watch API.
- Replace the watch implementation with a maintained async Firestore listen transport.
- Move realtime listening into the extracted client only if the client can expose a truly
  async interface without relying on sync watcher threads.
- If no stable async watch option exists, keep realtime as a HACS Gold+ feature and document
  that Core/Platinum readiness requires either async polling or a different realtime backend.

Non-goals for now:

- Do not hand-roll a fragile Firestore wire-protocol implementation just to satisfy a label.
- Do not remove working realtime updates unless there is a clearly better async replacement.
- Do not introduce live Firestore or OK credentials into the default test suite.

### 4. Platinum/Core Readiness

Goal: make the integration defensible against Home Assistant Core-level review if that ever
becomes a target.

Planned work:

- Use an external async OK client package.
- Ensure all runtime dependencies are async or have a Core-acceptable async story.
- Keep strict typing clean across the integration and client package.
- Keep the client compatible with injected web sessions/transports.
- Adapt custom integration files to Core conventions if submitting upstream.
- Re-run quality review against the Home Assistant version targeted by the submission.

## Deferred Ideas

These are useful, but not blockers for the current Gold+ target:

- Optional live validation suite gated behind explicit environment variables.
- More dashboard examples for scheduling and price cards.
- Additional repair issues for repeated API schema drift or unsupported account/device
  shapes.
- More granular diagnostics around realtime watcher health and fallback polling.
