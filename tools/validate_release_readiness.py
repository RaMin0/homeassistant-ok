"""Validate release metadata and public repository readiness.

This check intentionally uses only the Python standard library so it can run early in CI without
installing the project or Home Assistant.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"^## v(?P<version>\d+\.\d+\.\d+)\b", re.MULTILINE)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_json(path: str) -> Any:
    return json.loads(_read(path))


def _api_version() -> str:
    module = ast.parse(_read("custom_components/ok/api/_version.py"))
    for node in module.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__version__"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise RuntimeError("custom_components/ok/api/_version.py does not define __version__")


def _semantic_release_config(pyproject: dict[str, Any]) -> dict[str, Any]:
    return pyproject.get("tool", {}).get("semantic_release", {})


def main() -> int:
    errors: list[str] = []
    pyproject = tomllib.loads(_read("pyproject.toml"))
    manifest = _load_json("custom_components/ok/manifest.json")
    hacs = _load_json("hacs.json")
    release_workflow = _read(".github/workflows/release.yml")
    validate_workflow = _read(".github/workflows/validate.yml")

    project_version = pyproject["project"]["version"]
    versions = {
        "pyproject.toml": project_version,
        "custom_components/ok/manifest.json": manifest.get("version"),
        "custom_components/ok/api/_version.py": _api_version(),
    }
    if len(set(versions.values())) != 1:
        errors.append(f"Version files are out of sync: {versions}")

    changelog = _read("CHANGELOG.md")
    first_changelog_version = VERSION_PATTERN.search(changelog)
    if first_changelog_version is None:
        errors.append("CHANGELOG.md does not contain a release heading such as '## v0.1.0'.")
    elif first_changelog_version.group("version") != project_version:
        errors.append(
            "CHANGELOG.md latest release heading "
            f"{first_changelog_version.group('version')!r} does not match {project_version!r}."
        )

    semantic_release = _semantic_release_config(pyproject)
    if "pyproject.toml:project.version" not in semantic_release.get("version_toml", []):
        errors.append("semantic-release does not update pyproject.toml project.version.")
    expected_version_variables = {
        "custom_components/ok/api/_version.py:__version__",
        "custom_components/ok/manifest.json:version",
    }
    configured_version_variables = set(semantic_release.get("version_variables", []))
    if missing := sorted(expected_version_variables - configured_version_variables):
        errors.append(f"semantic-release is missing version variables: {missing}")

    if hacs.get("zip_release") is not True:
        errors.append("hacs.json must keep zip_release enabled.")
    if hacs.get("filename") != "ok.zip":
        errors.append("hacs.json filename must be ok.zip.")

    required_release_snippets = {
        "RELEASE_TOKEN": "Release workflow must authenticate release writes with RELEASE_TOKEN.",
        "permissions:\n  contents: read": "Release workflow must keep GITHUB_TOKEN read-only.",
        "RELEASE_ASSET_NAME: ok.zip": "Release workflow must build the ok.zip HACS asset.",
        '"manifest.json"': "Release asset validation must require manifest.json.",
        '"api/_version.py"': "Release asset validation must require api/_version.py.",
        '"brand/icon.png"': "Release asset validation must require brand/icon.png.",
        '"translations/en.json"': "Release asset validation must require English translations.",
    }
    for snippet, message in required_release_snippets.items():
        if snippet not in release_workflow:
            errors.append(message)

    if "Release Readiness" not in validate_workflow:
        errors.append("Validate workflow must include the Release Readiness job.")
    if "Workflow Permissions" not in validate_workflow:
        errors.append("Validate workflow must include the Workflow Permissions guard.")

    required_docs = {
        "README.md": [
            "docs/TROUBLESHOOTING.md",
            "docs/PRIVACY_AND_API_RISKS.md",
            "docs/PROJECT_MAP.md",
        ],
        "README.da.md": [
            "docs/TROUBLESHOOTING.md",
            "docs/PRIVACY_AND_API_RISKS.md",
            "docs/PROJECT_MAP.md",
        ],
        "PUBLISHING.md": [
            "RELEASE_TOKEN",
            "Release Readiness",
            "tools/validate_release_readiness.py",
        ],
        "docs/REPO_INVARIANTS.md": ["RELEASE_TOKEN", "GITHUB_TOKEN", "ok.zip"],
        "docs/PRIVACY_AND_API_RISKS.md": ["unofficial", "diagnostics", "OK API behavior change"],
        "docs/PROJECT_MAP.md": [
            "Scheduling",
            "Reliability And Diagnostics",
            "Publishing And HACS Quality",
        ],
    }
    for path, snippets in required_docs.items():
        text = _read(path)
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{path} is missing expected release/support text: {snippet!r}")

    required_issue_files = [
        ".github/ISSUE_TEMPLATE/api_behavior_change.yml",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/setup_problem.yml",
        ".github/milestones.yml",
        ".github/labels.yml",
    ]
    for path in required_issue_files:
        if not (ROOT / path).is_file():
            errors.append(f"Missing public support file: {path}")

    if errors:
        sys.stderr.write("Release readiness validation failed:\n")
        for error in errors:
            sys.stderr.write(f"- {error}\n")
        return 1

    sys.stdout.write(f"Release readiness validation passed for v{project_version}.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
