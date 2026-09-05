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


def _make_ico(png_path: str) -> str:
    """Generate a multi-size .ico from a PNG using Pillow. Returns the .ico path."""
    from PIL import Image
    ico_path = os.path.splitext(png_path)[0] + ".ico"
    img = Image.open(png_path).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    imgs = [img.resize(s, Image.LANCZOS) for s in sizes]
    imgs[0].save(ico_path, format="ICO", append_images=imgs[1:])
    return ico_path


def _make_icns(png_path: str) -> str:
    """Generate a .icns from a PNG using macOS sips and iconutil. Returns the .icns path."""
    import subprocess
    import tempfile
    icns_path = os.path.splitext(png_path)[0] + ".icns"
    sizes = [(16, 1), (16, 2), (32, 1), (32, 2), (128, 1), (128, 2), (256, 1), (256, 2), (512, 1), (512, 2)]
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "CrystalSweep.iconset")
        os.makedirs(iconset)
        for size, scale in sizes:
            px = size * scale
            suffix = f"@{scale}x" if scale > 1 else ""
            name = f"icon_{size}x{size}{suffix}.png"
            subprocess.run(
                ["sips", "-z", str(px), str(px), png_path, "--out", os.path.join(iconset, name)],
                capture_output=True, check=True,
            )
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns_path], check=True)
    return icns_path


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
    parser.add_argument("-t", "--test", action="store_true", help="run the test suite")
    parser.add_argument("-m", "--make-icon", action="store_true", help="create desktop shortcut icon")
    parser.add_argument("-p", "--public", action="store_true", help="create shortcut on public desktop")

    args = parser.parse_args()

    _assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    _png = os.path.join(_assets_dir, "crystalsweep_logo.png")

    if args.make_icon or args.public:
        from pyshortcuts import make_shortcut
        bindir = "Scripts" if os.name == "nt" else "bin"
        script = os.path.join(sys.prefix, bindir, "crystalsweep")
        if sys.platform == "darwin":
            icns = os.path.join(_assets_dir, "crystalsweep_logo.icns")
            if not os.path.isfile(icns):
                icns = _make_icns(_png)
            icon = icns
        elif os.name == "nt":
            ico = os.path.join(_assets_dir, "crystalsweep_logo.ico")
            if not os.path.isfile(ico):
                ico = _make_ico(_png)
            icon = _win_local_icon(ico)
        else:
            icon = _png
        make_shortcut(script, name="CrystalSweep", icon=icon, terminal=False,
                      public=args.public, folder="GSEApps" if args.public else None)
        return

    if args.test:
        import pytest
        sys.exit(pytest.main([]))

    from crystalsweep.ui import start_ui
    start_ui()
