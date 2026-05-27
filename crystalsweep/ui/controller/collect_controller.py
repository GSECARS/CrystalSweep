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
import multiprocessing
import threading
import time as _time
from typing import Callable

import wx
from epics import caget, caput, caput_many

from crystalsweep.model import MainModel
from crystalsweep.model.collection_model import CollectionPoint
from crystalsweep.model.detector_model import get_detector_model
from crystalsweep.model.motor_limits import check_soft_limits, clear_limit_monitors, subscribe_limit_monitors
from crystalsweep.ui.controller.scan_engine import ScanEngine
from crystalsweep.ui.view import MainView
from crystalsweep.ui.view.custom.widgets import DarkAbortingDialog

__all__ = ["CollectController"]

_log = logging.getLogger(__name__)

_PROGRESS_INTERVAL_MS = 100
_TRIGGERING_POLL_S = 0.05


class CollectController:
    """Drives the collect panel: sequential collection loop with per-point hardware scans."""

    def __init__(self, model: MainModel, view: MainView) -> None:
        self._model = model
        self._view = view
        self._engine = ScanEngine(script_model=model.scripts)
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
        self._completed_weight: int = 0
        self._point_weight: int = 1
        self._total_weight: int = 1

        self._restore_pv_snapshot: dict[str, object] = {}
        self._monitored_limit_pvs: list[str] = []
        self._aborting_dlg: DarkAbortingDialog | None = None

        self._view.collect.bind_collect(self._on_collect)
        self._view.collect.bind_abort(self._on_abort)
        self._view.bind_abort(self._on_abort)
        self.refresh_eta()

    def bind_collecting_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_collecting_changed = callback

    def on_config_applied(self) -> None:
        """Re-subscribe soft-limit monitors for the newly active beamline config."""
        clear_limit_monitors(self._monitored_limit_pvs)
        config = self._model.beamline.active
        pvs = [m.pv for m in config.motors if m.pv.strip()]
        if config.rotation_motor and config.rotation_motor.pv.strip():
            pvs.append(config.rotation_motor.pv)
        self._monitored_limit_pvs = subscribe_limit_monitors(pvs, lambda **_: wx.CallAfter(self.validate_limits))

    def _on_collect(self) -> None:
        focused = self._view.FindFocus()
        if focused is not None:
            focused.Navigate()

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

    def validate_limits(self) -> None:
        """Check all collection points against motor soft limits in a background thread.

        Marks rows with red outlines and disables the Collect button when violations
        are found.  Clears all markers and re-enables the button when everything is OK.
        """
        if not self._model.beamline.has_active:
            return

        all_points = self._model.collection.points
        config = self._model.beamline.active

        def _worker() -> None:
            rotation_cfg = config.rotation_motor
            violations: set[int] = set()
            field_errors: dict[int, tuple[dict[str, bool], bool, bool]] = {}

            for idx, point in enumerate(all_points):
                if not point.selected:
                    continue

                motor_errors: dict[str, bool] = {}
                for motor_cfg in config.motors:
                    raw = point.motor_positions.get(motor_cfg.shorthand)
                    if raw is None:
                        continue
                    try:
                        pos = float(raw)
                    except (ValueError, TypeError):
                        continue
                    motor_errors[motor_cfg.shorthand] = bool(check_soft_limits(motor_cfg.pv, pos))

                rot_start_error = False
                rot_end_error = False
                if rotation_cfg is not None:
                    if point.rotation_start:
                        try:
                            pos = float(point.rotation_start)
                            rot_start_error = bool(check_soft_limits(rotation_cfg.pv, pos))
                        except (ValueError, TypeError):
                            pass
                    if point.rotation_end:
                        try:
                            pos = float(point.rotation_end)
                            rot_end_error = bool(check_soft_limits(rotation_cfg.pv, pos))
                        except (ValueError, TypeError):
                            pass

                if any(motor_errors.values()) or rot_start_error or rot_end_error:
                    violations.add(idx)
                field_errors[idx] = (motor_errors, rot_start_error, rot_end_error)

            wx.CallAfter(self._apply_limit_errors, violations, field_errors, len(all_points))

        threading.Thread(target=_worker, daemon=True, name="limit-check").start()

    def _apply_limit_errors(self, violations: set[int], field_errors: dict, total: int) -> None:
        for idx in range(total):
            in_violation = idx in violations
            self._view.collection_table.set_row_limit_error(idx, in_violation)
            motor_errors, rot_start_error, rot_end_error = field_errors.get(idx, ({}, False, False))
            self._view.collection_table.set_row_field_limit_errors(idx, motor_errors, rot_start_error, rot_end_error)
        self._view.collect.set_collect_enabled(not violations)

    @staticmethod
    def _point_frame_weight(point: CollectionPoint) -> int:
        """Return the number of frames for a point (1 for still/wide, n_frames for step)."""
        if point.scan_type == "step":
            try:
                step = float(point.step) if point.step else 1.0
                start = float(point.rotation_start) if point.rotation_start else 0.0
                end = float(point.rotation_end) if point.rotation_end else 0.0
                return max(1, round(abs(end - start) / step)) if step > 0 else 1
            except (ValueError, ZeroDivisionError):
                return 1
        return 1

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

    def _show_aborting_dialog(self, elapsed_str: str) -> None:
        if self._aborting_dlg is not None:
            return
        self._aborting_dlg = DarkAbortingDialog(self._view, elapsed=elapsed_str)
        self._aborting_dlg.Show()
        self._aborting_dlg.Raise()
        self._aborting_dlg.SetFocus()

    def _ready_aborting_dialog(self) -> None:
        if self._aborting_dlg is not None:
            self._aborting_dlg.ready()
        self._aborting_dlg = None

    def _on_file_number_updated(self, file_number: int) -> None:
        self._model.file_settings.frame_number = file_number
        wx.CallAfter(self._view.file_settings.set_frame_number, file_number)

    def _on_abort(self) -> None:
        if not self._abort_event.is_set():
            self._abort_event.set()
            self._engine.abort()
            wx.CallAfter(self._view.collect.set_status, "Aborting...", wx.Colour(220, 160, 40))
            elapsed = _time.monotonic() - self._start_time
            h, rem = divmod(int(elapsed), 3600)
            m, s = divmod(rem, 60)
            elapsed_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
            wx.CallAfter(self._show_aborting_dialog, elapsed_str)

        config = self._model.beamline.active
        det = config.active_detector_config
        if det is not None and det.pv_prefix.strip():
            def _abort_detector() -> None:
                try:
                    get_detector_model(det.type, det.pv_prefix, det.file_format).abort()
                except Exception as exc:
                    _log.warning("Failed to abort detector: %s", exc)
            threading.Thread(target=_abort_detector, daemon=True, name="abort-detector").start()

        abort_pvs = config.abort_pvs
        if abort_pvs:
            pvs = [pv for pv, _ in abort_pvs]
            values = [value for _, value in abort_pvs]
            try:
                caput_many(pvs, values)
            except Exception as exc:
                _log.warning("Failed to write abort PVs: %s", exc)

        if self._restore_pv_snapshot:
            snapshot = self._restore_pv_snapshot
            try:
                caput_many(list(snapshot.keys()), list(snapshot.values()))
                _log.info("Restored %d PV(s) on abort", len(snapshot))
            except Exception as exc:
                _log.warning("Failed to restore PVs on abort: %s", exc)

        _log.info("Collection aborted by user")

    def _on_elapsed_tick(self, _event: wx.TimerEvent) -> None:
        elapsed = _time.monotonic() - self._start_time
        self._view.collect.set_elapsed(elapsed)

    def _on_point_tick(self, _event: wx.TimerEvent) -> None:
        elapsed = _time.monotonic() - self._point_timer_start
        inner = min(1.0, elapsed / self._point_timer_duration) if self._point_timer_duration > 0 else 1.0
        weighted = (self._completed_weight + inner * self._point_weight) / self._total_weight
        self._view.collect.set_progress(
            self._point_timer_idx,
            self._point_timer_total,
            point_fraction=weighted,
        )

    def _start_point_timer(self, idx: int, total: int, duration: float, completed_weight: int = 0, point_weight: int = 1, total_weight: int = 1) -> None:
        self._point_timer_start = _time.monotonic()
        self._point_timer_duration = max(duration, 0.1)
        self._point_timer_idx = idx
        self._point_timer_total = total
        self._completed_weight = completed_weight
        self._point_weight = point_weight
        self._total_weight = max(1, total_weight)
        self._point_timer.Start(_PROGRESS_INTERVAL_MS)

    def _stop_point_timer(self, idx: int, total: int) -> None:
        self._point_timer.Stop()
        weighted = (self._completed_weight + self._point_weight) / self._total_weight
        self._view.collect.set_progress(idx, total, point_fraction=weighted)

    def _stop_elapsed_timer(self) -> None:
        self._elapsed_timer.Stop()
        elapsed = _time.monotonic() - self._start_time
        self._view.collect.set_elapsed(elapsed)

    def _run(self, points: list[CollectionPoint]) -> None:
        total = len(points)
        config = self._model.beamline.active
        file_settings = self._model.file_settings
        all_points = self._model.collection.points
        pre_scan_error: str | None = None

        self._restore_pv_snapshot = {}
        for pv in config.restore_pvs:
            if not pv:
                continue
            try:
                val = caget(pv)
                if val is not None:
                    self._restore_pv_snapshot[pv] = val
            except Exception as exc:
                _log.warning("Failed to read restore PV %s: %s", pv, exc)
        if self._restore_pv_snapshot:
            _log.info("Snapshotted %d restore PV(s) at collection start", len(self._restore_pv_snapshot))

        rotation_cfg = config.rotation_motor
        original_rotation: float | None = None
        original_velocity: float | None = None
        if rotation_cfg is not None:
            try:
                raw = caget(rotation_cfg.pv)
                original_rotation = float(raw) if raw is not None else None
            except Exception:
                original_rotation = None
            try:
                pv_base = rotation_cfg.pv.removesuffix(".VAL")
                raw_vel = caget(f"{pv_base}.VELO")
                original_velocity = float(raw_vel) if raw_vel is not None else None
            except Exception:
                original_velocity = None

        original_motor_positions: dict[str, float] = {}
        for motor_cfg in config.motors:
            try:
                raw = caget(motor_cfg.pv)
                if raw is not None:
                    original_motor_positions[motor_cfg.shorthand] = float(raw)
            except Exception:
                pass

        frame_weights = [self._point_frame_weight(p) for p in points]
        total_weight = max(1, sum(frame_weights))
        completed_weight = 0

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
                group_weights = [frame_weights[gi] for gi in group_indices]
                error = self._engine.pre_scan(point, config)
                if error is not None:
                    _log.warning("Pre-scan failed for map group %s: %s", group_id, error)
                    pre_scan_error = error
                    self._abort_event.set()
                    break
                self._run_map_group(group_points, idx + 1, total, config, file_settings, all_points, completed_weight, group_weights, total_weight)
                completed_weight += sum(group_weights)
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
                _log.warning("Pre-scan failed for %s: %s", point.label, error)
                pre_scan_error = error
                self._abort_event.set()
                break

            if self._abort_event.is_set():
                break

            wx.CallAfter(
                self._view.collect.set_status,
                f"[{idx}/{total}] {point.label} — {point.scan_type}…",
                wx.Colour(99, 179, 237),
            )

            if rotation_cfg is not None and original_velocity is not None:
                try:
                    pv_base = rotation_cfg.pv.removesuffix(".VAL")
                    caput(f"{pv_base}.VELO", original_velocity, wait=True)
                except Exception as exc:
                    _log.warning("Failed to set rotation velocity before point %s: %s", point.label, exc)

            for motor_cfg in config.motors:
                raw = point.motor_positions.get(motor_cfg.shorthand)
                if raw is None:
                    continue
                try:
                    caput(motor_cfg.pv, float(raw), wait=True)
                except Exception as exc:
                    _log.warning("Failed to move motor %s before point %s: %s", motor_cfg.shorthand, point.label, exc)

            if self._abort_event.is_set():
                break

            point_weight = frame_weights[idx - 1]
            if point.scan_type == "still":
                self._run_still(point, idx, total, config, file_settings, completed_weight, point_weight, total_weight)
            elif point.scan_type == "wide":
                self._run_wide(point, idx, total, config, file_settings, completed_weight, point_weight, total_weight)
            elif point.scan_type == "step":
                self._run_step(point, idx, total, config, file_settings, completed_weight, point_weight, total_weight)
            else:
                _log.info("Scan type %r not yet implemented, skipping point %s", point.scan_type, point.label)
                wx.CallAfter(
                    self._view.collect.set_status,
                    f"[{idx}/{total}] {point.label}: scan type '{point.scan_type}' not yet supported",
                    wx.Colour(220, 160, 40),
                )

            self._engine.post_scan(point, config)
            completed_weight += point_weight

        if rotation_cfg is not None:
            pv_base = rotation_cfg.pv.removesuffix(".VAL")
            if original_velocity is not None:
                try:
                    caput(f"{pv_base}.VELO", original_velocity)
                    _log.debug("Restored rotation motor velocity to %.4f", original_velocity)
                except Exception as exc:
                    _log.warning("Failed to restore rotation motor velocity: %s", exc)
            if original_rotation is not None:
                try:
                    caput(rotation_cfg.pv, original_rotation)
                    _log.debug("Restored rotation motor to %.4f", original_rotation)
                except Exception as exc:
                    _log.warning("Failed to restore rotation motor position: %s", exc)

        for motor_cfg in config.motors:
            original = original_motor_positions.get(motor_cfg.shorthand)
            if original is not None:
                try:
                    caput(motor_cfg.pv, original)
                    _log.debug("Restored motor %s to %.4f", motor_cfg.shorthand, original)
                except Exception as exc:
                    _log.warning("Failed to restore motor %s: %s", motor_cfg.shorthand, exc)

        if self._restore_pv_snapshot and not self._abort_event.is_set():
            snapshot = self._restore_pv_snapshot
            try:
                caput_many(list(snapshot.keys()), list(snapshot.values()))
                _log.info("Restored %d PV(s) at collection end", len(snapshot))
            except Exception as exc:
                _log.warning("Failed to restore PVs at collection end: %s", exc)
        self._restore_pv_snapshot = {}

        if not self._abort_event.is_set() and pre_scan_error is None and self._model.file_settings.use_ext:
            self._on_file_number_updated(self._model.file_settings.frame_number + 1)

        wx.CallAfter(self._stop_elapsed_timer)
        if self._on_collecting_changed is not None:
            wx.CallAfter(self._on_collecting_changed, False)
        wx.CallAfter(self._ready_aborting_dialog)
        if pre_scan_error is not None:
            wx.CallAfter(self._view.collect.set_status, f"Pre-scan error: {pre_scan_error}", wx.Colour(220, 80, 40))
        elif self._abort_event.is_set():
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
        completed_weight: int = 0,
        group_weights: list[int] | None = None,
        total_weight: int = 1,
    ) -> None:
        scan_type = group_points[0].scan_type
        motor1 = group_points[0].map_motor1
        motor2 = group_points[0].map_motor2
        use_trajectory = self._view.collection_table.trajectory_scan
        keep_shutter_open = self._view.collection_table.keep_shutter_open
        if scan_type == "wide" and not self._model.collection_settings.wide_flip:
            keep_shutter_open = False
        original_shutter_mode: int = 1
        weights = group_weights if group_weights is not None else [1] * len(group_points)
        map_completed_weight = completed_weight

        rows: dict[int, list[CollectionPoint]] = {}
        for pt in group_points:
            rows.setdefault(pt.map_row, []).append(pt)
        sorted_rows = [rows[r] for r in sorted(rows.keys())]
        n_rows = len(sorted_rows)

        motor1_cfg = next((m for m in config.motors if m.shorthand == motor1), None) if motor1 else None
        motor2_cfg = next((m for m in config.motors if m.shorthand == motor2), None) if motor2 else None
        map_motor_shorthands = {s for s in (motor1, motor2) if s}
        other_motors = [m for m in config.motors if m.shorthand not in map_motor_shorthands]

        original_motor1: float | None = None
        original_motor2: float | None = None
        if motor1_cfg is not None:
            try:
                raw = caget(motor1_cfg.pv)
                original_motor1 = float(raw) if raw is not None else None
            except Exception:
                pass
        if motor2_cfg is not None:
            try:
                raw = caget(motor2_cfg.pv)
                original_motor2 = float(raw) if raw is not None else None
            except Exception:
                pass

        if keep_shutter_open:
            original_shutter_mode = self._engine._disable_detector_shutter_control(config)

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

            pvs: list[str] = []
            vals: list[float] = []
            if motor2_cfg is not None:
                try:
                    pos2 = float(first_pt.motor_positions.get(motor2, "0") or "0")
                    limit_err = check_soft_limits(motor2_cfg.pv, pos2)
                    if limit_err:
                        wx.CallAfter(wx.MessageBox, f"Soft limit violation — {limit_err}", "Soft Limit Violation", wx.OK | wx.ICON_ERROR)
                        self._abort_event.set()
                        break
                    pvs.append(motor2_cfg.pv)
                    vals.append(pos2)
                except Exception as exc:
                    _log.warning("Failed to prepare motor2 move %s: %s", motor2, exc)
            if self._abort_event.is_set():
                break
            if motor1_cfg is not None:
                try:
                    pos1_row = float(first_pt.motor_positions.get(motor1, "0") or "0")
                    limit_err = check_soft_limits(motor1_cfg.pv, pos1_row)
                    if limit_err:
                        wx.CallAfter(wx.MessageBox, f"Soft limit violation — {limit_err}", "Soft Limit Violation", wx.OK | wx.ICON_ERROR)
                        self._abort_event.set()
                        break
                    pvs.append(motor1_cfg.pv)
                    vals.append(pos1_row)
                except Exception as exc:
                    _log.warning("Failed to prepare motor1 start move %s: %s", motor1, exc)
            if self._abort_event.is_set():
                break
            if pvs:
                try:
                    caput_many(pvs, vals, wait=True)
                except Exception as exc:
                    _log.warning("Failed to move map motors to row start: %s", exc)

            if self._abort_event.is_set():
                break

            if scan_type == "still" and use_trajectory:
                self._run_map_row_trajectory(row_points, row_num, n_rows, start_idx, total, motor1, config, file_settings, all_points, keep_shutter_open=keep_shutter_open)
            else:
                for col_pt in row_points:
                    if self._abort_event.is_set():
                        break
                    col_model_index = all_points.index(col_pt) if col_pt in all_points else -1
                    wx.CallAfter(self._view.collection_table.set_active_row, col_model_index)

                    if motor1_cfg is not None:
                        try:
                            pos1 = float(col_pt.motor_positions.get(motor1, "0") or "0")
                            limit_err = check_soft_limits(motor1_cfg.pv, pos1)
                            if limit_err:
                                wx.CallAfter(wx.MessageBox, f"Soft limit violation — {limit_err}", "Soft Limit Violation", wx.OK | wx.ICON_ERROR)
                                self._abort_event.set()
                                break
                            caput(motor1_cfg.pv, pos1, wait=True)
                        except Exception as exc:
                            _log.warning("Failed to move map motor1 %s: %s", motor1, exc)

                    for motor_cfg in other_motors:
                        raw = col_pt.motor_positions.get(motor_cfg.shorthand)
                        if raw is None:
                            continue
                        try:
                            caput(motor_cfg.pv, float(raw), wait=True)
                        except Exception as exc:
                            _log.warning("Failed to move non-map motor %s: %s", motor_cfg.shorthand, exc)

                    if self._abort_event.is_set():
                        break

                    wx.CallAfter(
                        self._view.collect.set_status,
                        f"[map] {col_pt.label} — {col_pt.scan_type}…",
                        wx.Colour(99, 179, 237),
                    )

                    gidx = group_points.index(col_pt)
                    pt_idx = start_idx + gidx
                    pt_weight = weights[gidx]
                    if scan_type == "still":
                        self._run_still(col_pt, pt_idx, total, config, file_settings, map_completed_weight, pt_weight, total_weight)
                    elif scan_type == "wide":
                        self._run_wide(col_pt, pt_idx, total, config, file_settings, map_completed_weight, pt_weight, total_weight, keep_shutter_open=keep_shutter_open)
                    elif scan_type == "step":
                        self._run_step(col_pt, pt_idx, total, config, file_settings, map_completed_weight, pt_weight, total_weight)
                    map_completed_weight += pt_weight

        if keep_shutter_open:
            self._engine._close_shutter(config)
            self._engine._restore_detector_shutter_control(config, original_shutter_mode)

        if original_motor1 is not None and motor1_cfg is not None:
            try:
                caput(motor1_cfg.pv, original_motor1, wait=True)
                _log.debug("Restored map motor1 %s to %.4f", motor1, original_motor1)
            except Exception as exc:
                _log.warning("Failed to restore map motor1 %s: %s", motor1, exc)
        if original_motor2 is not None and motor2_cfg is not None:
            try:
                caput(motor2_cfg.pv, original_motor2, wait=True)
                _log.debug("Restored map motor2 %s to %.4f", motor2, original_motor2)
            except Exception as exc:
                _log.warning("Failed to restore map motor2 %s: %s", motor2, exc)

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
        keep_shutter_open: bool = False,
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
                keep_shutter_open=keep_shutter_open,
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

    def _handle_scan_error(self, exc: Exception, label: str) -> None:
        msg = str(exc)
        if "Soft limit violation" in msg:
            wx.MessageBox(msg, "Soft Limit Violation", wx.OK | wx.ICON_ERROR)

    def _spawn_crysalis_conversion(self, point: CollectionPoint, frame_number: int | None = None) -> None:
        if point.scan_type != "step":
            return
        fs = self._model.file_settings
        if not fs.use_crysalis:
            return
        if fs.crysalis_calibration is None:
            return

        config = self._model.beamline.active
        det = config.active_detector_config
        file_format = det.file_format if det else "hdf5"

        label = point.label.strip() if fs.use_ext else ""
        base = fs.filename or ""
        parts = [p for p in [base, label] if p]
        basename = "_".join(parts) if parts else base

        filenumber = frame_number if frame_number is not None else fs.frame_number

        try:
            omega_start = float(point.rotation_start) if point.rotation_start else 0.0
        except ValueError:
            omega_start = 0.0
        try:
            omega_end = float(point.rotation_end) if point.rotation_end else omega_start
        except ValueError:
            omega_end = omega_start
        try:
            step = float(point.step) if point.step else abs(omega_end - omega_start)
        except ValueError:
            step = abs(omega_end - omega_start) or 1.0
        try:
            count = max(1, round(abs(omega_end - omega_start) / step)) if step > 0 else 1
        except ZeroDivisionError:
            count = 1

        try:
            exposure_time = float(point.time) if point.time else 1.0
        except ValueError:
            exposure_time = 1.0

        scan_info = {
            "omega_start": omega_start,
            "omega_end": omega_end,
            "domega": step,
            "count": count,
            "kappa": 0.0,
            "theta": 0.0,
            "phi": 0.0,
            "alpha": 50.0,
            "dist": 200.0,
            "center_x": 0.0,
            "center_y": 0.0,
            "mono": 0.99,
            "wavelength": 0.2952,
            "dtheta": 0.0,
            "dkappa": 0.0,
            "dphi": 0.0,
            "Exposure_time": exposure_time,
            "pixel_size": 0.075,
            "l1": 0.2952,
            "l2": 0.2952,
            "l12": 0.2952,
            "b": 0.2952,
            "monotype": "SYNCHROTRON",
        }

        args = {
            "filepath": str(fs.directory),
            "basename": basename,
            "filenumber": filenumber,
            "par_file": str(fs.crysalis_calibration),
            "scan_info": scan_info,
            "file_format": file_format,
        }

        try:
            from crystalsweep.model.crysalis_converter import run_conversion
            p = multiprocessing.Process(target=run_conversion, args=(args,), daemon=True)
            p.start()
        except Exception as exc:
            _log.warning("Failed to spawn crysalis conversion: %s", exc)

    def _run_still(self, point: CollectionPoint, idx: int, total: int, config, file_settings=None, completed_weight: int = 0, point_weight: int = 1, total_weight: int = 1) -> None:
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

        def on_status(phase: str) -> None:
            wx.CallAfter(self._view.collect.set_status, f"[{idx}/{total}] {point.label} — {phase}", wx.Colour(99, 179, 237))

        try:
            self._engine.run_still(point, config, on_done=on_done, on_error=on_error, file_settings=file_settings, on_file_number_updated=self._on_file_number_updated, on_status=on_status)
        except RuntimeError as exc:
            wx.CallAfter(self._view.collect.set_status, str(exc), wx.Colour(220, 80, 40))
            return

        det = config.active_detector_config
        if det is not None and det.type == "eiger":
            self._wait_for_eiger_triggering(det.pv_prefix)

        wx.CallAfter(self._start_point_timer, idx, total, exposure, completed_weight, point_weight, total_weight)
        done_event.wait()
        if self._engine._thread is not None:
            self._engine._thread.join()
        wx.CallAfter(self._stop_point_timer, idx, total)

        if error_holder:
            wx.CallAfter(self._handle_scan_error, error_holder[0], point.label)
            wx.CallAfter(
                self._view.collect.set_status,
                f"[{idx}/{total}] {point.label}: {error_holder[0]}",
                wx.Colour(220, 80, 40),
            )
            self._abort_event.set()
        else:
            self._spawn_crysalis_conversion(point)

    def _run_step(self, point: CollectionPoint, idx: int, total: int, config, file_settings=None, completed_weight: int = 0, point_weight: int = 1, total_weight: int = 1) -> None:
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

        def on_status(phase: str) -> None:
            wx.CallAfter(self._view.collect.set_status, f"[{idx}/{total}] {point.label} — {phase}", wx.Colour(99, 179, 237))

        def on_frame(frame: int, total_frames: int) -> None:
            frame_holder[0] = (frame, total_frames)
            inner = frame / total_frames if total_frames > 0 else 0.0
            weighted = (completed_weight + inner * point_weight) / total_weight
            wx.CallAfter(
                self._view.collect.set_progress,
                idx, total,
                frame, total_frames,
                weighted,
            )

        def on_done() -> None:
            print(f"[collect] [{idx}/{total}] {point.label}: step scan complete ({n_frames} frames)")
            done_event.set()

        def on_error(exc: Exception) -> None:
            error_holder.append(exc)
            print(f"[collect] [{idx}/{total}] {point.label}: ERROR — {exc}")
            done_event.set()

        use_slew = self._view.collection_table.slew_scan

        frame_number_before = self._model.file_settings.frame_number

        try:
            self._engine.run_step(point, config, on_frame=on_frame, on_done=on_done, on_error=on_error, slew=use_slew, file_settings=file_settings, on_file_number_updated=self._on_file_number_updated, on_status=on_status)
        except RuntimeError as exc:
            wx.CallAfter(self._view.collect.set_status, str(exc), wx.Colour(220, 80, 40))
            return

        wx.CallAfter(self._view.collect.set_progress, idx, total, 0, n_frames, completed_weight / total_weight)
        done_event.wait()
        if self._engine._thread is not None:
            self._engine._thread.join()
        wx.CallAfter(self._view.collect.set_progress, idx, total, n_frames, n_frames, (completed_weight + point_weight) / total_weight)

        if error_holder:
            wx.CallAfter(self._handle_scan_error, error_holder[0], point.label)
            wx.CallAfter(
                self._view.collect.set_status,
                f"[{idx}/{total}] {point.label}: {error_holder[0]}",
                wx.Colour(220, 80, 40),
            )
            self._abort_event.set()
        else:
            self._spawn_crysalis_conversion(point, frame_number_before)

    def _run_wide(self, point: CollectionPoint, idx: int, total: int, config, file_settings=None, completed_weight: int = 0, point_weight: int = 1, total_weight: int = 1, keep_shutter_open: bool = False) -> None:
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

        def on_status(phase: str) -> None:
            wx.CallAfter(self._view.collect.set_status, f"[{idx}/{total}] {point.label} — {phase}", wx.Colour(99, 179, 237))

        try:
            self._engine.run_wide(point, config, on_done=on_done, on_error=on_error, file_settings=file_settings, on_file_number_updated=self._on_file_number_updated, on_status=on_status, keep_shutter_open=keep_shutter_open)
        except RuntimeError as exc:
            wx.CallAfter(self._view.collect.set_status, str(exc), wx.Colour(220, 80, 40))
            return

        det = config.active_detector_config
        if det is not None and det.type == "eiger":
            self._wait_for_eiger_triggering(det.pv_prefix)

        wx.CallAfter(self._start_point_timer, idx, total, exposure, completed_weight, point_weight, total_weight)
        done_event.wait()
        if self._engine._thread is not None:
            self._engine._thread.join()
        wx.CallAfter(self._stop_point_timer, idx, total)

        if error_holder:
            wx.CallAfter(self._handle_scan_error, error_holder[0], point.label)
            wx.CallAfter(
                self._view.collect.set_status,
                f"[{idx}/{total}] {point.label}: {error_holder[0]}",
                wx.Colour(220, 80, 40),
            )
            self._abort_event.set()

        else:
            self._spawn_crysalis_conversion(point)
