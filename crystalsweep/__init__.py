# SPDX-License-Identifier: MIT

import logging
import sys
from argparse import ArgumentParser
from importlib.metadata import version
from pathlib import Path

from wxutils import AppConfig, WxApplication, add_application_arguments, handle_shortcut_arguments

from crystalsweep.controller import MainController
from crystalsweep.paths import user_app_dir
from crystalsweep.view import MainView

__version__ = version("crystalsweep")
__all__ = ["__version__", "main"]

APP_CONFIG = AppConfig(
    name="CrystalSweep",
    assets=str(Path(__file__).resolve().parent / "assets"),
    description="beamline control and data acquisition software for single-crystal X-ray diffraction experiments",
    application_id="gsecars.crystalsweep",
)


def _configure_logging() -> None:
    log_path = user_app_dir() / "crystalsweep.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    if any(getattr(h, "_crystalsweep", False) for h in root.handlers):
        return
    root.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    fh._crystalsweep = True
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh._crystalsweep = True
    root.addHandler(fh)
    root.addHandler(sh)
    logging.getLogger("epicsapps").setLevel(logging.WARNING)
    logging.getLogger(__name__).info("Logging to %s", log_path)


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

    _configure_logging()
    app = WxApplication(APP_CONFIG, False)
    view = MainView(version=__version__, with_inspect=args.inspect)
    MainController(view=view)
    app.run(view)
