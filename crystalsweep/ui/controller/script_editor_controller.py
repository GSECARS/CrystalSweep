#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/script_editor_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# Controller for the script editor dialog. Bridges ScriptModel and
# FlatScriptEditorDialog: opens the dialog, loads hooks.py into the editor,
# and saves edits back to disk on demand.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging

import wx

from crystalsweep.model.script_model import ScriptModel
from crystalsweep.ui.view.main_view import MainView
from crystalsweep.ui.view.custom.theme import app_theme
from wxutils import FlatScriptEditorDialog

__all__ = ["ScriptEditorController"]

_log = logging.getLogger(__name__)


class ScriptEditorController:
    """Bridges ScriptModel and FlatScriptEditorDialog."""

    def __init__(self, model: ScriptModel, view: MainView) -> None:
        self._model = model
        self._view = view
        self._dialog: FlatScriptEditorDialog | None = None

        view.bind_open_scripts(self.open_editor)

    def open_editor(self) -> None:
        if self._dialog is None:
            self._dialog = FlatScriptEditorDialog(
                self._view,
                title="Script Editor — hooks.py",
                syntax_scheme=app_theme.syntax_scheme(),
            )
            self._dialog.bind_save(self._on_save)
            self._dialog.Bind(wx.EVT_CLOSE, lambda e: self._dialog.Hide() or e.Veto())

        self._dialog.load_source(self._model.load_source())
        self._dialog.Show()
        self._dialog.Raise()

    def _on_save(self, source: str) -> None:
        try:
            self._model.save_source(source)
            self._dialog.set_status(
                f"Saved — {self._model.hooks_path.name}",
                ok_color=app_theme.green,
                error_color=app_theme.red,
            )
            _log.info("hooks.py saved")
        except Exception as exc:
            self._dialog.set_status(
                f"Save failed: {exc}",
                ok_color=app_theme.green,
                error_color=app_theme.red,
                error=True,
            )
            _log.error("Failed to save hooks.py: %s", exc)
