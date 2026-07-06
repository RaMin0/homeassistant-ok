# Validation

Use Docker for Home Assistant runtime validation. Do not use a host Home Assistant install for
integration QA.

Default tests must be hermetic and must not call live OK, Firebase, or Google APIs.

## Compose Validation

Validate the local compose file, including the optional watcher profile:

```bash
docker compose --profile watch config
```

Start the development Home Assistant instance:

```bash
docker compose up -d homeassistant
```

Start it with automatic restarts when `custom_components/ok` changes:

```bash
docker compose --profile watch up -d homeassistant watcher
```

Stop it:

```bash
docker compose down
```

The local Home Assistant config at `docker/ha/config` is runtime state and must stay ignored.

## Brand Assets

Validate local brand images from inside the Home Assistant container:

```bash
docker compose run --rm \
  -v "$PWD":/workspace \
  -w /workspace \
  --entrypoint python \
  homeassistant \
  tools/validate_brand_images.py custom_components/ok/brand
```

Expected files:

- `custom_components/ok/brand/icon.png`
- `custom_components/ok/brand/icon@2x.png`
- `custom_components/ok/brand/logo.png`
- `custom_components/ok/brand/logo@2x.png`

## Target Home Assistant Gate

Run this before merging code changes that affect the integration, client, tests, CI, or release
metadata. Run both commands. The Home Assistant command installs test/type tooling into a temporary
virtual environment with access to Home Assistant's packaged dependencies, so pip does not mutate the
Home Assistant runtime interpreter.

```bash
docker compose run --rm \
  -v "$PWD":/workspace \
  -w /workspace \
  --entrypoint sh \
  homeassistant \
  -lc 'set -e
  python - <<'"'"'PY'"'"'
from __future__ import annotations

import json
from pathlib import Path

from homeassistant.util.package import install_package

constraints = "/usr/src/homeassistant/homeassistant/package_constraints.txt"
manifest = json.loads(Path("custom_components/ok/manifest.json").read_text())
failed = [
    requirement
    for requirement in manifest["requirements"]
    if not install_package(requirement, constraints=constraints)
]
if failed:
    raise SystemExit(
        "Home Assistant could not install manifest requirements: " + ", ".join(failed)
    )
PY
  HA_VENV=/tmp/ok-ha-venv
  python -m venv --system-site-packages "$HA_VENV" && \
  "$HA_VENV/bin/python" -m pip install --upgrade pip >/tmp/ok-pip-upgrade.log && \
  "$HA_VENV/bin/python" -m pip install -e ".[firebase]" -r requirements-manifest.txt \
    "mypy>=1.17,<3" "pytest>=8.4,<10" "pytest-asyncio>=1.1,<2" \
    "pytest-cov>=6.2,<8" >/tmp/ok-pip.log && \
  MYPYPATH=/usr/src/homeassistant "$HA_VENV/bin/python" -m mypy && \
  "$HA_VENV/bin/python" -m pytest --cov=custom_components.ok --cov-report=term-missing && \
  "$HA_VENV/bin/python" -c "from custom_components.ok.api._firestore import _close_owned_firestore_client, _create_default_firestore_client; client = _create_default_firestore_client(project_id=\"ok-ci-smoke\", credentials=None); _close_owned_firestore_client(client)"'
```

```bash
docker run --rm \
  -e PIP_ROOT_USER_ACTION=ignore \
  -v "$PWD":/workspace \
  -w /workspace \
  python:3.13-slim \
  sh -lc 'set -e
  python -m pip install --upgrade pip "build>=1.2,<2" "pip-audit>=2.9,<3" \
    "ruff>=0.12,<1" "twine>=6.0,<7" >/tmp/ok-pip.log && \
  python - <<'"'"'PY'"'"' > /tmp/ok-audit-requirements.txt
from __future__ import annotations

from pathlib import Path
import tomllib

pyproject = tomllib.loads(Path("pyproject.toml").read_text())
for dependency in pyproject["project"]["dependencies"]:
    print(dependency)
for line in Path("requirements-manifest.txt").read_text().splitlines():
    stripped = line.strip()
    if stripped and not stripped.startswith("#"):
        print(stripped)
PY
  python -m pip_audit -r /tmp/ok-audit-requirements.txt --progress-spinner off && \
  python -m ruff format --check custom_components tests tools && \
  python -m ruff check custom_components tests tools && \
  python -m build --outdir /tmp/dist && \
  python -m twine check /tmp/dist/* && \
  python - <<'"'"'PY'"'"'
from __future__ import annotations

from pathlib import Path
import zipfile

wheel = next(Path("/tmp/dist").glob("*.whl"))
required = {
    "custom_components/ok/__init__.py",
    "custom_components/ok/manifest.json",
    "custom_components/ok/api/__init__.py",
    "custom_components/ok/py.typed",
    "custom_components/ok/translations/en.json",
}
with zipfile.ZipFile(wheel) as archive:
    names = set(archive.namelist())
if missing := sorted(required - names):
    raise SystemExit(f"Wheel is missing required files: {missing}")
PY'
```

This repository uses Python packaging only as a validation/build mechanism for the HACS custom
component. It does not publish a standalone importable OK client wheel while the client remains
bundled under `custom_components/ok/api`.

## Latest Stable Home Assistant Gate

Run this before public release prep and after compatibility-related changes. Also run the Python
quality/package command from the target gate above once.

```bash
docker run --rm \
  -v "$PWD":/workspace \
  -w /workspace \
  ghcr.io/home-assistant/home-assistant:stable \
  sh -lc 'set -e
  python - <<'"'"'PY'"'"'
from __future__ import annotations

import json
from pathlib import Path

from homeassistant.util.package import install_package

constraints = "/usr/src/homeassistant/homeassistant/package_constraints.txt"
manifest = json.loads(Path("custom_components/ok/manifest.json").read_text())
failed = [
    requirement
    for requirement in manifest["requirements"]
    if not install_package(requirement, constraints=constraints)
]
if failed:
    raise SystemExit(
        "Home Assistant could not install manifest requirements: " + ", ".join(failed)
    )
PY
  HA_VENV=/tmp/ok-ha-venv
  python -m venv --system-site-packages "$HA_VENV" && \
  "$HA_VENV/bin/python" -m pip install --upgrade pip >/tmp/ok-pip-upgrade.log && \
  "$HA_VENV/bin/python" -m pip install -e ".[firebase]" -r requirements-manifest.txt \
    "mypy>=1.17,<3" "pytest>=8.4,<10" "pytest-asyncio>=1.1,<2" \
    "pytest-cov>=6.2,<8" >/tmp/ok-pip.log && \
  MYPYPATH=/usr/src/homeassistant "$HA_VENV/bin/python" -m mypy && \
  "$HA_VENV/bin/python" -m pytest --cov=custom_components.ok --cov-report=term-missing && \
  "$HA_VENV/bin/python" -c "from custom_components.ok.api._firestore import _close_owned_firestore_client, _create_default_firestore_client; client = _create_default_firestore_client(project_id=\"ok-ci-smoke\", credentials=None); _close_owned_firestore_client(client)"'
```

## Focused Tests

Use focused tests while iterating, then run the full gate when the change is ready.

Examples:

```bash
docker compose run --rm -v "$PWD":/workspace -w /workspace --entrypoint sh homeassistant \
  -lc 'set -e
  HA_VENV=/tmp/ok-ha-venv
  python -m venv --system-site-packages "$HA_VENV"
  "$HA_VENV/bin/python" -m pip install -e ".[firebase]" -r requirements-manifest.txt \
    "pytest>=8.4,<10" "pytest-asyncio>=1.1,<2" >/tmp/ok-pip.log
  "$HA_VENV/bin/python" -m pytest tests/custom_components/ok/test_sensor.py -q'
```

```bash
docker compose run --rm -v "$PWD":/workspace -w /workspace --entrypoint sh homeassistant \
  -lc 'set -e
  HA_VENV=/tmp/ok-ha-venv
  python -m venv --system-site-packages "$HA_VENV"
  "$HA_VENV/bin/python" -m pip install -e ".[firebase]" -r requirements-manifest.txt \
    "pytest>=8.4,<10" "pytest-asyncio>=1.1,<2" >/tmp/ok-pip.log
  "$HA_VENV/bin/python" -m pytest tests/test_client_async.py tests/test_firestore.py -q'
```

## Publish-Surface Audit

Before publishing, confirm no local runtime state or generated clutter would be committed:

```bash
find . \
  -path './.codex' -prune -o \
  -path './docker/ha/config' -prune -o \
  -path './.git' -prune -o \
  -type f \( \
    -name '*.pyc' -o \
    -name '.coverage' -o \
    -name '*.db' -o \
    -name '*.log' -o \
    -name '.env*' -o \
    -name 'secrets.yaml' -o \
    -name '*.sqlite' -o \
    -name '*.sqlite3' -o \
    -name '*.token' -o \
    -name '*.key' -o \
    -name '*.pem' -o \
    -name '*.apk' -o \
    -name '*.apks' -o \
    -name '*.aab' \
  \) -print
```

Also check that release version metadata is synchronized and inspect remaining version literals for
stale references:

```bash
version="$(awk -F'"' '/^version = / {print $2; exit}' pyproject.toml)"
rg -n "version = \"$version\"|\"version\": \"$version\"|__version__ = \"$version\"" \
  pyproject.toml custom_components/ok/manifest.json custom_components/ok/api/_version.py
rg -n "^## v$version([ (]|$)" CHANGELOG.md
rg -n "v?[0-9]+\\.[0-9]+\\.[0-9]+" \
  README.md README.da.md PUBLISHING.md CONTRIBUTING.md ROADMAP.md SECURITY.md AGENTS.md \
  docs .github custom_components/ok/manifest.json custom_components/ok/api/_version.py pyproject.toml
```

If generated caches exist, remove them outside integration code. Do not add integration code that
cleans developer runtime state.
