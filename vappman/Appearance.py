#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Semantic colour roles for vappman.

Colour is decoration, never information.  Every role degrades to an attribute
(or to plain text) when the terminal has no colour, so the installed markers
(``✔``/``🔒``), the ``S``/``U`` flags and the ``⚠️`` prompts always remain
readable on a monochrome terminal.

The role ids are ``console_window.Theme``'s semantic pairs rather than literal
colour numbers.  console-window installs those pairs at startup and re-installs
them whenever a theme is applied, so a future theme picker only has to change
the active theme -- no rendering code in vappman needs to know the palette.

Phase 1 (this module) has no theme picker, no CLI flag and no preference file.
Those are deliberately deferred; see README-DEV.md, FUTURE ENHANCEMENTS.
"""

import curses

from console_window import Theme

# Role -> attribute used when colour is off.  The hierarchy is preserved with
# emphasis instead of hue: destructive prompts are bold+reverse, informational
# rows carry nothing (their ✔/🔒 and S/U markers already distinguish them).
MONO_ROLES = {
    Theme.DANGER: curses.A_BOLD | curses.A_REVERSE,
    Theme.ERROR: curses.A_BOLD | curses.A_REVERSE,
    Theme.WARNING: curses.A_BOLD,
    Theme.SUCCESS: curses.A_BOLD,
    Theme.EMPHASIS: curses.A_BOLD,
    Theme.INFO: curses.A_NORMAL,
    Theme.PROGRESS: curses.A_NORMAL,
    Theme.OLD_SUCCESS: curses.A_NORMAL,
}

# Process-wide switch, seeded by a future --no-color / NO_COLOR.  One terminal,
# so one decision.
_COLORS_ENABLED = True


def set_colors_enabled(enabled):
    """Turn semantic colour on or off for the whole process."""
    global _COLORS_ENABLED  # pylint: disable=global-statement
    _COLORS_ENABLED = bool(enabled)


def colors_enabled():
    """True while semantic roles resolve to colour pairs rather than attributes."""
    return _COLORS_ENABLED


def semantic_attr(pair_id):
    """Attribute for a console-window ``Theme`` role, or plain when no colour.

    With colour off the role becomes an attribute from :data:`MONO_ROLES`, so
    the UI keeps its emphasis hierarchy on a monochrome terminal.  Otherwise
    both ``curses.has_colors()`` and ``curses.color_pair()`` can raise
    ``curses.error`` before ``initscr()`` (and a failed lookup must never abort
    a redraw), so any failure degrades to plain text.
    """
    if not _COLORS_ENABLED:
        return MONO_ROLES.get(pair_id, curses.A_NORMAL)
    try:
        if not curses.has_colors():
            return 0
        return curses.color_pair(pair_id)
    except curses.error:
        return 0
