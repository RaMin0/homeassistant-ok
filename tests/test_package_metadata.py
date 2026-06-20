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


def test_manifest_requirements_mirror_matches_manifest() -> None:
    manifest = json.loads((ROOT / "custom_components/ok/manifest.json").read_text(encoding="utf-8"))
    mirror = [
        line.strip()
        for line in (ROOT / "requirements-manifest.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    assert mirror == manifest["requirements"]
