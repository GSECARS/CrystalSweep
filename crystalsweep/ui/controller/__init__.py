# SPDX-License-Identifier: MIT

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
