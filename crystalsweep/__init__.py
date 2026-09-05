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

import os
import sys
from argparse import ArgumentParser


def _win_local_icon(src: str) -> str:
    """Copy the .ico to %PROGRAMDATA%\\CrystalSweep so Windows finds it before network shares mount."""
    import shutil
    dest_dir = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "CrystalSweep")
    try:
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, "crystalsweep.ico")
        shutil.copy2(src, dest)
        return dest
    except OSError:
        return src


def main() -> None:
    """Main entry point for `crystalsweep` console script."""
    parser = ArgumentParser("CrystalSweep CLI")
    parser.add_argument("-g", "--gui", action="store_true", help="launch the GUI application")
    parser.add_argument("-t", "--test", action="store_true", help="run the test suite")
    parser.add_argument("-m", "--make-icon", action="store_true", help="create desktop shortcut icon")
    parser.add_argument("-p", "--public", action="store_true", help="create shortcut on public desktop")

    args = parser.parse_args()

    _assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

    if args.make_icon or args.public:
        from pyshortcuts import make_shortcut
        bindir = "Scripts" if os.name == "nt" else "bin"
        script = os.path.join(sys.prefix, bindir, "crystalsweep")
        if sys.platform == "darwin":
            icns = os.path.join(_assets_dir, "crystalsweep_logo.icns")
            icon = icns if os.path.isfile(icns) else os.path.join(_assets_dir, "crystalsweep_logo.png")
        elif os.name == "nt":
            ico = os.path.join(_assets_dir, "crystalsweep_logo.ico")
            icon = _win_local_icon(ico) if os.path.isfile(ico) else os.path.join(_assets_dir, "crystalsweep_logo.png")
        else:
            icon = os.path.join(_assets_dir, "crystalsweep_logo.png")
        make_shortcut(script, name="CrystalSweep", icon=icon, terminal=False,
                      public=args.public, folder="GSEApps" if args.public else None)
        return

    if args.gui:
        # Lazy import to avoid loading wx on CLI mode
        from crystalsweep.ui import start_ui

        start_ui()
    elif args.test:
        import pytest

        sys.exit(pytest.main([]))
    else:
        parser.print_help()
