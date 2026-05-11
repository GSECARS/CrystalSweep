#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/icons.py
# ----------------------------------------------------------------------------------
# Purpose:
# Icon draw functions used with IconButton and similar wx.GraphicsContext painters.
# Each function accepts (gc, s) where gc is a wx.GraphicsContext and s is the size.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import math

import wx

from crystalsweep.ui.view.custom.theme import ACCENT, BG_SURFACE, ICON_FG

__all__ = ["draw_folder", "draw_chevron_left", "draw_chevron_right", "draw_cog"]


def draw_folder(gc: wx.GraphicsContext, s: int) -> None:
    """Folder icon with an upward arrow."""
    m, tab_w, tab_h, r = s * 0.12, s * 0.38, s * 0.16, s * 0.08
    body = gc.CreatePath()
    body.AddRoundedRectangle(m, m + tab_h, s - 2 * m, s - 2 * m - tab_h, r)
    gc.SetBrush(wx.Brush(wx.Colour(ACCENT.Red(), ACCENT.Green(), ACCENT.Blue(), 200)))
    gc.SetPen(wx.TRANSPARENT_PEN)
    gc.FillPath(body)
    tab = gc.CreatePath()
    tab.AddRoundedRectangle(m, m, tab_w, tab_h + r, r * 0.8)
    gc.FillPath(tab)
    cx, cy = s * 0.62, s * 0.56
    aw, ah = s * 0.22, s * 0.22
    arrow = gc.CreatePath()
    arrow.MoveToPoint(cx, cy - ah * 0.5)
    arrow.AddLineToPoint(cx, cy + ah * 0.3)
    arrow.MoveToPoint(cx - aw * 0.45, cy - ah * 0.04)
    arrow.AddLineToPoint(cx, cy - ah * 0.5)
    arrow.AddLineToPoint(cx + aw * 0.45, cy - ah * 0.04)
    gc.SetPen(wx.Pen(BG_SURFACE, max(1, int(s * 0.1)), wx.PENSTYLE_SOLID))
    gc.StrokePath(arrow)


def draw_chevron_left(gc: wx.GraphicsContext, s: int) -> None:
    """Left-pointing chevron."""
    cx, cy, hw, hh = s * 0.55, s * 0.5, s * 0.18, s * 0.28
    p = gc.CreatePath()
    p.MoveToPoint(cx + hw, cy - hh)
    p.AddLineToPoint(cx - hw, cy)
    p.AddLineToPoint(cx + hw, cy + hh)
    gc.SetPen(wx.Pen(ICON_FG, max(1, int(s * 0.1)), wx.PENSTYLE_SOLID))
    gc.SetBrush(wx.TRANSPARENT_BRUSH)
    gc.StrokePath(p)


def draw_chevron_right(gc: wx.GraphicsContext, s: int) -> None:
    """Right-pointing chevron."""
    cx, cy, hw, hh = s * 0.45, s * 0.5, s * 0.18, s * 0.28
    p = gc.CreatePath()
    p.MoveToPoint(cx - hw, cy - hh)
    p.AddLineToPoint(cx + hw, cy)
    p.AddLineToPoint(cx - hw, cy + hh)
    gc.SetPen(wx.Pen(ICON_FG, max(1, int(s * 0.1)), wx.PENSTYLE_SOLID))
    gc.SetBrush(wx.TRANSPARENT_BRUSH)
    gc.StrokePath(p)


def draw_cog(gc: wx.GraphicsContext, s: int) -> None:
    """Gear / settings icon."""
    cx, cy = s / 2.0, s / 2.0
    outer_r, inner_r = s * 0.38, s * 0.22
    tooth_n = 8
    tooth_depth = s * 0.09
    half_angle = math.pi / tooth_n * 0.55

    path = gc.CreatePath()
    for i in range(tooth_n * 2):
        angle = i * math.pi / tooth_n
        r = outer_r + tooth_depth if i % 2 == 0 else outer_r
        x = cx + r * math.cos(angle - half_angle)
        y = cy + r * math.sin(angle - half_angle)
        if i == 0:
            path.MoveToPoint(x, y)
        else:
            path.AddLineToPoint(x, y)
        path.AddLineToPoint(cx + r * math.cos(angle + half_angle), cy + r * math.sin(angle + half_angle))
    path.CloseSubpath()

    hole = gc.CreatePath()
    hole.AddCircle(cx, cy, inner_r)

    gc.SetBrush(wx.Brush(ICON_FG))
    gc.SetPen(wx.TRANSPARENT_PEN)
    gc.FillPath(path)
    gc.SetBrush(wx.Brush(BG_SURFACE))
    gc.FillPath(hole)
