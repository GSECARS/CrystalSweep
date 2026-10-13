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
from importlib.metadata import version
from pathlib import Path

from wxutils import AppConfig, WxApplication, add_application_arguments, handle_shortcut_arguments

from crystalsweep.ui.controller.main_controller import MainController
from crystalsweep.ui.view.main_view import MainView

__version__ = version("crystalsweep")
__all__ = ["__version__", "main"]

APP_CONFIG = AppConfig(
    name="CrystalSweep",
    assets=str(Path(__file__).resolve().parent / "assets"),
    description="beamline control and data acquisition software for single-crystal X-ray diffraction experiments",
    application_id="gsecars.crystalsweep",
)


def make_parser():
    """Builds the application command line parser."""
    parser = ArgumentParser(f"{APP_CONFIG.name} {__version__}")
    parser.add_argument("-t", "--test", action="store_true", help="run the test suite")
    add_application_arguments(parser)
    return parser


def main() -> None:
    """Main entry point for `crystalsweep` console script."""
    parser = make_parser()
    args = parser.parse_args()

    if handle_shortcut_arguments(parser, args, APP_CONFIG):
        return

    if args.test:
        import pytest

        sys.exit(pytest.main([]))

    app = WxApplication(APP_CONFIG, False)
    view = MainView(version=__version__, with_inspect=args.inspect)
    controller = MainController(view=view)
    app.run(view)
