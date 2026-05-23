#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/collect_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# Controller for the collect section: wires the Collect / Abort buttons and
# drives the collection loop using ScanEngine for still scans on the rotation motor.
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
from crystalsweep.model.collection_model import CollectionPoint
from crystalsweep.ui.controller.scan_engine import ScanEngine
from crystalsweep.ui.view import MainView

__all__ = ["CollectController"]

_log = logging.getLogger(__name__)

_PROGRESS_INTERVAL_MS = 100


class CollectController:
    """Drives the collect panel: sequential collection loop with per-point hardware scans."""

    def __init__(self, model: MainModel, view: MainView) -> None:
        self._model = model
        self._view = view
        self._engine = ScanEngine()
        self._abort_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_time: float = 0.0
        self._elapsed_timer = wx.Timer()
        self._elapsed_timer.Bind(wx.EVT_TIMER, self._on_elapsed_tick)

        self._point_timer = wx.Timer()
        self._point_timer.Bind(wx.EVT_TIMER, self._on_point_tick)
        self._point_timer_start: float = 0.0
        self._point_timer_duration: float = 1.0
        self._point_timer_idx: int = 1
        self._point_timer_total: int = 1

        self._view.collect.bind_collect(self._on_collect)
        self._view.collect.bind_abort(self._on_abort)
        self.refresh_eta()

    def _on_collect(self) -> None:
        if self._view.collect.test_mode:
            points = self._model.collection.points
        else:
            points = [p for p in self._model.collection.points if p.selected]

        if not points:
            self._view.collect.set_status("No points selected.", wx.Colour(220, 160, 40))
            return

        if not self._model.beamline.has_active:
            self._view.collect.set_status("No active beamline config.", wx.Colour(220, 80, 40))
            return

        self._abort_event.clear()
        self._start_time = _time.monotonic()
        self._view.collect.set_status_collecting()
        self._elapsed_timer.Start(1000)
        self._thread = threading.Thread(target=self._run, args=(points,), daemon=True, name="collect-loop")
        self._thread.start()

    def refresh_eta(self) -> None:
        """Recompute and display the estimated collection time for selected points only."""
        selected = [p for p in self._model.collection.points if p.selected]
        if not selected:
            self._view.collect.clear_eta()
            return
        self._view.collect.set_eta(self._estimate_total_seconds(selected))

    @staticmethod
    def _estimate_total_seconds(points: list[CollectionPoint]) -> float:
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

    def _on_file_number_updated(self, file_number: int) -> None:
        self._model.file_settings.frame_number = file_number
        wx.CallAfter(self._view.file_settings.set_frame_number, file_number)

    def _on_abort(self) -> None:
        self._abort_event.set()
        self._engine.abort()
        _log.info("Collection aborted by user")

    def _on_elapsed_tick(self, _event: wx.TimerEvent) -> None:
        elapsed = _time.monotonic() - self._start_time
        self._view.collect.set_elapsed(elapsed)

    def _on_point_tick(self, _event: wx.TimerEvent) -> None:
        elapsed = _time.monotonic() - self._point_timer_start
        fraction = min(1.0, elapsed / self._point_timer_duration) if self._point_timer_duration > 0 else 1.0
        self._view.collect.set_progress(
            self._point_timer_idx,
            self._point_timer_total,
            point_fraction=fraction,
        )

    def _start_point_timer(self, idx: int, total: int, duration: float) -> None:
        self._point_timer_start = _time.monotonic()
        self._point_timer_duration = max(duration, 0.1)
        self._point_timer_idx = idx
        self._point_timer_total = total
        self._point_timer.Start(_PROGRESS_INTERVAL_MS)

    def _stop_point_timer(self, idx: int, total: int) -> None:
        self._point_timer.Stop()
        self._view.collect.set_progress(idx, total, point_fraction=1.0)

    def _stop_elapsed_timer(self) -> None:
        self._elapsed_timer.Stop()
        elapsed = _time.monotonic() - self._start_time
        self._view.collect.set_elapsed(elapsed)

    def _run(self, points: list[CollectionPoint]) -> None:
        total = len(points)
        config = self._model.beamline.active
        file_settings = self._model.file_settings

        for idx, point in enumerate(points, start=1):
            if self._abort_event.is_set():
                break

            wx.CallAfter(
                self._view.collect.set_status,
                f"[{idx}/{total}] {point.label} — pre-scan…",
                wx.Colour(99, 179, 237),
            )

            error = self._engine.pre_scan(point, config)
            if error is not None:
                _log.warning("Pre-scan check failed for %s: %s", point.label, error)
                wx.CallAfter(
                    self._view.collect.set_status,
                    f"[{idx}/{total}] {point.label} skipped: {error}",
                    wx.Colour(220, 160, 40),
                )
                continue

            if self._abort_event.is_set():
                break

            wx.CallAfter(
                self._view.collect.set_status,
                f"[{idx}/{total}] {point.label} — {point.scan_type}…",
                wx.Colour(99, 179, 237),
            )

            if point.scan_type == "still":
                self._run_still(point, idx, total, config, file_settings)
            elif point.scan_type == "wide":
                self._run_wide(point, idx, total, config, file_settings)
            elif point.scan_type == "step":
                self._run_step(point, idx, total, config, file_settings)
            else:
                _log.info("Scan type %r not yet implemented, skipping point %s", point.scan_type, point.label)
                wx.CallAfter(
                    self._view.collect.set_status,
                    f"[{idx}/{total}] {point.label}: scan type '{point.scan_type}' not yet supported",
                    wx.Colour(220, 160, 40),
                )
                continue

        wx.CallAfter(self._stop_elapsed_timer)
        if self._abort_event.is_set():
            wx.CallAfter(self._view.collect.set_status, "Aborted", wx.Colour(220, 160, 40))
            wx.CallAfter(self._view.collect.set_collecting, False)
        else:
            wx.CallAfter(self._view.collect.set_progress, total, total, point_fraction=1.0)
            wx.CallAfter(self._view.collect.set_status, "Done", wx.Colour(99, 179, 237))
            wx.CallAfter(self._view.collect.set_collecting, False)

    def _run_still(self, point: CollectionPoint, idx: int, total: int, config, file_settings=None) -> None:
        done_event = threading.Event()
        error_holder: list[Exception] = []

        try:
            exposure = float(point.time) if point.time else 1.0
        except ValueError:
            exposure = 1.0

        def on_done() -> None:
            print(f"[collect] [{idx}/{total}] {point.label}: still scan complete")
            done_event.set()

        def on_error(exc: Exception) -> None:
            error_holder.append(exc)
            print(f"[collect] [{idx}/{total}] {point.label}: ERROR — {exc}")
            done_event.set()

        try:
            self._engine.run_still(point, config, on_done=on_done, on_error=on_error, file_settings=file_settings, on_file_number_updated=self._on_file_number_updated)
        except RuntimeError as exc:
            wx.CallAfter(self._view.collect.set_status, str(exc), wx.Colour(220, 80, 40))
            return

        wx.CallAfter(self._start_point_timer, idx, total, exposure)
        done_event.wait()
        if self._engine._thread is not None:
            self._engine._thread.join()
        wx.CallAfter(self._stop_point_timer, idx, total)

        if error_holder:
            wx.CallAfter(
                self._view.collect.set_status,
                f"[{idx}/{total}] {point.label}: {error_holder[0]}",
                wx.Colour(220, 80, 40),
            )
            self._abort_event.set()

    def _run_step(self, point: CollectionPoint, idx: int, total: int, config, file_settings=None) -> None:
        done_event = threading.Event()
        error_holder: list[Exception] = []

        try:
            exposure = float(point.time) if point.time else 1.0
            step_size = float(point.step) if point.step else 1.0
            omega_start = float(point.rotation_start) if point.rotation_start else 0.0
            omega_end = float(point.rotation_end) if point.rotation_end else 0.0
        except ValueError:
            exposure = 1.0
            step_size = 1.0
            omega_start = 0.0
            omega_end = 0.0

        n_frames = max(1, round(abs(omega_end - omega_start) / step_size)) if step_size > 0 else 1
        total_duration = exposure * n_frames

        frame_holder: list[tuple[int, int]] = [(0, n_frames)]

        def on_frame(frame: int, total_frames: int) -> None:
            frame_holder[0] = (frame, total_frames)
            wx.CallAfter(
                self._view.collect.set_progress,
                idx, total,
                frame, total_frames,
            )

        def on_done() -> None:
            print(f"[collect] [{idx}/{total}] {point.label}: step scan complete ({n_frames} frames)")
            done_event.set()

        def on_error(exc: Exception) -> None:
            error_holder.append(exc)
            print(f"[collect] [{idx}/{total}] {point.label}: ERROR — {exc}")
            done_event.set()

        use_slew = self._view.collection_table.slew_scan

        try:
            self._engine.run_step(point, config, on_frame=on_frame, on_done=on_done, on_error=on_error, slew=use_slew, file_settings=file_settings, on_file_number_updated=self._on_file_number_updated)
        except RuntimeError as exc:
            wx.CallAfter(self._view.collect.set_status, str(exc), wx.Colour(220, 80, 40))
            return

        wx.CallAfter(self._view.collect.set_progress, idx, total, 0, n_frames)
        done_event.wait()
        if self._engine._thread is not None:
            self._engine._thread.join()
        wx.CallAfter(self._view.collect.set_progress, idx, total, n_frames, n_frames)

        if error_holder:
            wx.CallAfter(
                self._view.collect.set_status,
                f"[{idx}/{total}] {point.label}: {error_holder[0]}",
                wx.Colour(220, 80, 40),
            )
            self._abort_event.set()

    def _run_wide(self, point: CollectionPoint, idx: int, total: int, config, file_settings=None) -> None:
        done_event = threading.Event()
        error_holder: list[Exception] = []

        try:
            exposure = float(point.time) if point.time else 1.0
        except ValueError:
            exposure = 1.0

        def on_done() -> None:
            print(f"[collect] [{idx}/{total}] {point.label}: wide scan complete")
            done_event.set()

        def on_error(exc: Exception) -> None:
            error_holder.append(exc)
            print(f"[collect] [{idx}/{total}] {point.label}: ERROR — {exc}")
            done_event.set()

        try:
            self._engine.run_wide(point, config, on_done=on_done, on_error=on_error, file_settings=file_settings, on_file_number_updated=self._on_file_number_updated)
        except RuntimeError as exc:
            wx.CallAfter(self._view.collect.set_status, str(exc), wx.Colour(220, 80, 40))
            return

        wx.CallAfter(self._start_point_timer, idx, total, exposure)
        done_event.wait()
        if self._engine._thread is not None:
            self._engine._thread.join()
        wx.CallAfter(self._stop_point_timer, idx, total)

        if error_holder:
            wx.CallAfter(
                self._view.collect.set_status,
                f"[{idx}/{total}] {point.label}: {error_holder[0]}",
                wx.Colour(220, 80, 40),
            )
            self._abort_event.set()
