#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The appearance preferences for vappman.

Colour is decoration, never information.  Every role degrades to an attribute
(or to plain text) when the terminal has no colour, so the installed markers
(``✔``/``🔒``), the ``S``/``U`` flags and the ``⚠️`` prompts always remain
readable on a monochrome terminal.

The role ids are ``console_window.Theme``'s semantic pairs rather than literal
colour numbers.  console-window installs those pairs at startup and re-installs
them whenever a theme is applied, so changing the active theme recolours the
whole UI without an edit to any draw code.

The role-to-attribute mapping, the process-wide switch and the forgiving lookup
live in :mod:`console_window.appearance`, and are re-exported here.  Keeping one
switch matters: the library's theme picker paints its swatches through that
layer, so a vappman-local copy would leave the picker in colour while the rest
of the UI went mono.

``mono`` is vappman's own no-colour pseudo-theme: console-window's
``dark-mono``/``light-mono`` are still colour themes, so the true monochrome
appearance is "colour off" rather than a library theme.  It is part of the
picker's rotation but is not a library theme.
"""

import os

from console_window import Theme
from console_window.appearance import (
    MONO_ROLES, colors_enabled, semantic_attr, set_colors_enabled,
)

# Explicit re-exports: the appearance API is read from this module by vappman.
__all__ = [
    'MONO_ROLES', 'MONO_THEME', 'appearance_choices', 'appearance_label',
    'colors_enabled', 'resolve_ui_prefs', 'semantic_attr',
    'set_colors_enabled',
]

# vappman's pseudo-theme: no colour at all, only attributes.
MONO_THEME = 'mono'


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
