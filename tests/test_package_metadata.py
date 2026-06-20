from __future__ import annotations

import json
import tomllib
from pathlib import Path

from custom_components.ok.api import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_published_versions_match() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "custom_components/ok/manifest.json").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == manifest["version"] == __version__
