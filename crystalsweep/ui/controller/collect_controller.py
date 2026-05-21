#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/collect_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# Controller for the collect section: wires the Collect / Abort buttons and
# drives the collection loop in a background thread.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
import threading
import time as _time

import wx

from crystalsweep.model import MainModel
from crystalsweep.ui.view import MainView

__all__ = ["CollectController"]

_log = logging.getLogger(__name__)


class CollectController:
    """Drives the collect panel: collection loop with per-point and per-frame progress."""

    def __init__(self, model: MainModel, view: MainView) -> None:
        self._model = model
        self._view = view
        self._abort_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_time: float = 0.0
        self._elapsed_timer = wx.Timer()
        self._elapsed_timer.Bind(wx.EVT_TIMER, self._on_elapsed_tick)

        self._view.collect.bind_collect(self._on_collect)
        self._view.collect.bind_abort(self._on_abort)
        self.refresh_eta()

    def _on_collect(self) -> None:
        points = self._model.collection.points
        if not points:
            self._view.collect.set_status("No collection points.", wx.Colour(220, 160, 40))
            return

        self._abort_event.clear()
        self._start_time = _time.monotonic()
        self._view.collect.set_status_collecting()
        self._elapsed_timer.Start(1000)
        self._thread = threading.Thread(target=self._run, args=(points,), daemon=True)
        self._thread.start()

    def refresh_eta(self) -> None:
        """Recompute and display the estimated collection time for selected points only."""
        selected = [p for p in self._model.collection.points if p.selected]
        if not selected:
            self._view.collect.clear_eta()
            return
        self._view.collect.set_eta(self._estimate_total_seconds(selected))

    @staticmethod
    def _estimate_total_seconds(points) -> float:
        total = 0.0
        for point in points:
            try:
                exposure = float(point.time) if point.time else 1.0
            except ValueError:
                exposure = 1.0
            if point.scan_type == "step":
                try:
                    step = float(point.step) if point.step else 1.0
                    start = float(point.rotation_start) if point.rotation_start else 0.0
                    end = float(point.rotation_end) if point.rotation_end else 180.0
                    n_frames = max(1, round(abs(end - start) / step))
                except (ValueError, ZeroDivisionError):
                    n_frames = 1
                total += exposure * n_frames
            else:
                total += exposure
        return total

    def _on_abort(self) -> None:
        self._abort_event.set()
        _log.info("Collection aborted by user")

    def _on_elapsed_tick(self, _event: wx.TimerEvent) -> None:
        elapsed = _time.monotonic() - self._start_time
        self._view.collect.set_elapsed(elapsed)

    def _stop_elapsed_timer(self) -> None:
        self._elapsed_timer.Stop()
        elapsed = _time.monotonic() - self._start_time
        self._view.collect.set_elapsed(elapsed)

    def _run(self, points) -> None:
        total = len(points)

        for idx, point in enumerate(points, start=1):
            if self._abort_event.is_set():
                break

            scan_type = point.scan_type

            if scan_type == "step":
                try:
                    step_size = float(point.step) if point.step else 1.0
                    rot_start = float(point.rotation_start) if point.rotation_start else 0.0
                    rot_end   = float(point.rotation_end)   if point.rotation_end   else 180.0
                    n_frames  = max(1, round(abs(rot_end - rot_start) / step_size))
                except (ValueError, ZeroDivisionError):
                    n_frames = 1
            else:
                n_frames = 1

            for frame in range(1, n_frames + 1):
                if self._abort_event.is_set():
                    break

                wx.CallAfter(
                    self._view.collect.set_progress,
                    idx,
                    total,
                    frame if n_frames > 1 else 0,
                    n_frames if n_frames > 1 else 0,
                )

            _log.debug("Point %d/%d (%s) done", idx, total, point.label)

        wx.CallAfter(self._stop_elapsed_timer)
        if self._abort_event.is_set():
            wx.CallAfter(self._view.collect.set_status, "Aborted", wx.Colour(220, 160, 40))
            wx.CallAfter(self._view.collect.set_collecting, False)
        else:
            wx.CallAfter(self._view.collect.set_progress, total, total, 0, 0)
            wx.CallAfter(self._view.collect.set_status, "Done", wx.Colour(99, 179, 237))
            wx.CallAfter(self._view.collect.set_collecting, False)
