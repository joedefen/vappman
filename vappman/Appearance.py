#!/usr/bin/env python3
"""The appearance preferences for vappman."""

import os

from console_window import (
    MONO_ROLES,
    Theme,
    colors_enabled,
    semantic_attr,
    set_colors_enabled,
)

__all__ = [
    'MONO_ROLES', 'MONO_THEME', 'appearance_choices', 'appearance_label',
    'colors_enabled', 'resolve_ui_prefs', 'semantic_attr',
    'set_colors_enabled',
]

MONO_THEME = Theme.MONO

def appearance_choices():
    """Every appearance the picker cycles, in order."""
    others = [name for name in Theme.list_all() if name != MONO_THEME]
    return others + [MONO_THEME]


def appearance_label(theme, colors):
    """The name to show for the live appearance."""
    if not colors:
        return MONO_THEME
    return theme or 'default'


def resolve_ui_prefs(cli_theme=None, no_color=False, saved_theme='',
                     saved_colors=True, environ=None):
    """Determine the preferences per precedents."""
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
