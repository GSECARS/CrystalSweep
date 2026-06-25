#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/theme.py
# ----------------------------------------------------------------------------------
# Purpose:
# Shared dark-theme colour constants used across all custom view widgets.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import sys

import wx

_PT_TO_PX = {9: 10, 10: 11, 11: 12, 12: 13, 13: 14}
_WIN_PX_ADJUST = -2


def scaled_font(
    pt: int,
    family: int = wx.FONTFAMILY_DEFAULT,
    style: int = wx.FONTSTYLE_NORMAL,
    weight: int = wx.FONTWEIGHT_NORMAL,
) -> wx.Font:
    px = _PT_TO_PX.get(pt, pt)
    if sys.platform == "win32":
        px = max(1, px + _WIN_PX_ADJUST)
    return wx.Font(wx.Size(0, px), family, style, weight)


BG_SURFACE = wx.Colour(18, 18, 18)
BG_CARD = wx.Colour(28, 28, 30)
BG_ELEVATED = wx.Colour(38, 38, 42)
FG_PRIMARY = wx.Colour(230, 230, 235)
FG_SECONDARY = wx.Colour(140, 140, 150)
ACCENT = wx.Colour(99, 179, 237)
ACCENT_HOVER = wx.Colour(130, 200, 255)
SEP_COLOUR = wx.Colour(55, 55, 60)
BTN_HOVER_BG = wx.Colour(55, 55, 55)
BTN_PRESS_BG = wx.Colour(80, 80, 80)

POPUP_BG = BG_CARD
POPUP_FG = FG_PRIMARY
POPUP_BTN_BG = wx.Colour(45, 45, 50)
POPUP_BTN_HOVER = wx.Colour(62, 62, 70)
POPUP_BTN_PRESS = wx.Colour(85, 85, 95)

PONI_LOADED = wx.Colour(46, 139, 78)
PONI_MISSING = wx.Colour(110, 110, 120)

DANGER = wx.Colour(180, 40, 40)
DANGER_HOVER = wx.Colour(210, 55, 55)
DANGER_PRESS = wx.Colour(150, 30, 30)

DISABLED_BG = wx.Colour(33, 33, 36)
DISABLED_FG = wx.Colour(90, 90, 96)

ICON_FG = wx.Colour(200, 200, 210)
ICON_SIZE = 20

LIVE_W = 24
LIVE_H = 56
LIVE_OFF = wx.Colour(90, 90, 95)
LIVE_ON = wx.Colour(180, 40, 40)
LIVE_ON_HOVER = wx.Colour(210, 55, 55)
LIVE_OFF_HOVER = wx.Colour(120, 120, 125)
LIVE_SCHEME = (LIVE_OFF, LIVE_OFF_HOVER, LIVE_ON, LIVE_ON_HOVER)

def btn_font() -> wx.Font:
    """Return the standard FlatButton font. Call after wx.App is created."""
    return scaled_font(12)

BTN_DISABLED = (DISABLED_BG, DISABLED_FG)

DEFAULT_SCHEME = (POPUP_BTN_BG, POPUP_BTN_HOVER, POPUP_BTN_PRESS, FG_PRIMARY, FG_PRIMARY)
DANGER_SCHEME  = (POPUP_BTN_BG, DANGER_HOVER, DANGER_PRESS, wx.Colour(230, 90, 90), FG_PRIMARY)
TOGGLE_SCHEME  = (POPUP_BTN_BG, POPUP_BTN_HOVER, PONI_LOADED, FG_SECONDARY)
MUTED_SCHEME   = (wx.Colour(38, 38, 44), wx.Colour(55, 60, 75), wx.Colour(30, 35, 55), wx.Colour(120, 150, 190), wx.Colour(120, 150, 190))
STATUS_SCHEME  = (DISABLED_BG, DISABLED_FG)
RADIO_SCHEME    = (BG_CARD, BG_ELEVATED, ACCENT_HOVER, FG_SECONDARY)
PROGRESS_SCHEME = (BG_ELEVATED, ACCENT)
TAB_SCHEME = (BG_CARD, BG_ELEVATED, wx.Colour(40, 40, 46), FG_PRIMARY, FG_SECONDARY, ACCENT, SEP_COLOUR)
MENU_BAR_SCHEME = (
    wx.Colour(24, 24, 26),   # bar_bg
    wx.Colour(50, 50, 56),   # btn_hover_bg
    wx.Colour(60, 60, 68),   # btn_active_bg
    FG_SECONDARY,            # btn_fg
    DISABLED_FG,             # btn_disabled_fg
    wx.Colour(55, 55, 62),   # sep_colour
    POPUP_BG,                # popup_bg
    POPUP_BTN_HOVER,         # popup_hover_bg
    FG_PRIMARY,              # popup_fg
    FG_SECONDARY,            # popup_secondary_fg
    wx.Colour(55, 55, 62),   # popup_sep
)

def dialog_scheme():
    """Return a DialogScheme using CS dark colours."""
    return (
        BG_SURFACE,
        FG_PRIMARY,
        FG_SECONDARY,
        SEP_COLOUR,
        DEFAULT_SCHEME,
        BTN_DISABLED,
    )

def icon_scheme(bg: wx.Colour) -> tuple:
    """Return an (idle_bg, hover_bg, press_bg) IconScheme for a given idle background."""
    return (bg, BTN_HOVER_BG, BTN_PRESS_BG)
TEXT_SCHEME    = (BG_ELEVATED, FG_PRIMARY, FG_SECONDARY, DISABLED_BG, DISABLED_FG, wx.Colour(70, 28, 28))
COMBO_SCHEME   = (BG_ELEVATED, BTN_HOVER_BG, FG_PRIMARY, SEP_COLOUR, FG_SECONDARY, DISABLED_BG, DISABLED_FG, POPUP_BG, POPUP_BTN_HOVER)
SCROLLBAR_SCHEME = (wx.Colour(28, 28, 32), wx.Colour(70, 70, 80), wx.Colour(100, 100, 115))
SPLITTER_SCHEME  = (wx.Colour(60, 60, 65), wx.Colour(90, 90, 100))
SYNTAX_SCHEME = (
    wx.Colour(28, 28, 32),    # editor_bg
    wx.Colour(220, 220, 228), # editor_fg
    wx.Colour(22, 22, 26),    # gutter_bg
    wx.Colour(90, 90, 100),   # gutter_fg
    wx.Colour(50, 80, 120),   # sel_bg
    wx.Colour(86, 156, 214),  # keyword_fg
    wx.Colour(78, 201, 176),  # keyword2_fg
    wx.Colour(206, 145, 120), # string_fg
    wx.Colour(106, 153, 85),  # comment_fg
    wx.Colour(181, 206, 168), # number_fg
    wx.Colour(212, 212, 212), # operator_fg
    wx.Colour(220, 220, 100), # decorator_fg
    wx.Colour(220, 220, 170), # defname_fg
)
DIVIDER_FG       = wx.Colour(140, 140, 150)   # matches FG_SECONDARY
DIVIDER_LINE     = wx.Colour(70, 70, 76)
