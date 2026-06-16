#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/epics_scan_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# EPICS Channel Access step-scan model: moves a motor PV position by position
# via caput and waits for each move to complete before calling on_point.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
import time
from typing import Callable

from epics import caget, caput

from crystalsweep.model.scan_model import ScanSpec

__all__ = ["EpicsScanModel"]

_log = logging.getLogger(__name__)


class EpicsScanModel:
    """EPICS caput scan: step (points >= 2) or wide slew (points == 1, start != end).

    For wide slews, prepare() applies the exposure-controlled velocity so that
    the caller can safely move-to-start and open the shutter before run() issues
    the slew to *end*.  The original velocity is restored by run() (or abort()).
    """

    def __init__(self) -> None:
        self._abort = False
        self._wide_velo_pv: str | None = None
        self._wide_saved_velocity: float | None = None

    def prepare(self, spec: ScanSpec) -> None:
        if not spec.pv:
            raise ValueError("EpicsScanModel requires a non-empty PV.")
        if spec.points < 1:
            raise ValueError(f"points must be >= 1, got {spec.points}.")
        if spec.exposure <= 0:
            raise ValueError(f"exposure must be > 0, got {spec.exposure}.")

        # Reset any prior wide-slew state.
        self._wide_velo_pv = None
        self._wide_saved_velocity = None

        if spec.points == 1 and spec.start != spec.end:
            self._prepare_wide_slew(spec)

    def run(self, spec: ScanSpec, on_point: Callable[[int, float], None]) -> None:
        self._abort = False

        if spec.points == 1 and spec.start != spec.end:
            self._run_wide_slew(spec, on_point)
            return

        settle = float(spec.controller_params.get("settle_time", 0.05))
        for i, pos in enumerate(spec.positions()):
            if self._abort:
                _log.info("EpicsScanModel aborted at point %d", i)
                break
            caput(spec.pv, pos, wait=True)
            time.sleep(settle)
            on_point(i, pos)
            _log.debug("EpicsScanModel point %d/%d pos=%.4f", i + 1, spec.points, pos)

    def _prepare_wide_slew(self, spec: ScanSpec) -> None:
        pv_base = spec.pv.removesuffix(".VAL")
        velo_pv = f"{pv_base}.VELO"

        sweep = abs(spec.end - spec.start)
        velocity = sweep / spec.exposure if spec.exposure > 0 else 0.0
        if velocity <= 0:
            raise ValueError(f"Wide slew requires a positive velocity (sweep={sweep}, exposure={spec.exposure}).")

        try:
            raw = caget(velo_pv)
            saved = float(raw) if raw is not None else None
        except Exception as exc:
            _log.warning("EpicsScanModel wide: could not read %s: %s", velo_pv, exc)
            saved = None

        _log.info(
            "EpicsScanModel wide prepare: pv=%s start=%.4f end=%.4f exposure=%.4fs velocity=%.4f (saved=%s)",
            spec.pv,
            spec.start,
            spec.end,
            spec.exposure,
            velocity,
            saved,
        )

        caput(velo_pv, velocity, wait=True)
        self._wide_velo_pv = velo_pv
        self._wide_saved_velocity = saved

    def _run_wide_slew(self, spec: ScanSpec, on_point: Callable[[int, float], None]) -> None:
        try:
            if self._abort:
                _log.info("EpicsScanModel wide aborted before slew")
                return
            caput(spec.pv, spec.end, wait=True)
            on_point(0, spec.end)
        finally:
            self._restore_wide_velocity()

    def _restore_wide_velocity(self) -> None:
        if self._wide_velo_pv is not None and self._wide_saved_velocity is not None:
            try:
                caput(self._wide_velo_pv, self._wide_saved_velocity, wait=True)
            except Exception as exc:
                _log.warning("EpicsScanModel wide: failed to restore %s: %s", self._wide_velo_pv, exc)
        self._wide_velo_pv = None
        self._wide_saved_velocity = None

    def abort(self) -> None:
        self._abort = True
        # Restore the velocity if a wide slew was prepared but never finished.
        self._restore_wide_velocity()
