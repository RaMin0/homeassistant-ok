# Copilot Instructions

Follow the repository guidance in `AGENTS.md` before suggesting or applying changes.

Critical reminders:

- Do not call live OK APIs or require live OK credentials in default tests.
- Use Docker for Home Assistant runtime validation.
- Keep the bundled OK client inside `custom_components/ok/api` unless explicitly asked to extract
  it.
- Keep OK uppercase in user-visible text.
- Keep English and Danish translations synchronized.
- Do not commit local Home Assistant runtime state from `docker/ha/config` or any secrets,
  logs, databases, caches, or unsanitized API captures.
