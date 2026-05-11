#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/integration_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Model for pyFAI azimuthal integration and d-spacing computation.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

try:
    import pyFAI

    HAS_PYFAI = True
except ImportError:
    HAS_PYFAI = False

__all__ = ["IntegrationModel", "HAS_PYFAI"]

UNIT_LABELS: dict[str, str] = {"2th_deg": "2\u03b8 (\u00b0)", "q_nm^-1": "q (nm\u207b\u00b9)", "q_A^-1": "Q (\u212b\u207b\u00b9)", "d_A": "d (\u212b)"}


@dataclass()
class IntegrationModel:
    """Handles pyFAI calibration loading, azimuthal integration, and d-spacing computation."""

    _ai: "pyFAI.AzimuthalIntegrator | None" = field(init=False, compare=False, repr=False, default=None)
    _poni_path: Path | None = field(init=False, compare=False, repr=False, default=None)

    @property
    def is_calibrated(self) -> bool:
        """Returns True if a calibration file has been loaded."""
        return self._ai is not None

    @property
    def poni_path(self) -> Path | None:
        """Returns the path of the loaded .poni file, or None."""
        return self._poni_path

    def load_poni(self, poni_path: Path) -> None:
        """Loads a pyFAI .poni calibration file."""
        if not HAS_PYFAI:
            raise ImportError("pyFAI is not installed.")

        self._ai = pyFAI.load(str(poni_path))
        self._poni_path = poni_path

    def integrate1d(
        self,
        frame: np.ndarray,
        npt: int,
        unit: str,
        roi: tuple[int, int, int, int] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, str]:
        """Runs pyFAI azimuthal integration."""
        if self._ai is None:
            raise RuntimeError("No calibration loaded. Call load_poni() first.")

        mask = None
        if roi is not None:
            x1, y1, x2, y2 = roi
            h, w = frame.shape
            mask = np.ones(frame.shape, dtype=np.uint8)
            mask[max(0, y1) : min(h, y2), max(0, x1) : min(w, x2)] = 0

        result = self._ai.integrate1d(
            frame.astype(np.float32),
            npt,
            mask=mask,
            unit=unit,
            correctSolidAngle=True,
        )

        xs = np.array(result.radial)
        ys = np.array(result.intensity)
        x_label = UNIT_LABELS.get(unit, unit)
        return xs, ys, x_label

    def integrate1d_line(
        self,
        frame: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        unit: str = "2th_deg",
    ) -> tuple[np.ndarray, np.ndarray, str]:
        """Extracts the intensity profile along a line between two pixels."""

        h, w = frame.shape
        length = math.hypot(x2 - x1, y2 - y1)
        npt = max(2, int(round(length)))

        ts = np.linspace(0.0, 1.0, npt)
        xs_f = x1 + ts * (x2 - x1)
        ys_f = y1 + ts * (y2 - y1)

        xi = np.clip(xs_f, 0, w - 1)
        yi = np.clip(ys_f, 0, h - 1)

        xi0 = np.floor(xi).astype(int)
        yi0 = np.floor(yi).astype(int)
        xi1 = np.clip(xi0 + 1, 0, w - 1)
        yi1 = np.clip(yi0 + 1, 0, h - 1)
        fx = xi - xi0
        fy = yi - yi0

        img = frame.astype(np.float64)
        intensities = img[yi0, xi0] * (1 - fx) * (1 - fy) + img[yi0, xi1] * fx * (1 - fy) + img[yi1, xi0] * (1 - fx) * fy + img[yi1, xi1] * fx * fy

        if self._ai is not None:
            try:
                radial_map = self._ai.center_array(unit=unit)
                radial_vals = (
                    radial_map[yi0, xi0] * (1 - fx) * (1 - fy) + radial_map[yi0, xi1] * fx * (1 - fy) + radial_map[yi1, xi0] * (1 - fx) * fy + radial_map[yi1, xi1] * fx * fy
                )
                x_label = UNIT_LABELS.get(unit, unit)
                return radial_vals, intensities, x_label
            except Exception:
                pass

        pixel_dist = ts * length
        return pixel_dist, intensities, "Pixel"

    def compute_two_theta(self, ix: int, iy: int) -> float | None:
        """Returns 2θ in degrees for a given image pixel, or None on error."""
        if self._ai is None:
            return None
        try:
            tth_rad = self._ai.center_array(unit="2th_rad")[iy, ix]
            if tth_rad <= 0:
                return None
            return math.degrees(tth_rad)
        except Exception:
            return None

    def compute_d_spacing(self, ix: int, iy: int) -> float | None:
        """Returns d-spacing in Angstroms for a given image pixel, or None on error."""
        if self._ai is None:
            return None
        try:
            wavelength_m = self._ai.wavelength
            tth = self._ai.center_array(unit="2th_rad")[iy, ix]
            if tth <= 0:
                return None
            d_m = wavelength_m / (2.0 * math.sin(tth / 2.0))
            return d_m * 1e10
        except Exception:
            return None
