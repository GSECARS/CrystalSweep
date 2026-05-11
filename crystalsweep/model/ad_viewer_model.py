#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/ad_viewer_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to implement the AD Viewer model.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
from contextlib import suppress
from dataclasses import dataclass, field
from threading import Event, Thread
from time import sleep
from typing import Protocol

import numpy as np
from p4p.client.thread import Context, Subscription

__all__ = ["ADViewerModel"]

_log = logging.getLogger(__name__)


class FrameCallback(Protocol):
    """Protocol for callbacks that receive a new detector frame."""

    def __call__(self, frame: np.ndarray) -> None: ...


@dataclass()
class ADViewerModel:
    """Streams images from an EPICS PVA NTNDArray PV using p4p."""

    use_polling: bool = field(default=True)
    poll_interval: float = field(default=0.1)
    poll_join_timeout: float = field(default=1.0)
    default_request: str = field(default="field(value,dimension,uniqueId)")
    monitor_request: str = field(default="field(value,dimension)")

    _context: Context = field(init=False, compare=False, repr=False, default_factory=lambda: Context("pva"))
    _pv_name: str = field(init=False, compare=False, repr=False, default="")
    _frame_callback: FrameCallback | None = field(init=False, compare=False, repr=False, default=None)
    _subscription: Subscription | None = field(init=False, compare=False, repr=False, default=None)
    _polling_thread: Thread | None = field(init=False, compare=False, repr=False, default=None)
    _stop_polling: Event = field(init=False, compare=False, repr=False, default_factory=Event)

    def subscribe(self, pv_name: str, frame_callback: FrameCallback) -> None:
        """Start monitoring *pv_name* and deliver frames to *frame_callback*."""
        self.unsubscribe()

        self._pv_name = pv_name
        self._frame_callback = frame_callback

        if self.use_polling:
            _log.info("AD viewer subscribing to %s (polling @ %.0f Hz)", pv_name, 1.0 / self.poll_interval)
            self._stop_polling.clear()
            self._polling_thread = Thread(target=self._poll_loop, name="ADViewerPollThread", daemon=True)
            self._polling_thread.start()
        else:
            _log.info("AD viewer subscribing to %s (monitor mode)", pv_name)
            self._subscription = self._context.monitor(
                name=self._pv_name,
                cb=self._on_ntndarray,
                request=self.monitor_request,
            )

    def unsubscribe(self) -> None:
        """Stop monitoring the current PV, if any."""
        if self.use_polling:
            self._stop_polling.set()
            if self._polling_thread is not None and self._polling_thread.is_alive():
                self._polling_thread.join(timeout=self.poll_join_timeout)
            self._polling_thread = None
        else:
            if self._subscription is not None:
                self._subscription.close()
                self._subscription = None

    def _poll_loop(self) -> None:
        """Background loop: fetch latest PV value at ``poll_interval`` Hz."""
        last_unique_id: object = None

        while not self._stop_polling.is_set():
            try:
                value = self._context.get(self._pv_name, request=self.default_request)
                current_id = value.get("uniqueId", None)

                if current_id is not None and current_id == last_unique_id:
                    sleep(self.poll_interval)
                    continue

                last_unique_id = current_id
                _log.debug("New frame received via polling (uniqueId=%s)", current_id)
                self._process_image(value)

            except Exception:
                _log.exception("Error polling PV %s", self._pv_name)

            sleep(self.poll_interval)

    def _on_ntndarray(self, value: object) -> None:
        """Callback invoked by the p4p monitor on each PV update."""
        _log.debug("New frame received via PV monitor")
        self._process_image(value)

    def _process_image(self, value: object) -> None:
        """Decode an NTNDArray *value* and forward the resulting frame to the callback."""
        if self._frame_callback is None:
            return

        with suppress(Exception):
            flat = np.array(value["value"], copy=False)
            dims: list[int] = [d["size"] for d in value["dimension"] if d["size"] > 0]

            if not dims or flat.size == 0:
                _log.debug("Skipping empty NTNDArray (dims=%s, flat.size=%d)", dims, flat.size)
                return

            image = flat.reshape(dims[::-1])
            _log.debug("Delivering frame shape=%s dtype=%s", image.shape, image.dtype)
            self._frame_callback(image)
