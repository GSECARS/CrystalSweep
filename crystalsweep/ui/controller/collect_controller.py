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

        self._view.collect.bind_collect(self._on_collect)
        self._view.collect.bind_abort(self._on_abort)

    def _on_collect(self) -> None:
        points = self._model.collection.points
        if not points:
            self._view.collect.set_status("No collection points.", wx.Colour(220, 160, 40))
            return

        self._abort_event.clear()
        self._view.collect.set_status_collecting()
        self._thread = threading.Thread(target=self._run, args=(points,), daemon=True)
        self._thread.start()

    def _on_abort(self) -> None:
        self._abort_event.set()
        _log.info("Collection aborted by user")

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

        if self._abort_event.is_set():
            wx.CallAfter(self._view.collect.set_status, "Aborted", wx.Colour(220, 160, 40))
            wx.CallAfter(self._view.collect.set_collecting, False)
        else:
            wx.CallAfter(self._view.collect.set_progress, total, total, 0, 0)
            wx.CallAfter(self._view.collect.set_status, "Done", wx.Colour(99, 179, 237))
            wx.CallAfter(self._view.collect.set_collecting, False)
