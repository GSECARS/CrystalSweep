#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/theme.py
# ----------------------------------------------------------------------------------
# Purpose:
# CS dark ColorTheme + derived scheme constants for widgets that still take
# explicit tuples (LiveToggle, CrystalMenuBar, dialogs, icon buttons, syntax editor).
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import sys

import wx
from wxutils import ColorTheme, set_theme

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

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


def btn_font() -> wx.Font:
    """Return the standard FlatButton font. Call after wx.App is created."""
    return scaled_font(12)


# ---------------------------------------------------------------------------
# CS dark ColorTheme
#
# Terminal token → CS role mapping:
#   background    BG_SURFACE  (18,18,18)     main window surface
#   black         BG_CARD     (28,28,30)     editor bg, popup bg, input bg
#   bright_black  BG_ELEVATED (38,38,42)     btn idle bg, border, sep, disabled bg
#   foreground    FG_PRIMARY  (230,230,235)  primary text
#   white         BTN_HOVER   (55,55,55)     btn hover bg, secondary text proxy
#   blue          ACCENT      (99,179,237)   accent, selection, check mark
#   bright_blue   ACCENT_HOVER(130,200,255)  accent hover
#   red           DANGER      (180,40,40)    destructive action idle
#   bright_red    DANGER_HOVER(210,55,55)    destructive action hover
#   green         PONI_LOADED (46,139,78)    success / calibration loaded
#   yellow        number literal (181,206,168)
#   magenta       keyword     (86,156,214)   -- VS Code blue used for keywords
#   cyan          keyword2    (78,201,176)   teal
#   bright_white  FG_PRIMARY  (230,230,235)  used where bright text needed
#   bright_green  string fg   (206,145,120)  warm orange-ish strings
#   bright_yellow comment fg  (106,153,85)   green comments
#   bright_magenta decorator  (220,220,100)
#   bright_cyan   def name    (220,220,170)
#   cursor_fg     BG_SURFACE  (18,18,18)
#   cursor_bg     FG_PRIMARY  (230,230,235)
#   selection_fg  FG_PRIMARY  (230,230,235)
#   selection_bg  (50,80,120)
# ---------------------------------------------------------------------------

def cs_dark_theme() -> ColorTheme:
    """CS custom dark ColorTheme. Call set_theme(cs_dark_theme()) at app startup."""
    return ColorTheme(
        foreground=wx.Colour(230, 230, 235),    # FG_PRIMARY
        background=wx.Colour(18, 18, 18),        # BG_SURFACE
        cursor_fg=wx.Colour(18, 18, 18),
        cursor_bg=wx.Colour(230, 230, 235),
        selection_fg=wx.Colour(230, 230, 235),
        selection_bg=wx.Colour(50, 80, 120),
        black=wx.Colour(28, 28, 30),             # BG_CARD — editor/popup/input bg
        red=wx.Colour(180, 40, 40),              # DANGER
        green=wx.Colour(46, 139, 78),            # PONI_LOADED / success
        yellow=wx.Colour(181, 206, 168),         # number literals
        blue=wx.Colour(99, 179, 237),            # ACCENT
        magenta=wx.Colour(86, 156, 214),         # keyword fg (VS Code blue)
        cyan=wx.Colour(78, 201, 176),            # keyword2 / def name fg
        white=wx.Colour(55, 55, 55),             # BTN_HOVER_BG / secondary text proxy
        bright_black=wx.Colour(38, 38, 42),      # BG_ELEVATED — btn idle bg, border, sep
        bright_red=wx.Colour(210, 55, 55),       # DANGER_HOVER
        bright_green=wx.Colour(206, 145, 120),   # string fg (warm orange)
        bright_yellow=wx.Colour(106, 153, 85),   # comment fg (green)
        bright_blue=wx.Colour(130, 200, 255),    # ACCENT_HOVER
        bright_magenta=wx.Colour(220, 220, 100), # decorator fg
        bright_cyan=wx.Colour(220, 220, 170),    # def name fg
        bright_white=wx.Colour(230, 230, 235),   # FG_PRIMARY (bright alias)
    )


def apply_cs_theme() -> None:
    """Set the CS dark theme as the active wxutils theme. Call once after wx.App()."""
    set_theme(cs_dark_theme())


# ---------------------------------------------------------------------------
# Derived colour constants — for widgets that still take explicit tuples,
# or CS-specific widgets (LiveToggle, CrystalMenuBar, icons, dialogs).
# These are computed from cs_dark_theme() tokens so they stay in sync.
# ---------------------------------------------------------------------------

# Grab tokens once at module level (wx.Colour is safe here — module is imported
# after wx.App() is created in CS).
_T = cs_dark_theme()

BG_SURFACE   = _T.background           # (18,18,18)
BG_CARD      = _T.black                # (28,28,30)
BG_ELEVATED  = _T.bright_black         # (38,38,42)
FG_PRIMARY   = _T.foreground           # (230,230,235)
FG_SECONDARY = wx.Colour(140, 140, 150)
ACCENT       = _T.blue                 # (99,179,237)
ACCENT_HOVER = _T.bright_blue          # (130,200,255)
SEP_COLOUR   = wx.Colour(55, 55, 60)
BTN_HOVER_BG = _T.white                # (55,55,55)
BTN_PRESS_BG = wx.Colour(80, 80, 80)

POPUP_BG       = BG_CARD
POPUP_FG       = FG_PRIMARY
POPUP_BTN_BG   = wx.Colour(45, 45, 50)
POPUP_BTN_HOVER = wx.Colour(62, 62, 70)
POPUP_BTN_PRESS = wx.Colour(85, 85, 95)

PONI_LOADED  = _T.green                # (46,139,78)
PONI_MISSING = wx.Colour(110, 110, 120)

DANGER       = _T.red                  # (180,40,40)
DANGER_HOVER = _T.bright_red           # (210,55,55)
DANGER_PRESS = wx.Colour(150, 30, 30)

DISABLED_BG  = wx.Colour(33, 33, 36)
DISABLED_FG  = wx.Colour(90, 90, 96)

ICON_FG   = wx.Colour(200, 200, 210)
ICON_SIZE = 20

LIVE_W        = 24
LIVE_H        = 56
LIVE_OFF      = wx.Colour(90, 90, 95)
LIVE_ON       = DANGER
LIVE_ON_HOVER = DANGER_HOVER
LIVE_OFF_HOVER = wx.Colour(120, 120, 125)
LIVE_SCHEME   = (LIVE_OFF, LIVE_OFF_HOVER, LIVE_ON, LIVE_ON_HOVER)

BTN_DISABLED    = (DISABLED_BG, DISABLED_FG)
DEFAULT_SCHEME  = (POPUP_BTN_BG, POPUP_BTN_HOVER, POPUP_BTN_PRESS, FG_PRIMARY, FG_PRIMARY)
DANGER_SCHEME   = (POPUP_BTN_BG, DANGER_HOVER, DANGER_PRESS, wx.Colour(230, 90, 90), FG_PRIMARY)
TOGGLE_SCHEME   = (POPUP_BTN_BG, POPUP_BTN_HOVER, PONI_LOADED, FG_SECONDARY)
MUTED_SCHEME    = (wx.Colour(38, 38, 44), wx.Colour(55, 60, 75), wx.Colour(30, 35, 55), wx.Colour(120, 150, 190), wx.Colour(120, 150, 190))
STATUS_SCHEME   = (DISABLED_BG, DISABLED_FG)
RADIO_SCHEME    = (BG_CARD, BG_ELEVATED, ACCENT_HOVER, FG_SECONDARY)
PROGRESS_SCHEME = (BG_ELEVATED, ACCENT)
TAB_SCHEME      = (BG_CARD, BG_ELEVATED, wx.Colour(40, 40, 46), FG_PRIMARY, FG_SECONDARY, ACCENT, SEP_COLOUR)
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

TEXT_SCHEME     = (BG_ELEVATED, FG_PRIMARY, FG_SECONDARY, DISABLED_BG, DISABLED_FG, wx.Colour(70, 28, 28))
COMBO_SCHEME    = (BG_ELEVATED, BTN_HOVER_BG, FG_PRIMARY, SEP_COLOUR, FG_SECONDARY, DISABLED_BG, DISABLED_FG, POPUP_BG, POPUP_BTN_HOVER)
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
DIVIDER_FG   = wx.Colour(140, 140, 150)
DIVIDER_LINE = wx.Colour(70, 70, 76)


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
