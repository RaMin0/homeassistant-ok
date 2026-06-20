#!/usr/bin/env python3
"""Validate Home Assistant brand image names and PNG dimensions."""

from __future__ import annotations

import argparse
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

ICON_SIZES = {
    "icon.png": (256, 256),
    "dark_icon.png": (256, 256),
    "icon@2x.png": (512, 512),
    "dark_icon@2x.png": (512, 512),
}

LOGO_FILES = {
    "logo.png": (128, 256),
    "dark_logo.png": (128, 256),
    "logo@2x.png": (256, 512),
    "dark_logo@2x.png": (256, 512),
}

MDI_ICON_RE = re.compile(r"^mdi:[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class PngInfo:
    """Basic PNG metadata read from IHDR."""

    width: int
    height: int


def read_png_info(path: Path) -> PngInfo:
    """Read PNG width and height without external dependencies."""
    with path.open("rb") as file:
        signature = file.read(8)
        if signature != PNG_SIGNATURE:
            raise ValueError("not a PNG file")

        length_bytes = file.read(4)
        chunk_type = file.read(4)
        if len(length_bytes) != 4 or chunk_type != b"IHDR":
            raise ValueError("missing IHDR chunk")

        length = struct.unpack(">I", length_bytes)[0]
        if length != 13:
            raise ValueError(f"unexpected IHDR length {length}")

        data = file.read(13)
        if len(data) != 13:
            raise ValueError("truncated IHDR chunk")

    width, height, *_rest = struct.unpack(">IIBBBBB", data)
    return PngInfo(width, height)


def validate_icon_txt(path: Path) -> list[str]:
    """Return validation errors for a Material Design Icon fallback file."""
    value = path.read_text(encoding="utf-8").strip()
    if not MDI_ICON_RE.fullmatch(value):
        return [f"{path.name}: expected a single Material Design Icon value like mdi:home"]
    return []


def validate_file(path: Path, allow_icon_txt: bool) -> list[str]:
    """Return validation errors for one brand file."""
    if path.name == "icon.txt":
        if allow_icon_txt:
            return validate_icon_txt(path)
        return [f"{path.name}: unexpected file name; pass --allow-icon-txt for Core fallback"]

    if path.suffix.lower() != ".png":
        return [f"{path.name}: file extension must be .png"]

    try:
        info = read_png_info(path)
    except ValueError as err:
        return [f"{path.name}: {err}"]

    errors: list[str] = []
    if path.name in ICON_SIZES:
        expected = ICON_SIZES[path.name]
        if (info.width, info.height) != expected:
            errors.append(
                f"{path.name}: expected {expected[0]}x{expected[1]}, got {info.width}x{info.height}"
            )
    elif path.name in LOGO_FILES:
        min_short, max_short = LOGO_FILES[path.name]
        short_side = min(info.width, info.height)
        if not min_short <= short_side <= max_short:
            errors.append(
                f"{path.name}: shortest side must be {min_short}-{max_short}px, "
                f"got {short_side}px ({info.width}x{info.height})"
            )
    else:
        errors.append(f"{path.name}: unexpected file name")
    return errors


def validate_directory(
    directory: Path,
    *,
    require_icon: bool,
    allow_icon_txt: bool,
) -> tuple[list[str], list[str]]:
    """Validate a brand directory and return errors and warnings."""
    if not directory.exists():
        return [f"{directory}: directory does not exist"], []
    if not directory.is_dir():
        return [f"{directory}: not a directory"], []

    errors: list[str] = []
    warnings: list[str] = []
    has_icon = (directory / "icon.png").exists()
    has_icon_txt = allow_icon_txt and (directory / "icon.txt").exists()

    if require_icon and not (has_icon or has_icon_txt):
        required = "icon.png or icon.txt" if allow_icon_txt else "icon.png"
        errors.append(f"{required} is required")
    if has_icon and has_icon_txt:
        warnings.append("icon.txt is ignored when icon.png is present")

    for path in sorted(path for path in directory.iterdir() if path.is_file()):
        errors.extend(validate_file(path, allow_icon_txt))

    for normal, hidpi in (
        ("icon.png", "icon@2x.png"),
        ("dark_icon.png", "dark_icon@2x.png"),
        ("logo.png", "logo@2x.png"),
        ("dark_logo.png", "dark_logo@2x.png"),
    ):
        if (directory / normal).exists() and not (directory / hidpi).exists():
            warnings.append(f"{hidpi} is recommended when {normal} exists")

    for path in sorted(path for path in directory.iterdir() if path.is_dir()):
        warnings.append(f"{path.name}/ is ignored; brand folders should contain image files only")

    return errors, warnings


def main() -> int:
    """Run the brand validator CLI."""
    parser = argparse.ArgumentParser(
        description="Validate Home Assistant brand icon/logo PNG files."
    )
    parser.add_argument("directory", type=Path, help="Brand image directory to validate")
    parser.add_argument(
        "--no-require-icon",
        action="store_true",
        help="Do not require icon.png.",
    )
    parser.add_argument(
        "--allow-icon-txt",
        action="store_true",
        help="Allow Core integration icon.txt Material Design Icon fallback.",
    )
    args = parser.parse_args()

    errors, warnings = validate_directory(
        args.directory,
        require_icon=not args.no_require_icon,
        allow_icon_txt=args.allow_icon_txt,
    )

    for warning in warnings:
        sys.stderr.write(f"WARNING: {warning}\n")
    for error in errors:
        sys.stderr.write(f"ERROR: {error}\n")

    if errors:
        return 1

    sys.stdout.write(f"OK: {args.directory} brand images passed basic validation\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
