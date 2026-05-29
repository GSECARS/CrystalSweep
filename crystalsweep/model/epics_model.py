#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/epics_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Provides a reusable Channel Access interface backed by pyepics.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from epicscorelibs.path import get_lib

os.environ.setdefault("PYEPICS_LIBCA", get_lib("ca"))

from epics import caget

__all__ = ["EpicsModel"]

_log = logging.getLogger(__name__)


@dataclass()
class EpicsModel:
    """Reusable Channel Access interface using pyepics."""

    connect_timeout: float = field(default=2.0)

    def caget(self, pv: str) -> Any:
        """Return the current value of a PV, or None if unreachable."""
        return caget(pv, timeout=self.connect_timeout)

    def is_online(self, pv: str) -> bool:
        """Return True if the PV is reachable."""
        return self.caget(pv) is not None
