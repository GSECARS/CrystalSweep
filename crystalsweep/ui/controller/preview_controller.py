#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/preview_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# Controller for the Preview tab inside the Single-Crystal Centering Tools
# section.  Manages the centering-motors column: it builds rows from the active
# beamline config, subscribes camonitor() on each motor's readback PV, and
# performs relative caput moves when the user clicks the jog arrows.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
import threading

import wx
from epics import caget, camonitor, camonitor_clear, caput

from crystalsweep.model import MainModel
from crystalsweep.model.beamline_config_model import BeamlineConfig, DetectorConfig, MotorConfig
from crystalsweep.ui.view.preview_view import CenteringMotorSpec, PreviewView

__all__ = ["PreviewController"]

_log = logging.getLogger(__name__)


def _rbv_pv(pv: str) -> str:
    """Return the canonical readback PV name for a motor record .VAL field."""
    base = pv.removesuffix(".VAL")
    return f"{base}.RBV"


def _val_pv(pv: str) -> str:
    """Return the canonical setpoint PV (always with the .VAL field)."""
    base = pv.removesuffix(".VAL")
    return f"{base}.VAL"


def _cam_pv(detector: DetectorConfig, field: str) -> str:
    """Return ``<prefix>cam1:<field>``; appends ``:`` to the prefix when missing."""
    prefix = detector.pv_prefix.strip()
    if not prefix:
        return ""
    if not prefix.endswith(":"):
        prefix += ":"
    return f"{prefix}cam1:{field}"


class PreviewController:
    """Bridges PreviewView with the active beamline config and EPICS."""

    def __init__(self, model: MainModel, view: PreviewView) -> None:
        self._model = model
        self._view = view
        self._monitored_rbvs: list[str] = []
        # Map readback PV -> setpoint PV so the camonitor callback can locate
        # the row to update via view.update_centering_value(pv=setpoint).
        self._rbv_to_setpoint: dict[str, str] = {}

        # Preview state: saved detector PV values keyed by PV name so we can
        # restore them when the preview is stopped (manually or by timeout).
        self._previewing = False
        self._saved_pv_values: dict[str, object] = {}
        self._timeout_timer: threading.Timer | None = None
        # Max-intensity observer state
        self._max_observer_active = False
        self._original_max_intensity: float | None = None
        self._best_max_intensity: float | None = None
        self._best_capture_token: int = 0
        # Auto-optimize state.
        self._auto_optimize_running = False
        self._auto_optimize_cancel = threading.Event()
        self._original_snapshot: dict[str, float] = {}
        self._current_snapshot: dict[str, float] = {}
        self._best_snapshot: dict[str, float] = {}

        self._view.bind_jog_minus(self._on_jog_minus)
        self._view.bind_jog_plus(self._on_jog_plus)
        self._view.bind_start(self._on_start_preview)
        self._view.bind_stop(self._on_stop_preview)
        self._view.bind_auto_optimize(self._on_auto_optimize_clicked)
        self._view.bind_go_original(self._on_go_original)
        self._view.bind_go_current(self._on_go_current)
        self._view.bind_go_best(self._on_go_best)

        self.on_config_applied(self._model.beamline.active)

    def on_config_applied(self, cfg: BeamlineConfig | None) -> None:
        """Rebuild rows + monitors whenever the active beamline config changes."""
        if self._previewing:
            # Stop any in-flight preview before tearing down state.
            self._stop_preview(restore=True)
        self._clear_monitors()
        self._view.set_auto_optimize_enabled(False)
        specs = self._collect_specs(cfg)
        self._view.set_centering_motors(specs)
        if not specs:
            return
        self._subscribe_monitors(specs)
        self._prime_initial_values(specs)

    def shutdown(self) -> None:
        """Best-effort cleanup; safe to call multiple times."""
        if self._previewing:
            self._stop_preview(restore=True)
        if self._max_observer_active:
            try:
                self._model.ad_viewer.remove_max_intensity_observer(self._on_max_intensity_change)
            except Exception:
                pass
            self._max_observer_active = False
        self._clear_monitors()

    @staticmethod
    def _collect_specs(cfg: BeamlineConfig | None) -> list[CenteringMotorSpec]:
        if cfg is None:
            return []
        specs: list[CenteringMotorSpec] = []
        candidates: list[MotorConfig] = []
        if cfg.rotation_motor is not None:
            candidates.append(cfg.rotation_motor)
        candidates.extend(cfg.motors)
        for m in candidates:
            if not m.centering_enabled:
                continue
            if not m.pv.strip():
                continue
            specs.append(
                CenteringMotorSpec(
                    shorthand=m.shorthand,
                    description=m.description,
                    pv=m.pv.strip(),
                    precision=m.precision,
                )
            )
        return specs

    def _subscribe_monitors(self, specs: list[CenteringMotorSpec]) -> None:
        for spec in specs:
            rbv = _rbv_pv(spec.pv)
            self._rbv_to_setpoint[rbv] = spec.pv
            try:
                camonitor(rbv, callback=self._on_rbv_change)
                self._monitored_rbvs.append(rbv)
            except Exception as exc:
                _log.warning("Failed to camonitor %s: %s", rbv, exc)

    def _prime_initial_values(self, specs: list[CenteringMotorSpec]) -> None:
        """Push initial readbacks so rows show a value before the first monitor event."""

        def _worker() -> None:
            for spec in specs:
                value: float | None
                try:
                    raw = caget(_rbv_pv(spec.pv))
                    value = float(raw) if raw is not None else None
                except Exception:
                    value = None
                wx.CallAfter(self._view.update_centering_value, spec.pv, value)

        threading.Thread(target=_worker, daemon=True, name="centering-prime").start()

    def _clear_monitors(self) -> None:
        for pv in self._monitored_rbvs:
            try:
                camonitor_clear(pv)
            except Exception:
                pass
        self._monitored_rbvs.clear()
        self._rbv_to_setpoint.clear()

    def _on_rbv_change(self, pvname: str = "", value=None, **_: object) -> None:
        setpoint = self._rbv_to_setpoint.get(pvname)
        if setpoint is None:
            return
        try:
            numeric: float | None = float(value) if value is not None else None
        except TypeError, ValueError:
            numeric = None
        wx.CallAfter(self._view.update_centering_value, setpoint, numeric)
        # Mirror the value into the Current Positions column when previewing.
        if self._previewing:
            wx.CallAfter(self._view.update_current_position, setpoint, numeric)
            if numeric is not None:
                self._current_snapshot[setpoint] = numeric

    def _on_jog_minus(self, spec: CenteringMotorSpec) -> None:
        self._jog(spec, sign=-1.0)

    def _on_jog_plus(self, spec: CenteringMotorSpec) -> None:
        self._jog(spec, sign=+1.0)

    def _jog(self, spec: CenteringMotorSpec, sign: float) -> None:
        step_mm = self._view.step_mm
        if step_mm <= 0:
            return
        delta = sign * step_mm
        setpoint = _val_pv(spec.pv)
        readback = _rbv_pv(spec.pv)

        def _worker() -> None:
            try:
                current = caget(readback)
                if current is None:
                    current = caget(setpoint)
                if current is None:
                    return
                target = float(current) + delta
                caput(setpoint, target)
            except Exception as exc:
                _log.warning("Jog failed for %s: %s", spec.pv, exc)

        threading.Thread(target=_worker, daemon=True, name=f"jog-{spec.shorthand or spec.pv}").start()

    # ----- Start / stop preview -------------------------------------------------

    def _on_start_preview(self) -> None:
        if self._previewing:
            return
        cfg = self._model.beamline.active
        detector = cfg.active_detector_config if cfg is not None else None
        if detector is None or not detector.pv_prefix.strip():
            _log.warning("No active detector with a PV prefix; cannot start preview.")
            return

        exposure_pv = _cam_pv(detector, "AcquireTime")
        period_pv = _cam_pv(detector, "AcquirePeriod")
        num_pv = _cam_pv(detector, "NumImages")
        image_mode_pv = _cam_pv(detector, "ImageMode")
        acquire_pv = _cam_pv(detector, "Acquire")

        exposure = float(cfg.preview_exposure)
        num_images = int(cfg.preview_num_images)
        timeout = float(cfg.preview_timeout)

        self._previewing = True
        self._view.set_previewing(True)
        self._view.set_auto_optimize_enabled(True)

        specs = list(self._view.centering_specs())
        max_intensity = self._model.ad_viewer.last_roi_max_intensity
        self._original_max_intensity = max_intensity
        self._best_max_intensity = max_intensity
        self._best_capture_token = 0

        # Subscribe to live max-intensity updates while previewing.
        if not self._max_observer_active:
            self._model.ad_viewer.add_max_intensity_observer(self._on_max_intensity_change)
            self._max_observer_active = True

        def _worker() -> None:
            try:
                # Snapshot current values so we can restore them on stop.
                snapshot: dict[str, object] = {}
                for pv in (exposure_pv, period_pv, num_pv, image_mode_pv):
                    try:
                        current = caget(pv)
                    except Exception:
                        current = None
                    if current is not None:
                        snapshot[pv] = current
                self._saved_pv_values = snapshot

                # Capture original motor RBVs for the Original Positions column.
                originals: list[tuple[str, str, float | None, int]] = []
                currents: list[tuple[str, str, float | None, int]] = []
                self._original_snapshot.clear()
                self._current_snapshot.clear()
                self._best_snapshot.clear()
                for spec in specs:
                    label = spec.description or spec.shorthand or spec.pv
                    try:
                        raw = caget(_rbv_pv(spec.pv))
                        value: float | None = float(raw) if raw is not None else None
                    except Exception:
                        value = None
                    originals.append((spec.pv, label, value, spec.precision))
                    currents.append((spec.pv, label, value, spec.precision))
                    if value is not None:
                        self._original_snapshot[spec.pv] = value
                        self._current_snapshot[spec.pv] = value
                        self._best_snapshot[spec.pv] = value
                wx.CallAfter(self._view.set_original_positions, originals, max_intensity)
                wx.CallAfter(self._view.set_current_positions, currents, max_intensity, max_intensity)
                wx.CallAfter(self._view.set_best_positions, list(currents), max_intensity)

                # Apply preview settings (continuous image mode = 2 in areaDetector).
                if exposure_pv:
                    caput(exposure_pv, exposure, wait=True)
                if period_pv:
                    caput(period_pv, exposure, wait=True)
                if num_pv:
                    caput(num_pv, num_images, wait=True)
                if image_mode_pv:
                    caput(image_mode_pv, 2, wait=True)
                if acquire_pv:
                    caput(acquire_pv, 1)
            except Exception as exc:
                _log.warning("Failed to start preview acquisition: %s", exc)
                wx.CallAfter(self._stop_preview, True)
                return

            if timeout > 0:
                self._timeout_timer = threading.Timer(timeout, lambda: wx.CallAfter(self._on_timeout_expired))
                self._timeout_timer.daemon = True
                self._timeout_timer.start()

        threading.Thread(target=_worker, daemon=True, name="preview-start").start()

    def _on_stop_preview(self) -> None:
        if not self._previewing:
            return
        self._stop_preview(restore=True)

    def _on_timeout_expired(self) -> None:
        if not self._previewing:
            return
        _log.info("Preview timeout reached; stopping acquisition.")
        self._stop_preview(restore=True)

    def _stop_preview(self, restore: bool) -> None:
        """Tear down preview: cancel timer, stop acquire, restore saved PVs."""
        if self._timeout_timer is not None:
            try:
                self._timeout_timer.cancel()
            except Exception:
                pass
            self._timeout_timer = None

        self._previewing = False
        self._view.set_previewing(False)
        self._view.clear_original_positions()
        self._view.clear_current_positions()
        self._view.clear_best_positions()
        self._view.set_auto_optimize_enabled(False)

        # Cancel any auto-optimize worker.
        self._auto_optimize_cancel.set()

        # Unsubscribe from live max-intensity updates.
        if self._max_observer_active:
            try:
                self._model.ad_viewer.remove_max_intensity_observer(self._on_max_intensity_change)
            except Exception:
                pass
            self._max_observer_active = False
        self._original_max_intensity = None
        self._best_max_intensity = None
        self._best_capture_token += 1
        self._original_snapshot.clear()
        self._current_snapshot.clear()
        self._best_snapshot.clear()

        detector = self._active_detector()
        acquire_pv = _cam_pv(detector, "Acquire") if detector is not None else ""
        snapshot = self._saved_pv_values
        self._saved_pv_values = {}

        def _worker() -> None:
            if acquire_pv:
                try:
                    caput(acquire_pv, 0)
                except Exception as exc:
                    _log.warning("Failed to stop acquisition: %s", exc)
            if restore:
                for pv, value in snapshot.items():
                    try:
                        caput(pv, value)
                    except Exception as exc:
                        _log.warning("Failed to restore %s: %s", pv, exc)

        threading.Thread(target=_worker, daemon=True, name="preview-stop").start()

    def _active_detector(self) -> DetectorConfig | None:
        cfg = self._model.beamline.active
        return cfg.active_detector_config if cfg is not None else None

    def _on_max_intensity_change(self, value: float | None) -> None:
        """Forwarded from ADViewerModel; runs on the controller thread."""
        if not self._previewing:
            return
        wx.CallAfter(self._view.update_current_max_intensity, value)

        if value is None:
            return
        prev_best = self._best_max_intensity
        if prev_best is not None and value <= prev_best:
            return
        # New running best — capture the motor positions at this moment.
        self._best_max_intensity = value
        self._best_capture_token += 1
        token = self._best_capture_token
        specs = list(self._view.centering_specs())

        def _worker() -> None:
            best_positions: list[tuple[str, str, float | None, int]] = []
            new_snapshot: dict[str, float] = {}
            for spec in specs:
                label = spec.description or spec.shorthand or spec.pv
                try:
                    raw = caget(_rbv_pv(spec.pv))
                    position: float | None = float(raw) if raw is not None else None
                except Exception:
                    position = None
                best_positions.append((spec.pv, label, position, spec.precision))
                if position is not None:
                    new_snapshot[spec.pv] = position
            if token != self._best_capture_token or not self._previewing:
                return
            self._best_snapshot = new_snapshot
            wx.CallAfter(self._view.set_best_positions, best_positions, value)

        threading.Thread(target=_worker, daemon=True, name="preview-best-capture").start()

    _AUTO_SETTLE_MARGIN = 0.05

    def _on_auto_optimize_clicked(self) -> None:
        if self._auto_optimize_running:
            # Re-clicking the button cancels the in-flight sweep.
            self._auto_optimize_cancel.set()
            return
        if not self._previewing:
            _log.warning("Auto optimize requires Start Preview to be active.")
            return

        range_value = self._view.auto_optimize_range
        step_value = self._view.auto_optimize_step
        if range_value is None or step_value is None:
            _log.warning("Auto optimize: provide a positive Range and Step.")
            return
        if step_value > range_value:
            _log.warning("Auto optimize: step must be <= range.")
            return

        specs = list(self._view.centering_specs())
        if not specs:
            _log.warning("Auto optimize: no centering motors available.")
            return

        cfg = self._model.beamline.active
        exposure = float(cfg.preview_exposure) if cfg is not None else 0.1
        settle = max(0.05, exposure + self._AUTO_SETTLE_MARGIN)

        self._auto_optimize_running = True
        self._auto_optimize_cancel.clear()
        wx.CallAfter(self._view.set_auto_optimize_enabled, False)

        threading.Thread(
            target=self._auto_optimize_worker,
            args=(specs, range_value, step_value, settle),
            daemon=True,
            name="preview-auto-optimize",
        ).start()

    def _auto_optimize_worker(
        self,
        specs: list[CenteringMotorSpec],
        sweep_range: float,
        sweep_step: float,
        settle: float,
    ) -> None:
        cancel = self._auto_optimize_cancel
        try:
            for spec in specs:
                if cancel.is_set() or not self._previewing:
                    return
                setpoint = _val_pv(spec.pv)
                readback = _rbv_pv(spec.pv)
                try:
                    start_raw = caget(readback)
                    if start_raw is None:
                        start_raw = caget(setpoint)
                    if start_raw is None:
                        _log.warning("Auto optimize: %s has no readback; skipping.", spec.pv)
                        continue
                    start = float(start_raw)
                except Exception as exc:
                    _log.warning("Auto optimize: failed to read %s: %s", spec.pv, exc)
                    continue

                # Build the 1D grid centred on the start position.
                half = sweep_range / 2.0
                n_steps = max(1, int(round(sweep_range / sweep_step)))
                # Endpoints inclusive; n_steps intervals => n_steps + 1 points.
                positions = [start - half + i * sweep_step for i in range(n_steps + 1)]

                best_value: float | None = None
                best_position = start
                for target in positions:
                    if cancel.is_set() or not self._previewing:
                        # Abort: leave motor where it currently is.
                        return
                    try:
                        caput(setpoint, target, wait=True)
                    except Exception as exc:
                        _log.warning("Auto optimize: caput %s -> %g failed: %s", spec.pv, target, exc)
                        continue
                    # Wait for an integration to land for this position.
                    if cancel.wait(settle):
                        return
                    sample = self._model.ad_viewer.last_roi_max_intensity
                    if sample is None:
                        continue
                    if best_value is None or sample > best_value:
                        best_value = sample
                        best_position = target

                # Move motor to its best position before continuing to next motor.
                if cancel.is_set() or not self._previewing:
                    return
                try:
                    caput(setpoint, best_position, wait=True)
                except Exception as exc:
                    _log.warning(
                        "Auto optimize: failed to move %s to best %g: %s",
                        spec.pv,
                        best_position,
                        exc,
                    )
        finally:
            self._auto_optimize_running = False
            if self._previewing:
                wx.CallAfter(self._view.set_auto_optimize_enabled, True)

    def _on_go_original(self, key: str | None) -> None:
        self._dispatch_go(self._original_snapshot, key, "original")

    def _on_go_current(self, key: str | None) -> None:
        self._dispatch_go(self._current_snapshot, key, "current")

    def _on_go_best(self, key: str | None) -> None:
        self._dispatch_go(self._best_snapshot, key, "best")

    def _dispatch_go(self, snapshot: dict[str, float], key: str | None, label: str) -> None:
        """Issue caputs to move to *snapshot* values; *key=None* moves all."""
        if not snapshot:
            _log.warning("Go (%s): no snapshot available.", label)
            return
        if key is None:
            targets = list(snapshot.items())
        else:
            position = snapshot.get(key)
            if position is None:
                _log.warning("Go (%s): no snapshot for %s.", label, key)
                return
            targets = [(key, position)]

        def _worker() -> None:
            for pv, position in targets:
                try:
                    caput(_val_pv(pv), position, wait=True)
                except Exception as exc:
                    _log.warning("Go (%s): failed to move %s to %g: %s", label, pv, position, exc)

        threading.Thread(target=_worker, daemon=True, name=f"preview-go-{label}").start()
