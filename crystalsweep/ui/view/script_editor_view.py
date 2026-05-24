#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/script_editor_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# Modal dialog for editing hooks.py (pre_scan + post_scan) with Python syntax
# highlighting via wx.stc (Scintilla) and a styled dark scrollbar.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable

import wx
import wx.stc as stc

from crystalsweep.ui.view.custom.theme import (
    BG_ELEVATED,
    BG_SURFACE,
    DANGER,
    FG_PRIMARY,
    FG_SECONDARY,
    PONI_LOADED,
    SEP_COLOUR,
    scaled_font,
)
from crystalsweep.ui.view.custom.widgets import DarkHScrollBar, DarkScrollBar, FlatButton

_SB_W = 8
_SB_TRACK = wx.Colour(28, 28, 32)

__all__ = ["ScriptEditorDialog"]

_EDITOR_BG       = wx.Colour(28, 28, 32)
_EDITOR_FG       = wx.Colour(220, 220, 228)
_GUTTER_BG       = wx.Colour(22, 22, 26)
_GUTTER_FG       = wx.Colour(90, 90, 100)
_CARET           = wx.Colour(220, 220, 228)
_SEL_BG          = wx.Colour(50, 80, 120)
_KEYWORD_FG      = wx.Colour(86, 156, 214)
_KEYWORD2_FG     = wx.Colour(78, 201, 176)
_STRING_FG       = wx.Colour(206, 145, 120)
_COMMENT_FG      = wx.Colour(106, 153, 85)
_NUMBER_FG       = wx.Colour(181, 206, 168)
_OPERATOR_FG     = wx.Colour(212, 212, 212)
_DECORATOR_FG    = wx.Colour(220, 220, 100)
_DEFNAME_FG      = wx.Colour(220, 220, 170)

_MONO_FACE = "Consolas" if wx.Platform == "__WXMSW__" else "Menlo"
_FONT_SIZE = 11


def _apply_python_highlighting(ed: stc.StyledTextCtrl) -> None:
    ed.SetLexer(stc.STC_LEX_PYTHON)

    ed.StyleSetBackground(stc.STC_STYLE_DEFAULT, _EDITOR_BG)
    ed.StyleSetForeground(stc.STC_STYLE_DEFAULT, _EDITOR_FG)
    ed.StyleSetFaceName(stc.STC_STYLE_DEFAULT, _MONO_FACE)
    ed.StyleSetSize(stc.STC_STYLE_DEFAULT, _FONT_SIZE)
    ed.StyleClearAll()

    ed.StyleSetBackground(stc.STC_STYLE_LINENUMBER, _GUTTER_BG)
    ed.StyleSetForeground(stc.STC_STYLE_LINENUMBER, _GUTTER_FG)
    ed.StyleSetFaceName(stc.STC_STYLE_LINENUMBER, _MONO_FACE)
    ed.StyleSetSize(stc.STC_STYLE_LINENUMBER, _FONT_SIZE - 1)

    def _s(num, fg, bold=False):
        ed.StyleSetForeground(num, fg)
        ed.StyleSetBackground(num, _EDITOR_BG)
        if bold:
            ed.StyleSetBold(num, True)

    _s(stc.STC_P_DEFAULT,       _EDITOR_FG)
    _s(stc.STC_P_COMMENTLINE,   _COMMENT_FG)
    _s(stc.STC_P_NUMBER,        _NUMBER_FG)
    _s(stc.STC_P_STRING,        _STRING_FG)
    _s(stc.STC_P_CHARACTER,     _STRING_FG)
    _s(stc.STC_P_WORD,          _KEYWORD_FG,  bold=True)
    _s(stc.STC_P_TRIPLE,        _STRING_FG)
    _s(stc.STC_P_TRIPLEDOUBLE,  _STRING_FG)
    _s(stc.STC_P_CLASSNAME,     _DEFNAME_FG,  bold=True)
    _s(stc.STC_P_DEFNAME,       _DEFNAME_FG)
    _s(stc.STC_P_OPERATOR,      _OPERATOR_FG)
    _s(stc.STC_P_IDENTIFIER,    _EDITOR_FG)
    _s(stc.STC_P_COMMENTBLOCK,  _COMMENT_FG)
    _s(stc.STC_P_STRINGEOL,     _STRING_FG)
    _s(stc.STC_P_WORD2,         _KEYWORD2_FG)
    _s(stc.STC_P_DECORATOR,     _DECORATOR_FG)

    ed.SetKeyWords(0,
        "False None True and as assert async await break class continue def del "
        "elif else except finally for from global if import in is lambda nonlocal "
        "not or pass raise return try while with yield"
    )
    ed.SetKeyWords(1,
        "abs all any bin bool bytearray bytes callable chr classmethod compile "
        "complex delattr dict dir divmod enumerate eval exec filter float format "
        "frozenset getattr globals hasattr hash help hex id input int isinstance "
        "issubclass iter len list locals map max min next object oct open ord pow "
        "print property range repr reversed round set setattr slice sorted "
        "staticmethod str sum super tuple type vars zip self cls __name__ __file__"
    )


class ScriptEditorDialog(wx.Dialog):
    """Dark-themed hooks.py editor with Python syntax highlighting and styled scrollbar."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(
            parent,
            title="Script Editor — hooks.py",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.SetBackgroundColour(_SB_TRACK)

        self._on_save_cb: Callable[[str], None] | None = None

        self._container = wx.Panel(self, style=wx.BORDER_NONE)
        self._container.SetBackgroundColour(_SB_TRACK)

        self._editor = stc.StyledTextCtrl(self._container, style=wx.BORDER_NONE)
        self._setup_editor()

        self._vscrollbar = DarkScrollBar(self._container, on_scroll=self._on_vsb_scroll)
        self._hscrollbar = DarkHScrollBar(self._container, on_scroll=self._on_hsb_scroll)

        _corner = wx.Panel(self._container, size=(_SB_W, _SB_W))
        _corner.SetBackgroundColour(_SB_TRACK)

        editor_row = wx.BoxSizer(wx.HORIZONTAL)
        editor_row.Add(self._editor, 1, wx.EXPAND)
        editor_row.Add(self._vscrollbar, 0, wx.EXPAND)

        scroll_row = wx.BoxSizer(wx.HORIZONTAL)
        scroll_row.Add(self._hscrollbar, 1, wx.EXPAND)
        scroll_row.Add(_corner, 0)

        sep = wx.Panel(self, size=(-1, 1))
        sep.SetBackgroundColour(SEP_COLOUR)

        self._status_label = wx.StaticText(self, label="")
        self._status_label.SetFont(scaled_font(11))
        self._status_label.SetForegroundColour(FG_SECONDARY)
        self._status_label.SetBackgroundColour(_SB_TRACK)

        self._save_btn = FlatButton(self, "Save")
        self._save_btn.SetMinSize((90, 28))
        self._save_btn.set_action(self._on_save_clicked)

        container_sizer = wx.BoxSizer(wx.VERTICAL)
        container_sizer.Add(editor_row, 1, wx.EXPAND)
        container_sizer.Add(scroll_row, 0, wx.EXPAND)
        self._container.SetSizer(container_sizer)

        bottom = wx.BoxSizer(wx.HORIZONTAL)
        bottom.Add(self._status_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
        bottom.Add(self._save_btn, 0, wx.RIGHT | wx.TOP | wx.BOTTOM, 6)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self._container, 1, wx.EXPAND)
        outer.Add(sep, 0, wx.EXPAND)
        outer.Add(bottom, 0, wx.EXPAND)
        self.SetSizer(outer)

        self.SetSize(780, 560)
        self.SetMinSize((480, 340))
        self.CentreOnParent()

        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def _setup_editor(self) -> None:
        ed = self._editor

        _apply_python_highlighting(ed)

        ed.SetCaretForeground(_CARET)
        ed.SetSelBackground(True, _SEL_BG)
        ed.SetSelForeground(False, _EDITOR_FG)

        ed.SetMarginType(0, stc.STC_MARGIN_NUMBER)
        ed.SetMarginWidth(0, 44)

        ed.SetMarginType(1, stc.STC_MARGIN_SYMBOL)
        ed.SetMarginWidth(1, 4)
        ed.SetMarginBackground(1, _EDITOR_BG)

        ed.SetTabWidth(4)
        ed.SetUseTabs(False)
        ed.SetIndent(4)
        ed.SetTabIndents(True)
        ed.SetBackSpaceUnIndents(True)
        ed.SetIndentationGuides(stc.STC_IV_LOOKBOTH)

        ed.SetEOLMode(stc.STC_EOL_LF)
        ed.SetViewEOL(False)
        ed.SetViewWhiteSpace(stc.STC_WS_INVISIBLE)
        ed.SetScrollWidth(1)
        ed.SetScrollWidthTracking(True)

        ed.SetUseVerticalScrollBar(False)
        ed.SetUseHorizontalScrollBar(False)

        ed.Bind(stc.EVT_STC_CHARADDED, self._on_char_added)
        ed.Bind(stc.EVT_STC_UPDATEUI, self._on_update_ui)
        ed.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)
        ed.Bind(wx.EVT_SIZE, self._on_editor_size)

    def _on_update_ui(self, event: stc.StyledTextEvent) -> None:
        ed = self._editor

        total = ed.GetLineCount()
        visible = ed.LinesOnScreen()
        first = ed.GetFirstVisibleLine()
        if total <= visible:
            self._vscrollbar.update(0.0, 1.0)
        else:
            scrollable = total - visible
            self._vscrollbar.update(first / scrollable, visible / total)

        scroll_width = ed.GetScrollWidth()
        client_width = ed.GetClientSize().width
        x_offset = ed.GetXOffset()
        if scroll_width <= client_width:
            self._hscrollbar.update(0.0, 1.0)
        else:
            scrollable_w = scroll_width - client_width
            self._hscrollbar.update(
                min(x_offset / scrollable_w, 1.0),
                client_width / scroll_width,
            )

        event.Skip()

    def _on_vsb_scroll(self, fraction: float) -> None:
        ed = self._editor
        total = ed.GetLineCount()
        visible = ed.LinesOnScreen()
        scrollable = max(1, total - visible)
        ed.ScrollToLine(round(fraction * scrollable))

    def _on_hsb_scroll(self, fraction: float) -> None:
        ed = self._editor
        scroll_width = ed.GetScrollWidth()
        client_width = ed.GetClientSize().width
        scrollable_w = max(1, scroll_width - client_width)
        ed.SetXOffset(round(fraction * scrollable_w))

    def _on_editor_size(self, event: wx.SizeEvent) -> None:
        self._on_update_ui(stc.StyledTextEvent(stc.wxEVT_STC_UPDATEUI))
        event.Skip()

    def _on_wheel(self, event: wx.MouseEvent) -> None:
        ed = self._editor
        delta = event.GetWheelRotation() // event.GetWheelDelta()
        ed.ScrollToLine(max(0, ed.GetFirstVisibleLine() - delta * 3))
        self._on_update_ui(stc.StyledTextEvent(stc.wxEVT_STC_UPDATEUI))

    def _on_char_added(self, event: stc.StyledTextEvent) -> None:
        if event.GetKey() == ord("\n"):
            self._auto_indent()
        event.Skip()

    def _auto_indent(self) -> None:
        ed = self._editor
        line = ed.GetCurrentLine()
        if line == 0:
            return
        prev = ed.GetLine(line - 1)
        indent = len(prev) - len(prev.lstrip())
        if prev.rstrip().endswith(":"):
            indent += 4
        ed.SetLineIndentation(line, indent)
        ed.GotoPos(ed.GetLineIndentPosition(line))

    def bind_save(self, callback: Callable[[str], None]) -> None:
        self._on_save_cb = callback

    def load_source(self, source: str) -> None:
        self._editor.SetValue(source)
        self._editor.EmptyUndoBuffer()
        self._editor.GotoPos(0)
        self.set_status("")

    def get_source(self) -> str:
        return self._editor.GetValue()

    def set_status(self, text: str, error: bool = False) -> None:
        self._status_label.SetLabel(text)
        self._status_label.SetForegroundColour(DANGER if error else PONI_LOADED if text else FG_SECONDARY)
        self._status_label.Refresh()

    def _on_save_clicked(self) -> None:
        if self._on_save_cb is not None:
            self._on_save_cb(self._editor.GetValue())

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Hide()
        else:
            event.Skip()
