#!/usr/bin/env python3
"""Tests for theme switching: preferences, mono and the picker screen."""
from types import SimpleNamespace

import pytest

from console_window import Theme
from vappman import Appearance
from vappman.main import (
    THEME_PICKER_NOTE, THEMES_ST, HomeScreen, Vappman,
    VappmanHelpScreen, VappmanThemeScreen)


@pytest.fixture(autouse=True)
def restore_colour_switch():
    """Every test starts and ends with semantic colour on."""
    Appearance.set_colors_enabled(True)
    yield
    Appearance.set_colors_enabled(True)


# --- preference resolution -------------------------------------------------

def test_saved_preference_is_used_when_nothing_overrides_it():
    assert Appearance.resolve_ui_prefs(
        saved_theme='nord', saved_colors=True, environ={}) == ('nord', True)


def test_explicit_theme_wins_and_re_enables_colour():
    assert Appearance.resolve_ui_prefs(
        cli_theme='gruvbox', saved_theme='', saved_colors=False,
        environ={}) == ('gruvbox', True)


def test_explicit_mono_disables_colour():
    assert Appearance.resolve_ui_prefs(
        cli_theme=Appearance.MONO_THEME, environ={}) == ('', False)


def test_no_color_flag_wins_over_an_explicit_theme():
    assert Appearance.resolve_ui_prefs(
        cli_theme='nord', no_color=True, environ={}) == ('nord', False)


def test_no_color_environment_disables_saved_colour():
    assert Appearance.resolve_ui_prefs(
        saved_theme='nord', saved_colors=True,
        environ={'NO_COLOR': '1'}) == ('nord', False)


def test_unknown_theme_falls_back_to_default():
    assert Appearance.resolve_ui_prefs(
        cli_theme='not-a-theme', environ={})[0] == 'default'


def test_appearance_label_names_mono():
    assert Appearance.appearance_label('', False) == Appearance.MONO_THEME
    assert Appearance.appearance_label('', True) == 'default'
    assert Appearance.appearance_label('nord', True) == 'nord'


def test_choices_end_with_mono():
    choices = Appearance.appearance_choices()

    assert choices[-1] == Appearance.MONO_THEME
    assert set(Theme.list_all()) <= set(choices)


# --- applying an appearance ------------------------------------------------

class _FakeWindow:
    def __init__(self):
        self.theme = 'default'
        self.calls = []

    def set_theme(self, name):
        self.calls.append(name)
        self.theme = name
        return True


class _FakeDisk:
    def __init__(self, theme='', colors=True):
        self.theme = theme
        self.colors = colors
        self.saves = 0

    def save(self):
        self.saves += 1


def _vappman():
    app = Vappman.__new__(Vappman)
    app.appearance_theme = ''
    app.appearance_colors = True
    app.win = _FakeWindow()
    app.disk_state = _FakeDisk()
    return app


def test_apply_mono_turns_colour_off_and_remembers_it():
    app = _vappman()

    app.apply_appearance(Appearance.MONO_THEME)

    assert app.appearance_theme == ''
    assert app.appearance_colors is False
    assert app.win.theme == Appearance.MONO_THEME
    assert not Appearance.colors_enabled()
    assert app.disk_state.theme == ''
    assert app.disk_state.colors is False
    assert app.disk_state.saves == 1


def test_apply_named_theme_re_enables_colour():
    app = _vappman()

    app.apply_appearance('nord')

    assert app.appearance_theme == 'nord'
    assert app.appearance_colors is True
    assert app.win.theme == 'nord'
    assert Appearance.colors_enabled()
    assert app.disk_state.theme == 'nord'
    assert app.disk_state.colors is True


def test_cycling_reaches_mono_and_wraps_to_the_first_theme():
    app = _vappman()
    app.appearance_theme = 'nord'  # the last library theme

    app.cycle_appearance()
    assert app.appearance_label() == Appearance.MONO_THEME

    app.cycle_appearance()
    assert app.appearance_theme == Theme.list_all()[0]
    assert app.appearance_colors is True


# --- screen wiring ---------------------------------------------------------

def _built(screen_class):
    pushed = []
    app = SimpleNamespace(
        win=SimpleNamespace(pick_pos=4),
        ss=SimpleNamespace(push=lambda st, pos: pushed.append((st, pos))))
    return screen_class(app), pushed


def test_home_and_help_can_open_the_picker():
    home, home_pushed = _built(HomeScreen)
    help_screen, help_pushed = _built(VappmanHelpScreen)

    home.theme_screen_ACTION()
    help_screen.theme_screen_ACTION()

    assert home_pushed == [(THEMES_ST, 4)]
    assert help_pushed == [(THEMES_ST, 4)]


def test_picker_cycles_the_app_and_escape_pops():
    events = []
    app = SimpleNamespace(
        win=SimpleNamespace(),
        cycle_appearance=lambda: events.append('cycle'),
        ss=SimpleNamespace(pop=lambda: events.append('pop')))

    screen = VappmanThemeScreen(app)
    screen.spin_theme_ACTION()
    screen.escape_theme_ACTION()

    assert events == ['cycle', 'pop']


# --- the picker's own drawing ----------------------------------------------

# The role order the library's picker draws, for attribute comparisons.
PICKER_ROLE_ORDER = (
    Theme.DANGER, Theme.SUCCESS, Theme.OLD_SUCCESS, Theme.WARNING,
    Theme.INFO, Theme.EMPHASIS, Theme.ERROR, Theme.PROGRESS, Theme.HOTSWAP,
)


class _RecordingWindow:
    """Captures the header/body calls so the mono preview can be inspected."""

    def __init__(self, theme='mono'):
        self.theme = theme
        self.headers = []
        self.bodies = []

    def set_pick_mode(self, on=True, pick_size=1):
        """The picker always leaves pick mode before drawing."""

    def add_header(self, text, attr=None, resume=False, **kwargs):
        """Record a header line."""
        self.headers.append(text)

    def add_body(self, text, attr=None, resume=False, **kwargs):
        """Record a body line with the attribute it was drawn with."""
        self.bodies.append((text, attr))


def test_picker_note_does_not_explain_the_mono_entry():
    # The note is under every theme; naming mono there confused every screen.
    assert 'mono' not in THEME_PICKER_NOTE.lower()


def test_mono_picker_is_named_mono_and_previews_without_colour():
    # The window still reports the palette underneath; the label and the
    # swatches must follow the switch, not that leftover name.
    win = _RecordingWindow(theme='nord')
    app = SimpleNamespace(win=win)
    Appearance.set_colors_enabled(False)

    VappmanThemeScreen(app).draw_screen()

    assert Appearance.MONO_THEME in win.headers[0]
    rows = win.bodies[:-1]
    assert [attr for _, attr in rows] == [
        Appearance.MONO_ROLES[role] for role in PICKER_ROLE_ORDER]
    assert win.bodies[-1][0] == THEME_PICKER_NOTE


def test_colour_picker_names_the_installed_theme():
    win = _RecordingWindow(theme='nord')
    app = SimpleNamespace(win=win)

    VappmanThemeScreen(app).draw_screen()

    assert 'nord' in win.headers[0]
