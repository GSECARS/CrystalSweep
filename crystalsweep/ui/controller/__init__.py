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

from importlib.metadata import version

from crystalsweep.ui.controller.main_controller import MainController

__all__ = ["UIApplication"]


UIApplication = MainController(version=version("crystalsweep")).run
