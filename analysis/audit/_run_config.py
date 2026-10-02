"""Thin wrapper: preload DLLs (see _dll_preload.py), then run the real,
unmodified upgradecanary.runner on the given config. No project file is
imported-and-changed; this just fixes a machine-local DLL search-order
issue before calling the existing runner.

Usage: python analysis/audit/_run_config.py <config_path>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import _dll_preload  # noqa: E402

_dll_preload.preload()

from upgradecanary.runner import main  # noqa: E402

if __name__ == "__main__":
    main(["--config", sys.argv[1]])
