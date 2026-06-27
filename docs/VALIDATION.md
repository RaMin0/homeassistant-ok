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
metadata:

```bash
docker compose run --rm \
  -v "$PWD":/workspace \
  -w /workspace \
  --entrypoint sh \
  homeassistant \
  -lc 'python -m pip install --upgrade pip >/tmp/ok-pip-upgrade.log && \
  python -m pip install -e ".[dev]" -r requirements-manifest.txt >/tmp/ok-pip.log && \
  python -m pip_audit -r requirements-manifest.txt --progress-spinner off && \
  python -m ruff format --check custom_components tests tools && \
  python -m ruff check custom_components tests tools && \
  MYPYPATH=/usr/src/homeassistant python -m mypy && \
  python -m pytest --cov=custom_components.ok --cov-report=term-missing && \
  python -c "from custom_components.ok.api._firestore import _close_owned_firestore_client, _create_default_firestore_client; client = _create_default_firestore_client(project_id=\"ok-ci-smoke\", credentials=None); _close_owned_firestore_client(client)" && \
  python -m build --outdir /tmp/dist && \
  python -m twine check /tmp/dist/* && \
  python -m pip install --force-reinstall --no-deps /tmp/dist/*.whl >/tmp/ok-wheel-install.log && \
  cd /tmp && python -c "import custom_components.ok.api as ok_api; print(ok_api.__version__); assert \"site-packages\" in ok_api.__file__"'
```

## Latest Stable Home Assistant Gate

Run this before public release prep and after compatibility-related changes:

```bash
docker run --rm \
  -v "$PWD":/workspace \
  -w /workspace \
  ghcr.io/home-assistant/home-assistant:stable \
  sh -lc 'python -m pip install --upgrade pip >/tmp/ok-pip-upgrade.log && \
  python -m pip install -e ".[dev]" -r requirements-manifest.txt >/tmp/ok-pip.log && \
  python -m pip_audit -r requirements-manifest.txt --progress-spinner off && \
  python -m ruff format --check custom_components tests tools && \
  python -m ruff check custom_components tests tools && \
  MYPYPATH=/usr/src/homeassistant python -m mypy && \
  python -m pytest --cov=custom_components.ok --cov-report=term-missing && \
  python -c "from custom_components.ok.api._firestore import _close_owned_firestore_client, _create_default_firestore_client; client = _create_default_firestore_client(project_id=\"ok-ci-smoke\", credentials=None); _close_owned_firestore_client(client)" && \
  python -m build --outdir /tmp/dist && \
  python -m twine check /tmp/dist/* && \
  python -m pip install --force-reinstall --no-deps /tmp/dist/*.whl >/tmp/ok-wheel-install.log && \
  cd /tmp && python -c "import custom_components.ok.api as ok_api; print(ok_api.__version__); assert \"site-packages\" in ok_api.__file__"'
```

## Focused Tests

Use focused tests while iterating, then run the full gate when the change is ready.

Examples:

```bash
docker compose run --rm -v "$PWD":/workspace -w /workspace --entrypoint sh homeassistant \
  -lc 'python -m pip install -e ".[dev]" >/tmp/ok-pip.log && python -m pytest tests/custom_components/ok/test_sensor.py -q'
```

```bash
docker compose run --rm -v "$PWD":/workspace -w /workspace --entrypoint sh homeassistant \
  -lc 'python -m pip install -e ".[dev]" >/tmp/ok-pip.log && python -m pytest tests/test_client_async.py tests/test_firestore.py -q'
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
    -name '*.pem' \
  \) -print
```

Also check that local development version metadata is synchronized and inspect remaining version
literals for stale references:

```bash
version="$(awk -F'"' '/^version = / {print $2; exit}' pyproject.toml)"
rg -n "version = \"$version\"|\"version\": \"$version\"|__version__ = \"$version\"" \
  pyproject.toml custom_components/ok/manifest.json custom_components/ok/api/_version.py
rg -n "v?[0-9]+\\.[0-9]+\\.[0-9]+" \
  README.md README.da.md PUBLISHING.md CONTRIBUTING.md ROADMAP.md SECURITY.md AGENTS.md \
  docs .github custom_components/ok/manifest.json custom_components/ok/api/_version.py pyproject.toml
```

If generated caches exist, remove them outside integration code. Do not add integration code that
cleans developer runtime state.
