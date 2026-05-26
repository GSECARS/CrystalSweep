#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/motor_limits.py
# ----------------------------------------------------------------------------------
# Purpose:
# Shared helper for reading EPICS motor soft limits and validating positions.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable

from epics import caget, camonitor, camonitor_clear

__all__ = ["check_soft_limits", "subscribe_limit_monitors", "clear_limit_monitors"]


def check_soft_limits(pv: str, position: float) -> str | None:
    """Return an error string if *position* violates the soft limits of *pv*, else None.

    Reads the .LLM (lower) and .HLM (upper) fields from EPICS.  Returns None when
    the limits cannot be retrieved or when both are 0.0 (no limits configured).
    """
    pv_base = pv.removesuffix(".VAL")
    try:
        llm = caget(f"{pv_base}.LLM")
        hlm = caget(f"{pv_base}.HLM")
    except Exception:
        return None
    if llm is None or hlm is None:
        return None
    try:
        lo = float(llm)
        hi = float(hlm)
    except (TypeError, ValueError):
        return None
    if lo == hi == 0.0:
        return None
    if position < lo:
        return f"{pv_base}: {position:.4g} < lower limit {lo:.4g}"
    if position > hi:
        return f"{pv_base}: {position:.4g} > upper limit {hi:.4g}"
    return None


def subscribe_limit_monitors(pvs: list[str], callback: Callable) -> list[str]:
    """Subscribe *callback* to .LLM and .HLM changes for each PV in *pvs*.

    Returns the list of monitored PV names so the caller can pass them to
    *clear_limit_monitors* later.  Silently skips PVs that fail to connect.
    """
    monitored: list[str] = []
    for pv in pvs:
        pv_base = pv.removesuffix(".VAL")
        for field in (f"{pv_base}.LLM", f"{pv_base}.HLM"):
            try:
                camonitor(field, callback=callback)
                monitored.append(field)
            except Exception:
                pass
    return monitored


def clear_limit_monitors(monitored_pvs: list[str]) -> None:
    """Clear all monitors previously set up by *subscribe_limit_monitors*."""
    for pv in monitored_pvs:
        try:
            camonitor_clear(pv)
        except Exception:
            pass
