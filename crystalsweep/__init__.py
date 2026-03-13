#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/__init__.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to initialize the CrystalSweep package.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from crystalsweep.controller import GUIApplication


def main() -> None:
    """Main entry point for the CrystalSweep package."""

    GUIApplication()
