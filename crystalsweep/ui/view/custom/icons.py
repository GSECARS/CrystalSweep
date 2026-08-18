#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/icons.py
# ----------------------------------------------------------------------------------
# Purpose:
# Icon draw functions for use with IconButton and FlatIconButton.
# Colors are pulled from app_theme at draw time so icons follow dark/light mode.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import math

import wx

from crystalsweep.ui.view.custom.theme import app_theme

__all__ = [
    "draw_chevron_left",
    "draw_chevron_right",
    "draw_cog",
    "draw_folder",
    "draw_folder_open",
    "draw_refresh",
    "draw_update",
]


def _pen(s: float) -> wx.Pen:
    return wx.Pen(app_theme.foreground, max(1, int(s * 0.1)))


def draw_chevron_left(gc: wx.GraphicsContext, s: int) -> None:
    """Left-pointing chevron."""
    cx, cy, hw, hh = s * 0.55, s * 0.5, s * 0.18, s * 0.28
    p = gc.CreatePath()
    p.MoveToPoint(cx + hw, cy - hh)
    p.AddLineToPoint(cx - hw, cy)
    p.AddLineToPoint(cx + hw, cy + hh)
    gc.SetPen(_pen(s))
    gc.SetBrush(wx.TRANSPARENT_BRUSH)
    gc.StrokePath(p)


def draw_chevron_right(gc: wx.GraphicsContext, s: int) -> None:
    """Right-pointing chevron."""
    cx, cy, hw, hh = s * 0.45, s * 0.5, s * 0.18, s * 0.28
    p = gc.CreatePath()
    p.MoveToPoint(cx - hw, cy - hh)
    p.AddLineToPoint(cx + hw, cy)
    p.AddLineToPoint(cx - hw, cy + hh)
    gc.SetPen(_pen(s))
    gc.SetBrush(wx.TRANSPARENT_BRUSH)
    gc.StrokePath(p)


def draw_cog(gc: wx.GraphicsContext, s: int) -> None:
    """Gear / settings icon."""
    t = app_theme
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
        path.AddLineToPoint(
            cx + r * math.cos(angle + half_angle),
            cy + r * math.sin(angle + half_angle),
        )
    path.CloseSubpath()
    gc.SetBrush(wx.Brush(t.foreground))
    gc.SetPen(wx.TRANSPARENT_PEN)
    gc.FillPath(path)
    hole = gc.CreatePath()
    hole.AddCircle(cx, cy, inner_r)
    gc.SetBrush(wx.Brush(t.background))
    gc.FillPath(hole)


def draw_folder(gc: wx.GraphicsContext, s: int) -> None:
    """Folder icon with an upward arrow."""
    t = app_theme
    accent = t.blue
    m, tab_w, tab_h, r = s * 0.12, s * 0.38, s * 0.16, s * 0.08
    body = gc.CreatePath()
    body.AddRoundedRectangle(m, m + tab_h, s - 2 * m, s - 2 * m - tab_h, r)
    gc.SetBrush(wx.Brush(wx.Colour(accent.Red(), accent.Green(), accent.Blue(), 200)))
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
    gc.SetPen(wx.Pen(t.background, max(1, int(s * 0.1))))
    gc.StrokePath(arrow)


def draw_folder_open(gc: wx.GraphicsContext, s: int) -> None:
    """Open folder / browse directory icon."""
    t = app_theme
    accent = t.blue
    m, r = s * 0.1, s * 0.07
    body = gc.CreatePath()
    body.AddRoundedRectangle(m, m + s * 0.18, s - 2 * m, s - 2 * m - s * 0.18, r)
    gc.SetBrush(wx.Brush(wx.Colour(accent.Red(), accent.Green(), accent.Blue(), 200)))
    gc.SetPen(wx.TRANSPARENT_PEN)
    gc.FillPath(body)
    tab = gc.CreatePath()
    tab.AddRoundedRectangle(m, m, s * 0.38, s * 0.18 + r, r * 0.8)
    gc.FillPath(tab)
    gc.SetPen(wx.Pen(t.background, max(1, int(s * 0.09))))
    cx, cy, aw = s * 0.62, s * 0.6, s * 0.18
    path = gc.CreatePath()
    path.MoveToPoint(cx - aw, cy)
    path.AddLineToPoint(cx + aw, cy)
    gc.StrokePath(path)


def draw_refresh(gc: wx.GraphicsContext, s: int) -> None:
    """Circular refresh / reset icon."""
    gc.SetPen(_pen(s))
    gc.SetBrush(wx.TRANSPARENT_BRUSH)
    cx, cy, r = s * 0.5, s * 0.5, s * 0.32
    path = gc.CreatePath()
    path.AddArc(cx, cy, r, math.radians(30), math.radians(330), True)
    gc.StrokePath(path)
    ang = math.radians(30)
    tx, ty = cx + r * math.cos(ang), cy + r * math.sin(ang)
    head = s * 0.12
    path2 = gc.CreatePath()
    path2.MoveToPoint(tx - head, ty)
    path2.AddLineToPoint(tx, ty - head)
    path2.AddLineToPoint(tx + head * 0.4, ty + head * 0.7)
    gc.StrokePath(path2)


def draw_update(gc: wx.GraphicsContext, s: int) -> None:
    """Upward arrow / apply / update icon."""
    fg = app_theme.foreground
    cx = s * 0.5
    stem_top, stem_bot = s * 0.22, s * 0.78
    stem_w, head_w = s * 0.1, s * 0.28
    gc.SetBrush(wx.Brush(fg))
    gc.SetPen(wx.TRANSPARENT_PEN)
    stem = gc.CreatePath()
    stem.AddRectangle(cx - stem_w / 2, stem_top + s * 0.14, stem_w, stem_bot - stem_top - s * 0.14)
    gc.FillPath(stem)
    arrow = gc.CreatePath()
    arrow.MoveToPoint(cx, stem_top)
    arrow.AddLineToPoint(cx - head_w / 2, stem_top + s * 0.22)
    arrow.AddLineToPoint(cx + head_w / 2, stem_top + s * 0.22)
    arrow.CloseSubpath()
    gc.FillPath(arrow)
