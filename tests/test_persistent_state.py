#!/usr/bin/env python3
"""Tests for the JSON-backed persistent state store.

The important property here is migration: a state file written before an
option existed must not reset the options it *does* contain.
"""
import json
from pathlib import Path

import pytest

from vappman.PersistentState import PersistentState

DEFAULTS = dict(max_backups=1, install_opts='', database='am',
                theme='', colors=True)


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    """Point ``Path.home()`` at a temporary directory."""
    monkeypatch.setattr(Path, 'home', staticmethod(lambda: tmp_path))
    return tmp_path / '.config' / 'vappman'


def _write_state(state_dir, payload):
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / 'state_vars.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path


def test_older_file_keeps_its_values_and_gains_new_defaults(state_dir):
    path = _write_state(state_dir, {
        'max_backups': 3, 'install_opts': 'icons', 'database': 'am'})

    state = PersistentState('vappman', **DEFAULTS)

    assert (state.max_backups, state.install_opts, state.database) == (
        3, 'icons', 'am')
    assert state.theme == ''
    assert state.colors is True
    assert json.loads(path.read_text(encoding='utf-8')) == {
        'max_backups': 3, 'install_opts': 'icons', 'database': 'am',
        'theme': '', 'colors': True}


def test_key_from_a_newer_version_is_dropped_not_fatal(state_dir):
    path = _write_state(state_dir, {
        'max_backups': 2, 'install_opts': '', 'database': 'am',
        'theme': 'nord', 'colors': False, 'future_option': 1})

    state = PersistentState('vappman', **DEFAULTS)

    assert state.theme == 'nord'
    assert state.colors is False
    assert not hasattr(state, 'future_option')
    assert json.loads(path.read_text(encoding='utf-8')) == {
        'max_backups': 2, 'install_opts': '', 'database': 'am',
        'theme': 'nord', 'colors': False}


def test_type_mismatch_for_a_known_key_still_resets(state_dir, capsys):
    path = _write_state(state_dir, {
        'max_backups': 'three', 'install_opts': '', 'database': 'am'})

    state = PersistentState('vappman', **DEFAULTS)

    assert state.max_backups == 1
    assert 'Invalid state file' in capsys.readouterr().out
    assert json.loads(path.read_text(encoding='utf-8')) == DEFAULTS


def test_missing_file_is_created_with_defaults(state_dir):
    state = PersistentState('vappman', **DEFAULTS)

    assert state.theme == ''
    assert state.colors is True
    assert json.loads((state_dir / 'state_vars.json').read_text(
        encoding='utf-8')) == DEFAULTS
