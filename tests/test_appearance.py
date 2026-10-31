#!/usr/bin/env python3
"""Tests for vappman's semantic colour roles.

Colour is decoration: the mono fallback must preserve the same hierarchy with
attributes alone, and a missing curses screen must never make a redraw fail.
"""
import curses

import pytest

from console_window import Theme
from vappman import Appearance


@pytest.fixture
def colors_off():
    """Run a test with the process-wide colour switch off."""
    Appearance.set_colors_enabled(False)
    yield
    Appearance.set_colors_enabled(True)


def test_no_colour_support_degrades_to_plain(monkeypatch):
    monkeypatch.setattr(curses, 'has_colors', lambda: False)

    assert Appearance.semantic_attr(Theme.INFO) == 0


def test_colour_path_returns_the_pair_id(monkeypatch):
    monkeypatch.setattr(curses, 'has_colors', lambda: True)
    monkeypatch.setattr(curses, 'color_pair', lambda pair: pair << 8)

    assert Appearance.semantic_attr(Theme.INFO) == Theme.INFO << 8


def test_curses_error_degrades_to_plain(monkeypatch):
    def no_screen():
        raise curses.error('no initscr')

    monkeypatch.setattr(curses, 'has_colors', no_screen)

    assert Appearance.semantic_attr(Theme.DANGER) == 0


def test_mono_roles_become_attributes(colors_off):
    assert not Appearance.colors_enabled()
    assert Appearance.semantic_attr(Theme.INFO) == curses.A_NORMAL
    assert Appearance.semantic_attr(Theme.DANGER) == (
        curses.A_BOLD | curses.A_REVERSE)


def test_unknown_role_is_plain_in_mono(colors_off):
    assert Appearance.semantic_attr(999) == curses.A_NORMAL
