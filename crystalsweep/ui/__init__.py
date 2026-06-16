#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/__init__.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to initialize the CrystalSweep UI.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging

from crystalsweep.paths import user_app_dir

__all__ = ["start_ui"]


def _configure_logging() -> None:
    """Write app logs to %APPDATA%\\CrystalSweep\\crystalsweep.log and to stderr."""
    log_path = user_app_dir() / "crystalsweep.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    if any(getattr(h, "_crystalsweep", False) for h in root.handlers):
        return
    root.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    fh._crystalsweep = True  # type: ignore[attr-defined]
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh._crystalsweep = True  # type: ignore[attr-defined]
    root.addHandler(fh)
    root.addHandler(sh)
    logging.getLogger(__name__).info("Logging to %s", log_path)


def start_ui() -> None:
    """Starts the CrystalSweep UI."""
    _configure_logging()
    # Lazy import to avoid loading wx on CLI mode
    from crystalsweep.ui.controller import UIApplication

    UIApplication()
