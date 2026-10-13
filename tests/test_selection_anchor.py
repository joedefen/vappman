#!/usr/bin/env python3
"""
Unit tests for logical selection anchoring across filter edits.

When the incremental search filter changes, the highlighted app should stay
the same *app* even though its row index shifts. These tests exercise the
pure helper methods `visible_app_keys()` and `_restore_selection()` without
starting curses.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from types import SimpleNamespace

from vappman.main import Vappman


class _FakeVappman(Vappman):
    """Vappman with __init__ bypassed (no curses / prereqs needed)."""

    def __init__(self, installs=None, avail=None, filt=None, database='am'):
        self.installs = installs or {}
        self.apps_by_name_db = avail or {}
        self.filter = filt
        self.opts = SimpleNamespace(database=database)
        self.win = SimpleNamespace(pick_pos=0)
        self.search_anchor = None


def _ns(appname, db='am', synopsis=''):
    return SimpleNamespace(appname=appname, db=db, synopsis=synopsis)


def test_visible_keys_installed_first_then_available():
    installs = {('a', 'am'): _ns('a'), ('b', 'am'): _ns('b')}
    avail = {
        ('a', 'am'): _ns('a'),   # already installed -> must not be duplicated
        ('c', 'am'): _ns('c'),
        ('d', 'am'): _ns('d'),
    }
    v = _FakeVappman(installs, avail)
    assert v.visible_app_keys() == [
        ('a', 'am'), ('b', 'am'), ('c', 'am'), ('d', 'am')]


def test_visible_keys_respects_selected_database():
    avail = {
        ('a', 'am'): _ns('a', 'am'),
        ('p', 'python'): _ns('p', 'python'),
    }
    v = _FakeVappman({}, avail, database='am')
    assert v.visible_app_keys() == [('a', 'am')]


def test_visible_keys_all_database_includes_everything():
    avail = {
        ('a', 'am'): _ns('a', 'am'),
        ('p', 'python'): _ns('p', 'python'),
    }
    v = _FakeVappman({}, avail, database='ALL')
    assert v.visible_app_keys() == [('a', 'am'), ('p', 'python')]


def test_restore_selection_follows_reindexed_anchor():
    installs = {
        ('a', 'am'): _ns('a'),
        ('b', 'am'): _ns('b'),
        ('blink', 'am'): _ns('blink'),
        ('c', 'am'): _ns('c'),
    }
    v = _FakeVappman(installs, {})
    # 'blink' was selected at index 2 before the filter changed.
    v.search_anchor = ('blink', 'am')
    v.win.pick_pos = 2

    # Narrowing the pattern keeps only 'a' and 'blink' -> blink is now index 1.
    v.filter = re.compile(r'^(a|blink) @am')
    v._restore_selection()
    assert v.win.pick_pos == 1


def test_restore_selection_falls_back_to_top_when_unmatched():
    installs = {
        ('a', 'am'): _ns('a'),
        ('blink', 'am'): _ns('blink'),
    }
    v = _FakeVappman(installs, {})
    v.search_anchor = ('blink', 'am')
    v.win.pick_pos = 1

    # The new pattern excludes 'blink' entirely.
    v.filter = re.compile(r'^a @am')
    v._restore_selection()
    assert v.win.pick_pos == 0


def test_restore_selection_noop_without_anchor():
    v = _FakeVappman({('a', 'am'): _ns('a')}, {})
    v.win.pick_pos = 0
    v.search_anchor = None
    v._restore_selection()
    assert v.win.pick_pos == 0


def test_selected_app_key_maps_index_to_identity():
    installs = {('a', 'am'): _ns('a'), ('b', 'am'): _ns('b')}
    v = _FakeVappman(installs, {})
    v.win.pick_pos = 1
    assert v.selected_app_key() == ('b', 'am')
    v.win.pick_pos = 99  # out of range
    assert v.selected_app_key() is None


def test_restore_selection_keeps_index_when_app_removed():
    installs = {
        ('a', 'am'): _ns('a'),
        ('b', 'am'): _ns('b'),
        ('c', 'am'): _ns('c'),
    }
    v = _FakeVappman(installs, {})
    v.win.pick_pos = 5  # stale index from a longer list
    v.restore_selection(('gone', 'am'))  # targeted app no longer present
    assert v.win.pick_pos == 2  # clamped to last row, not jumped to the top


def test_restore_selection_top_when_flagged():
    installs = {('a', 'am'): _ns('a'), ('b', 'am'): _ns('b')}
    v = _FakeVappman(installs, {})
    v.win.pick_pos = 1
    v.restore_selection(('gone', 'am'), fallback_to_top=True)
    assert v.win.pick_pos == 0


def test_restore_selection_handles_empty_list():
    v = _FakeVappman({}, {})
    v.win.pick_pos = 3
    v.restore_selection(('a', 'am'))
    assert v.win.pick_pos == 0


def test_restore_selection_follows_app_across_sections():
    """Install moves an app from the available section into installed; the
    cursor should follow the same app, not stay on the old row index."""
    avail = {('blink', 'am'): _ns('blink'), ('zed', 'am'): _ns('zed')}
    v = _FakeVappman({('zed', 'am'): _ns('zed')}, dict(avail))
    v.win.pick_pos = 1  # 'blink' selected in the available section
    anchor = v.selected_app_key()
    assert anchor == ('blink', 'am')

    # Simulate a successful install: blink is now installed (listed first).
    v.installs = {('blink', 'am'): _ns('blink'), ('zed', 'am'): _ns('zed')}
    v.restore_selection(anchor)

    assert v.win.pick_pos == 0
    assert v.visible_app_keys()[v.win.pick_pos] == ('blink', 'am')
