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

from wxutils import FlatButton
from crystalsweep.ui.view.custom.theme import (
    ACCENT,
    ACCENT_HOVER,
    BG_CARD,
    BG_ELEVATED,
    BG_SURFACE,
    BTN_DISABLED,
    btn_font,
    BTN_HOVER_BG,
    BTN_PRESS_BG,
    DANGER,
    DANGER_HOVER,
    DANGER_PRESS,
    DANGER_SCHEME,
    DEFAULT_SCHEME,
    DISABLED_BG,
    DISABLED_FG,
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
    scaled_font,
)

__all__ = [
    "DarkAbortingDialog",
    "DarkConfirmDialog",
    "DarkMenuBar",
    "DarkMessageDialog",
    "DarkTabbedPanel",
    "IconButton",
    "LiveToggle",
    "RadioDot",
    "ReadbackBox",
]


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
        super().Bind(wx.EVT_SIZE, lambda e: (self.Refresh(), e.Skip()))
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
        gc.SetBrush(wx.Brush(BG_SURFACE))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        colour = (LIVE_ON_HOVER if self._hovered else LIVE_ON) if self._live else (LIVE_OFF_HOVER if self._hovered else LIVE_OFF)
        gc.SetPen(wx.Pen(colour, 1))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRoundedRectangle(1, 1, w - 2, h - 2, 3)
        font = scaled_font(10, weight=wx.FONTWEIGHT_BOLD)
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

    def __init__(self, parent: wx.Window, draw_fn: Callable, size: int = ICON_SIZE, tooltip: str = "", bg: wx.Colour | None = None) -> None:
        super().__init__(parent, size=wx.Size(size + 8, size + 8), style=wx.BORDER_NONE)
        self._draw_fn = draw_fn
        self._icon_size = size
        self._hovered = False
        self._pressed = False
        self._idle_bg: wx.Colour = bg if bg is not None else wx.Colour(0, 0, 0)
        self._callback: Callable[[wx.CommandEvent], None] | None = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        if tooltip:
            self.SetToolTip(tooltip)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, self._on_size)
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

    def _on_size(self, event: wx.SizeEvent) -> None:
        self.Refresh()
        event.Skip()

    def Enable(self, enable: bool = True) -> bool:
        result = super().Enable(enable)
        self.Refresh()
        return result

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        enabled = self.IsEnabled()
        gc.SetBrush(wx.Brush(self._idle_bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        if not enabled:
            bg = self._idle_bg
        elif self._pressed:
            bg = BTN_PRESS_BG
        elif self._hovered:
            bg = BTN_HOVER_BG
        else:
            bg = self._idle_bg
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(0, 0, w, h, 4)
        gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
        offset = (w - self._icon_size) / 2
        gc.Translate(offset, offset)
        if not enabled:
            gc.BeginLayer(0.25)
        self._draw_fn(gc, self._icon_size)
        if not enabled:
            gc.EndLayer()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        self.set_hovered(False)
        event.Skip()

    def _on_motion(self, event: wx.MouseEvent) -> None:
        self.set_hovered(wx.Rect(0, 0, *self.GetClientSize()).Contains(event.GetPosition()))
        event.Skip()

    def _on_press(self, event: wx.MouseEvent) -> None:
        if not self.IsEnabled():
            return
        self._pressed = True
        self.Refresh()
        event.Skip()

    def _on_release(self, event: wx.MouseEvent) -> None:
        if not self.IsEnabled():
            return
        if self._pressed:
            self._pressed = False
            self.Refresh()
            if self._callback is not None:
                evt = wx.CommandEvent()
                evt.SetEventType(wx.EVT_BUTTON.typeId)
                self._callback(evt)
        event.Skip()


class _DarkMenuPopup(wx.PopupTransientWindow):
    """Dark-themed dropdown popup used by DarkCombo — scrollable for long lists."""

    _ROW_H = 26
    _MAX_VISIBLE = 16

    def __init__(
        self,
        parent: wx.Window,
        choices: list[str],
        selection: int,
        on_select: Callable[[int], None],
        choice_colours: dict[str, wx.Colour] | None = None,
    ) -> None:
        super().__init__(parent, wx.BORDER_SIMPLE)
        self._choices = list(choices)
        self._selection = selection
        self._hover_index = -1
        self._scroll_offset = 0
        self._visible_rows = min(self._MAX_VISIBLE, len(self._choices))
        self._on_select = on_select
        self._choice_colours: dict[str, wx.Colour] = choice_colours or {}
        self._dismissed = False
        self.SetBackgroundColour(POPUP_BG)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)
        self.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)

    def popup_below(self, screen_pt: wx.Point, min_width: int) -> None:
        dc = wx.ClientDC(self)
        dc.SetFont(scaled_font(12))
        text_w = max((dc.GetTextExtent(c)[0] for c in self._choices), default=0)
        width = max(min_width, text_w + 24)
        height = self._ROW_H * self._visible_rows + 4
        self.SetSize(width, height)
        self._scroll_to(self._selection)
        self.SetPosition(screen_pt)
        self.Popup()

    def _scroll_to(self, idx: int) -> None:
        if idx < 0:
            return
        if idx < self._scroll_offset:
            self._scroll_offset = idx
        elif idx >= self._scroll_offset + self._visible_rows:
            self._scroll_offset = idx - self._visible_rows + 1
        self._scroll_offset = max(0, min(self._scroll_offset, max(0, len(self._choices) - self._visible_rows)))

    def _row_at(self, y: int) -> int:
        idx = self._scroll_offset + (y - 2) // self._ROW_H
        return int(idx) if 0 <= idx < len(self._choices) else -1

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(POPUP_BG))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        font = scaled_font(12)
        for slot in range(self._visible_rows):
            i = self._scroll_offset + slot
            if i >= len(self._choices):
                break
            label = self._choices[i]
            y = 2 + slot * self._ROW_H
            if i == self._hover_index:
                gc.SetBrush(wx.Brush(POPUP_BTN_HOVER))
                gc.SetPen(wx.TRANSPARENT_PEN)
                gc.DrawRectangle(0, y, w, self._ROW_H)
            colour = self._choice_colours.get(label, FG_PRIMARY)
            gc.SetFont(font, colour)
            _, th = gc.GetTextExtent(label)
            gc.DrawText(label, 10, y + (self._ROW_H - th) / 2)

    def _on_motion(self, event: wx.MouseEvent) -> None:
        idx = self._row_at(event.GetY())
        if idx != self._hover_index:
            self._hover_index = idx
            self.Refresh()
        event.Skip()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        if self._hover_index != -1:
            self._hover_index = -1
            self.Refresh()
        event.Skip()

    def _on_left_up(self, event: wx.MouseEvent) -> None:
        idx = self._row_at(event.GetY())
        if idx >= 0 and not self._dismissed:
            self._dismissed = True
            self.Dismiss()
            wx.CallAfter(self._on_select, idx)

    def ProcessLeftDown(self, event: wx.MouseEvent) -> bool:
        return False

    def _on_wheel(self, event: wx.MouseEvent) -> None:
        delta = -1 if event.GetWheelRotation() > 0 else 1
        new_offset = max(0, min(self._scroll_offset + delta, max(0, len(self._choices) - self._visible_rows)))
        if new_offset != self._scroll_offset:
            self._scroll_offset = new_offset
            self._hover_index = -1
            self.Refresh()


_MENU_BAR_H = 28
_MENU_BAR_BG = wx.Colour(24, 24, 26)
_MENU_BTN_HOVER = wx.Colour(50, 50, 56)
_MENU_BTN_ACTIVE = wx.Colour(60, 60, 68)
_MENU_SEP = wx.Colour(55, 55, 62)
_MENU_ITEM_H = 26
_MENU_SEP_H = 9


class _DarkMenuDropdown(wx.PopupTransientWindow):
    """Dark dropdown for DarkMenuBar items, supports separator (None) entries."""

    def __init__(
        self,
        parent: wx.Window,
        items: list[str | None],
        shortcuts: list[str | None],
        on_select: Callable[[int], None],
    ) -> None:
        super().__init__(parent, flags=wx.BORDER_SIMPLE | wx.PU_CONTAINS_CONTROLS)
        self._items = items
        self._shortcuts = shortcuts
        self._on_select = on_select
        self._hover_index: int = -1
        self.SetBackgroundColour(POPUP_BG)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)

    def _row_height(self, i: int) -> int:
        return _MENU_SEP_H if self._items[i] is None else _MENU_ITEM_H

    def _row_y(self, target: int) -> int:
        y = 4
        for i in range(target):
            y += self._row_height(i)
        return y

    def _index_at(self, py: int) -> int:
        y = 4
        for i, item in enumerate(self._items):
            h = self._row_height(i)
            if item is not None and y <= py < y + h:
                return i
            y += h
        return -1

    def popup_below(self, screen_pt: wx.Point) -> None:
        dc = wx.ClientDC(self)
        dc.SetFont(scaled_font(12))
        items = [i for i in self._items if i is not None]
        shortcuts = [s for s in self._shortcuts if s is not None]
        label_w = max((dc.GetTextExtent(i)[0] for i in items), default=0)
        short_w = max((dc.GetTextExtent(s)[0] for s in shortcuts), default=0) if shortcuts else 0
        width = label_w + short_w + (48 if short_w else 24)
        height = 8 + sum(self._row_height(i) for i in range(len(self._items)))
        self.SetSize(max(160, width), height)
        self.Position(screen_pt, (0, 0))
        self.Popup()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(POPUP_BG))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        font = scaled_font(12)
        shortcut_font = scaled_font(11)
        y = 4
        for i, item in enumerate(self._items):
            rh = self._row_height(i)
            if item is None:
                cy = y + rh / 2
                gc.SetPen(wx.Pen(_MENU_SEP, 1))
                gc.StrokeLine(8, cy, w - 8, cy)
            else:
                if i == self._hover_index:
                    gc.SetBrush(wx.Brush(POPUP_BTN_HOVER))
                    gc.SetPen(wx.TRANSPARENT_PEN)
                    gc.DrawRectangle(0, y, w, rh)
                gc.SetFont(font, FG_PRIMARY)
                _, th = gc.GetTextExtent(item)
                gc.DrawText(item, 12, y + (rh - th) / 2)
                sc = self._shortcuts[i]
                if sc:
                    gc.SetFont(shortcut_font, FG_SECONDARY)
                    sw, _ = gc.GetTextExtent(sc)
                    gc.DrawText(sc, w - sw - 12, y + (rh - th) / 2)
            y += rh

    def _on_motion(self, event: wx.MouseEvent) -> None:
        idx = self._index_at(event.GetY())
        if idx != self._hover_index:
            self._hover_index = idx
            self.Refresh()
        event.Skip()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        if self._hover_index != -1:
            self._hover_index = -1
            self.Refresh()
        event.Skip()

    def _on_left_up(self, event: wx.MouseEvent) -> None:
        idx = self._index_at(event.GetY())
        if idx >= 0:
            self.Dismiss()
            wx.CallAfter(self._on_select, idx)
        else:
            event.Skip()


class _DarkMenuButton(wx.Control):
    """Single menu title button in the DarkMenuBar."""

    def __init__(self, parent: wx.Window, label: str) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self._label = label
        self._hovered = False
        self._active = False
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, lambda e: (self.Refresh(), e.Skip()))
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_press)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.Refresh()

    def DoGetBestSize(self) -> wx.Size:
        dc = wx.ClientDC(self)
        dc.SetFont(scaled_font(12))
        tw, _ = dc.GetTextExtent(self._label)
        return wx.Size(tw + 20, _MENU_BAR_H)

    def Enable(self, enable: bool = True) -> bool:
        result = super().Enable(enable)
        self.Refresh()
        return result

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        enabled = self.IsEnabled()
        if not enabled:
            bg = _MENU_BAR_BG
        elif self._active:
            bg = _MENU_BTN_ACTIVE
        elif self._hovered:
            bg = _MENU_BTN_HOVER
        else:
            bg = _MENU_BAR_BG
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        font = scaled_font(12)
        gc.SetFont(font, DISABLED_FG if not enabled else FG_SECONDARY)
        tw, th = gc.GetTextExtent(self._label)
        gc.DrawText(self._label, (w - tw) / 2, (h - th) / 2)

    def _on_enter(self, event: wx.MouseEvent) -> None:
        self._hovered = True
        self.Refresh()
        event.Skip()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        self._hovered = False
        self.Refresh()
        event.Skip()

    def _on_press(self, event: wx.MouseEvent) -> None:
        if not self.IsEnabled():
            return
        wx.PostEvent(self, wx.CommandEvent(wx.EVT_BUTTON.typeId, self.GetId()))
        event.Skip()


class DarkMenuBar(wx.Panel):
    """Custom dark-themed menu bar replacing the native wx.MenuBar."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, size=(-1, _MENU_BAR_H), style=wx.BORDER_NONE)
        self.SetBackgroundColour(_MENU_BAR_BG)
        self._menus: list[tuple[_DarkMenuButton, list[str | None], list[str | None], list[Callable[[], None] | None]]] = []
        self._btn_count: int = 0
        self._sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._config_prefix = wx.StaticText(self, label="")
        self._config_prefix.SetBackgroundColour(_MENU_BAR_BG)
        self._config_prefix.SetForegroundColour(FG_SECONDARY)
        self._config_prefix.SetFont(scaled_font(11))
        self._config_name = wx.StaticText(self, label="")
        self._config_name.SetBackgroundColour(_MENU_BAR_BG)
        self._config_name.SetForegroundColour(ACCENT)
        self._config_name.SetFont(scaled_font(11))
        self._epics_prefix_label = wx.StaticText(self, label="")
        self._epics_prefix_label.SetBackgroundColour(_MENU_BAR_BG)
        self._epics_prefix_label.SetForegroundColour(FG_SECONDARY)
        self._epics_prefix_label.SetFont(scaled_font(11))
        self._epics_value_label = wx.StaticText(self, label="")
        self._epics_value_label.SetBackgroundColour(_MENU_BAR_BG)
        self._epics_value_label.SetFont(scaled_font(11))
        self._sizer.AddStretchSpacer(1)
        self._sizer.Add(self._epics_prefix_label, 0, wx.ALIGN_CENTER_VERTICAL)
        self._sizer.Add(self._epics_value_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        self._sizer.Add(self._config_prefix, 0, wx.ALIGN_CENTER_VERTICAL)
        self._sizer.Add(self._config_name, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        self.SetSizer(self._sizer)

    def Enable(self, enable: bool = True) -> bool:
        for btn, _, _, _ in self._menus:
            btn.Enable(enable)
        return True

    def set_config_name(self, name: str) -> None:
        """Update the active configuration name shown on the right of the menu bar."""
        self._config_prefix.SetLabel("Active config: ")
        self._config_name.SetLabel(name)
        self.Layout()

    def set_epics_status(self, online: bool) -> None:
        """Update the EPICS connectivity indicator in the menu bar."""
        self._epics_prefix_label.SetLabel("EPICS: ")
        self._epics_value_label.SetLabel("Online" if online else "Offline")
        self._epics_value_label.SetForegroundColour(PONI_LOADED if online else DANGER)
        self._epics_value_label.Refresh()
        self.Layout()

    def append_menu(
        self,
        title: str,
        items: list[str | None],
        shortcuts: list[str | None],
        callbacks: list[Callable[[], None] | None],
    ) -> None:
        btn = _DarkMenuButton(self, title)
        idx = len(self._menus)
        btn.Bind(wx.EVT_BUTTON, lambda e, i=idx: self._open_menu(i))
        self._menus.append((btn, items, shortcuts, callbacks))
        self._sizer.Insert(self._btn_count, btn, 0, wx.EXPAND)
        self._btn_count += 1
        self.Layout()

    def append_action(self, title: str, callback: Callable[[], None]) -> None:
        """Add a menu button that fires callback directly on click (no dropdown)."""
        btn = _DarkMenuButton(self, title)

        def _on_click(_event: wx.CommandEvent) -> None:
            btn.set_active(True)
            callback()
            btn.set_active(False)

        btn.Bind(wx.EVT_BUTTON, _on_click)
        self._menus.append((btn, [], [], []))
        self._sizer.Insert(self._btn_count, btn, 0, wx.EXPAND)
        self._btn_count += 1
        self.Layout()

    def _open_menu(self, menu_idx: int) -> None:
        btn, items, shortcuts, callbacks = self._menus[menu_idx]
        btn.set_active(True)

        def on_select(item_idx: int) -> None:
            btn.set_active(False)
            cb = callbacks[item_idx]
            if cb is not None:
                cb()

        def on_dismiss() -> None:
            btn.set_active(False)

        popup = _DarkMenuDropdown(self, items, shortcuts, on_select)
        popup.Bind(wx.EVT_SHOW, lambda e: on_dismiss() if not e.IsShown() else None)
        pos = btn.ClientToScreen(wx.Point(0, btn.GetSize().height))
        popup.popup_below(pos)


class RadioDot(wx.Panel):
    """Small dark-styled radio indicator. Click toggles to selected and fires the callback."""

    _SIZE = 16

    def __init__(self, parent: wx.Window, value: bool = False, tooltip: str = "") -> None:
        super().__init__(parent, size=wx.Size(self._SIZE + 8, self._SIZE + 8), style=wx.BORDER_NONE)
        self._value = value
        self._hovered = False
        self._callback: Callable[[], None] | None = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(BG_CARD)
        if tooltip:
            self.SetToolTip(tooltip)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, lambda e: (self.Refresh(), e.Skip()))
        self.Bind(wx.EVT_LEFT_UP, self._on_click)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter_dot)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave_dot)

    def set_value(self, value: bool) -> None:
        if value != self._value:
            self._value = value
            self.Refresh()

    def get_value(self) -> bool:
        return self._value

    def set_action(self, callback: Callable[[], None]) -> None:
        self._callback = callback

    def _on_enter_dot(self, event: wx.MouseEvent) -> None:
        self._hovered = True
        self.Refresh()
        event.Skip()

    def _on_leave_dot(self, event: wx.MouseEvent) -> None:
        self._hovered = False
        self.Refresh()
        event.Skip()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(BG_CARD))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        cx, cy = w / 2, h / 2
        r = self._SIZE / 2
        ring = ACCENT_HOVER if (self._value or self._hovered) else FG_SECONDARY
        gc.SetPen(wx.Pen(ring, 2))
        gc.SetBrush(wx.Brush(BG_ELEVATED))
        gc.DrawEllipse(cx - r, cy - r, self._SIZE, self._SIZE)
        if self._value:
            inner = self._SIZE * 0.45
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.SetBrush(wx.Brush(ACCENT_HOVER))
            gc.DrawEllipse(cx - inner / 2, cy - inner / 2, inner, inner)

    def _on_click(self, event: wx.MouseEvent) -> None:
        if not self._value:
            self._value = True
            self.Refresh()
            if self._callback is not None:
                self._callback()
        event.Skip()


class ReadbackBox(wx.Control):
    """Dark-styled read-only value display with text centred on both axes."""

    def __init__(self, parent: wx.Window, height: int = 28) -> None:
        super().__init__(parent, size=wx.Size(-1, height), style=wx.BORDER_NONE)
        self._text = ""
        self._font = scaled_font(12, weight=wx.FONTWEIGHT_BOLD)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        super().Bind(wx.EVT_PAINT, self._on_paint)
        super().Bind(wx.EVT_SIZE, lambda e: (self.Refresh(), e.Skip()))

    def set_text(self, text: str) -> None:
        self._text = text
        self.Refresh()

    def get_text(self) -> str:
        return self._text

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(DISABLED_BG))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(0, 0, w, h, 3)
        if not self._text:
            return
        gc.SetFont(self._font, DISABLED_FG)
        tw, th = gc.GetTextExtent(self._text)
        gc.DrawText(self._text, (w - tw) / 2, (h - th) / 2)


class DarkAbortingDialog(wx.Dialog):
    """Dark-themed dialog shown while a collection is aborting.

    Blocks the rest of the application until the user clicks OK.
    Call *ready()* from the main thread once cleanup is complete to
    enable the OK button.
    """

    def __init__(self, parent: wx.Window, elapsed: str = "") -> None:
        super().__init__(
            parent,
            title="Collection Aborted",
            style=wx.DEFAULT_DIALOG_STYLE & ~wx.CLOSE_BOX,
        )
        self.SetBackgroundColour(BG_SURFACE)

        outer = wx.BoxSizer(wx.VERTICAL)

        title_label = wx.StaticText(self, label="Collection aborted")
        title_label.SetForegroundColour(DANGER)
        title_label.SetBackgroundColour(BG_SURFACE)
        title_label.SetFont(scaled_font(13, weight=wx.FONTWEIGHT_BOLD))
        outer.Add(title_label, 0, wx.LEFT | wx.TOP | wx.RIGHT, 20)

        lines = ["The collection was aborted. Motors are being restored,"]
        lines.append("the detector is being stopped, and abort PVs are being written.")
        if elapsed:
            lines.append(f"\nElapsed time: {elapsed}")
        self._status_label = wx.StaticText(self, label="\nCleaning up, please wait…")
        self._status_label.SetForegroundColour(FG_SECONDARY)
        self._status_label.SetBackgroundColour(BG_SURFACE)
        self._status_label.SetFont(scaled_font(12))
        msg_label = wx.StaticText(self, label="\n".join(lines))
        msg_label.SetForegroundColour(FG_SECONDARY)
        msg_label.SetBackgroundColour(BG_SURFACE)
        msg_label.SetFont(scaled_font(12))
        msg_label.Wrap(400)
        outer.Add(msg_label, 0, wx.LEFT | wx.RIGHT, 20)
        outer.Add(self._status_label, 0, wx.LEFT | wx.BOTTOM | wx.RIGHT, 20)

        sep = wx.Panel(self, size=(-1, 1))
        sep.SetBackgroundColour(SEP_COLOUR)
        outer.Add(sep, 0, wx.EXPAND)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        self._ok_btn = FlatButton(self, "OK", color_scheme=DEFAULT_SCHEME, disabled_scheme=BTN_DISABLED, font=btn_font())
        self._ok_btn.SetMinSize((80, 28))
        self._ok_btn.Enable(False)
        self._ok_btn.SetAction(self._on_ok)
        btn_sizer.Add(self._ok_btn, 0, wx.ALL, 8)
        outer.Add(btn_sizer, 0, wx.EXPAND)

        self.SetSizer(outer)
        self.Fit()
        self.CentreOnParent()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_CLOSE, lambda e: None)
        if parent:
            parent.Enable(False)

    def _on_ok(self, _e=None) -> None:
        parent = self.GetParent()
        if parent:
            parent.Enable(True)
            parent.Raise()
        self.Destroy()

    def _on_key(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_ESCAPE) and self._ok_btn.IsEnabled():
            self._on_ok()
        else:
            event.Skip()

    def ready(self) -> None:
        """Enable the OK button once cleanup is complete."""
        if self:
            self._status_label.SetLabel("\nCleanup complete.")
            self._ok_btn.Enable(True)
            self._ok_btn.SetFocus()


class DarkMessageDialog(wx.Dialog):
    """Dark-themed single-button message dialog (OK only)."""

    def __init__(self, parent: wx.Window, message: str, title: str) -> None:
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)
        self.SetBackgroundColour(BG_SURFACE)

        outer = wx.BoxSizer(wx.VERTICAL)

        msg_label = wx.StaticText(self, label=message)
        msg_label.SetForegroundColour(FG_PRIMARY)
        msg_label.SetBackgroundColour(BG_SURFACE)
        msg_label.SetFont(scaled_font(12))
        msg_label.Wrap(380)
        outer.Add(msg_label, 0, wx.ALL, 20)

        sep = wx.Panel(self, size=(-1, 1))
        sep.SetBackgroundColour(SEP_COLOUR)
        outer.Add(sep, 0, wx.EXPAND)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        btn_ok = FlatButton(self, "OK", color_scheme=DEFAULT_SCHEME, disabled_scheme=BTN_DISABLED, font=btn_font())
        btn_ok.SetMinSize((80, 28))
        btn_ok.SetAction(lambda _e: self.EndModal(wx.ID_OK))
        btn_sizer.Add(btn_ok, 0, wx.ALL, 8)
        outer.Add(btn_sizer, 0, wx.EXPAND)

        self.SetSizer(outer)
        self.Fit()
        self.CentreOnParent()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _on_key(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_ESCAPE):
            self.EndModal(wx.ID_OK)
        else:
            event.Skip()


class DarkConfirmDialog(wx.Dialog):
    """Dark-themed Yes/No confirmation dialog."""

    def __init__(self, parent: wx.Window, message: str, title: str) -> None:
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)
        self.SetBackgroundColour(BG_SURFACE)

        outer = wx.BoxSizer(wx.VERTICAL)

        msg_label = wx.StaticText(self, label=message)
        msg_label.SetForegroundColour(FG_PRIMARY)
        msg_label.SetBackgroundColour(BG_SURFACE)
        msg_label.SetFont(scaled_font(12))
        msg_label.Wrap(380)
        outer.Add(msg_label, 0, wx.ALL, 20)

        sep = wx.Panel(self, size=(-1, 1))
        sep.SetBackgroundColour(SEP_COLOUR)
        outer.Add(sep, 0, wx.EXPAND)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()

        btn_yes = FlatButton(self, "Yes", color_scheme=DANGER_SCHEME, disabled_scheme=BTN_DISABLED, font=btn_font())
        btn_yes.SetAction(lambda _e: self.EndModal(wx.ID_YES))
        btn_yes.SetMinSize((80, 28))

        btn_no = FlatButton(self, "No", color_scheme=DEFAULT_SCHEME, disabled_scheme=BTN_DISABLED, font=btn_font())
        btn_no.SetAction(lambda _e: self.EndModal(wx.ID_NO))
        btn_no.SetMinSize((80, 28))

        btn_sizer.Add(btn_yes, 0, wx.ALL, 8)
        btn_sizer.Add(btn_no, 0, wx.TOP | wx.BOTTOM | wx.RIGHT, 8)
        outer.Add(btn_sizer, 0, wx.EXPAND)

        self.SetSizer(outer)
        self.Fit()
        self.CentreOnParent()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _on_key(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_NO)
        else:
            event.Skip()


_TAB_BAR_H = 30
_TAB_PAD_X = 14
_TAB_BG = BG_CARD
_TAB_INACTIVE_FG = FG_SECONDARY
_TAB_ACTIVE_FG = FG_PRIMARY
_TAB_HOVER_BG = wx.Colour(40, 40, 46)
_TAB_ACTIVE_BG = BG_ELEVATED
_TAB_UNDERLINE = ACCENT


class _DarkTabBar(wx.Control):
    """Header strip that renders tab labels for DarkTabbedPanel."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self._labels: list[str] = []
        self._selection: int = 0
        self._hover: int = -1
        self._on_select: Callable[[int], None] | None = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(_TAB_BG)
        self.SetMinSize((-1, _TAB_BAR_H))
        super().Bind(wx.EVT_PAINT, self._on_paint)
        super().Bind(wx.EVT_SIZE, lambda e: (self.Refresh(), e.Skip()))
        super().Bind(wx.EVT_MOTION, self._on_motion)
        super().Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        super().Bind(wx.EVT_LEFT_UP, self._on_click)

    def set_labels(self, labels: list[str]) -> None:
        self._labels = list(labels)
        self.Refresh()

    def set_selection(self, idx: int) -> None:
        if 0 <= idx < len(self._labels):
            self._selection = idx
            self.Refresh()

    def set_on_select(self, callback: Callable[[int], None]) -> None:
        self._on_select = callback

    def _tab_rects(self) -> list[tuple[int, int, int, int]]:
        dc = wx.ClientDC(self)
        dc.SetFont(scaled_font(12, weight=wx.FONTWEIGHT_BOLD))
        _, h = self.GetClientSize()
        rects: list[tuple[int, int, int, int]] = []
        x = 0
        for label in self._labels:
            tw, _ = dc.GetTextExtent(label)
            w = tw + _TAB_PAD_X * 2
            rects.append((x, 0, w, h))
            x += w
        return rects

    def _index_at(self, px: int, py: int) -> int:
        for i, (x, y, w, h) in enumerate(self._tab_rects()):
            if x <= px < x + w and y <= py < y + h:
                return i
        return -1

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(_TAB_BG))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        font = scaled_font(12, weight=wx.FONTWEIGHT_BOLD)
        for i, (tx, ty, tw, th) in enumerate(self._tab_rects()):
            active = i == self._selection
            hovered = i == self._hover
            if active:
                bg = _TAB_ACTIVE_BG
            elif hovered:
                bg = _TAB_HOVER_BG
            else:
                bg = _TAB_BG
            gc.SetBrush(wx.Brush(bg))
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.DrawRectangle(tx, ty, tw, th)
            fg = _TAB_ACTIVE_FG if active or hovered else _TAB_INACTIVE_FG
            gc.SetFont(font, fg)
            label = self._labels[i]
            ltw, lth = gc.GetTextExtent(label)
            gc.DrawText(label, tx + (tw - ltw) / 2, (th - lth) / 2)
            if active:
                gc.SetBrush(wx.Brush(_TAB_UNDERLINE))
                gc.DrawRectangle(tx, th - 2, tw, 2)
        gc.SetPen(wx.Pen(SEP_COLOUR, 1))
        gc.StrokeLine(0, h - 1, w, h - 1)

    def _on_motion(self, event: wx.MouseEvent) -> None:
        idx = self._index_at(event.GetX(), event.GetY())
        if idx != self._hover:
            self._hover = idx
            self.Refresh()
        event.Skip()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        if self._hover != -1:
            self._hover = -1
            self.Refresh()
        event.Skip()

    def _on_click(self, event: wx.MouseEvent) -> None:
        idx = self._index_at(event.GetX(), event.GetY())
        if idx >= 0 and idx != self._selection:
            self._selection = idx
            self.Refresh()
            if self._on_select is not None:
                self._on_select(idx)
        event.Skip()


class DarkTabbedPanel(wx.Panel):
    """Dark-themed tabbed container. Pages are created via add_page()."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundColour(BG_CARD)
        self._tab_bar = _DarkTabBar(self)
        self._tab_bar.set_on_select(self._on_tab_selected)
        self._content = wx.Panel(self)
        self._content.SetBackgroundColour(BG_CARD)
        self._content_sizer = wx.BoxSizer(wx.VERTICAL)
        self._content.SetSizer(self._content_sizer)
        self._pages: list[tuple[str, wx.Window]] = []
        self._selection: int = -1
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._tab_bar, 0, wx.EXPAND)
        sizer.Add(self._content, 1, wx.EXPAND)
        self.SetSizer(sizer)

    def add_page(self, label: str, page: wx.Window) -> None:
        page.Reparent(self._content)
        self._pages.append((label, page))
        self._content_sizer.Add(page, 1, wx.EXPAND)
        self._tab_bar.set_labels([lbl for lbl, _ in self._pages])
        if self._selection == -1:
            self.set_selection(0)
        else:
            page.Show(False)
            self._content.Layout()

    def set_selection(self, idx: int) -> None:
        if not (0 <= idx < len(self._pages)) or idx == self._selection:
            return
        self._selection = idx
        for i, (_, page) in enumerate(self._pages):
            page.Show(i == idx)
        self._tab_bar.set_selection(idx)
        self._content.Layout()

    def get_page(self, idx: int) -> wx.Window:
        return self._pages[idx][1]

    def _on_tab_selected(self, idx: int) -> None:
        self.set_selection(idx)
