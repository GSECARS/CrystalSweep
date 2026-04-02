#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/__init__.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to initialize the CrystalSweep controller.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from importlib.metadata import PackageNotFoundError, version

__all__ = ["UIApplication"]


def _get_version() -> str:
    try:
        return version("crystalsweep")
    except PackageNotFoundError:
        return "dev"


def UIApplication() -> None:
    """Initializes the CrystalSweep UI application."""
    # Lazy import to avoid loading wx on CLI mode
    from crystalsweep.ui.controller.main_controller import MainController

    MainController(version=_get_version()).run()
