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

import numpy as np

from epicsapps.pva_adviewer.ad_viewer_controller import ADViewerController as EpicsAppsController
from epicsapps.pva_adviewer.image_loader_model import ImageLoaderModel

from crystalsweep.model import MainModel
from crystalsweep.ui.view import MainView

__all__ = ["ADViewerController"]

_log = logging.getLogger(__name__)


class ADViewerController(EpicsAppsController):
    """Crystalsweep-specific shim over the epicsapps ADViewerController.

    Adds crystalsweep-specific wiring:
    - resubscribe_detector(): reads the active detector PV from beamline config
    - _publish_max(): mirrors ROI integration max to model.ad_viewer for the preview controller
    """

    def __init__(self, model: MainModel, view: MainView) -> None:
        self._cs_model = model
        super().__init__(
            ad_model=model.ad_viewer,
            image_loader=ImageLoaderModel(),
            view=view.ad_viewer,
        )
        self.resubscribe_detector()

    def resubscribe_detector(self) -> None:
        """(Re)subscribe to the active detector's image PV; no-op when the PV hasn't changed."""
        active = self._cs_model.beamline.active.active_detector_config
        pv_name = active.image_pv if active is not None else ""
        if not pv_name:
            if self._ad_model.is_subscribed:
                self._ad_model.unsubscribe()
            self._view.set_status_overlay("No detector configured")
            return
        if self._ad_model.is_subscribed and self._ad_model.pv_name == pv_name:
            self._view.set_status_overlay("")
            return
        self._view.set_status_overlay("")
        self.subscribe(pv_name)

    # ------------------------------------------------------------------
    # ROI max intensity mirroring — used by the preview controller to
    # track peak signal while sweeping the sample.
    # ------------------------------------------------------------------

    def _run_integration(self, frame: np.ndarray) -> None:
        super()._run_integration(frame)
        # _last_raw_ys is set by the parent for azimuthal integration runs.
        self._publish_max(self._last_raw_ys)

    def _apply_compute(self, integration, mask_rgba) -> None:
        super()._apply_compute(integration, mask_rgba)
        if integration is not None:
            _, ys, _ = integration
            self._publish_max(ys)

    def _publish_max(self, ys) -> None:
        if ys is None or len(ys) == 0:
            self._ad_model.clear_last_roi_max_intensity()
            return
        try:
            self._ad_model.set_last_roi_max_intensity(float(np.asarray(ys).max()))
        except (TypeError, ValueError):
            self._ad_model.clear_last_roi_max_intensity()
