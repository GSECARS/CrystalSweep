#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/widgets.py
# ----------------------------------------------------------------------------------
# Purpose:
# Reusable dark-themed custom wx controls shared across view panels.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable

import wx

from crystalsweep.ui.view.custom.theme import (
    ACCENT_HOVER,
    BG_ELEVATED,
    BG_SURFACE,
    BTN_HOVER_BG,
    BTN_PRESS_BG,
    FG_PRIMARY,
    FG_SECONDARY,
    ICON_SIZE,
    LIVE_H,
    LIVE_OFF,
    LIVE_OFF_HOVER,
    LIVE_ON,
    LIVE_ON_HOVER,
    LIVE_W,
    PONI_LOADED,
    POPUP_BG,
    POPUP_BTN_BG,
    POPUP_BTN_HOVER,
    POPUP_BTN_PRESS,
    SEP_COLOUR,
)

__all__ = ["FlatButton", "FrameLabel", "LiveToggle", "IconButton", "DarkTextCtrl", "DarkToggle", "DarkCombo"]


class FlatButton(wx.Control):
    """Flat dark button with hover/press states, used inside popups."""

    def __init__(self, parent: wx.Window, label: str) -> None:
        super().__init__(parent, style=wx.BORDER_NONE | wx.WANTS_CHARS)
        self._label = label
        self._hovered = False
        self._pressed = False
        self._action: Callable[[], None] | None = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetMinSize((-1, 26))
        super().Bind(wx.EVT_PAINT, self._on_paint)
        super().Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        super().Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        super().Bind(wx.EVT_LEFT_DOWN, self._on_press)
        super().Bind(wx.EVT_LEFT_UP, self._on_release)

    def set_action(self, callback: Callable[[], None]) -> None:
        self._action = callback

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        if self._pressed:
            bg = POPUP_BTN_PRESS
        elif self._hovered:
            bg = POPUP_BTN_HOVER
        else:
            bg = POPUP_BTN_BG
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(0, 0, w, h, 4)
        font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        gc.SetFont(font, FG_PRIMARY)
        tw, th = gc.GetTextExtent(self._label)
        gc.DrawText(self._label, (w - tw) / 2, (h - th) / 2)

    def _on_enter(self, event: wx.MouseEvent) -> None:
        self._hovered = True
        self.Refresh()
        event.Skip()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        self._hovered = False
        self._pressed = False
        self.Refresh()
        event.Skip()

    def _on_press(self, event: wx.MouseEvent) -> None:
        self._pressed = True
        self.Refresh()
        event.Skip()

    def _on_release(self, event: wx.MouseEvent) -> None:
        was_pressed = self._pressed
        self._pressed = False
        self.Refresh()
        if was_pressed and self._action is not None:
            self._action()
        event.Skip()


class FrameLabel(wx.Control):
    """Read-only frame-index display, centered, dark-styled."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, size=wx.Size(36, 28), style=wx.BORDER_NONE)
        self._value: str = "0"
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        super().Bind(wx.EVT_PAINT, self._on_paint)

    def ChangeValue(self, value: str) -> None:
        self._value = value
        self.Refresh()

    def GetValue(self) -> str:
        return self._value

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(BG_ELEVATED))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(0, 0, w, h, 3)
        font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, FG_PRIMARY)
        tw, th = gc.GetTextExtent(self._value)
        gc.DrawText(self._value, (w - tw) / 2, (h - th) / 2)


class LiveToggle(wx.Control):
    """Vertical LIVE toggle button. Gray when off, matte red when on."""

    def __init__(self, parent: wx.Window, live: bool = True, tooltip: str = "Toggle live updates") -> None:
        super().__init__(parent, size=wx.Size(LIVE_W, LIVE_H), style=wx.BORDER_NONE)
        self._live = live
        self._hovered = False
        self._on_toggled: Callable[[bool], None] | None = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetToolTip(tooltip)
        super().Bind(wx.EVT_PAINT, self._on_paint)
        super().Bind(wx.EVT_MOTION, self._on_motion)
        super().Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        super().Bind(wx.EVT_LEFT_UP, self._on_click)

    def set_toggled_callback(self, cb: Callable[[bool], None]) -> None:
        self._on_toggled = cb

    def set_live(self, live: bool) -> None:
        self._live = live
        self.Refresh()

    def set_hovered(self, hovered: bool) -> None:
        if hovered != self._hovered:
            self._hovered = hovered
            self.Refresh()

    @property
    def is_live(self) -> bool:
        return self._live

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(wx.Colour(0, 0, 0)))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        colour = (LIVE_ON_HOVER if self._hovered else LIVE_ON) if self._live else (LIVE_OFF_HOVER if self._hovered else LIVE_OFF)
        gc.SetPen(wx.Pen(colour, 1))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRoundedRectangle(1, 1, w - 2, h - 2, 3)
        font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, colour)
        _, ch_h = gc.GetTextExtent("L")
        y = (h - (4 * ch_h + 6)) / 2
        for ch in "LIVE":
            tw, th = gc.GetTextExtent(ch)
            gc.DrawText(ch, (w - tw) / 2, y)
            y += th + 2

    def _on_motion(self, event: wx.MouseEvent) -> None:
        inside = wx.Rect(0, 0, *self.GetClientSize()).Contains(event.GetPosition())
        if inside != self._hovered:
            self._hovered = inside
            self.Refresh()
        event.Skip()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        self._hovered = False
        self.Refresh()
        event.Skip()

    def _on_click(self, event: wx.MouseEvent) -> None:
        self._live = not self._live
        self.Refresh()
        if self._on_toggled:
            self._on_toggled(self._live)
        event.Skip()


class IconButton(wx.Panel):
    """Borderless icon button with hover and press background effects."""

    def __init__(self, parent: wx.Window, draw_fn: Callable, size: int = ICON_SIZE, tooltip: str = "") -> None:
        super().__init__(parent, size=wx.Size(size + 8, size + 8), style=wx.BORDER_NONE)
        self._draw_fn = draw_fn
        self._icon_size = size
        self._hovered = False
        self._pressed = False
        self._callback: Callable[[wx.CommandEvent], None] | None = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        if tooltip:
            self.SetToolTip(tooltip)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_press)
        self.Bind(wx.EVT_LEFT_UP, self._on_release)

    def Bind(self, event, handler, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        if event == wx.EVT_BUTTON:
            self._callback = handler
        else:
            super().Bind(event, handler, source, id, id2)

    def set_hovered(self, hovered: bool) -> None:
        if hovered != self._hovered:
            self._hovered = hovered
            if not hovered:
                self._pressed = False
            self.Refresh()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        if self._pressed:
            bg = BTN_PRESS_BG
        elif self._hovered:
            bg = BTN_HOVER_BG
        else:
            bg = wx.Colour(0, 0, 0)
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(0, 0, w, h, 4)
        gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
        offset = (w - self._icon_size) / 2
        gc.Translate(offset, offset)
        self._draw_fn(gc, self._icon_size)

    def _on_leave(self, event: wx.MouseEvent) -> None:
        self.set_hovered(False)
        event.Skip()

    def _on_motion(self, event: wx.MouseEvent) -> None:
        self.set_hovered(wx.Rect(0, 0, *self.GetClientSize()).Contains(event.GetPosition()))
        event.Skip()

    def _on_press(self, event: wx.MouseEvent) -> None:
        self._pressed = True
        self.Refresh()
        event.Skip()

    def _on_release(self, event: wx.MouseEvent) -> None:
        if self._pressed:
            self._pressed = False
            self.Refresh()
            if self._callback is not None:
                evt = wx.CommandEvent()
                evt.SetEventType(wx.EVT_BUTTON.typeId)
                self._callback(evt)
        event.Skip()


class DarkTextCtrl(wx.Panel):
    """Custom-painted editable text field, dark-styled with centered text."""

    def __init__(self, parent: wx.Window, value: str = "") -> None:
        super().__init__(parent, style=wx.BORDER_NONE, size=wx.Size(80, 32))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._value = value
        self._editing = False
        self._callback_enter: Callable | None = None
        self._callback_kill: Callable | None = None
        self._font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self._ctrl = wx.TextCtrl(self, value=value, style=wx.TE_PROCESS_ENTER | wx.TE_CENTER | wx.BORDER_NONE)
        self._ctrl.SetBackgroundColour(BG_ELEVATED)
        self._ctrl.SetForegroundColour(FG_PRIMARY)
        self._ctrl.SetFont(self._font)
        self._ctrl.EnableVisibleFocus(False)
        self._ctrl.Hide()
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._start_edit)
        self.Bind(wx.EVT_SIZE, lambda e: (self._reposition_ctrl(), self.Refresh(), e.Skip()))
        self._ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_enter)
        self._ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_kill)

    def _reposition_ctrl(self) -> None:
        w, h = self.GetClientSize()
        _, th = self._ctrl.GetTextExtent("0")
        ctrl_h = th + 4
        self._ctrl.SetSize(0, (h - ctrl_h) // 2, w, ctrl_h)

    def GetValue(self) -> str:
        return self._ctrl.GetValue() if self._editing else self._value

    def SetValue(self, value: str) -> None:
        self._value = value
        self._ctrl.SetValue(value)
        self.Refresh()

    def Bind(self, event, handler, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        if event == wx.EVT_KEY_DOWN:
            self._ctrl.Bind(event, handler)
        elif event == wx.EVT_KILL_FOCUS:
            self._callback_kill = handler
        elif event == wx.EVT_TEXT_ENTER:
            self._callback_enter = handler
        else:
            super().Bind(event, handler, source, id, id2)

    def _start_edit(self, event: wx.MouseEvent) -> None:
        self._editing = True
        self._ctrl.SetValue(self._value)
        self._reposition_ctrl()
        self._ctrl.Show()
        self._ctrl.SetFocus()
        self._ctrl.SelectAll()
        self.Refresh()
        event.Skip()

    def _on_enter(self, event: wx.Event) -> None:
        self._value = self._ctrl.GetValue()
        self._ctrl.Hide()
        self._editing = False
        self.Refresh()
        if self._callback_enter:
            self._callback_enter(event)

    def _on_kill(self, event: wx.FocusEvent) -> None:
        self._value = self._ctrl.GetValue()
        self._ctrl.Hide()
        self._editing = False
        self.Refresh()
        if self._callback_kill:
            self._callback_kill(event)
        event.Skip()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(BG_ELEVATED))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(0, 0, w, h, 3)
        if not self._editing:
            gc.SetFont(self._font, FG_PRIMARY)
            tw, th = gc.GetTextExtent(self._value)
            gc.DrawText(self._value, (w - tw) / 2, (h - th) / 2)


class DarkToggle(wx.Panel):
    """Custom-painted checkbox, dark-styled."""

    _BOX_W, _BOX_H, _R = 16, 16, 3

    def __init__(self, parent: wx.Window, label: str, value: bool = False) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self._label = label
        self._value = value
        self._hovered = False
        self._callback: Callable[[bool], None] | None = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(POPUP_BG)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_UP, self._on_click)
        self.Bind(wx.EVT_ENTER_WINDOW, lambda e: (setattr(self, "_hovered", True), self.Refresh(), e.Skip()))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: (setattr(self, "_hovered", False), self.Refresh(), e.Skip()))
        self.Bind(wx.EVT_SIZE, lambda e: (self.Refresh(), e.Skip()))

    def DoGetBestSize(self) -> wx.Size:
        dc = wx.ClientDC(self)
        dc.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        tw, th = dc.GetTextExtent(self._label)
        return wx.Size(self._BOX_W + 8 + tw + 8, max(26, self._BOX_H + 8))

    def GetValue(self) -> bool:
        return self._value

    def SetValue(self, value: bool) -> None:
        self._value = value
        self.Refresh()

    def Bind(self, event, handler, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        if event == wx.EVT_CHECKBOX:
            self._callback = handler
        else:
            super().Bind(event, handler, source, id, id2)

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(POPUP_BG))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        cy = h / 2
        bx, by = 4, cy - self._BOX_H / 2
        if self._value:
            gc.SetBrush(wx.Brush(PONI_LOADED))
            gc.SetPen(wx.Pen(PONI_LOADED, 1))
        else:
            gc.SetBrush(wx.Brush(BG_ELEVATED))
            gc.SetPen(wx.Pen(SEP_COLOUR, 1))
        gc.DrawRoundedRectangle(bx, by, self._BOX_W, self._BOX_H, self._R)
        if self._value:
            gc.SetPen(wx.Pen(BG_SURFACE, 2))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            path = gc.CreatePath()
            path.MoveToPoint(bx + 3, by + self._BOX_H / 2)
            path.AddLineToPoint(bx + self._BOX_W * 0.42, by + self._BOX_H - 3.5)
            path.AddLineToPoint(bx + self._BOX_W - 3, by + 3)
            gc.StrokePath(path)
        font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        gc.SetFont(font, FG_PRIMARY if not self._hovered else ACCENT_HOVER)
        _, th = gc.GetTextExtent(self._label)
        gc.DrawText(self._label, bx + self._BOX_W + 8, cy - th / 2)

    def _on_click(self, event: wx.MouseEvent) -> None:
        self._value = not self._value
        self.Refresh()
        if self._callback is not None:
            self._callback(self._value)
        event.Skip()


class DarkCombo(wx.Panel):
    """Custom-painted read-only dropdown, dark-styled."""

    _H = 28

    def __init__(self, parent: wx.Window, choices: list[str], selection: int = 0) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self._choices = choices
        self._selection = selection
        self._hovered = False
        self._callback: Callable[[str], None] | None = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(BG_ELEVATED)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_UP, self._on_click)
        self.Bind(wx.EVT_ENTER_WINDOW, lambda e: (setattr(self, "_hovered", True), self.Refresh(), e.Skip()))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: (setattr(self, "_hovered", False), self.Refresh(), e.Skip()))

    def DoGetBestSize(self) -> wx.Size:
        dc = wx.ClientDC(self)
        dc.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        max_w = max((dc.GetTextExtent(c)[0] for c in self._choices), default=60)
        return wx.Size(max_w + 40, self._H)

    def GetStringSelection(self) -> str:
        return self._choices[self._selection] if self._choices else ""

    def SetSelection(self, idx: int) -> None:
        self._selection = idx
        self.Refresh()

    def Bind(self, event, handler, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        if event == wx.EVT_CHOICE:
            self._callback = handler
        else:
            super().Bind(event, handler, source, id, id2)

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(BTN_HOVER_BG if self._hovered else BG_ELEVATED))
        gc.SetPen(wx.Pen(SEP_COLOUR, 1))
        gc.DrawRoundedRectangle(0, 0, w, h, 4)
        font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        gc.SetFont(font, FG_PRIMARY)
        label = self.GetStringSelection()
        _, th = gc.GetTextExtent(label)
        gc.DrawText(label, 8, (h - th) / 2)
        arrow_x, arrow_y = w - 16, h / 2
        gc.SetPen(wx.Pen(FG_SECONDARY, 1))
        path = gc.CreatePath()
        path.MoveToPoint(arrow_x - 4, arrow_y - 2)
        path.AddLineToPoint(arrow_x, arrow_y + 2)
        path.AddLineToPoint(arrow_x + 4, arrow_y - 2)
        gc.StrokePath(path)

    def _on_click(self, event: wx.MouseEvent) -> None:
        menu = wx.Menu()
        for i, name in enumerate(self._choices):
            item = menu.AppendRadioItem(wx.ID_ANY, name)
            if i == self._selection:
                item.Check(True)
            self.Bind(wx.EVT_MENU, lambda e, idx=i: self._select(idx), item)
        self.PopupMenu(menu)
        menu.Destroy()
        event.Skip()

    def _select(self, idx: int) -> None:
        self._selection = idx
        self.Refresh()
        if self._callback is not None:
            self._callback(self.GetStringSelection())
