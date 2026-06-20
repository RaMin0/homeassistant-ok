# Contributing

Use Docker or the provided Home Assistant compose environment for runtime validation.

## AI And Automation Contributors

Read `AGENTS.md` before changing this repository. It defines the project-specific architecture,
entity model, API-client boundary, validation commands, and release invariants that automated
contributors must follow.

## Commit And PR Titles

Pull request titles must use [Conventional Commits](https://www.conventionalcommits.org/):

- `fix: handle missing session cost`
- `feat(sensor): add charger diagnostics`
- `docs: update HACS install instructions`
- `feat!: change setup requirements`

The release workflow uses the commit history on `main` to calculate the next version. Use
squash merges with the PR title as the squash commit message so only releaseable Conventional
Commit messages reach `main`.

Release impact:

- `fix:` creates a patch release.
- `feat:` creates a minor release.
- `!` or `BREAKING CHANGE:` creates a breaking release.
- `docs:`, `test:`, `ci:`, `chore:`, `refactor:`, `style:`, `build:`, `perf:`, and `revert:`
  do not create a release unless the release parser is configured differently later.

Before submitting changes, run the relevant Docker validation from `docs/VALIDATION.md`.
Use the target Home Assistant gate for integration, client, test, CI, or release changes, and use
the stable Home Assistant gate before public release prep.

Do not commit real OK credentials, Home Assistant storage, local `.env` files, logs, database
files, or unsanitized API captures.

There is intentionally no `.env.example`. Supported setup is through Home Assistant's config flow,
and the default tests use fixtures and mocks rather than live OK credentials.
