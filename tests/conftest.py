from __future__ import annotations

import sys
from pathlib import Path

API_PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "ok"

if str(API_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(API_PACKAGE_ROOT))
