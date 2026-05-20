#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/scan/driver.py
# ----------------------------------------------------------------------------------
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

__all__ = ["ScanDriver", "ScanSpec"]


@dataclass
class ScanSpec:
    """Everything needed to execute one scan axis."""

    pv: str
    start: float
    end: float
    points: int
    exposure: float
    controller_params: dict = field(default_factory=dict)

    @property
    def step_size(self) -> float:
        if self.points <= 1:
            return 0.0
        return (self.end - self.start) / (self.points - 1)

    def positions(self) -> list[float]:
        if self.points <= 1:
            return [self.start]
        return [self.start + self.step_size * i for i in range(self.points)]


@runtime_checkable
class ScanDriver(Protocol):
    """Common interface every scan backend must implement."""

    def prepare(self, spec: ScanSpec) -> None: ...
    def run(self, spec: ScanSpec, on_point: Callable[[int, float], None]) -> None: ...
    def abort(self) -> None: ...
