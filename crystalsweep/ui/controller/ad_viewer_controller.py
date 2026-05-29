#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/ad_viewer_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to implement the AD Viewer controller for the CrystalSweep
# application.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
from pathlib import Path
from threading import Lock

import numpy as np
import wx

from crystalsweep.model import MainModel
from crystalsweep.model.integration_model import HAS_PYFAI
from crystalsweep.ui.view import MainView

__all__ = ["ADViewerController"]

_log = logging.getLogger(__name__)


class ADViewerController:
    """Bridges the AD Viewer model and view."""

    def __init__(self, model: MainModel, view: MainView) -> None:
        """Initialises the controller, wires up bindings, and starts the PV stream."""
        self._model = model
        self._view = view
        self._pending_frame: np.ndarray | None = None
        self._pending_lock = Lock()

        self._view.ad_viewer.bind_load_file(self._on_load_file)
        self._view.ad_viewer.bind_load_poni(self._on_load_poni)
        self._view.ad_viewer.bind_integration_settings_changed(self._on_integration_settings_changed)
        self._view.ad_viewer.bind_roi_changed(self._on_roi_changed)
        self._view.ad_viewer.bind_line_changed(self._on_line_changed)
        self._view.ad_viewer.bind_frame_navigation(self._on_navigate_frame)
        self._view.ad_viewer.bind_roi_live_integration(self._on_roi_live_integration_changed)

        self.resubscribe_detector()

    def resubscribe_detector(self) -> None:
        """(Re)subscribe to the active detector's image PV, or unsubscribe if none."""
        active = self._model.beamline.active.active_detector_config
        pv_name = active.image_pv if active is not None else ""
        if not pv_name:
            _log.info("No active detector configured; AD viewer is idle.")
            self._model.ad_viewer.unsubscribe()
            self._view.ad_viewer.set_status_overlay("No detector configured")
            return
        self._view.ad_viewer.set_status_overlay("")
        self._model.ad_viewer.subscribe(
            pv_name=pv_name,
            frame_callback=self._on_new_frame,
        )

    def _on_new_frame(self, frame: np.ndarray) -> None:
        """Deliver a detector frame to the view on the GUI thread, dropping frames if busy."""
        with self._pending_lock:
            already_pending = self._pending_frame is not None
            self._pending_frame = frame
        if not already_pending:
            wx.CallAfter(self._on_new_frame_gui)

    def _on_new_frame_gui(self) -> None:
        """Handle a new frame on the GUI thread: update image and optionally ROI plot."""
        with self._pending_lock:
            frame = self._pending_frame
            self._pending_frame = None
        if frame is None:
            return
        self._view.ad_viewer.update_frame(frame)
        current_frame = self._view.ad_viewer.current_frame
        if current_frame is None:
            return
        roi = self._view.ad_viewer.get_roi_coords()
        line = self._view.ad_viewer.get_line_coords()
        if roi is None and line is None:
            return
        if self._model.integration.is_calibrated:
            if not self._view.ad_viewer.is_roi_live_integration:
                return
            self._run_integration(current_frame)
        elif line is not None:
            self._run_line_integration(current_frame, *line)
        else:
            x1, y1, x2, y2 = roi
            self._run_roi_fallback(current_frame, x1, y1, x2, y2)

    def _on_load_file(self, filepath: Path) -> None:
        """Load an image file and display it; disable live updates on success."""
        suffix = filepath.suffix.lower()
        try:
            if suffix in (".h5", ".hdf5"):
                frame = self._model.image_loader.load_hdf5(filepath)
            else:
                wx.MessageBox(f"Unsupported file format: {suffix}", "Error", wx.OK | wx.ICON_ERROR)
                return
        except ImportError as exc:
            wx.MessageBox(str(exc), "Missing Dependency", wx.OK | wx.ICON_ERROR)
            return
        except Exception as exc:
            _log.exception("Failed to load image file %s", filepath)
            wx.MessageBox(f"Error loading file:\n{exc}", "Error", wx.OK | wx.ICON_ERROR)
            return

        self._view.ad_viewer.display_frame(frame)
        self._view.ad_viewer.set_live_updates(False)

        frame_count = self._model.image_loader.frame_count
        self._view.ad_viewer.set_frame_navigation(frame_count, 0)

        if self._model.integration.is_calibrated:
            self._run_integration(frame)

    def _on_load_poni(self, poni_path: Path) -> None:
        """Load a pyFAI .poni calibration file and re-integrate the current frame."""
        if not HAS_PYFAI:
            wx.MessageBox("pyFAI is not installed.", "Missing Dependency", wx.OK | wx.ICON_ERROR)
            return

        try:
            self._model.integration.load_poni(poni_path)
        except Exception as exc:
            _log.exception("Failed to load .poni file %s", poni_path)
            wx.MessageBox(f"Failed to load .poni file:\n{exc}", "Error", wx.OK | wx.ICON_ERROR)
            return

        self._view.ad_viewer.set_poni_label(poni_path.name, success=True)
        self._view.ad_viewer.set_d_spacing_func(self._model.integration.compute_d_spacing)
        self._view.ad_viewer.set_two_theta_func(self._model.integration.compute_two_theta)

        current_frame = self._view.ad_viewer.current_frame
        if current_frame is not None:
            self._run_integration(current_frame)

    def _on_roi_live_integration_changed(self, enabled: bool) -> None:
        """React to the ROI live integration toggle."""
        if enabled:
            current_frame = self._view.ad_viewer.current_frame
            if current_frame is None:
                return
            roi = self._view.ad_viewer.get_roi_coords()
            line = self._view.ad_viewer.get_line_coords()
            if roi is None and line is None:
                return
            if self._model.integration.is_calibrated:
                self._run_integration(current_frame)
            elif line is not None:
                self._run_line_integration(current_frame, *line)
            else:
                self._run_roi_fallback(current_frame, *roi)

    def _on_integration_settings_changed(self) -> None:
        """Re-integrate the current frame when npt or unit changes."""
        current_frame = self._view.ad_viewer.current_frame
        if current_frame is not None and self._model.integration.is_calibrated:
            self._run_integration(current_frame)

    def _on_navigate_frame(self, index: int) -> None:
        """Load and display the requested frame index from the current HDF5 file."""
        try:
            frame = self._model.image_loader.load_hdf5_frame(index)
        except Exception as exc:
            _log.exception("Failed to load frame %d", index)
            wx.MessageBox(f"Error loading frame {index}:\n{exc}", "Error", wx.OK | wx.ICON_ERROR)
            return

        self._view.ad_viewer.display_frame(frame)

        if self._model.integration.is_calibrated:
            self._run_integration(frame)
        else:
            roi = self._view.ad_viewer.get_roi_coords()
            line = self._view.ad_viewer.get_line_coords()
            if line is not None:
                self._run_line_integration(frame, *line)
            elif roi is not None:
                self._run_roi_fallback(frame, *roi)

    def _on_roi_changed(self, x1: int | None, y1: int | None, x2: int | None, y2: int | None) -> None:
        """React to an ROI draw or clear event from the canvas."""
        current_frame = self._view.ad_viewer.current_frame

        if x1 is None or y1 is None or x2 is None or y2 is None or current_frame is None:
            self._view.ad_viewer.clear_integration_plot()
            return

        if self._model.integration.is_calibrated:
            self._run_integration(current_frame)
        else:
            self._run_roi_fallback(current_frame, x1, y1, x2, y2)

    def _on_line_changed(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """React to a line ROI committed via Alt+click on the canvas."""
        current_frame = self._view.ad_viewer.current_frame
        if current_frame is None:
            return
        self._run_line_integration(current_frame, x1, y1, x2, y2)

    def _run_roi_fallback(self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> None:
        """Compute column-sum integration over the ROI and push results to the view."""
        h, w = frame.shape[:2]
        x1c = max(0, min(x1, w - 1))
        x2c = max(x1c + 1, min(x2, w))
        y1c = max(0, min(y1, h - 1))
        y2c = max(y1c + 1, min(y2, h))
        roi = frame[y1c:y2c, x1c:x2c].astype(np.float64)
        if roi.ndim == 3:
            roi = roi.mean(axis=2)
        ys = roi.sum(axis=0)
        xs = np.arange(x1c, x1c + len(ys), dtype=np.float64)
        self._view.ad_viewer.set_integration_data(xs, ys, "Pixel")

    def _run_line_integration(self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> None:
        """Extract line profile via the model and push results to the view."""
        _, unit = self._view.ad_viewer.get_integration_settings()
        try:
            xs, ys, x_label = self._model.integration.integrate1d_line(frame, x1, y1, x2, y2, unit=unit)
        except Exception:
            _log.exception("integrate1d_line failed")
            return
        self._view.ad_viewer.set_integration_data(xs, ys, x_label)

    def _run_integration(self, frame: np.ndarray) -> None:
        """Execute pyFAI azimuthal integration or line profile and push results to the view."""
        npt, unit = self._view.ad_viewer.get_integration_settings()

        line = self._view.ad_viewer.get_line_coords()
        if line is not None:
            self._run_line_integration(frame, *line)
            return

        roi = self._view.ad_viewer.get_roi_coords()

        try:
            xs, ys, x_label = self._model.integration.integrate1d(frame, npt, unit, roi=roi)
        except Exception:
            _log.exception("pyFAI integrate1d failed")
            return

        self._view.ad_viewer.set_integration_data(xs, ys, x_label)
