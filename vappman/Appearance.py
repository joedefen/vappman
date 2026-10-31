#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Semantic colour roles and the appearance preferences for vappman.

Colour is decoration, never information.  Every role degrades to an attribute
(or to plain text) when the terminal has no colour, so the installed markers
(``✔``/``🔒``), the ``S``/``U`` flags and the ``⚠️`` prompts always remain
readable on a monochrome terminal.

The role ids are ``console_window.Theme``'s semantic pairs rather than literal
colour numbers.  console-window installs those pairs at startup and re-installs
them whenever a theme is applied, so changing the active theme recolours the
whole UI without an edit to any draw code.

``mono`` is vappman's own no-colour pseudo-theme: console-window's
``dark-mono``/``light-mono`` are still colour themes, so the true monochrome
appearance lives here as the :data:`MONO_ROLES` mapping.  It is part of the
picker's rotation but is not a library theme.
"""

import os
import curses

from console_window import Theme

# vappman's pseudo-theme: no colour at all, only attributes.
MONO_THEME = 'mono'

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
    Theme.HOTSWAP: curses.A_NORMAL,
}

# Process-wide switch, seeded at startup by --no-color / NO_COLOR / mono.  One
# terminal, so one decision.
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


def appearance_choices():
    """Every appearance the picker cycles, in order.

    console-window's themes come first (in ``Theme.THEMES`` order), then
    vappman's no-colour pseudo-theme, so one cycle always reaches ``mono``.
    """
    return list(Theme.list_all()) + [MONO_THEME]


def appearance_label(theme, colors):
    """The name to show for the live appearance."""
    if not colors:
        return MONO_THEME
    return theme or 'default'


def resolve_ui_prefs(cli_theme=None, no_color=False, saved_theme='',
                     saved_colors=True, environ=None):
    """Starting ``(theme, colors)`` from the flag, the environment and the prefs.

    Precedence, highest first: an explicit ``--theme`` / ``--no-color``, the
    ``NO_COLOR`` convention (any non-empty value disables colour), then the
    remembered choice.  An explicit ``--theme`` is a statement of intent, so it
    re-enables colour even when the saved choice was ``mono`` (unless
    ``--no-color`` says otherwise); an unknown theme name falls back to
    console-window's ``default``.

    ``theme`` is ``''`` for the library default.  The special value ``mono``
    forces ``colors`` off and is reported as ``theme=''``: there is no library
    theme to install, because mono is the attribute mapping in this module.
    """
    env = os.environ if environ is None else environ
    if cli_theme:
        if cli_theme == MONO_THEME:
            return '', False
        return Theme.resolve(cli_theme), not no_color
    theme = '' if saved_theme in (None, MONO_THEME) else Theme.resolve(saved_theme)
    colors = bool(saved_colors) and saved_theme != MONO_THEME
    if env.get('NO_COLOR') or no_color:
        colors = False
    return theme, colors
