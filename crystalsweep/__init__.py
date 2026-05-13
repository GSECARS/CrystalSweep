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

from argparse import ArgumentParser


def main() -> None:
    """Main entry point for `crystalsweep` console script."""
    parser = ArgumentParser("CrystalSweep CLI")
    parser.add_argument("-g", "--gui", action="store_true", help="launch the GUI application")

    args = parser.parse_args()

    if args.gui:
        # Lazy import to avoid loading wx on CLI mode
        from crystalsweep.ui import start_ui

        start_ui()
    else:
        parser.print_help()
