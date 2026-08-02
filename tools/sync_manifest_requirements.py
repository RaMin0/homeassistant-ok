"""Synchronize the pip dependency mirror from the integration manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "custom_components/ok/manifest.json"
MIRROR_PATH = ROOT / "requirements-manifest.txt"
HEADER = (
    "# Generated from custom_components/ok/manifest.json for Dependabot and pip-audit.\n"
    "# Run python tools/sync_manifest_requirements.py after changing manifest requirements.\n"
)


def expected_mirror() -> str:
    """Return the dependency mirror generated from the integration manifest."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    requirements = manifest["requirements"]
    if not isinstance(requirements, list) or not all(
        isinstance(requirement, str) for requirement in requirements
    ):
        msg = f"{MANIFEST_PATH} requirements must be a list of strings"
        raise ValueError(msg)
    return HEADER + "\n".join(requirements) + "\n"


def main() -> int:
    """Write the mirror, or verify it when invoked with --check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the mirror is stale")
    args = parser.parse_args()

    expected = expected_mirror()
    current = MIRROR_PATH.read_text(encoding="utf-8") if MIRROR_PATH.exists() else ""
    if current == expected:
        return 0
    if args.check:
        sys.stderr.write(
            f"{MIRROR_PATH.relative_to(ROOT)} is stale; "
            "run python tools/sync_manifest_requirements.py\n"
        )
        return 1

    MIRROR_PATH.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
