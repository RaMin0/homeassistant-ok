# Publishing

This checklist is for maintainers preparing the OK integration for public GitHub/HACS use.

## Before The First Push

- Initialize or connect the local folder as a Git repository.
- Confirm ignored runtime files are not staged:
  - `.env`, `.env.*`, `.envrc`
  - `docker/ha/config`
  - `secrets.yaml`
  - unsanitized API captures
  - Python cache directories
- Keep Docker Home Assistant runtime config out of git. User-specific dashboards, scripts,
  HACS files, card resources, debug logging, logs, and databases belong in the ignored runtime
  config directories.
- Verify `README.md`, `hacs.json`, `custom_components/ok/manifest.json`, brand images,
  translations, services, and blueprints are present.
- Run the Docker validation commands in `docs/VALIDATION.md`.

## GitHub Repository Settings

- Enable Issues.
- Enable private vulnerability reporting so `SECURITY.md` has a working private report path.
- Enable squash merges and use the PR title as the squash commit message.
- Disable merge commits for `main`.
- The HACS validation job is guarded for public repositories because HACS validation requires a
  public GitHub repository. If the repository is made private temporarily, re-run `Validate` after it
  is public again.
- Protect `main` and require:
  - `HACS`
  - `Hassfest`
  - `Workflow Permissions`
  - `Python / HA 2025.12.5`
  - `Python / HA stable`
  - `Type Check / HA 2025.12.5`
  - `Python Quality / Python 3.13`
  - `Python Quality / Python 3.14`
  - `Bundled API client / Python 3.13`
  - `Bundled API client / Python 3.14`
  - `Conventional Commit`
- The release workflow uses a fine-grained personal access token stored as the repository secret
  `RELEASE_TOKEN`. The token must:
  - Belong to `RaMin0`, because that user is the ruleset bypass actor.
  - Be scoped only to `RaMin0/homeassistant-ok`.
  - Grant only `Contents: Read and write`; `Metadata: Read-only` is automatic.
  - Use the maximum acceptable expiration for the account. For personal repositories, GitHub allows
    no expiration for fine-grained tokens unless a policy restricts it; otherwise use the longest
    available custom expiration and rotate before expiry.
- Keep `main` protected. In this personal repository, the ruleset intentionally exempts only:
  - `RaMin0`, for maintainer direct-push and emergency force-push operations.
  - `github-actions[bot]` may appear as a bypass actor for compatibility, but the release workflow
    must not rely on it. Pushes authenticated with the built-in `GITHUB_TOKEN` are evaluated as the
    GitHub Actions app, not as the bot user, and GitHub rejected the app bypass for this personal
    repository.
- Keep `Workflow Permissions` required. It verifies that no workflow grants `contents: write` to
  the built-in `GITHUB_TOKEN`; release writes must use the fine-grained `RELEASE_TOKEN` secret.
- Automated release jobs are guarded for public repositories. Keep the repository public when
  creating releases.
- Add repository topics:
  - `home-assistant`
  - `hacs`
  - `custom-component`
  - `ok`
  - `ev-charging`
  - `denmark`

## Release Flow

### Current Baseline Release

The current public baseline is the latest GitHub Release. Its tag must match the version in
`pyproject.toml`, `custom_components/ok/manifest.json`, and
`custom_components/ok/api/_version.py`, and the GitHub Release must include `ok.zip` for HACS.

Do not publish to PyPI while the OK API client remains bundled. The repository uses HACS
release-asset installation through `zip_release`, so every public release users can select in HACS
must include an `ok.zip` asset stamped with the released version.

### Automated Releases

1. Merge a PR with a Conventional Commit title.
2. The `Validate` workflow runs on `main`.
3. After `Validate` succeeds, the `Release` workflow runs.
4. Python Semantic Release calculates the next version from commits on `main`.
5. If a release is needed, semantic-release commits the synchronized release metadata directly to
   `main` as `chore(release): vX.Y.Z`:
   - `pyproject.toml`
   - `custom_components/ok/manifest.json`
   - `custom_components/ok/api/_version.py`
   - `CHANGELOG.md`
6. The workflow creates a tag such as `vX.Y.Z` on that release metadata commit and creates a GitHub
   Release using `CHANGELOG.md`.
7. The workflow checks out the released commit, builds `ok.zip` from `custom_components/ok`, and
   uploads that asset to the GitHub Release for HACS.

Out-of-band GitHub releases created directly in the GitHub UI are not automated. If one is ever
needed, build and upload `ok.zip` with the same version as the tag. Prefer the semantic-release
workflow for normal changes, including manual `workflow_dispatch` runs from `main`.

No PyPI publishing is configured while the OK API client remains bundled inside the Home Assistant
custom component.

## HACS

- First test installation by adding the public repository as a custom HACS integration repository.
- Install from the public repository, restart Home Assistant, and complete setup through the config
  flow.
- Verify entities, actions, diagnostics, realtime updates, force refresh, and the schedule script
  blueprint.
- Keep `requirements-manifest.txt` synchronized with `custom_components/ok/manifest.json` so
  Dependabot can surface runtime dependency updates while Home Assistant still installs from the
  manifest.
- Submit to HACS default repositories only after custom-repository installation is proven with a
  published GitHub Release.
