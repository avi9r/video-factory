#!/usr/bin/env python3
"""Build the SFX library from CC0 downloads (real recordings, not synthetic)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from download_sfx_library import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
