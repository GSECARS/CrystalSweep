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

PONI_LOADED = wx.Colour(72, 199, 116)
PONI_MISSING = wx.Colour(110, 110, 120)

DANGER = wx.Colour(180, 40, 40)
DANGER_HOVER = wx.Colour(210, 55, 55)
DANGER_PRESS = wx.Colour(150, 30, 30)

ICON_FG = wx.Colour(200, 200, 210)
ICON_SIZE = 20

LIVE_W = 24
LIVE_H = 56
LIVE_OFF = wx.Colour(90, 90, 95)
LIVE_ON = wx.Colour(180, 40, 40)
LIVE_ON_HOVER = wx.Colour(210, 55, 55)
LIVE_OFF_HOVER = wx.Colour(120, 120, 125)
