#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/utils/validators.py
# ----------------------------------------------------------------------------------
# Purpose:
# Validators used across the application.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from pydantic import TypeAdapter

__all__ = ["MotorPositionValidator"]

_float_adapter = TypeAdapter(float)
_int_adapter = TypeAdapter(int)


class MotorPositionValidator:
    """Validates and formats a motor position string as a float with fixed precision."""

    def __init__(self, raw: str, precision: int = 4) -> None:
        self._value: float = _float_adapter.validate_python(raw.strip())
        self._precision: int = max(0, _int_adapter.validate_python(precision))

    @property
    def formatted(self) -> str:
        """Return the value formatted to the configured number of decimal places."""
        return f"{self._value:.{self._precision}f}"
