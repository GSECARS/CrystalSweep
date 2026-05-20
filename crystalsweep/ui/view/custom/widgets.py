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
    BG_CARD,
    BG_ELEVATED,
    BG_SURFACE,
    BTN_HOVER_BG,
    BTN_PRESS_BG,
    DANGER,
    DANGER_HOVER,
    DANGER_PRESS,
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
    "DANGER_SCHEME",
    "DEFAULT_SCHEME",
    "MUTED_SCHEME",
    "DarkCombo",
    "DarkMenuBar",
    "DarkScrollBar",
    "DarkTextCtrl",
    "DarkToggle",
    "FlatButton",
    "FrameLabel",
    "IconButton",
    "LiveToggle",
    "RadioDot",
    "ThemedSplitter",
]


# Colour palettes for FlatButton: (idle, hover, press, foreground).
DEFAULT_SCHEME = (POPUP_BTN_BG, POPUP_BTN_HOVER, POPUP_BTN_PRESS, FG_PRIMARY)
DANGER_SCHEME = (POPUP_BTN_BG, DANGER_HOVER, DANGER_PRESS, wx.Colour(230, 90, 90))
MUTED_SCHEME = (wx.Colour(38, 38, 44), wx.Colour(55, 60, 75), wx.Colour(30, 35, 55), wx.Colour(120, 150, 190))


class FlatButton(wx.Control):
    """Flat dark button with hover/press states, used inside popups."""

    def __init__(
        self,
        parent: wx.Window,
        label: str,
        color_scheme: tuple[wx.Colour, wx.Colour, wx.Colour, wx.Colour] = DEFAULT_SCHEME,
    ) -> None:
        super().__init__(parent, style=wx.BORDER_NONE | wx.WANTS_CHARS)
        self._label = label
        self._hovered = False
        self._pressed = False
        self._action: Callable[[], None] | None = None
        self._idle_bg, self._hover_bg, self._press_bg, self._fg = color_scheme
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetMinSize((-1, 26))
        super().Bind(wx.EVT_PAINT, self._on_paint)
        super().Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        super().Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        super().Bind(wx.EVT_LEFT_DOWN, self._on_press)
        super().Bind(wx.EVT_LEFT_UP, self._on_release)

    def set_action(self, callback: Callable[[], None]) -> None:
        self._action = callback

    def SetLabel(self, label: str) -> None:
        self._label = label
        self.Refresh()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        if self._pressed:
            bg = self._press_bg
        elif self._hovered:
            bg = self._hover_bg
        else:
            bg = self._idle_bg
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(0, 0, w, h, 4)
        font = scaled_font(12)
        gc.SetFont(font, self._fg)
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
        event.Skip()
        if was_pressed and self._action is not None:
            wx.CallAfter(self._action)


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
        font = scaled_font(12, weight=wx.FONTWEIGHT_BOLD)
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
        gc.SetBrush(wx.Brush(self._idle_bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        if self._pressed:
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

    def __init__(self, parent: wx.Window, value: str = "", placeholder: str = "", parent_bg: wx.Colour | None = None) -> None:
        super().__init__(parent, style=wx.BORDER_NONE, size=wx.Size(80, 28))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._parent_bg: wx.Colour = parent_bg if parent_bg is not None else BG_SURFACE
        self._value = value
        self._placeholder = placeholder
        self._editing = False
        self._error = False
        self._disabled = False
        self._validator: Callable[[str], str] | None = None
        self._restrict_to_float = False
        self._callback_enter: Callable | None = None
        self._callback_kill: Callable | None = None
        self._font = scaled_font(12, weight=wx.FONTWEIGHT_BOLD)
        self._placeholder_font = scaled_font(12, style=wx.FONTSTYLE_ITALIC)
        self._ctrl = wx.TextCtrl(self, value=value, style=wx.TE_PROCESS_ENTER | wx.TE_CENTER | wx.BORDER_NONE)
        self._ctrl.SetBackgroundColour(BG_ELEVATED)
        self._ctrl.SetForegroundColour(FG_PRIMARY)
        self._ctrl.SetFont(self._font)
        if placeholder:
            self._ctrl.SetHint(placeholder)
        self._ctrl.EnableVisibleFocus(False)
        self._ctrl.Hide()
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._start_edit)
        self.Bind(wx.EVT_SIZE, self._on_ctrl_size)
        self._ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_enter)
        self._ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_kill)

    def set_validator(self, validator: Callable[[str], str] | None) -> None:
        """Set an optional validator called on commit."""
        self._validator = validator

    def set_restrict_to_float(self, restrict: bool) -> None:
        """When True, keystroke filtering allows only digits, one '.', and '-' at position 0."""
        if restrict and not self._restrict_to_float:
            self._ctrl.Bind(wx.EVT_CHAR, self._on_char_float)
        elif not restrict and self._restrict_to_float:
            self._ctrl.Unbind(wx.EVT_CHAR, handler=self._on_char_float)
        self._restrict_to_float = restrict

    def _on_char_float(self, event: wx.KeyEvent) -> None:
        if self._disabled:
            return
        key = event.GetKeyCode()
        char = chr(key) if 32 <= key < 127 else None

        if key < 32 or event.ControlDown():
            event.Skip()
            return

        if char is None:
            return

        current = self._ctrl.GetValue()
        insert_pos = self._ctrl.GetInsertionPoint()
        sel_from, sel_to = self._ctrl.GetSelection()
        has_selection = sel_from != sel_to
        after_replace = current[:sel_from] + current[sel_to:] if has_selection else current

        if char == "-":
            effective_pos = sel_from if has_selection else insert_pos
            if effective_pos == 0 and not after_replace.startswith("-"):
                event.Skip()
            return

        if char == ".":
            if "." not in after_replace:
                event.Skip()
            return

        if char.isdigit():
            event.Skip()
            return

    def set_error(self, error: bool) -> None:
        if error != self._error:
            self._error = error
            bg = wx.Colour(70, 28, 28) if error else BG_ELEVATED
            self._ctrl.SetBackgroundColour(bg)
            self.Refresh()

    def set_disabled(self, disabled: bool) -> None:
        if disabled == self._disabled:
            return
        self._disabled = disabled
        if disabled and self._editing:
            self._ctrl.Hide()
            self._editing = False
        self.Refresh()

    def SetPlaceholder(self, text: str) -> None:
        self._placeholder = text
        self._ctrl.SetHint(text)
        self.Refresh()

    def _on_ctrl_size(self, event: wx.SizeEvent) -> None:
        self._reposition_ctrl()
        self.Refresh()
        event.Skip()

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
        if self._disabled:
            return
        self._editing = True
        self._ctrl.SetValue(self._value)
        self._reposition_ctrl()
        self._ctrl.Show()
        self._ctrl.SetFocus()
        self._ctrl.SelectAll()
        self.Refresh()
        event.Skip()

    def _commit(self, raw: str) -> bool:
        """Validate *raw*, update internal state, and return True on success."""
        if self._validator is not None:
            try:
                canonical = self._validator(raw)
                self._value = canonical
                self._ctrl.SetValue(canonical)
                self.set_error(False)
            except Exception:
                self._ctrl.SetValue(self._value)
                self.set_error(True)
                return False
        else:
            self._value = raw
        return True

    def _on_enter(self, event: wx.Event) -> None:
        raw = self._ctrl.GetValue()
        self._commit(raw)
        self._ctrl.Hide()
        self._editing = False
        self.Refresh()
        if self._callback_enter:
            self._callback_enter(event)

    def _on_kill(self, event: wx.FocusEvent) -> None:
        raw = self._ctrl.GetValue()
        self._commit(raw)
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
        gc.SetBrush(wx.Brush(self._parent_bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        if self._disabled:
            bg = BG_SURFACE
        elif self._error:
            bg = wx.Colour(70, 28, 28)
        else:
            bg = BG_ELEVATED
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(0, 0, w, h, 3)
        if self._editing:
            return
        fg = FG_SECONDARY if self._disabled else FG_PRIMARY
        if self._value:
            gc.SetFont(self._font, fg)
            tw, th = gc.GetTextExtent(self._value)
            gc.DrawText(self._value, (w - tw) / 2, (h - th) / 2)
        elif self._placeholder and not self._disabled:
            gc.SetFont(self._placeholder_font, FG_SECONDARY)
            tw, th = gc.GetTextExtent(self._placeholder)
            gc.DrawText(self._placeholder, (w - tw) / 2, (h - th) / 2)


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
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave_toggle)
        self.Bind(wx.EVT_SIZE, self._on_size)

    def _on_enter(self, event: wx.MouseEvent) -> None:
        self._hovered = True
        self.Refresh()
        event.Skip()

    def _on_leave_toggle(self, event: wx.MouseEvent) -> None:
        self._hovered = False
        self.Refresh()
        event.Skip()

    def _on_size(self, event: wx.SizeEvent) -> None:
        self.Refresh()
        event.Skip()

    def DoGetBestSize(self) -> wx.Size:
        dc = wx.ClientDC(self)
        dc.SetFont(scaled_font(12))
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
        font = scaled_font(12)
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

    def __init__(self, parent: wx.Window, choices: list[str], selection: int = 0, choice_colours: dict[str, wx.Colour] | None = None) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self._choices = choices
        self._selection = selection
        self._hovered = False
        self._choice_colours: dict[str, wx.Colour] = choice_colours or {}
        self._callback: Callable[[str], None] | None = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(BG_ELEVATED)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_UP, self._on_click)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter_combo)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave_combo)

    def DoGetBestSize(self) -> wx.Size:
        dc = wx.ClientDC(self)
        dc.SetFont(scaled_font(12))
        max_w = max((dc.GetTextExtent(c)[0] for c in self._choices), default=60)
        return wx.Size(max_w + 40, self._H)

    def GetStringSelection(self) -> str:
        return self._choices[self._selection] if self._choices else ""

    def SetSelection(self, idx: int) -> None:
        self._selection = idx
        self.Refresh()

    def SetChoices(self, choices: list[str], selection: int = 0) -> None:
        self._choices = list(choices)
        self._selection = max(0, min(selection, len(self._choices) - 1)) if self._choices else 0
        self.InvalidateBestSize()
        self.Refresh()

    def Bind(self, event, handler, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        if event == wx.EVT_CHOICE:
            self._callback = handler
        else:
            super().Bind(event, handler, source, id, id2)

    def _on_enter_combo(self, event: wx.MouseEvent) -> None:
        self._hovered = True
        self.Refresh()
        event.Skip()

    def _on_leave_combo(self, event: wx.MouseEvent) -> None:
        self._hovered = False
        self.Refresh()
        event.Skip()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(BTN_HOVER_BG if self._hovered else BG_ELEVATED))
        gc.SetPen(wx.Pen(SEP_COLOUR, 1))
        gc.DrawRoundedRectangle(0, 0, w, h, 4)
        font = scaled_font(12)
        label = self.GetStringSelection()
        colour = self._choice_colours.get(label, FG_PRIMARY)
        gc.SetFont(font, colour)
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
        if not self._choices:
            event.Skip()
            return
        popup = _DarkMenuPopup(self, self._choices, self._selection, on_select=self._select, choice_colours=self._choice_colours)
        w, h = self.GetSize()
        popup.popup_below(self.ClientToScreen(wx.Point(0, h)), w)
        event.Skip()

    def _select(self, idx: int) -> None:
        self._selection = idx
        self.Refresh()
        if self._callback is not None:
            self._callback(self.GetStringSelection())


class _DarkMenuPopup(wx.PopupTransientWindow):
    """Dark-themed dropdown popup used by DarkCombo."""

    _ROW_H = 26

    def __init__(
        self,
        parent: wx.Window,
        choices: list[str],
        selection: int,
        on_select: Callable[[int], None],
        choice_colours: dict[str, wx.Colour] | None = None,
    ) -> None:
        super().__init__(parent, flags=wx.BORDER_SIMPLE | wx.PU_CONTAINS_CONTROLS)
        self._choices = list(choices)
        self._selection = selection
        self._hover_index = -1
        self._on_select = on_select
        self._choice_colours: dict[str, wx.Colour] = choice_colours or {}
        self.SetBackgroundColour(POPUP_BG)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)

    def popup_below(self, screen_pt: wx.Point, min_width: int) -> None:
        dc = wx.ClientDC(self)
        dc.SetFont(scaled_font(12))
        text_w = max((dc.GetTextExtent(c)[0] for c in self._choices), default=0)
        width = max(min_width, text_w + 24)
        height = self._ROW_H * len(self._choices) + 4
        self.SetSize(width, height)
        self.Position(screen_pt, (0, 0))
        self.Popup()

    def _row_at(self, y: int) -> int:
        idx = (y - 2) // self._ROW_H
        return int(idx) if 0 <= idx < len(self._choices) else -1

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(POPUP_BG))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        font = scaled_font(12)
        for i, label in enumerate(self._choices):
            y = 2 + i * self._ROW_H
            if i == self._hover_index:
                gc.SetBrush(wx.Brush(POPUP_BTN_HOVER))
                gc.SetPen(wx.TRANSPARENT_PEN)
                gc.DrawRectangle(0, y, w, self._ROW_H)
            base_colour = self._choice_colours.get(label, FG_PRIMARY)
            colour = ACCENT_HOVER if i == self._selection else base_colour
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
        if idx >= 0:
            self.Dismiss()
            wx.CallAfter(self._on_select, idx)
        else:
            event.Skip()


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

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        if self._active:
            bg = _MENU_BTN_ACTIVE
        elif self._hovered:
            bg = _MENU_BTN_HOVER
        else:
            bg = _MENU_BAR_BG
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        font = scaled_font(12)
        gc.SetFont(font, FG_PRIMARY)
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
        wx.PostEvent(self, wx.CommandEvent(wx.EVT_BUTTON.typeId, self.GetId()))
        event.Skip()


class DarkMenuBar(wx.Panel):
    """Custom dark-themed menu bar replacing the native wx.MenuBar."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, size=(-1, _MENU_BAR_H), style=wx.BORDER_NONE)
        self.SetBackgroundColour(_MENU_BAR_BG)
        self._menus: list[tuple[_DarkMenuButton, list[str | None], list[str | None], list[Callable[[], None] | None]]] = []
        self._sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self._sizer)

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
        self._sizer.Add(btn, 0, wx.EXPAND)
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
        gc.SetBrush(wx.Brush(self.GetBackgroundColour()))
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


_SB_W = 8
_SB_TRACK = wx.Colour(28, 28, 32)
_SB_THUMB = wx.Colour(70, 70, 80)
_SB_THUMB_HOVER = wx.Colour(100, 100, 115)
_SB_RADIUS = 4


class DarkScrollBar(wx.Panel):
    """Thin custom-painted vertical scrollbar matching the dark theme."""

    def __init__(self, parent: wx.Window, on_scroll: Callable[[float], None]) -> None:
        super().__init__(parent, size=(_SB_W, -1), style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(_SB_TRACK)
        self._on_scroll = on_scroll
        self._thumb_pos: float = 0.0
        self._thumb_size: float = 1.0
        self._dragging = False
        self._drag_start_y: int = 0
        self._drag_start_pos: float = 0.0
        self._hovered = False
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_mouse_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_mouse_up)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)

    def update(self, thumb_pos: float, thumb_size: float) -> None:
        self._thumb_pos = max(0.0, min(thumb_pos, 1.0 - thumb_size))
        self._thumb_size = max(0.0, min(thumb_size, 1.0))
        self.Refresh()

    @property
    def visible(self) -> bool:
        return self._thumb_size < 1.0

    def _thumb_rect(self) -> tuple[int, int, int, int]:
        _, h = self.GetClientSize()
        track_h = h - 2
        ty = 1 + int(self._thumb_pos * track_h)
        th = max(20, int(self._thumb_size * track_h))
        th = min(th, track_h - (ty - 1))
        return 1, ty, _SB_W - 2, th

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(_SB_TRACK))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        if not self.visible:
            return
        x, y, tw, th = self._thumb_rect()
        colour = _SB_THUMB_HOVER if (self._hovered or self._dragging) else _SB_THUMB
        gc.SetBrush(wx.Brush(colour))
        gc.DrawRoundedRectangle(x, y, tw, th, _SB_RADIUS)

    def _on_mouse_down(self, event: wx.MouseEvent) -> None:
        x, y, tw, th = self._thumb_rect()
        ey = event.GetY()
        if y <= ey <= y + th:
            self._dragging = True
            self._drag_start_y = ey
            self._drag_start_pos = self._thumb_pos
            self.CaptureMouse()
        else:
            _, h = self.GetClientSize()
            track_h = h - 2
            pos = max(0.0, min((ey - 1) / track_h - self._thumb_size / 2, 1.0 - self._thumb_size))
            self._thumb_pos = pos
            self.Refresh()
            self._on_scroll(self._thumb_pos)
        event.Skip()

    def _on_mouse_up(self, event: wx.MouseEvent) -> None:
        if self._dragging and self.HasCapture():
            self.ReleaseMouse()
        self._dragging = False
        self.Refresh()
        event.Skip()

    def _on_motion(self, event: wx.MouseEvent) -> None:
        if self._dragging:
            _, h = self.GetClientSize()
            track_h = h - 2
            dy = event.GetY() - self._drag_start_y
            pos = max(0.0, min(self._drag_start_pos + dy / track_h, 1.0 - self._thumb_size))
            self._thumb_pos = pos
            self.Refresh()
            self._on_scroll(self._thumb_pos)
        else:
            x, y, tw, th = self._thumb_rect()
            hovered = y <= event.GetY() <= y + th
            if hovered != self._hovered:
                self._hovered = hovered
                self.Refresh()
        event.Skip()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        if self._hovered:
            self._hovered = False
            self.Refresh()
        event.Skip()


_SASH_COLOUR = wx.Colour(60, 60, 65)
_SASH_HOVER_COLOUR = wx.Colour(90, 90, 100)


class ThemedSplitter(wx.SplitterWindow):
    """SplitterWindow with a dark-themed sash overlay panel and hover highlight."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=wx.SP_LIVE_UPDATE)
        self._overlay = wx.Panel(self, style=wx.BORDER_NONE)
        self._overlay.SetBackgroundColour(_SASH_COLOUR)
        self._overlay.SetCursor(wx.Cursor(wx.CURSOR_SIZEWE))
        self._overlay.Bind(wx.EVT_ENTER_WINDOW, self._on_sash_enter)
        self._overlay.Bind(wx.EVT_LEAVE_WINDOW, self._on_sash_leave)
        self._overlay.Bind(wx.EVT_LEFT_DOWN, self._on_sash_down)
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self._reposition_overlay)
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGING, self._reposition_overlay)
        self.Bind(wx.EVT_SIZE, self._reposition_overlay)

    def _reposition_overlay(self, event: wx.Event | None = None) -> None:
        if event is not None:
            event.Skip()
        pos = self.GetSashPosition()
        if pos <= 0:
            self._overlay.Hide()
            return
        _, h = self.GetClientSize()
        sash_w = self.GetSashSize()
        self._overlay.SetSize(pos, 0, sash_w, h)
        self._overlay.Raise()
        self._overlay.Show()

    def _on_sash_enter(self, event: wx.MouseEvent) -> None:
        self._overlay.SetBackgroundColour(_SASH_HOVER_COLOUR)
        self._overlay.Refresh()
        event.Skip()

    def _on_sash_leave(self, event: wx.MouseEvent) -> None:
        self._overlay.SetBackgroundColour(_SASH_COLOUR)
        self._overlay.Refresh()
        event.Skip()

    def _on_sash_down(self, event: wx.MouseEvent) -> None:
        pt = self._overlay.ClientToScreen(event.GetPosition())
        pt = self.ScreenToClient(pt)
        new_event = wx.MouseEvent(wx.wxEVT_LEFT_DOWN)
        new_event.SetPosition(pt)
        wx.PostEvent(self, new_event)
        event.Skip()
