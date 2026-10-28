# SPDX-License-Identifier: MIT

import os
import sys
from pathlib import Path

__all__ = ["APP_NAME", "user_app_dir", "user_config_dir"]

APP_NAME = "CrystalSweep"


def user_app_dir() -> Path:
    """Return the per-user application data directory for CrystalSweep.

    Windows: %APPDATA%\\CrystalSweep
    macOS:   ~/Library/Application Support/CrystalSweep
    Linux:   $XDG_DATA_HOME/CrystalSweep (or ~/.local/share/CrystalSweep)
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


def user_config_dir() -> Path:
    """Return the per-user directory for beamline configs and the hooks script.

    The directory is created on first access.
    """
    path = user_app_dir() / "configs"
    path.mkdir(parents=True, exist_ok=True)
    return path
