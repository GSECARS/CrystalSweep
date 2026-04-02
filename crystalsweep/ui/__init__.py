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

__all__ = ["start_ui"]


def start_ui() -> None:
    """Starts the CrystalSweep UI."""
    # Lazy import to avoid loading wx on CLI mode
    from crystalsweep.ui.controller import UIApplication

    UIApplication()
