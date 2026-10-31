#!/usr/bin/env python3
"""Tests for the inline install/remove confirmation and the AM -y hand-off.

Install and remove no longer shell out immediately.  Install shows a one-key
options menu (n/s/c/b, or y for the last choice) on the header line; remove
keeps the plain y/ESC prompt.  The eventual appman/am command carries ``-y`` so
AM does not ask a second time.
"""
import curses
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from types import SimpleNamespace

from console_window import (
    ConsoleWindow, ConsoleWindowOpts, InlineConfirmation, Theme)
from console_window.backend import HeadlessBackend
import vappman.main as main_module
from vappman.main import HomeScreen, Vappman, install_options_legend


class _FakeVappman(Vappman):
    """Vappman with __init__ bypassed (no curses / prereqs needed)."""

    def __init__(self, has_appman=True, install_opts=''):
        self.has_appman = has_appman
        self.opts = SimpleNamespace(install_opts=install_opts)
        self.disk_state = SimpleNamespace(save_if_changed=lambda opts: None)


def _info(appname='blink', db='am', app_type=''):
    return SimpleNamespace(appname=appname, db=db, app_type=app_type)


# --- command construction --------------------------------------------------

def test_install_command_passes_assume_yes_first():
    # AM requires -y/--assume-yes to be argv[1]; anything later is ignored.
    v = _FakeVappman()
    assert v._build_appman_cmd('install', _info()) == [
        'appman', '-y', 'install', 'blink']


def test_install_command_keeps_options_after_install():
    v = _FakeVappman(install_opts='icons,sandbox')
    assert v._build_appman_cmd('install', _info()) == [
        'appman', '-y', 'install', '--icons', '--sandbox', 'blink']


def test_install_command_qualifies_non_default_db():
    v = _FakeVappman()
    assert v._build_appman_cmd('install', _info(db='python')) == [
        'appman', '-y', 'install', 'blink.python']


def test_remove_command_also_gets_assume_yes_first():
    v = _FakeVappman()
    assert v._build_appman_cmd('remove', _info()) == [
        'appman', '-y', 'remove', 'blink']


def test_other_confirmed_installed_commands_get_assume_yes_first():
    v = _FakeVappman()
    for verb in ('backup', '--icons', '--sandbox', '--disable-sandbox'):
        assert v._build_appman_cmd(verb, _info()) == [
            'appman', '-y', verb, 'blink'], verb


def test_unconfirmed_commands_do_not_get_assume_yes():
    v = _FakeVappman()
    for verb in ('about', 'update', 'overwrite'):
        assert v._build_appman_cmd(verb, _info()) == [
            'appman', verb, 'blink'], verb


def test_am_fallback_also_gets_assume_yes_first():
    v = _FakeVappman(has_appman=False)
    assert v._build_appman_cmd('install', _info()) == [
        'am', '-y', 'install', 'blink']


# --- install menu legend ---------------------------------------------------

def test_install_legend_marks_last_choice():
    assert install_options_legend('') == (
        '*n:none s:sandbox c:icons b:both y:last ESC')
    assert install_options_legend('sandbox') == (
        'n:none *s:sandbox c:icons b:both y:last ESC')
    assert install_options_legend('icons,sandbox') == (
        'n:none s:sandbox c:icons *b:both y:last ESC')


def test_install_legend_handles_legacy_flag_order():
    assert '*b:both' in install_options_legend('sandbox,icons')


# --- key handling ----------------------------------------------------------

class _ConfirmFake(_FakeVappman):
    """Vappman with an active inline install/remove confirmation."""

    def __init__(self, action='install', install_opts='', verb=None):
        super().__init__(install_opts=install_opts)
        self.confirmation = InlineConfirmation()
        self.pending_action = None
        self.win = SimpleNamespace(passthrough_mode=False)
        self.calls = []
        self.confirmation.start(action, 'blink', mode='y')
        self.pending_action = (verb or action, _info())
        self.win.passthrough_mode = True

    def run_appman(self, subcommand, info=None):
        self.calls.append((subcommand, info))


def test_install_menu_maps_each_key_to_its_flags():
    for key, flags in (('n', ''), ('s', 'sandbox'),
                       ('c', 'icons'), ('b', 'icons,sandbox')):
        v = _ConfirmFake(install_opts='sandbox')
        info = v.pending_action[1]

        v._handle_confirmation_key(ord(key))

        assert v.calls == [('install', info)], key
        assert v.opts.install_opts == flags, key
        assert not v.confirmation.active
        assert v.pending_action is None
        assert v.win.passthrough_mode is False


def test_install_uppercase_key_also_works():
    v = _ConfirmFake()

    v._handle_confirmation_key(ord('C'))

    assert len(v.calls) == 1
    assert v.opts.install_opts == 'icons'


def test_install_y_uses_the_last_choice():
    v = _ConfirmFake(install_opts='icons,sandbox')
    info = v.pending_action[1]

    v._handle_confirmation_key(ord('y'))

    assert v.calls == [('install', info)]
    assert v.opts.install_opts == 'icons,sandbox'


def test_install_escape_cancels_without_installing():
    v = _ConfirmFake(install_opts='sandbox')

    v._handle_confirmation_key(27)

    assert v.calls == []
    assert v.opts.install_opts == 'sandbox'
    assert not v.confirmation.active
    assert v.pending_action is None
    assert v.win.passthrough_mode is False


def test_install_other_keys_are_swallowed():
    v = _ConfirmFake(install_opts='sandbox')

    # 'i' is the key that opened the prompt; it must not mean "icons".
    for key in (ord('i'), ord('q'), ord('x'), 10):
        v._handle_confirmation_key(key)

    assert v.calls == []
    assert v.opts.install_opts == 'sandbox'
    assert v.confirmation.active
    assert v.pending_action is not None
    assert v.win.passthrough_mode is True


def test_remove_y_still_confirms():
    v = _ConfirmFake('remove')
    info = v.pending_action[1]

    v._handle_confirmation_key(ord('y'))

    assert v.calls == [('remove', info)]
    assert not v.confirmation.active
    assert v.pending_action is None


def test_remove_escape_cancels():
    v = _ConfirmFake('remove')

    v._handle_confirmation_key(27)

    assert v.calls == []
    assert not v.confirmation.active
    assert v.pending_action is None
    assert v.win.passthrough_mode is False


def test_remove_menu_keys_are_swallowed():
    v = _ConfirmFake('remove')

    # n/s/c/b are install-menu keys, not remove answers.
    for key in (ord('n'), ord('s'), ord('c'), ord('b')):
        v._handle_confirmation_key(key)

    assert v.calls == []
    assert v.confirmation.active
    assert v.pending_action is not None


def test_other_installed_actions_confirm_with_y():
    for action, verb in (('backup', 'backup'), ('icons', '--icons'),
                         ('sandbox', '--sandbox'),
                         ('unsandbox', '--disable-sandbox')):
        v = _ConfirmFake(action, verb=verb)
        info = v.pending_action[1]

        v._handle_confirmation_key(ord('y'))

        assert v.calls == [(verb, info)], action
        assert not v.confirmation.active


def test_other_installed_actions_cancel_with_escape():
    for action, verb in (('backup', 'backup'), ('icons', '--icons'),
                         ('sandbox', '--sandbox'),
                         ('unsandbox', '--disable-sandbox')):
        v = _ConfirmFake(action, verb=verb)

        v._handle_confirmation_key(27)

        assert v.calls == [], action
        assert not v.confirmation.active


# --- action entry points ---------------------------------------------------

def _screen_with_context(genre, app_type=''):
    win = SimpleNamespace(
        passthrough_mode=False,
        get_picked_context=lambda: SimpleNamespace(
            genre=genre, info=_info(app_type=app_type)),
    )
    app = SimpleNamespace(
        win=win,
        confirmation=InlineConfirmation(),
        pending_action=None,
    )
    return HomeScreen(app), app


def test_install_action_opens_the_menu():
    screen, app = _screen_with_context('uninstalled')

    screen.install_ACTION()

    assert app.confirmation.active
    assert app.confirmation.action_type == 'install'
    assert app.pending_action == ('install', _info())
    assert screen.win.passthrough_mode is True


def test_remove_action_opens_its_confirmation():
    screen, app = _screen_with_context('installed')

    screen.remove_ACTION()

    assert app.confirmation.active
    assert app.confirmation.action_type == 'remove'
    assert app.pending_action == ('remove', _info())
    assert screen.win.passthrough_mode is True


def test_backup_action_opens_its_confirmation():
    screen, app = _screen_with_context('installed')

    screen.backup_ACTION()

    assert app.confirmation.action_type == 'backup'
    assert app.pending_action == ('backup', _info())


def test_icons_action_opens_its_confirmation():
    screen, app = _screen_with_context('installed')

    screen.icons_ACTION()

    assert app.confirmation.action_type == 'icons'
    assert app.pending_action == ('--icons', _info())


def test_sandbox_action_confirms_sandboxing():
    screen, app = _screen_with_context('installed')

    screen.sandbox_ACTION()

    assert app.confirmation.action_type == 'sandbox'
    assert app.pending_action == ('--sandbox', _info())


def test_sandbox_action_confirms_unsandboxing():
    locked = 'AppImage 🔒'
    screen, app = _screen_with_context('installed', app_type=locked)

    screen.sandbox_ACTION()

    assert app.confirmation.action_type == 'unsandbox'
    assert app.pending_action == ('--disable-sandbox', _info(app_type=locked))


# --- layout: prompt goes below the entry's own rows ------------------------

def _drawn_screen(installed, action, install_opts='sandbox'):
    ns = SimpleNamespace(appname='blink', db='am', synopsis='A tiny browser',
                         version='1.0', app_type='AppImage', where='U')
    win = ConsoleWindow(
        opts=ConsoleWindowOpts(body_rows=50, head_rows=10,
                               min_cols_rows=(60, 10)),
        backend=HeadlessBackend(rows=30, cols=80))
    win.set_pick_mode(True)

    class _App:
        def __init__(self):
            self.win = win
            self.opts = SimpleNamespace(
                database='am', fancy_header='Off', demo_mode=False,
                max_backups=1, install_opts=install_opts, in_system_mode=False)
            self.confirmation = InlineConfirmation()
            self.pending_action = (action, ns)
            self.search_bar = SimpleNamespace(
                is_active=False, get_display_string=lambda prefix='': '')
            self.installs = {('blink', 'am'): ns} if installed else {}
            self.installs_by_appname = {'blink': [ns]} if installed else {}
            self.apps_by_name_db = {('blink', 'am'): ns}
            self.has_appman = True
            self.in_system_mode = False
            self.pick_identity = None
            self.disk_state = SimpleNamespace(save_if_changed=lambda opts: None)
            self.appman = SimpleNamespace(get_snapshots=lambda name, n: [])

        def _make_wanted(self):
            return lambda n: True

        def get_keys_line(self):
            return '[q]uit'

    app = _App()
    app.confirmation.start(action, 'blink', mode='y')
    HomeScreen(app).draw_screen()
    win.calc()  # what render() does before drawing the viewport
    texts = list(win.body.texts)
    genres = [getattr(ctx, 'genre', None) for ctx in win.body.contexts]
    headers = list(win.head.texts)
    attrs = [list(runs) for runs in win.body.text_attrs]
    # Abut range of the pick: the engine keeps this range in the viewport, so
    # the prompt rows must be inside it or they can fall off-screen.
    abut = win._abut_range_at(win.pick_pos)
    pickable = [win._is_pickable(i) for i in range(win.body.row_cnt)]
    win.stop_curses()
    return texts, genres, headers, abut, pickable, attrs


def test_install_prompt_sits_below_the_entry_rows():
    texts, genres, headers, abut, pickable, _ = _drawn_screen(False, 'install')

    assert texts[0].startswith('   ◆ blink') and 'A tiny browser' in texts[0]
    assert texts[1] == '    ⚠️  Install blink?'
    assert texts[2] == '    n:none *s:sandbox c:icons b:both y:last ESC'
    # TRANSIENT drives the engine's auto-abut; DECOR would not be reserved.
    assert genres[1:] == ['TRANSIENT', 'TRANSIENT']
    assert abut == (0, 2)
    assert pickable == [True, False, False]
    assert not any('y:last' in h for h in headers)


def test_remove_prompt_sits_below_the_detail_rows():
    texts, genres, headers, abut, pickable, _ = _drawn_screen(True, 'remove')

    assert texts[0].startswith(' ✔─U blink') and 'A tiny browser' in texts[0]
    assert '1.0 AppImage' in texts[1]
    assert texts[2] == '    ⚠️  Remove blink? Press y or ESC'
    assert genres[1:] == ['TRANSIENT', 'TRANSIENT']
    assert abut == (0, 2)
    assert pickable == [True, True, False]
    assert not any('y:last' in h for h in headers)


def test_installed_action_prompts_use_their_own_label():
    for action, label in (('backup', 'Backup'), ('sandbox', 'Sandbox'),
                          ('unsandbox', 'Unsandbox'),
                          ('icons', 'Set icons for')):
        texts, genres, headers, abut, pickable, _ = _drawn_screen(True, action)
        assert texts[2] == f'    ⚠️  {label} blink? Press y or ESC', action
        assert genres[2] == 'TRANSIENT'
        assert pickable[2] is False
        assert abut == (0, 2)


# --- semantic colour roles --------------------------------------------------
# The draw code must ask for the right role and nothing more.  Monkeypatching
# semantic_attr keeps the assertions independent of the terminal's palette.

INFO_SENTINEL = 0x4000
HOTSWAP_SENTINEL = 0x2000
DANGER_SENTINEL = 0x8000


def _sentinel_attr(pair_id):
    return {Theme.INFO: INFO_SENTINEL,
            Theme.HOTSWAP: HOTSWAP_SENTINEL,
            Theme.DANGER: DANGER_SENTINEL}.get(pair_id, 0)


def _run_attrs(attr_runs):
    return [attr for attr, _ in attr_runs]


def test_installed_row_uses_the_hotswap_role(monkeypatch):
    monkeypatch.setattr(main_module, 'semantic_attr', _sentinel_attr)

    *_, attrs = _drawn_screen(True, 'remove')

    assert HOTSWAP_SENTINEL in _run_attrs(attrs[0])
    assert INFO_SENTINEL not in _run_attrs(attrs[0])
    assert DANGER_SENTINEL not in _run_attrs(attrs[0])


def test_uninstalled_row_does_not_use_the_hotswap_role(monkeypatch):
    monkeypatch.setattr(main_module, 'semantic_attr', _sentinel_attr)

    *_, attrs = _drawn_screen(False, 'install')

    assert HOTSWAP_SENTINEL not in _run_attrs(attrs[0])


def test_install_prompt_uses_the_danger_role(monkeypatch):
    monkeypatch.setattr(main_module, 'semantic_attr', _sentinel_attr)

    *_, attrs = _drawn_screen(False, 'install')

    assert _run_attrs(attrs[1]) == [curses.A_BOLD | DANGER_SENTINEL]


def test_installed_action_prompt_uses_the_danger_role(monkeypatch):
    monkeypatch.setattr(main_module, 'semantic_attr', _sentinel_attr)

    *_, attrs = _drawn_screen(True, 'remove')

    assert _run_attrs(attrs[2]) == [curses.A_BOLD | DANGER_SENTINEL]
