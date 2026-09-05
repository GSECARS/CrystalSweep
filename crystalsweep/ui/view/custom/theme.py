#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/theme.py
# ----------------------------------------------------------------------------------
# Purpose:
# Central theme facade. Call AppTheme() once after wx.App is created; afterwards
# import and use the module-level app_theme proxy everywhere:
#
#     from crystalsweep.ui.view.custom.theme import app_theme
#     app_theme.red                   # wx.Colour, updated on OS dark/light switch
#     app_theme.danger_scheme()       # color tuple for FlatButton
#     app_theme.scaled_font(12)       # wx.Font
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import sys
from typing import Optional

import wx
from wxutils import (
    ColorTheme,
    dark_theme,
    get_theme,
    is_dark_theme,
    light_theme,
    register_darkdetect,
    set_theme,
)

__all__ = ["AppTheme", "app_theme"]


class AppTheme:
    """True singleton color/font cache.

    Call ``AppTheme()`` once right after ``wx.App`` is created (in the main
    controller).  Everywhere else import the module-level ``app_theme`` proxy
    and use it directly — colors are instance attributes updated automatically
    on OS-level dark/light mode switches.
    """

    _instance: "AppTheme | None" = None

    icon_size: int = 20
    _pt_to_px = {9: 10, 10: 11, 11: 12, 12: 13, 13: 14}
    _win_px_adjust = -2

    def __new__(
        cls,
        dark: Optional[ColorTheme] = None,
        light: Optional[ColorTheme] = None,
    ) -> "AppTheme":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        dark: Optional[ColorTheme] = None,
        light: Optional[ColorTheme] = None,
    ) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._dark_override = dark
        self._light_override = light
        if dark is not None or light is not None:
            self._apply_override(is_dark_theme())
        self._update()
        register_darkdetect(self._on_switch)

    def _on_switch(self, is_dark: bool) -> None:
        if self._dark_override is not None or self._light_override is not None:
            self._apply_override(is_dark)
        self._update()
        for win in wx.GetTopLevelWindows():
            win.Refresh()
            win.Update()

    def _apply_override(self, is_dark: bool) -> None:
        set_theme((self._dark_override or dark_theme()) if is_dark else (self._light_override or light_theme()))

    def _update(self) -> None:
        t = get_theme()
        self.foreground = t.foreground
        self.background = t.background
        self.black = t.black
        self.bright_black = t.bright_black
        self.red = t.red
        self.bright_red = t.bright_red
        self.green = t.green
        self.bright_green = t.bright_green
        self.blue = t.blue
        self.bright_blue = t.bright_blue
        self.yellow = t.yellow
        self.bright_yellow = t.bright_yellow
        self.cyan = t.cyan
        self.bright_cyan = t.bright_cyan
        self.magenta = t.magenta
        self.bright_magenta = t.bright_magenta
        self.selection_bg = t.selection_bg

    def danger_scheme(self) -> tuple:
        return (self.black, self.bright_red, self.red, wx.Colour(230, 90, 90), self.foreground)

    def syntax_scheme(self) -> tuple:
        return (
            self.black,  # editor_bg
            self.foreground,  # editor_fg
            self.background,  # gutter_bg
            self.bright_black,  # gutter_fg
            self.selection_bg,  # sel_bg
            self.magenta,  # keyword_fg
            self.cyan,  # keyword2_fg
            self.bright_green,  # string_fg
            self.bright_yellow,  # comment_fg
            self.yellow,  # number_fg
            self.foreground,  # operator_fg
            self.bright_magenta,  # decorator_fg
            self.bright_cyan,  # defname_fg
        )

    def scaled_font(
        self,
        pt: int,
        family: int = wx.FONTFAMILY_DEFAULT,
        style: int = wx.FONTSTYLE_NORMAL,
        weight: int = wx.FONTWEIGHT_NORMAL,
    ) -> wx.Font:
        px = self._pt_to_px.get(pt, pt)
        if sys.platform == "win32":
            px = max(1, px + self._win_px_adjust)
        return wx.Font(wx.Size(0, px), family, style, weight)

    def btn_font(self) -> wx.Font:
        return self.scaled_font(12)


class _AppThemeProxy:
    """Proxy so ``from theme import app_theme`` resolves to the singleton at access time.

    Safe to import before ``AppTheme()`` has been called — attribute resolution
    is deferred until first use.
    """

    __slots__ = ()

    def __getattr__(self, name: str):
        if AppTheme._instance is None:
            raise AttributeError("app_theme not initialized — call AppTheme() first")
        return getattr(AppTheme._instance, name)


app_theme = _AppThemeProxy()
