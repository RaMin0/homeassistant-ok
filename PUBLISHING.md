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
- The HACS validation job intentionally skips while the repository is private because HACS only
  supports public GitHub repositories. Re-run `Validate` after making the repository public.
- Protect `main` and require:
  - `HACS`
  - `Hassfest`
  - `Python / HA 2025.12.5`
  - `Python / HA stable`
  - `Pull Request Title`
- The release workflow commits version/changelog updates back to `main`. If branch protection
  blocks `GITHUB_TOKEN` from pushing release commits, use a dedicated GitHub App or fine-grained
  release token with contents write access and allow that actor to bypass the required checks.
- Automated release jobs intentionally skip while the repository is private. Make the repository
  public before creating the first release.
- Add repository topics:
  - `home-assistant`
  - `hacs`
  - `custom-component`
  - `ok`
  - `ev-charging`
  - `denmark`

## Release Flow

### First Public Release

After the first push to GitHub, create an initial `v0.1.0` tag and GitHub Release that matches the
version already present in `pyproject.toml`, `custom_components/ok/manifest.json`, and
`custom_components/ok/api/_version.py`. This gives Python Semantic Release a correct baseline for
future automated releases.

The first release can be created manually after the GitHub workflows pass. Do not publish to PyPI.
Publishing the manual GitHub Release triggers the `HACS Release Asset` job, which uploads `ok.zip`
for HACS. Add `zip_release` and `filename` to `hacs.json` only after the first `ok.zip` asset
exists, otherwise pre-release HACS validation can fail before it finds an integration manifest.

### Automated Releases

1. Merge a PR with a Conventional Commit title.
2. The `Validate` workflow runs on `main`.
3. After `Validate` succeeds, the `Release` workflow runs.
4. Python Semantic Release calculates the next version from commits on `main`.
5. If a release is needed, it updates:
   - `pyproject.toml`
   - `custom_components/ok/manifest.json`
   - `custom_components/ok/api/_version.py`
   - `CHANGELOG.md`
6. The release workflow pushes a release commit, creates a tag such as `v0.3.0`, and creates a
   GitHub Release.
7. The workflow checks out the released commit, builds `ok.zip` from `custom_components/ok`, and
   uploads that asset to the GitHub Release for HACS.

The `release.published` path also builds and uploads `ok.zip` for manually created releases. That
path stamps the release tag version into the files inside the archive only; it does not commit
version or changelog changes back to `main`. Use automated releases after the initial baseline.

No PyPI publishing is configured while the OK API client remains bundled inside the Home Assistant
custom component.

## HACS

- First test installation by adding the public repository as a custom HACS integration repository.
- Install from the public repository, restart Home Assistant, and complete setup through the config
  flow.
- Verify entities, actions, diagnostics, realtime updates, force refresh, and the schedule script
  blueprint.
- Submit to HACS default repositories only after custom-repository installation is proven with a
  published GitHub Release.
