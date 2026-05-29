#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/script_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Manages the user-editable hooks.py script stored on disk under the configs/
# directory. The file contains both pre_scan and post_scan (and any helpers the
# user adds). Scripts are hot-reloaded via importlib on every call so edits saved
# from the GUI take effect immediately without restarting the app.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import importlib.util
import logging
import traceback
from pathlib import Path

__all__ = ["ScriptModel"]

_log = logging.getLogger(__name__)

_HOOKS_FILE = "hooks.py"

_DEFAULT_HOOKS = '''\
from epics import caget, caput
from crystalsweep.model.collection_model import CollectionPoint
from crystalsweep.model.beamline_config_model import BeamlineConfig


# Helpers
def is_map(point: CollectionPoint) -> bool:
    """Return True if this point is part of a map group."""
    return bool(point.map_group)


def pre_scan(point: CollectionPoint, config: BeamlineConfig) -> str | None:
    """Called before each scan point.

    Return an error string to skip the point, or None to proceed.
    Example: return "Sample not aligned" to skip this point with that message.

    Useful point attributes:
      point.scan_type     -- "still", "wide", or "step"
      point.map_group     -- non-empty string if this point belongs to a map
      point.map_motor1    -- shorthand of the first map motor (e.g. "vert")
      point.map_motor2    -- shorthand of the second map motor (or "")
      point.motor_positions  -- dict of motor shorthand -> position string
      point.label         -- display label for this point
    """
    if is_map(point) and point.scan_type == "still":
        pass  # map still pre-scan logic here

    return None


def post_scan(point: CollectionPoint, config: BeamlineConfig) -> None:
    """Called after each scan point completes.

    Same point attributes as pre_scan are available.
    """
    pass
'''


class ScriptModel:
    """Loads, saves, and hot-reloads hooks.py from a scripts/ directory.

    Uses importlib to load the file as a proper Python module so that
    tracebacks point to the actual file and line numbers.
    """

    def __init__(self, directory: Path | str = "configs") -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._ensure_default()

    @property
    def directory(self) -> Path:
        return self._directory

    @property
    def hooks_path(self) -> Path:
        return self._directory / _HOOKS_FILE

    def load_source(self) -> str:
        path = self.hooks_path
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return _DEFAULT_HOOKS

    def save_source(self, source: str) -> None:
        self.hooks_path.write_text(source, encoding="utf-8")
        _log.info("Hooks script saved to %s", self.hooks_path)

    def call(self, name: str, *args, **kwargs):
        """Hot-reload hooks.py and call the named function with *args."""
        path = self.hooks_path
        if not path.is_file():
            _log.error("Hooks file not found: %s", path)
            return None

        try:
            spec = importlib.util.spec_from_file_location("crystalsweep_hooks", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            _log.error("hooks.py failed to load:\n%s", traceback.format_exc())
            return None

        fn = getattr(module, name, None)
        if fn is None:
            _log.error("hooks.py does not define a function named %r", name)
            return None

        try:
            return fn(*args, **kwargs)
        except Exception:
            _log.error("hooks.py %r raised an exception:\n%s", name, traceback.format_exc())
            return None

    def _ensure_default(self) -> None:
        if not self.hooks_path.is_file():
            self.hooks_path.write_text(_DEFAULT_HOOKS, encoding="utf-8")
