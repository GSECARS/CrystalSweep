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
from typing import Callable

import wx
from epics import caget, caput

from crystalsweep.model import MainModel
from crystalsweep.model.collection_model import CollectionPoint
from crystalsweep.ui.controller.scan_engine import ScanEngine
from crystalsweep.ui.view import MainView

__all__ = ["CollectController"]

_log = logging.getLogger(__name__)

_PROGRESS_INTERVAL_MS = 100
_TRIGGERING_POLL_S = 0.05


class CollectController:
    """Drives the collect panel: sequential collection loop with per-point hardware scans."""

    def __init__(self, model: MainModel, view: MainView) -> None:
        self._model = model
        self._view = view
        self._engine = ScanEngine()
        self._abort_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_time: float = 0.0
        self._on_collecting_changed: Callable[[bool], None] | None = None
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
        self._view.bind_abort(self._on_abort)
        self.refresh_eta()

    def bind_collecting_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_collecting_changed = callback

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
        if self._on_collecting_changed is not None:
            self._on_collecting_changed(True)
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
        all_points = self._model.collection.points

        rotation_cfg = config.rotation_motor
        original_rotation: float | None = None
        if rotation_cfg is not None:
            try:
                raw = caget(rotation_cfg.pv)
                original_rotation = float(raw) if raw is not None else None
            except Exception:
                original_rotation = None

        consumed: set[int] = set()
        idx = 0
        while idx < len(points):
            if self._abort_event.is_set():
                break
            if idx in consumed:
                idx += 1
                continue

            point = points[idx]

            if point.map_group:
                group_id = point.map_group
                group_points = [p for p in points if p.map_group == group_id]
                group_indices = [i for i, p in enumerate(points) if p.map_group == group_id]
                for gi in group_indices:
                    consumed.add(gi)
                self._run_map_group(group_points, idx + 1, total, config, file_settings, all_points)
                idx = max(group_indices) + 1
                continue

            idx += 1
            model_index = all_points.index(point) if point in all_points else -1
            wx.CallAfter(self._view.collection_table.set_active_row, model_index)

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

        if original_rotation is not None and rotation_cfg is not None:
            try:
                caput(rotation_cfg.pv, original_rotation, wait=True)
                _log.debug("Restored rotation motor to %.4f", original_rotation)
            except Exception as exc:
                _log.warning("Failed to restore rotation motor position: %s", exc)

        wx.CallAfter(self._stop_elapsed_timer)
        if self._on_collecting_changed is not None:
            wx.CallAfter(self._on_collecting_changed, False)
        if self._abort_event.is_set():
            wx.CallAfter(self._view.collect.set_status, "Aborted", wx.Colour(220, 160, 40))
        else:
            wx.CallAfter(self._view.collect.set_progress, total, total, point_fraction=1.0)
            wx.CallAfter(self._view.collect.set_status, "Done", wx.Colour(99, 179, 237))

    def _run_map_group(
        self,
        group_points: list[CollectionPoint],
        start_idx: int,
        total: int,
        config,
        file_settings,
        all_points: list[CollectionPoint],
    ) -> None:
        scan_type = group_points[0].scan_type
        motor1 = group_points[0].map_motor1
        motor2 = group_points[0].map_motor2
        use_trajectory = self._view.collection_table.trajectory_scan

        rows: dict[int, list[CollectionPoint]] = {}
        for pt in group_points:
            rows.setdefault(pt.map_row, []).append(pt)
        sorted_rows = [rows[r] for r in sorted(rows.keys())]
        n_rows = len(sorted_rows)

        motor2_cfg = None
        if motor2:
            motor2_cfg = next((m for m in config.motors if m.shorthand == motor2), None)

        for row_num, row in enumerate(sorted_rows):
            if self._abort_event.is_set():
                break

            sorted_cols = sorted(row, key=lambda p: p.map_col)
            snake_forward = (row_num % 2 == 0)
            row_points = sorted_cols if snake_forward else list(reversed(sorted_cols))

            first_pt = row_points[0]
            model_index = all_points.index(first_pt) if first_pt in all_points else -1
            wx.CallAfter(self._view.collection_table.set_active_row, model_index)

            wx.CallAfter(
                self._view.collect.set_status,
                f"[map {row_num + 1}/{n_rows}] row {row_num} — moving…",
                wx.Colour(99, 179, 237),
            )

            if motor2_cfg is not None:
                try:
                    pos2 = float(first_pt.motor_positions.get(motor2, "0") or "0")
                    caput(motor2_cfg.pv, pos2, wait=True)
                except Exception as exc:
                    _log.warning("Failed to move map motor2 %s: %s", motor2, exc)

            if self._abort_event.is_set():
                break

            if scan_type == "still" and use_trajectory:
                self._run_map_row_trajectory(row_points, row_num, n_rows, start_idx, total, motor1, config, file_settings, all_points)
            else:
                for col_pt in row_points:
                    if self._abort_event.is_set():
                        break
                    col_model_index = all_points.index(col_pt) if col_pt in all_points else -1
                    wx.CallAfter(self._view.collection_table.set_active_row, col_model_index)

                    if motor1:
                        motor1_cfg = next((m for m in config.motors if m.shorthand == motor1), None)
                        if motor1_cfg is not None:
                            try:
                                pos1 = float(col_pt.motor_positions.get(motor1, "0") or "0")
                                caput(motor1_cfg.pv, pos1, wait=True)
                            except Exception as exc:
                                _log.warning("Failed to move map motor1 %s: %s", motor1, exc)

                    wx.CallAfter(
                        self._view.collect.set_status,
                        f"[map] {col_pt.label} — {col_pt.scan_type}…",
                        wx.Colour(99, 179, 237),
                    )

                    pt_idx = start_idx + group_points.index(col_pt)
                    if scan_type == "still":
                        self._run_still(col_pt, pt_idx, total, config, file_settings)
                    elif scan_type == "wide":
                        self._run_wide(col_pt, pt_idx, total, config, file_settings)
                    elif scan_type == "step":
                        self._run_step(col_pt, pt_idx, total, config, file_settings)

    def _run_map_row_trajectory(
        self,
        row_points: list[CollectionPoint],
        row_num: int,
        n_rows: int,
        start_idx: int,
        total: int,
        motor1: str,
        config,
        file_settings,
        all_points: list[CollectionPoint],
    ) -> None:
        n_points = len(row_points)
        try:
            exposure = float(row_points[0].time) if row_points[0].time else 1.0
        except ValueError:
            exposure = 1.0

        epics_positions = []
        for pt in row_points:
            try:
                epics_positions.append(float(pt.motor_positions.get(motor1, "0") or "0"))
            except ValueError:
                epics_positions.append(0.0)

        done_event = threading.Event()
        error_holder: list[Exception] = []
        frame_holder: list[tuple[int, int]] = [(0, n_points)]

        def on_frame(frame: int, total_frames: int) -> None:
            frame_holder[0] = (frame, total_frames)
            pt_idx = start_idx + (frame - 1)
            wx.CallAfter(self._view.collect.set_progress, pt_idx, total, frame, total_frames)
            if 0 <= frame - 1 < len(row_points):
                model_index = all_points.index(row_points[frame - 1]) if row_points[frame - 1] in all_points else -1
                wx.CallAfter(self._view.collection_table.set_active_row, model_index)

        def on_done() -> None:
            done_event.set()

        def on_error(exc: Exception) -> None:
            error_holder.append(exc)
            done_event.set()

        wx.CallAfter(
            self._view.collect.set_status,
            f"[map {row_num + 1}/{n_rows}] trajectory {n_points} pts…",
            wx.Colour(99, 179, 237),
        )

        try:
            self._engine.run_map_row_trajectory(
                config=config,
                map_motor_shorthand=motor1,
                epics_positions=epics_positions,
                exposure=exposure,
                file_settings=file_settings,
                row_points=row_points,
                on_frame=on_frame,
                on_done=on_done,
                on_error=on_error,
                on_file_number_updated=self._on_file_number_updated,
            )
        except RuntimeError as exc:
            wx.CallAfter(self._view.collect.set_status, str(exc), wx.Colour(220, 80, 40))
            return

        det = config.active_detector_config
        if det is not None and det.type == "eiger":
            self._wait_for_eiger_triggering(det.pv_prefix, done_event)

        if not done_event.is_set():
            wx.CallAfter(self._start_point_timer, start_idx, total, exposure * n_points)
        done_event.wait()
        if self._engine._thread is not None:
            self._engine._thread.join()
        wx.CallAfter(self._stop_point_timer, start_idx + n_points - 1, total)

        if error_holder:
            wx.CallAfter(
                self._view.collect.set_status,
                f"[map row {row_num}]: {error_holder[0]}",
                wx.Colour(220, 80, 40),
            )
            self._abort_event.set()

    def _wait_for_eiger_triggering(self, pv_prefix: str, done_event: threading.Event | None = None) -> None:
        prefix = pv_prefix.strip()
        if not prefix.endswith(":"):
            prefix += ":"
        status_pv = f"{prefix}cam1:StatusMessage_RBV"
        seen_idle = None
        while not self._abort_event.is_set() and (done_event is None or not done_event.is_set()):
            try:
                val = caget(status_pv, as_string=True, timeout=1.0)
                if isinstance(val, str):
                    normalised = val.strip().lower()
                    if seen_idle is None:
                        seen_idle = normalised == "idle"
                    if seen_idle and normalised != "idle":
                        seen_idle = False
                    if not seen_idle and normalised == "triggering":
                        return
            except Exception:
                pass
            _time.sleep(_TRIGGERING_POLL_S)

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

        det = config.active_detector_config
        if det is not None and det.type == "eiger":
            self._wait_for_eiger_triggering(det.pv_prefix)

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

        det = config.active_detector_config
        if det is not None and det.type == "eiger":
            self._wait_for_eiger_triggering(det.pv_prefix)

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
