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
- Enable squash merges and use the PR title as the squash commit message.
- Disable merge commits for `main`.
- The HACS validation job is guarded for public repositories because HACS validation requires a
  public GitHub repository. If the repository is made private temporarily, re-run `Validate` after it
  is public again.
- Protect `main` and require:
  - `HACS`
  - `Hassfest`
  - `Python / HA 2025.12.5`
  - `Python / HA stable`
  - `Bundled API client / Python 3.13`
  - `Bundled API client / Python 3.14`
  - `Conventional Commit`
- The release workflow uses only the built-in GitHub Actions token. It must not require a
  maintainer personal access token or long-lived release token.
- Keep `main` protected. The ruleset exempts `github-actions[bot]` so semantic-release can push
  release metadata commits directly to `main` after the validated workflow run.
- For this personal repository, configure the bypass as the `github-actions[bot]` user. GitHub may
  reject the built-in GitHub Actions app integration as a bypass actor unless that app is part of
  the ruleset owner/source.
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

The current public baseline is `v0.3.1`. It matches the version in `pyproject.toml`,
`custom_components/ok/manifest.json`, and `custom_components/ok/api/_version.py`, and the GitHub
Release includes `ok.zip` for HACS.

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
6. The workflow creates a tag such as `v0.3.1` on that release metadata commit and creates a
   GitHub Release using `CHANGELOG.md`.
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
