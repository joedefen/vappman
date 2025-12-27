#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Custom Wrapper for python curses, providing structured window management
and an interactive option/key handler.

This module provides several key classes:

* :py:class:`ConsoleWindow` - High-level curses wrapper for terminal UI with header/body
  layout, scrolling, and pick (selection) mode
* :py:class:`IncrementalSearchBar` - Reusable search-as-you-type component with cursor editing
* :py:class:`OptionSpinner` - Manages key-driven application settings that can cycle
  through values or prompt for input
* :py:class:`Screen` - Base class for implementing individual screens in a multi-screen
  application with navigation
* :py:class:`ScreenStack` - Stack-based navigation system for managing screen transitions,
  similar to browser history
* :py:class:`BasicHelpScreen` - Example help screen implementation

Screen Stack Navigation
=======================

The Screen and ScreenStack classes provide a powerful navigation system for building
multi-screen terminal applications. Key features:

- **Stack-based navigation**: Push screens onto a stack, pop to go back
- **State preservation**: Each screen remembers its scroll/pick position
- **Navigation validation**: Screens can restrict which screens can navigate to them
- **Lifecycle hooks**: Screens can respond to being paused, resumed, or removed
- **Loop prevention**: Can't push the same screen twice onto the stack

Example usage:
    # Define screen IDs and names
    HOME_ST, SETTINGS_ST, HELP_ST = 0, 1, 2
    SCREENS = ['HOME', 'SETTINGS', 'HELP']

    # Create custom screen classes
    class HomeScreen(Screen):
        def draw_screen(self):
            self.win.add_header("Home")
            self.win.add_body("Welcome!")

    class SettingsScreen(Screen):
        def draw_screen(self):
            self.win.add_header("Settings")
            self.win.add_body("Configure here")

    # Initialize screens and stack
    screens = {
        HOME_ST: HomeScreen(app),
        SETTINGS_ST: SettingsScreen(app),
        HELP_ST: BasicHelpScreen(app)
    }
    ss = ScreenStack(win, app, SCREENS, screens)

    # Navigate
    ss.push(SETTINGS_ST, 0)  # Go to settings
    ss.pop()                  # Go back to home
"""
# pylint: disable=too-many-instance-attributes,too-many-arguments
# pylint: disable=invalid-name,broad-except,too-many-branches,global-statement
# pylint: disable=line-too-long,too-many-statements,too-many-locals

import sys
import re
import traceback
import atexit
import signal
import time
import curses
import textwrap
from types import SimpleNamespace
from curses.textpad import rectangle, Textbox
dump_str = None

ctrl_c_flag = False

# Navigation keys to exclude from demo mode highlighting
NAVIGATION_KEYS = {
    curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT,
    curses.KEY_HOME, curses.KEY_END, curses.KEY_PPAGE, curses.KEY_NPAGE,
    ord('j'), ord('k'), ord('h'), ord('l'),
    ord('0'), ord('$'), ord('H'), ord('M'), ord('L'),
    ord('\x15'),  # Ctrl-U (half page up)
    ord('\x04'),  # Ctrl-D (half page down)
    ord('\x02'),  # Ctrl-B (page up)
    ord('\x06'),  # Ctrl-F (page down)
}


class Context:
    """
    Base class for line metadata/context.

    Provides structured metadata for each line, avoiding the need to parse text.
    Apps can add custom attributes via **kwargs.

    :param genre: Category/type of the line (e.g., 'header', 'app', 'separator')
                  Special genres with uppercase names:
                  - 'DECOR': Visual decorations (separators, headers) - automatically non-pickable
                  - 'TRANSIENT': Conditional/dropdown content shown below parent row
                    Automatically gets abut to keep TRANSIENT rows visible when parent is picked
    :param pickable: Whether this line can be selected in pick mode (default: True)
                     Automatically set to False for uppercase genres
    :param kwargs: Custom attributes to attach to this context
    :type genre: str
    :type pickable: bool

    **Special attributes for pick_mode:**

    :param abut: Defines visible line range around picked line in pick_mode.
                 When set, only lines within [picked_line + before, picked_line + after] are visible.
                 "After" lines are prioritized when the range exceeds the viewport.

                 Formats:
                   - Negative int: lines before (e.g., abut=-3 shows 3 before, 0 after)
                   - Positive int: lines after (e.g., abut=7 shows 0 before, 7 after)
                   - List/tuple: [before, after] (e.g., abut=[-5, 3] shows 5 before, 3 after)
                   - Mixed list: min negative and max positive values are used
                     (e.g., abut=[-8, 3, -2, 12] → before=-8, after=12)

    Example::

        ctx = Context(genre='app', pickable=True,
                      app_name='firefox', installed=True, version='1.2.3')
        win.add_body("Firefox 1.2.3", context=ctx)

        # Later retrieve without parsing:
        ctx = win.get_picked_context()
        if ctx and ctx.genre == 'app':
            print(f"Selected: {ctx.app_name}")

        # Example with abut to limit visible context:
        ctx = Context(genre='result', pickable=True, abut=[-10, 20])
        win.put_body("Search result", context=ctx)
        # When this line is picked, only 10 lines before and 20 after are visible
    """
    def __init__(self, genre='', pickable=True, **kwargs):
        self.genre = genre
        # Auto-set pickable=False only for DECOR genre
        # TRANSIENT is navigable but ephemeral (handled by app logic)
        if genre == 'DECOR':
            self.pickable = False
        else:
            self.pickable = pickable
        # Allow apps to add custom attributes
        for key, value in kwargs.items():
            setattr(self, key, value)




class ConsoleWindowOpts:
    """
    Options class for ConsoleWindow with enforced valid members using __slots__.
    All options have sensible defaults.
    """
    __slots__ = ['head_line', 'head_rows', 'body_rows', 'body_cols', 'keys',
                 'pick_mode', 'pick_size', 'mod_pick', 'pick_attr', 'ctrl_c_terminates',
                 'return_if_pos_change', 'min_cols_rows', 'dialog_abort', 'dialog_return',
                 'single_cell_scroll_indicator', 'answer_show_redraws', 'strip_attrs_in_pick_mode',
                 'demo_mode']

    def __init__(self, **kwargs):
        """
        Initialize ConsoleWindowOpts with defaults. All parameters are optional.

        :param head_line: If True, draws a horizontal line between header and body (default: True)
        :param head_rows: Maximum capacity of internal header pad (default: 50)
        :param body_rows: Maximum capacity of internal body pad (default: 200)
        :param body_cols: Maximum width for content pads (default: 200)
        :param keys: Collection of key codes explicitly returned by prompt (default: None)
        :param pick_mode: If True, enables item highlighting/selection (default: False)
        :param pick_size: Number of rows highlighted as single 'pick' unit (default: 1)
        :param mod_pick: Optional callable to modify highlighted text (default: None)
        :param pick_attr: Curses attribute for highlighting picked items (default: curses.A_REVERSE)
        :param ctrl_c_terminates: If True, Ctrl-C terminates; if False, returns key 3 (default: True)
        :param return_if_pos_change: If True, prompt returns when pick position changes for immediate redraw (default: True)
        :param min_cols_rows: Minimum terminal size as (cols, rows) tuple (default: (70, 20))
        :param dialog_abort: How ESC aborts dialogs: None, "ESC", "ESC-ESC" (default: "ESC")
        :param dialog_return: Which key submits dialogs: "ENTER", "TAB" (default: "ENTER")
        :param single_cell_scroll_indicator: If True, shows single-cell position dot; if False, shows proportional range (default: False)
        :param strip_attrs_in_pick_mode: If True, strips attributes in pick mode (old behavior); if False, preserves them (default: False)
        """
        self.head_line = kwargs.get('head_line', True)
        self.head_rows = kwargs.get('head_rows', 50)
        self.body_rows = kwargs.get('body_rows', 200)
        self.body_cols = kwargs.get('body_cols', 200)
        self.keys = kwargs.get('keys', None)
        self.pick_mode = kwargs.get('pick_mode', False)
        self.pick_size = kwargs.get('pick_size', 1)
        self.mod_pick = kwargs.get('mod_pick', None)
        self.pick_attr = kwargs.get('pick_attr', curses.A_REVERSE)
        self.ctrl_c_terminates = kwargs.get('ctrl_c_terminates', True)
        self.return_if_pos_change = kwargs.get('return_if_pos_change', True)
        self.min_cols_rows = kwargs.get('min_cols_rows', (70, 20))
        self.dialog_abort = kwargs.get('dialog_abort', 'ESC')
        self.dialog_return = kwargs.get('dialog_return', 'ENTER')
        self.single_cell_scroll_indicator = kwargs.get('single_cell_scroll_indicator', False)
        self.answer_show_redraws = kwargs.get('answer_show_redraws', False)
        self.strip_attrs_in_pick_mode = kwargs.get('strip_attrs_in_pick_mode', False)
        self.demo_mode = kwargs.get('demo_mode', False)

        # Validate dialog_abort
        if self.dialog_abort not in [None, 'ESC', 'ESC-ESC']:
            raise ValueError(f"dialog_abort must be None, 'ESC', or 'ESC-ESC', got {self.dialog_abort!r}")

        # Validate dialog_return
        if self.dialog_return not in ['ENTER', 'TAB']:
            raise ValueError(f"dialog_return must be 'ENTER' or 'TAB', got {self.dialog_return!r}")

def ctrl_c_handler(sig, frame):
    """
    Custom handler for SIGINT (Ctrl-C).
    Sets a global flag to be checked by the main input loop.
    """
    global ctrl_c_flag
    ctrl_c_flag = True

def ignore_ctrl_c():
    """
    Ignores the **SIGINT** signal (Ctrl-C) to prevent immediate termination.
    Used during curses operation.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def restore_ctrl_c():
    """
    Restores the default signal handler for **SIGINT** (Ctrl-C).
    Called upon curses shutdown.
    """
    signal.signal(signal.SIGINT, signal.default_int_handler)


class IncrementalSearchBar:
    """
    Generic incremental search bar with text editing and cursor support.

    Provides a reusable pattern for implementing search-as-you-type functionality
    with full cursor editing capabilities (backspace, arrows, home/end, printable chars).

    Features:
        - Text editing with cursor position tracking
        - ENTER to accept changes, ESC to cancel (restores original text)
        - Callbacks for text changes, accept, and cancel events
        - Formatted display string with cursor indicator
        - Integrates with ConsoleWindow's passthrough_mode

    Example Usage:
        # Define callbacks for your application
        def on_text_change(text):
            # Update filter/search results incrementally
            app.compile_filter(text)

        def on_accept(text):
            # Finalize search, disable passthrough mode
            app.search_complete = True
            win.passthrough_mode = False

        def on_cancel(original_text):
            # Restore original state
            app.compile_filter(original_text)
            win.passthrough_mode = False

        # Create search bar instance
        search_bar = IncrementalSearchBar(
            on_change=on_text_change,
            on_accept=on_accept,
            on_cancel=on_cancel
        )

        # In your key binding action (e.g., slash key):
        def slash_ACTION(self):
            app.search_bar.start(app.current_filter)  # Start with current filter
            app.win.passthrough_mode = True  # Enable key passthrough

        # In your main event loop:
        key = win.prompt()
        if key is not None:
            if search_bar.is_active:
                # Let search bar handle the key first
                if search_bar.handle_key(key):
                    continue  # Key was handled, skip normal processing
            # Normal key handling...

        # In your header/display code:
        if search_bar.is_active:
            header += search_bar.get_display_string(prefix=' /')
        elif search_bar.text:
            header += f' /{search_bar.text}'

    Key Handling:
        - ENTER (10, 13): Accept current text, exit search mode
        - ESC (27): Cancel, restore original text, exit search mode
        - Backspace (8, 127, 263, KEY_BACKSPACE): Delete char before cursor
        - Left/Right arrows: Move cursor
        - Home/Ctrl-A: Move cursor to start
        - End/Ctrl-E: Move cursor to end
        - Printable chars (32-126): Insert at cursor position
    """

    def __init__(self, on_change=None, on_accept=None, on_cancel=None):
        """
        Initialize the incremental search bar.

        :param on_change: Callback function(text) called when text changes.
                         Use this to update search results incrementally.
        :param on_accept: Callback function(text) called when ENTER is pressed.
                         Use this to finalize the search.
        :param on_cancel: Callback function(original_text) called when ESC is pressed.
                         Use this to restore previous state.
        """
        self._active = False
        self._text = ''
        self._cursor_pos = 0
        self._start_text = ''  # Text when entering search mode

        # Callbacks
        self.on_change = on_change
        self.on_accept = on_accept
        self.on_cancel = on_cancel

    def start(self, initial_text=''):
        """
        Enter search mode with optional initial text.

        :param initial_text: Starting text for the search bar (default: empty string)
        """
        self._active = True
        self._text = initial_text
        self._start_text = initial_text
        self._cursor_pos = len(initial_text)

    def handle_key(self, key):
        """
        Handle a key press in search mode.

        :param key: Key code from curses
        :returns: True if the key was handled, False otherwise
        """
        if not self._active:
            return False

        # ENTER - accept search
        if key in [10, 13]:
            self._active = False
            if self.on_accept:
                self.on_accept(self._text)
            return True

        # ESC - cancel search, restore original text
        elif key == 27:
            self._text = self._start_text
            self._active = False
            if self.on_cancel:
                self.on_cancel(self._start_text)
            return True

        # Backspace - delete character before cursor
        elif key in [curses.KEY_BACKSPACE, 127, 8, 263]:
            if self._cursor_pos > 0:
                chars = list(self._text)
                chars.pop(self._cursor_pos - 1)
                self._text = ''.join(chars)
                self._cursor_pos -= 1
                if self.on_change:
                    self.on_change(self._text)
            return True

        # Left arrow - move cursor left
        elif key == curses.KEY_LEFT:
            if self._cursor_pos > 0:
                self._cursor_pos -= 1
            return True

        # Right arrow - move cursor right
        elif key == curses.KEY_RIGHT:
            if self._cursor_pos < len(self._text):
                self._cursor_pos += 1
            return True

        # Home or Ctrl-A - move to start
        elif key == curses.KEY_HOME or key == 1:
            self._cursor_pos = 0
            return True

        # End or Ctrl-E - move to end
        elif key == curses.KEY_END or key == 5:
            self._cursor_pos = len(self._text)
            return True

        # Printable characters - insert at cursor
        elif 32 <= key <= 126:
            chars = list(self._text)
            chars.insert(self._cursor_pos, chr(key))
            self._text = ''.join(chars)
            self._cursor_pos += 1
            if self.on_change:
                self.on_change(self._text)
            return True

        return False

    def get_display_string(self, prefix='/', suffix=''):
        """
        Get formatted display string with cursor indicator.

        When active (in search mode), shows cursor position with '|'.
        When inactive, just shows the text with prefix/suffix if text is non-empty.

        :param prefix: String to show before the search text (default: '/')
        :param suffix: String to show after the search text (default: '')
        :returns: Formatted string for display

        Example:
            Active with cursor: ' /hello| world'
            Active at end: ' /hello world|'
            Inactive with text: ' /hello world'
            Inactive without text: ''
        """
        if self._active:
            # Show cursor position with |
            before = self._text[:self._cursor_pos]
            after = self._text[self._cursor_pos:]
            # Add space after prefix to prevent pattern matching in fancy_header
            return f'{prefix} {before}|{after}{suffix}'
        elif self._text:
            return f'{prefix}{self._text}{suffix}'
        else:
            return ''

    @property
    def is_active(self):
        """Whether search mode is currently active."""
        return self._active

    @property
    def text(self):
        """Current search text."""
        return self._text

    @property
    def cursor_pos(self):
        """Current cursor position within the text."""
        return self._cursor_pos


class OptionSpinner:
    """
    Manages a set of application options where the value can be rotated through
    a fixed set of values (spinner) or requested via a dialog box (prompt) by
    pressing a single key.

    It also generates a formatted help screen based on the registered options.
    """
    def __init__(self, stack=None):
        """
        Initializes the OptionSpinner, setting up internal mappings for options
        and keys.

        :param stack: Optional ScreenStack reference for scope-aware key bindings.
                      If stack.obj is None, it will be set to this spinner's default_obj.
        :type stack: ScreenStack or None
        """
        self.options, self.keys = [], []
        self.margin = 4 # + actual width (1st column right pos)
        self.align = self.margin # + actual width (1st column right pos)
        self.default_obj = SimpleNamespace() # if not given one
        self.attr_to_option = {} # given an attribute, find its option ns
        self.key_to_option = {} # given key, options namespace
        self.keys = set()
        self.stack = stack  # Optional ScreenStack for scope-aware bindings
        self.key_scopes = {}  # Maps (key, screen) -> option_ns for scope tracking

        # If stack has None obj, give it our default_obj
        if self.stack and self.stack.obj is None:
            self.stack.obj = self.default_obj

    @staticmethod
    def _make_option_ns():
        """Internal helper to create a default namespace for an option."""
        return SimpleNamespace(
            keys=[],
            descr='',
            obj=None,
            attr='',
            vals=None,
            prompt=None,
            comments=[],
            genre=None,
            scope=None,  # None = all screens, or set of screen numbers
        )

    def get_value(self, attr, coerce=False):
        """
        Get the current value of the given attribute.

        :param attr: The name of the attribute (e.g., 'help_mode').
        :param coerce: If True, ensures the value is one of the valid 'vals'
                       or an empty string for prompted options.
        :type attr: str
        :type coerce: bool
        :returns: The current value of the option attribute.
        :rtype: Any
        """
        ns = self.attr_to_option.get(attr, None)
        obj = ns.obj if ns else None
        value = getattr(obj, attr, None) if obj else None
        if value is None and obj and coerce:
            if ns.vals:
                if value not in ns.vals:
                    value = ns.vals[0]
                    setattr(obj, attr, value)
            else:
                if value is None:
                    value = ''
                    setattr(ns.obj, ns.attr, '')
        return value

    def _register(self, ns):
        """
        Create the internal mappings needed for a new option namespace.
        Handles scope subtraction for overlapping keys.
        """
        if ns.attr in self.attr_to_option:
            existing = self.attr_to_option[ns.attr]
            raise ValueError(
                f"Attribute '{ns.attr}' already registered with description '{existing.descr}'. "
                f"Each add_key() must have a unique attr name. "
                f"If you want the same key on different screens, use different attr names with scope parameter."
            )
        self.attr_to_option[ns.attr] = ns

        # Get all screen numbers for scope calculations
        all_screens = set(range(len(self.stack.screens))) if self.stack else set()

        # Calculate effective scope for this new key
        # If scope is None and it's an action, need to determine which screens have this action
        if ns.scope is None:
            if ns.genre == 'action' and self.stack and self.stack.screen_objects:
                # Find all screens that implement this action (have method with name = attr)
                effective_scope = set()
                for screen_num, screen_obj in self.stack.screen_objects.items():
                    if hasattr(screen_obj, ns.attr):
                        effective_scope.add(screen_num)
                # If no screens found, default to all screens
                if not effective_scope:
                    effective_scope = all_screens
            else:
                # Not an action, or no stack available: all screens
                effective_scope = all_screens
        else:
            effective_scope = ns.scope.copy()

        # Store the effective scope in the namespace
        ns.effective_scope = effective_scope

        # Process each key for scope subtraction
        for key in ns.keys:
            # Perform subtraction FIRST: remove new scope from existing options with same key
            for existing_ns in self.options:
                if key in existing_ns.keys and hasattr(existing_ns, 'effective_scope'):
                    # Subtract the new scope from existing option's scope
                    # Also remove from key_scopes for screens that are being taken over
                    overlap = existing_ns.effective_scope & effective_scope
                    for screen_num in overlap:
                        if (key, screen_num) in self.key_scopes:
                            del self.key_scopes[(key, screen_num)]
                    existing_ns.effective_scope -= effective_scope

            # NOW check for conflicts: same key defined twice for the same screen
            # (After subtraction, there should be no conflicts if subtraction worked)
            for screen_num in effective_scope:
                if (key, screen_num) in self.key_scopes:
                    # This should not happen after subtraction
                    existing_ns = self.key_scopes[(key, screen_num)]
                    key_char = chr(key) if 32 <= key < 127 else f'<{key}>'
                    raise ValueError(
                        f'Key {key_char} ({key}) already defined for screen {screen_num} '
                        f'in option "{existing_ns.descr}". Cannot define same key twice for same screen.'
                    )

            # Store in key_scopes for each screen in the effective scope
            for screen_num in effective_scope:
                self.key_scopes[(key, screen_num)] = ns

            # Update global key tracking (if not using scopes, keep old behavior)
            if not self.stack:
                if key in self.key_to_option:
                    raise ValueError(f'key ({chr(key)}, {key}) already used')
                self.key_to_option[key] = ns

            self.keys.add(key)

        self.options.append(ns)
        self.align = max(self.align, self.margin+len(ns.descr))
        self.get_value(ns.attr, coerce=True)

    def add(self, obj, specs):
        """
        **Compatibility Method.** Adds options using an older array-of-specs format.

        A spec is a list or tuple like::

            ['a - allow auto suggestions', 'allow_auto', True, False],
            ['/ - filter pattern', 'filter_str', self.filter_str],

        The key is derived from the first character of the description string.
        It is recommended to use :py:meth:`add_key` for new code.

        :param obj: The object holding the option attributes (e.g., an argparse namespace).
        :param specs: An iterable of option specifications.
        :type obj: Any
        :type specs: list
        """
        for spec in specs:
            ns = self._make_option_ns()
            ns.descr = spec[0]
            ns.obj = obj
            ns.attr = spec[1]
            ns.vals=spec[2:]
            if None in ns.vals:
                idx = ns.vals.index(None)
                ns.vals = ns.vals[:idx]
                ns.comments = ns.vals[idx+1:]
            ns.keys = [ord(ns.descr[0])]
            self._register(ns)

    def add_key(self, attr, descr, obj=None, vals=None, prompt=None,
                keys=None, comments=None, genre=None, scope=None):
        """
        Adds an option that is toggled by a key press.

        The option can be a **spinner** (rotates through a list of ``vals``) or
        a **prompt** (requests string input via a dialog).

        :param attr: The name of the attribute for the value; referenced as ``obj.attr``.
        :param descr: The description of the key (for help screen).
        :param obj: The object holding the value. If None, uses ``self.default_obj``.
        :param vals: A list of values. If provided, the option is a spinner.
        :param prompt: A prompt string. If provided instead of ``vals``, the key press
                       will call :py:meth:`ConsoleWindow.answer`.
        :param keys: A single key code or string or a list of such that triggers
                     the action. If a string, ord(each-character) is assumed.
                     If None, uses the first letter of ``descr``.
        :param comments: Additional line(s) for the help screen item (string or list of strings).
        :param genre: (action, cycle, prompt)
        :param scope: Screen number(s) where this key is active. Can be:
                      - None (default): all screens, or all screens with action if genre='action'
                      - int: single screen number
                      - list/set: multiple screen numbers
                      Later add_key() calls for the same key subtract from earlier scopes.
        :type attr: str
        :type descr: str
        :type obj: Any
        :type vals: list or None
        :type prompt: str or None
        :type keys: int or list or tuple or None
        :type comments: str or list or tuple or None
        :type genre: str or None
        :type scope: int or list or set or None
        """

        ns = self._make_option_ns()
        if keys:
            keys = list(keys) if isinstance(keys, (list, tuple, set)) else [keys]
            ns.keys = []
            for key in keys:
                if isinstance(key, str):
                    for stroke in key:
                        ns.keys.append(ord(stroke))
                else:
                    ns.keys.append(key)
        else:
            ns.keys = [ord(descr[0])]
        if comments is None:
            ns.comments = []
        else:
            ns.comments = list(comments) if isinstance(comments, (list, tuple)) else [comments]
        ns.descr = descr
        ns.attr = attr
        ns.obj = obj if obj else self.default_obj
        if vals:
            ns.vals, ns.genre = vals, 'cycle'
        elif prompt:
            ns.prompt, ns.genre = prompt, 'prompt'
        else:
            # assert genre == 'action' # only one choice left ('action')
            ns.genre = 'action'

        # Process scope parameter
        if scope is None:
            ns.scope = None  # All screens (or all screens with action)
        elif isinstance(scope, int):
            ns.scope = {scope}
        elif isinstance(scope, (list, tuple, set)):
            ns.scope = set(scope)
        else:
            raise ValueError(f"scope must be None, int, or list/set, got {type(scope)}")

        self._register(ns)

    @staticmethod
    def show_help_nav_keys(win):
        """
        Displays the standard navigation keys blurb in the provided ConsoleWindow.

        :param win: The :py:class:`ConsoleWindow` instance to write to.
        :type win: ConsoleWindow
        """
        for line in ConsoleWindow.get_nav_keys_blurb().splitlines():
            if line:
                win.add_header(line)

    def show_help_body(self, win, screen_filter=None):
        """
        Writes the formatted list of all registered options and their current
        values to the body of the provided :py:class:`ConsoleWindow`.

        When using ScreenStack with scoped keys, only shows options applicable
        to the specified screens.

        :param win: The :py:class:`ConsoleWindow` instance to write to.
        :param screen_filter: Screen number(s) to filter options for. Can be:
                              - None: show all options (default)
                              - int: single screen number
                              - list/set: multiple screen numbers (typically [prev_screen, help_screen])
        :type win: ConsoleWindow
        :type screen_filter: int or list or set or None
        """
        win.add_body('Type keys to alter choice:', curses.A_UNDERLINE)

        # Convert screen_filter to a set for easy comparison
        if screen_filter is None:
            filter_screens = None
        elif isinstance(screen_filter, int):
            filter_screens = {screen_filter}
        elif isinstance(screen_filter, (list, tuple, set)):
            filter_screens = set(screen_filter)
        else:
            filter_screens = None

        for ns in self.options:
            # Skip options not applicable to the filtered screens
            if filter_screens is not None and hasattr(ns, 'effective_scope'):
                # Check if this option applies to any of the filter screens
                if not (ns.effective_scope & filter_screens):
                    continue

            # get / coerce the current value
            value = self.get_value(ns.attr)
            assert value is not None, f'cannot get value of {repr(ns.attr)}'

            colon = '' if ns.genre == 'action' else ':'
            win.add_body(f'{ns.descr:>{self.align}}{colon} ')

            if ns.genre in ('cycle', 'prompt'):
                choices = ns.vals if ns.vals else [value]
                for choice in choices:
                    shown = f'{choice}'
                    if isinstance(choice, bool):
                        shown = "ON" if choice else "off"
                    win.add_body(' ', resume=True)
                    win.add_body(shown, resume=True,
                        attr=curses.A_REVERSE if choice == value else None)

            for comment in ns.comments:
                win.add_body(f'{"":>{self.align}}:  {comment}')

    def do_key(self, key, win):
        """
        Processes a registered key press.

        If the option is a spinner, it rotates to the next value. If it
        requires a prompt, it calls ``win.answer()`` to get user input.

        :param key: The key code received from :py:meth:`ConsoleWindow.prompt`.
        :param win: The :py:class:`ConsoleWindow` instance for dialogs.
        :type key: int
        :type win: ConsoleWindow
        :returns: The new value of the option, or None if the key is unhandled.
        :rtype: Any or None
        """
        # Try scoped lookup first (if stack is available)
        ns = None
        if self.stack and hasattr(self.stack, 'curr') and self.stack.curr:
            current_screen = self.stack.curr.num
            ns = self.key_scopes.get((key, current_screen), None)

        # Fall back to global lookup (for backward compatibility without scopes)
        if ns is None:
            ns = self.key_to_option.get(key, None)

        if ns is None:
            return None
        value = self.get_value(ns.attr)
        if ns.genre == 'cycle':
            idx = ns.vals.index(value) if value in ns.vals else -1
            value = ns.vals[(idx+1) % len(ns.vals)] # choose next
        elif ns.genre == 'prompt':
            value = win.answer(prompt=ns.prompt, seed=str(value))
        elif ns.genre == 'action':
            value = True

        setattr(ns.obj, ns.attr, value)
        return value

class ConsoleWindow:
    """
    A high-level wrapper around the curses library that provides a structured
    interface for terminal applications.

    The screen is divided into a fixed-size **Header** area and a scrollable
    **Body** area, separated by an optional line. It manages screen
    initialization, cleanup, rendering, and user input including scrolling
    and an optional item selection (pick) mode.
    """
    timeout_ms = 2000
    static_scr = None
    nav_keys = """
        Navigation:      H/M/L:      top/middle/end-of-page
          k, UP:  up one row             0, HOME:  first row
        j, DOWN:  down one row           $, END:  last row
          Ctrl-u:  half-page up     Ctrl-b, PPAGE:  page up
          Ctrl-d:  half-page down     Ctrl-f, NPAGE:  page down
    """
    def __init__(self, opts=None, head_line=None, head_rows=None, body_rows=None,
                 body_cols=None, keys=None, pick_mode=None, pick_size=None,
                 mod_pick=None, ctrl_c_terminates=None):
        """
        Initializes the ConsoleWindow, sets up internal pads, and starts curses mode.

        :param opts: ConsoleWindowOpts instance with all options (recommended)
        :param head_line: DEPRECATED - use opts. If True, draws a horizontal line between header and body.
        :param head_rows: DEPRECATED - use opts. Maximum capacity of internal header pad.
        :param body_rows: DEPRECATED - use opts. Maximum capacity of internal body pad.
        :param body_cols: DEPRECATED - use opts. Maximum width for content pads.
        :param keys: DEPRECATED - use opts. Collection of key codes returned by prompt.
        :param pick_mode: DEPRECATED - use opts. If True, enables item highlighting/selection.
        :param pick_size: DEPRECATED - use opts. Number of rows highlighted as single pick unit.
        :param mod_pick: DEPRECATED - use opts. Optional callable to modify highlighted text.
        :param ctrl_c_terminates: DEPRECATED - use opts. If True, Ctrl-C terminates; if False, returns key 3.
        :type opts: ConsoleWindowOpts or None
        """
        # Enforce either opts OR deprecated parameters, not both
        has_opts = opts is not None
        has_deprecated = any(p is not None for p in [head_line, head_rows, body_rows, body_cols,
                                                       keys, pick_mode, pick_size, mod_pick, ctrl_c_terminates])

        if has_opts and has_deprecated:
            raise ValueError("Cannot use both 'opts' and deprecated parameters. Use opts only.")

        # Use opts or create default
        if has_opts:
            self.opts = opts
        elif has_deprecated:
            # Backward compatibility: create opts from deprecated parameters
            self.opts = ConsoleWindowOpts(
                head_line=head_line if head_line is not None else True,
                head_rows=head_rows if head_rows is not None else 50,
                body_rows=body_rows if body_rows is not None else 200,
                body_cols=body_cols if body_cols is not None else 200,
                keys=keys,
                pick_mode=pick_mode if pick_mode is not None else False,
                pick_size=pick_size if pick_size is not None else 1,
                mod_pick=mod_pick,
                ctrl_c_terminates=ctrl_c_terminates if ctrl_c_terminates is not None else True
            )
        else:
            # No parameters provided - use all defaults
            self.opts = ConsoleWindowOpts()

        # Modify signal handlers based on user choice
        global ignore_ctrl_c, restore_ctrl_c
        if self.opts.ctrl_c_terminates:
            # then never want to ignore_ctrl_c (so defeat the ignorer/restorer)
            def noop():
                return
            ignore_ctrl_c = restore_ctrl_c = noop
            self.ctrl_c_terminates = self.opts.ctrl_c_terminates
        else:
            # If not terminating, override the original signal functions
            # to set the custom handler, which will pass key 3 via the flag.
            def _setup_ctrl_c():
                signal.signal(signal.SIGINT, ctrl_c_handler)
            def _restore_ctrl_c():
                signal.signal(signal.SIGINT, signal.default_int_handler)
            ignore_ctrl_c = _setup_ctrl_c
            restore_ctrl_c = _restore_ctrl_c

        self.scr = self._start_curses()

        self.head = SimpleNamespace(
            pad=curses.newpad(self.opts.head_rows, self.opts.body_cols),
            rows=self.opts.head_rows,
            cols=self.opts.body_cols,
            row_cnt=0,  # no. head rows added
            texts = [],
            text_attrs = [],  # run-length encoded: [(attr, count), ...] per line
            contexts = [],  # Context object per line (or None)
            view_cnt=0,  # no. head rows viewable (NOT in body)
        )
        self.body = SimpleNamespace(
            pad = curses.newpad(self.opts.body_rows, self.opts.body_cols),
            rows= self.opts.body_rows,
            cols=self.opts.body_cols,
            row_cnt = 0,
            texts = [],
            text_attrs = [],  # run-length encoded: [(attr, count), ...] per line
            contexts = []  # Context object per line (or None)
        )
        self.mod_pick = self.opts.mod_pick # call back to modify highlighted row
        self.hor_line_cnt = 1 if self.opts.head_line else 0 # no. h-lines in header
        self.scroll_pos = 0  # how far down into body are we?
        self.max_scroll_pos = 0
        self.pick_pos = 0 # in highlight mode, where are we?
        self.last_pick_pos = -1 # last highlighted position
        self.pick_mode = self.opts.pick_mode # whether in highlight mode
        self.pick_size = self.opts.pick_size # whether in highlight mode
        self.rows, self.cols = 0, 0
        self.body_cols, self.body_rows = self.opts.body_cols, self.opts.body_rows
        self.scroll_view_size = 0  # no. viewable lines of the body
        self.handled_keys = set(self.opts.keys) if isinstance(self.opts.keys, (set, list)) else set()
        self.pending_keys = set()
        self.last_demo_key = ''  # Last key pressed in demo mode
        self.max_header_len = 0  # Max visible header length from previous render
        self.passthrough_mode = False  # When True, all printable keys pass through
        self._set_screen_dims()
        self.calc()

    def set_handled_keys(self, keys):
        """
        Set or update the keys that prompt() should return to the application.

        This allows keys to be set after initialization, breaking circular dependencies.

        :param keys: Collection of key codes (set, list, or OptionSpinner with .keys attribute)
        :type keys: set or list or OptionSpinner
        """
        if hasattr(keys, 'keys'):
            # It's an OptionSpinner or similar object
            self.handled_keys = set(keys.keys) if keys.keys else set()
        elif isinstance(keys, (set, list)):
            self.handled_keys = set(keys)
        else:
            self.handled_keys = set()

    def set_demo_mode(self, enabled):
        """
        Enable or disable demo mode.

        When demo mode is enabled, the last non-navigation key pressed is shown
        in reverse video at the end of the first header line.

        :param enabled: True to enable demo mode, False to disable
        :type enabled: bool
        """
        self.opts.demo_mode = enabled
        if not enabled:
            self.last_demo_key = ''

    def _format_key_for_demo(self, key):
        """
        Format a key code as a 3-character string for demo mode display.

        :param key: The key code to format
        :type key: int
        :returns: 3-character string representation of the key
        :rtype: str
        """
        # Special multi-character keys
        if key == 27:  # ESC
            return 'ESC'
        elif key == ord('\t'):
            return 'TAB'
        elif key == ord('\n') or key == curses.KEY_ENTER or key == 10 or key == 13:
            return 'ENT'
        elif key == ord(' '):
            return 'SPC'
        elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:
            return 'BSP'
        elif key == curses.KEY_DC:
            return 'DEL'
        # Printable single character keys - center with spaces
        elif 32 < key < 127:
            return f' {chr(key)} '
        # Default for unrecognized keys
        else:
            return '???'

    def get_pad_width(self):
        """
        Returns the maximum usable column width for content drawing.

        :returns: The width in columns.
        :rtype: int
        """
        return min(self.cols-1, self.body_cols)

    def _is_pickable(self, row):
        """
        Check if a body row is pickable.

        :param row: The row index to check
        :type row: int
        :returns: True if the row is pickable, False otherwise
        :rtype: bool
        """
        if row < 0 or row >= len(self.body.contexts):
            return True  # Default to pickable if no context
        ctx = self.body.contexts[row]
        if ctx is None:
            return True  # Default to pickable if no context
        return ctx.pickable

    def _count_pickable_rows(self, start_pos, count, direction=1):
        """
        Move through count pickable rows from start_pos in the given direction.

        This skips non-pickable rows (DECOR, TRANSIENT) so that page-up/down
        moves through a consistent number of actual content rows.

        :param start_pos: Starting row position
        :param count: Number of pickable rows to count
        :param direction: 1 for forward, -1 for backward
        :type start_pos: int
        :type count: int
        :type direction: int
        :returns: The row position after counting pickable rows
        :rtype: int
        """
        pos = start_pos
        pickable_count = 0

        while 0 <= pos < self.body.row_cnt and pickable_count < count:
            pos += direction
            if 0 <= pos < self.body.row_cnt and self._is_pickable(pos):
                pickable_count += 1

        return pos

    def get_picked_context(self):
        """
        Get the Context object for the currently picked line.

        :returns: The Context object for the current pick position, or None
        :rtype: Context or None
        """
        if not self.pick_mode:
            return None
        if self.pick_pos < 0 or self.pick_pos >= len(self.body.contexts):
            return None
        return self.body.contexts[self.pick_pos]

    def _cook_abut(self, abut_value):
        """
        Parse the abut attribute into [before, after] format.

        :param abut_value: Can be:
            - negative int: lines before (e.g., -3 -> [-3, 0])
            - positive int: lines after (e.g., 7 -> [0, 7])
            - list/tuple [before, after]: explicit range (e.g., [-5, 3])
        :returns: Tuple (before, after) where before <= 0 and after >= 0
        :rtype: tuple
        """
        if abut_value is None:
            return None

        if isinstance(abut_value, (list, tuple)):
            # Extract min negative and max positive
            before = min((x for x in abut_value if x < 0), default=0)
            after = max((x for x in abut_value if x >= 0), default=0)
            return (before, after)
        elif isinstance(abut_value, int):
            if abut_value < 0:
                return (abut_value, 0)
            else:
                return (0, abut_value)
        else:
            return None

    def _get_effective_abut(self, row):
        """
        Get the effective abut value for a row, either explicit or auto-calculated.

        For rows with TRANSIENT children, automatically calculates abut to show
        all consecutive TRANSIENT rows below.

        :param row: The row index to get abut for
        :type row: int
        :returns: Abut value (can be int, list, or None) suitable for _cook_abut()
        :rtype: int or list or None
        """
        if row < 0 or row >= len(self.body.contexts):
            return None

        ctx = self.body.contexts[row]
        if ctx is None:
            return None

        # Explicit abut takes precedence
        if hasattr(ctx, 'abut') and ctx.abut is not None:
            return ctx.abut

        # Auto-abut for TRANSIENT: count consecutive TRANSIENT rows below
        transient_count = 0
        for i in range(row + 1, self.body.row_cnt):
            next_ctx = self.body.contexts[i] if i < len(self.body.contexts) else None
            if next_ctx and next_ctx.genre == 'TRANSIENT':
                transient_count += 1
            else:
                break

        if transient_count > 0:
            return [0, transient_count]  # Show 0 before, N after

        return None

    @staticmethod
    def get_nav_keys_blurb():
        """
        Returns a multiline string describing the default navigation key bindings
        for use in help screens.

        :returns: String of navigation keys.
        :rtype: str
        """
        return textwrap.dedent(ConsoleWindow.nav_keys)

    def _set_screen_dims(self):
        """Recalculate dimensions based on current terminal size."""
        rows, cols = self.scr.getmaxyx()
        same = bool(rows == self.rows and cols == self.cols)
        self.rows, self.cols = rows, cols
        return same

    def _check_min_size(self):
        """
        Checks if current terminal size meets minimum requirements.
        Blocks with a message if too small, waiting for resize or ESC.

        :returns: True if size is acceptable, False if user pressed ESC to abort
        :rtype: bool
        """
        min_cols, min_rows = self.opts.min_cols_rows

        while self.rows < min_rows or self.cols < min_cols:
            self.scr.clear()
            msg1 = f"Min size: {min_cols}x{min_rows}"
            msg2 = f"Current: {self.cols}x{self.rows}"
            try:
                self.scr.addstr(0, 0, msg1, curses.A_REVERSE)
                self.scr.addstr(1, 0, msg2, curses.A_REVERSE)
            except curses.error:
                pass  # Terminal too small even for message
            self.scr.refresh()

            # Wait for key
            key = self.scr.getch()
            if key == 27:  # ESC to abort
                return False
            if key == curses.KEY_RESIZE:
                curses.update_lines_cols()
                self._set_screen_dims()

        return True

    @staticmethod
    def _start_curses():
        """
        For compatibility only. Used to be private, but that was annoying.
        """
        return ConsoleWindow.start_curses()

    @staticmethod
    def start_curses():
        """
        Performs the Curses initial setup: initscr, noecho, cbreak, curs_set(0),
        keypad(1), and sets up the timeout.

        :returns: The main screen object.
        :rtype: _curses.window
        """
        # The signal setup is handled in __init__ (via ignore_ctrl_c call below)
        atexit.register(ConsoleWindow.stop_curses)
        ignore_ctrl_c()
        ConsoleWindow.static_scr = scr = curses.initscr()
        curses.set_escdelay(25)  # Reduce ESC key delay from 1000ms to 25ms
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        scr.keypad(1)
        scr.timeout(ConsoleWindow.timeout_ms)
        scr.clear()
        return scr

    def set_pick_mode(self, on=True, pick_size=1):
        """
        Toggles the item highlighting/selection mode for the body area.

        If pick mode is enabled or the pick size changes, it forces a redraw
        of all body lines to clear any previous highlighting attributes.

        :param on: If True, enables pick mode.
        :param pick_size: The number of consecutive rows to highlight as one unit.
        :type on: bool
        :type pick_size: int
        """
        was_on, was_size = self.pick_mode, self.pick_size
        self.pick_mode = bool(on)
        self.pick_size = max(pick_size, 1)
        if self.pick_mode and (not was_on or was_size != self.pick_size):
            self.last_pick_pos = -2 # indicates need to clear them all

    @staticmethod
    def stop_curses():
        """
        Curses shutdown (registered to be called on exit). Restores the terminal
        to its pre-curses state.
        """
        if ConsoleWindow.static_scr:
            curses.nocbreak()
            curses.echo()
            ConsoleWindow.static_scr.keypad(0)
            curses.endwin()
            ConsoleWindow.static_scr = None
            restore_ctrl_c()

    def calc(self):
        """
        Recalculates the screen geometry, viewable areas, and maximum scroll position.

        :returns: True if the screen geometry has changed, False otherwise.
        :rtype: bool
        """
        same = self._set_screen_dims()
        self.head.view_cnt = min(self.rows - self.hor_line_cnt, self.head.row_cnt)
        self.scroll_view_size = self.rows - self.head.view_cnt - self.hor_line_cnt
        self.max_scroll_pos = max(self.body.row_cnt - self.scroll_view_size, 0)
        self.body_base = self.head.view_cnt + self.hor_line_cnt
        return not same

    def _put(self, ns, *args, context=None):
        """
        Adds text to the head/body pad using a mixed argument list.

        Allows interleaving of text (str/bytes) and curses attributes (int).
        Text segments before an attribute are flushed with that attribute.

        :param context: Optional Context object with metadata for this line.
        :type context: Context or None
        """
        def flush(attr=None):
            nonlocal self, is_body, row, text, seg, first, attrs_list
            if attr is None:
                attr = curses.A_NORMAL
            # Apply stripping logic if needed
            if is_body and self.pick_mode and self.opts.strip_attrs_in_pick_mode:
                attr = curses.A_NORMAL

            if seg and first:
                ns.pad.addstr(row, 0, seg[0:self.get_pad_width()], attr)
                attrs_list.append((attr, len(seg)))
            elif seg:
                _, x = ns.pad.getyx()
                cols = self.get_pad_width() - x
                if cols > 0:
                    actual_seg = seg[0:cols]
                    ns.pad.addstr(actual_seg, attr)
                    attrs_list.append((attr, len(actual_seg)))
            text += seg
            seg, first, attr = '', False, None

        is_body = bool(id(ns) == id(self.body))
        if ns.row_cnt < ns.rows:
            row = max(ns.row_cnt, 0)
            text, seg, first = '', '', True
            attrs_list = []  # run-length encoded attributes
            for arg in args:
                if isinstance(arg, bytes):
                    arg = arg.decode('utf-8')
                if isinstance(arg, str):
                    seg += arg  # note: add w/o spacing
                elif arg is None or isinstance(arg, (int)):
                    # assume arg is attribute ... flushes text
                    flush(attr=arg)
            flush()
            ns.texts.append(text)  # text only history
            ns.text_attrs.append(attrs_list)  # run-length encoded attributes
            ns.contexts.append(context)  # Context metadata (or None)
            ns.row_cnt += 1

    def put_head(self, *args, context=None):
        """
        Adds a line of text to the header pad, supporting mixed text and attributes.

        :param args: Mixed arguments of str/bytes (text) and int (curses attributes).
        :param context: Optional Context object with metadata for this line.
        :type args: Any
        :type context: Context or None
        """
        self._put(self.head, *args, context=context)

    def put_body(self, *args, context=None):
        """
        Adds a line of text to the body pad, supporting mixed text and attributes.

        :param args: Mixed arguments of str/bytes (text) and int (curses attributes).
        :param context: Optional Context object with metadata for this line.
        :type args: Any
        :type context: Context or None
        """
        self._put(self.body, *args, context=context)

    def _add(self, ns, text, attr=None, resume=False, context=None):
        """Internal method to add text to pad using its namespace (simpler version of _put)."""
        is_body = bool(id(ns) == id(self.body))
        if ns.row_cnt < ns.rows:
            row = max(ns.row_cnt - (1 if resume else 0), 0)
            if attr is None:
                attr = curses.A_NORMAL
            # Apply stripping logic if needed
            if is_body and self.pick_mode and self.opts.strip_attrs_in_pick_mode:
                attr = curses.A_NORMAL

            if resume:
                _, x = ns.pad.getyx()
                cols = self.get_pad_width() - x
                if cols > 0:
                    actual_text = text[0:cols]
                    ns.pad.addstr(actual_text, attr)
                    ns.texts[row] += actual_text
                    # Append to existing attrs list
                    if row < len(ns.text_attrs):
                        ns.text_attrs[row].append((attr, len(actual_text)))
                    # Note: context not updated on resume
            else:
                actual_text = text[0:self.cols]
                ns.pad.addstr(row, 0, actual_text, attr)
                ns.texts.append(actual_text)  # text only history
                ns.text_attrs.append([(attr, len(actual_text))])  # run-length encoded
                ns.contexts.append(context)  # Context metadata (or None)
                ns.row_cnt += 1

    def add_header(self, text, attr=None, resume=False, context=None):
        """
        Adds a line of text to the header pad.

        :param text: The text to add.
        :param attr: Curses attribute (e.g., curses.A_BOLD).
        :param resume: If True, adds the text to the current, incomplete line.
        :param context: Optional Context object with metadata for this line.
        :type text: str
        :type attr: int or None
        :type resume: bool
        :type context: Context or None
        """
        self._add(self.head, text, attr, resume, context)

    def add_body(self, text, attr=None, resume=False, context=None):
        """
        Adds a line of text to the body pad.

        :param text: The text to add.
        :param attr: Curses attribute (e.g., curses.A_BOLD).
        :param resume: If True, adds the text to the current, incomplete line.
        :param context: Optional Context object with metadata for this line.
        :type text: str
        :type attr: int or None
        :type resume: bool
        :type context: Context or None
        """
        self._add(self.body, text, attr, resume, context)

    def add_fancy_header(self, line, mode='Underline'):
        """
        Parses header line and adds it with fancy formatting.

        Modes:
        - 'Off': Normal formatting (no special handling)
        - 'Underline': Underlined and bold keys
        - 'Reverse': Reverse video keys

        Converts [x]text to formatted x (brackets removed).
        Handles x:text patterns by formatting x.
        Handles /pattern by highlighting the entire pattern.
        Multi-character keys like ESC:, ENTER:, TAB: are supported.

        :param line: The header text to add with formatting
        :param mode: Formatting mode ('Off', 'Underline', or 'Reverse')
        :type line: str
        :type mode: str
        """
        if mode == 'Off':
            # Fancy mode off, just add the line normally
            self.add_header(line)
            return

        # Choose the attribute based on mode
        key_attr = (curses.A_UNDERLINE | curses.A_BOLD) if mode == 'Underline' else curses.A_REVERSE

        # List of (text, attr) tuples
        result_sections = []
        i = 0
        current_text = ""

        # Check if line starts with all-caps word and extract it
        stripped = line.lstrip()
        if stripped:
            first_word_match = stripped.split()[0] if stripped.split() else ''
            if first_word_match and re.match(r'^[\w-]+$', first_word_match):
                # Add leading whitespace
                leading_space = line[:len(line) - len(stripped)]
                if leading_space:
                    result_sections.append((leading_space, None))
                # Add the all-caps word in BOLD
                result_sections.append((first_word_match, curses.A_BOLD))
                # Skip past it in our processing
                i = len(leading_space) + len(first_word_match)

        while i < len(line):
            # Check for [x]text pattern
            if line[i] == '[' and i + 2 < len(line) and line[i + 2] == ']':
                # Save any accumulated normal text
                if current_text:
                    result_sections.append((current_text, None))
                    current_text = ""

                # Extract the key letter and add it with chosen attribute
                key_char = line[i + 1]
                result_sections.append((key_char, key_attr))
                i += 3  # Skip past [x]

            # Check for multi-character key names like ESC:, ENTER:, TAB:
            elif (i == 0 or line[i - 1] == ' '):
                # Look ahead for uppercase word followed by colon
                match = re.match(r'([A-Z]{2,}|[A-Z]):', line[i:])
                if match:
                    # Found a key name followed by colon
                    if current_text:
                        result_sections.append((current_text, None))
                        current_text = ""

                    key_name = match.group(1)
                    result_sections.append((key_name, key_attr))
                    result_sections.append((':', None))  # Add the colon without formatting
                    i += len(key_name) + 1  # Skip past key and colon
                else:
                    match = re.match(r'/(\S+)', line[i:])
                    if match:
                        # Found a search pattern
                        if current_text:
                            result_sections.append((current_text, None))
                            current_text = ""

                        full_pattern = match.group(0)  # includes the /
                        result_sections.append((full_pattern, curses.A_BOLD | curses.A_REVERSE))
                        i += len(full_pattern)
                    else:
                        # Not a key pattern, just regular character
                        current_text += line[i]
                        i += 1

            else:
                # Regular character
                current_text += line[i]
                i += 1

        # Add any remaining text
        if current_text:
            result_sections.append((current_text, None))

        # Calculate visible length of this header line
        visible_length = sum(len(text) for text, attr in result_sections)

        # Check if this is the first header line
        is_first_header = (self.head.row_cnt == 0)

        # Add demo indicator to first header if demo mode is active
        if is_first_header and self.opts.demo_mode and self.last_demo_key:
            # Pad to max_header_len + 2 spaces
            padding_needed = max(0, self.max_header_len + 2 - visible_length)
            if padding_needed > 0:
                result_sections.append((' ' * padding_needed, None))
            # Add demo key in reverse video
            result_sections.append((self.last_demo_key, curses.A_REVERSE))

        # Now output the sections using add_header with resume
        for idx, (text, attr) in enumerate(result_sections):
            resume = bool(idx > 0)  # Resume for all but the first section
            self.add_header(text, attr=attr, resume=resume)

        # Track max header length for next render (excluding demo indicator)
        if visible_length > self.max_header_len:
            self.max_header_len = visible_length

    def draw(self, y, x, text, text_attr=None, width=None, leftpad=False, header=False):
        """
        Draws the given text at a specific position (row=y, col=x) on a pad.

        This method is useful for structured or overlay drawing, but is less
        efficient than the standard add/put methods.

        :param y: The row index on the pad.
        :param x: The column index on the pad.
        :param text: The text to draw (str or bytes).
        :param text_attr: Optional curses attribute.
        :param width: Optional fixed width for the drawn text (pads/truncates).
        :param leftpad: If True and ``width`` is used, left-pads with spaces.
        :param header: If True, draws to the header pad, otherwise to the body pad.
        :type y: int
        :type x: int
        :type text: str or bytes
        :type text_attr: int or None
        :type width: int or None
        :type leftpad: bool
        :type header: bool
        """
        ns = self.head if header else self.body
        text_attr = text_attr if text_attr else curses.A_NORMAL
        if y < 0 or y >= ns.rows or x < 0 or x >= ns.cols:
            return # nada if out of bounds
        ns.row_cnt = max(ns.row_cnt, y+1)

        uni = text if isinstance(text, str) else text.decode('utf-8')

        if width is not None:
            width = min(width, self.get_pad_width() - x)
            if width <= 0:
                return
            padlen = width - len(uni)
            if padlen > 0:
                if leftpad:
                    uni = padlen * ' ' + uni
                else:  # rightpad
                    uni += padlen * ' '
            text = uni[:width].encode('utf-8')
        else:
            text = uni.encode('utf-8')

        try:
            while y >= len(ns.texts):
                ns.texts.append('')
            ns.texts[y] = ns.texts[y][:x].ljust(x) + uni + ns.texts[y][x+len(uni):]
            ns.pad.addstr(y, x, text, text_attr)
        except curses.error:
            # curses errors on drawing the last character on the screen; ignore
            pass


    def highlight_picked(self):
        """
        Highlights the current selection and un-highlights the previous one.
        Called internally during :py:meth:`render_once` when in pick mode.
        """
        def get_text(pos):
            nonlocal self
            return self.body.texts[pos][0:self.cols] if pos < len(self.body.texts) else ''

        def get_attrs(pos):
            nonlocal self
            return self.body.text_attrs[pos] if pos < len(self.body.text_attrs) else None

        if not self.pick_mode:
            return
        pos0, pos1 = self.last_pick_pos, self.pick_pos
        if pos0 == -2: # special flag to clear all formatting
            for row in range(self.body.row_cnt):
                text = get_text(row).ljust(self.get_pad_width())
                attrs = get_attrs(row)
                self._draw_line_with_attrs(self.body.pad, row, 0, text, attrs, extra_attr=None)
        if pos0 != pos1:
            if 0 <= pos0 < self.body.row_cnt:
                for i in range(self.pick_size):
                    row_idx = pos0 + i
                    if row_idx < len(self.body.texts):
                        text = get_text(row_idx).ljust(self.get_pad_width())
                        attrs = get_attrs(row_idx)
                        self._draw_line_with_attrs(self.body.pad, row_idx, 0, text, attrs, extra_attr=None)
            if 0 <= pos1 < self.body.row_cnt:
                for i in range(self.pick_size):
                    row_idx = pos1 + i
                    if row_idx < len(self.body.texts):
                        text = get_text(row_idx)
                        if self.mod_pick:
                            text = self.mod_pick(text)
                        text = text.ljust(self.get_pad_width())
                        attrs = get_attrs(row_idx)

                        self._draw_line_with_attrs(self.body.pad, row_idx, 0, text, attrs, extra_attr=self.opts.pick_attr)
                self.last_pick_pos = pos1

    def _draw_line_with_attrs(self, pad, row, col_offset, text, attrs, extra_attr=None):
        """
        Draw a line using run-length encoded attributes.

        :param pad: The pad to draw on
        :param row: Row index in the pad
        :param col_offset: Starting column
        :param text: The text to draw
        :param attrs: Run-length encoded attributes [(attr, count), ...] or None
        :param extra_attr: Additional attribute to OR with each segment (e.g., A_REVERSE for highlighting)
        """
        if not attrs:
            # No stored attributes - draw with normal or extra_attr
            final_attr = extra_attr if extra_attr is not None else curses.A_NORMAL
            pad.addstr(row, col_offset, text[0:self.get_pad_width()-col_offset], final_attr)
            return

        col = col_offset
        pos = 0
        for attr, count in attrs:
            if pos >= len(text):
                break
            segment = text[pos:pos+count]
            final_attr = attr
            if extra_attr is not None:
                final_attr = attr | extra_attr

            # Ensure we don't exceed pad width
            max_len = self.get_pad_width() - col
            if max_len <= 0:
                break
            segment = segment[0:max_len]

            pad.addstr(row, col, segment, final_attr)
            col += len(segment)
            pos += count

    def _scroll_indicator_row(self):
        """Internal helper to compute the scroll indicator row position."""
        if self.max_scroll_pos <= 1:
            return self.body_base
        y2, y1 = self.scroll_view_size-1, 1
        x2, x1 = self.max_scroll_pos, 1
        x = self.scroll_pos
        pos = y1 + (y2-y1)*(x-x1)/(x2-x1)
        return min(self.body_base + int(max(pos, 0)), self.rows-1)

    def _scroll_indicator_col(self):
        """Internal helper to compute the scroll indicator column position."""
        if self.pick_mode:
            return self._calc_indicator(
                self.pick_pos, 0, self.body.row_cnt-1, 0, self.cols-1)
        return self._calc_indicator(
            self.scroll_pos, 0, self.max_scroll_pos, 0, self.cols-1)

    def _calc_indicator(self, pos, pos0, pos9, ind0, ind9):
        """Internal helper to calculate indicator position based on content position."""
        if self.max_scroll_pos <= 0:
            return -1 # not scrollable
        if pos9 - pos0 <= 0:
            return -1 # not scrollable
        if pos <= pos0:
            return ind0
        if pos >= pos9:
            return ind9
        ind = int(round(ind0 + (ind9-ind0+1)*(pos-pos0)/(pos9-pos0+1)))
        return min(max(ind, ind0+1), ind9-1)

    def render(self, redraw=False):
        """
        Draws the content of the pads to the visible screen.

        :param redraw: If True, forces a complete redraw of all pads and the screen
                    to clear terminal corruption.

        This method wraps :py:meth:`render_once` in a loop to handle spurious
        ``curses.error`` exceptions that can occur during screen resizing.
        """
        for _ in range(128):
            try:
                self.render_once(redraw)
                return
            except curses.error:
                time.sleep(0.16)
                self._set_screen_dims()
                continue
        try:
            self.render_once(redraw)
        except Exception:
            ConsoleWindow.stop_curses()
            print(f"""curses err:
    head.row_cnt={self.head.row_cnt}
    head.view_cnt={self.head.view_cnt}
    hor_line_cnt={self.hor_line_cnt}
    body.row_cnt={self.body.row_cnt}
    scroll_pos={self.scroll_pos}
    max_scroll_pos={self.max_scroll_pos}
    pick_pos={self.pick_pos}
    last_pick_pos={self.last_pick_pos}
    pick_mode={self.pick_mode}
    pick_size={self.pick_size}
    rows={self.rows}
    cols={self.cols}
""")
            raise


    def fix_positions(self, delta=0):
        """
        Ensures the vertical scroll and pick positions are within valid boundaries,
        adjusting the scroll position to keep the pick cursor visible.

        :param delta: An optional change in position (e.g., from key presses).
        :type delta: int
        :returns: The indent amount for the body content (1 if pick mode is active, 0 otherwise).
        :rtype: int
        """
        self.calc()

        # Save old pick position to check for abut constraints before applying delta
        old_pick_pos = self.pick_pos if self.pick_mode else -1

        if self.pick_mode:
            self.pick_pos += delta
        else:
            self.scroll_pos += delta
            self.pick_pos += delta

        indent = 0
        if self.body_base < self.rows:
            ind_pos = 0 if self.pick_mode else self._scroll_indicator_row()
            if self.pick_mode:
                # First, get abut range from the PREVIOUS pick position (before delta was applied)
                abut_range = None
                if 0 <= old_pick_pos < len(self.body.contexts):
                    effective_abut = self._get_effective_abut(old_pick_pos)
                    if effective_abut is not None:
                        cooked = self._cook_abut(effective_abut)
                        if cooked:
                            before, after = cooked
                            # Calculate the valid line range based on old position
                            min_line = max(0, old_pick_pos + before)
                            max_line = min(self.body.row_cnt - 1, old_pick_pos + after)
                            abut_range = (min_line, max_line)

                # Clamp pick_pos to valid bounds
                self.pick_pos = max(self.pick_pos, 0)
                self.pick_pos = min(self.pick_pos, self.body.row_cnt-1)

                # If abut range exists, further constrain pick_pos within that range
                if abut_range:
                    min_line, max_line = abut_range
                    self.pick_pos = max(self.pick_pos, min_line)
                    self.pick_pos = min(self.pick_pos, max_line)

                if self.pick_pos >= 0:
                    self.pick_pos -= (self.pick_pos % self.pick_size)

                # Re-check for abut in the CURRENT pick position for scroll adjustment
                abut_range = None
                effective_abut = self._get_effective_abut(self.pick_pos)
                if effective_abut is not None:
                    cooked = self._cook_abut(effective_abut)
                    if cooked:
                        before, after = cooked
                        # Calculate the valid line range: [min_line, max_line]
                        min_line = max(0, self.pick_pos + before)
                        max_line = min(self.body.row_cnt - 1, self.pick_pos + after)
                        abut_range = (min_line, max_line)

                if self.pick_pos < 0:
                    self.scroll_pos = 0
                elif abut_range:
                    # Apply abut constraints: "after trumps before"
                    min_line, max_line = abut_range
                    range_size = max_line - min_line + 1

                    if range_size <= self.scroll_view_size:
                        # Entire range fits: minimal scrolling to keep it visible
                        # Only scroll if the range would go off-screen
                        viewport_bottom = self.scroll_pos + self.scroll_view_size - 1

                        # Check if the range would go below viewport (prioritize "after" lines)
                        if max_line > viewport_bottom:
                            # Scroll down just enough to show max_line at the bottom
                            self.scroll_pos = max_line - self.scroll_view_size + 1
                        # Check if the range would go above viewport
                        elif min_line < self.scroll_pos:
                            # Scroll up to show min_line at the top
                            self.scroll_pos = min_line
                        # else: range is already fully visible, don't scroll
                    else:
                        # Range doesn't fit: minimal scrolling to keep picked line + abut lines visible
                        # Priority: keep "after" lines visible (they take precedence over "before" lines)

                        # Calculate the bottom of the current viewport
                        viewport_bottom = self.scroll_pos + self.scroll_view_size - 1

                        # Check if picked line + after lines would go below viewport
                        if max_line > viewport_bottom:
                            # Need to scroll down: position so max_line is at bottom of viewport
                            self.scroll_pos = max_line - self.scroll_view_size + 1
                        # Check if picked line + before lines would go above viewport
                        elif min_line < self.scroll_pos:
                            # Need to scroll up: position so min_line is at top of viewport
                            self.scroll_pos = min_line
                        # else: picked line + abut range is already fully visible, don't scroll

                        # Ensure we don't show lines above min_line or beyond max_line
                        self.scroll_pos = max(self.scroll_pos, min_line)
                        max_scroll = max_line - self.scroll_view_size + 1
                        self.scroll_pos = min(self.scroll_pos, max_scroll)
                elif self.scroll_pos > self.pick_pos:
                    # light position is below body bottom
                    self.scroll_pos = self.pick_pos
                elif self.scroll_pos < self.pick_pos - (self.scroll_view_size - self.pick_size):
                    # light position is above body top
                    self.scroll_pos = self.pick_pos - (self.scroll_view_size - self.pick_size)

                self.scroll_pos = max(self.scroll_pos, 0)
                self.scroll_pos = min(self.scroll_pos, self.max_scroll_pos)
                indent = 1
            else:
                self.scroll_pos = max(self.scroll_pos, 0)
                self.scroll_pos = min(self.scroll_pos, self.max_scroll_pos)
                self.pick_pos = self.scroll_pos + ind_pos - self.body_base
                # indent = 1 if self.body.row_cnt > self.scroll_view_size else 0
        return indent


    # Assuming this function is part of a class with attributes like self.scr, self.head, self.body, etc.

    def render_once(self, redraw: bool = False):
        """
        Performs the actual rendering of header, horizontal line, and body pads.
        Handles pick highlighting and scroll bar drawing.

        :param redraw: If True, forces a complete redraw of all pads and the screen
                    to clear terminal corruption.
        """

        # --- 1. Preparation and Conditional Redrawwin ---

        if redraw:
            # Mark the main screen and all pads as requiring a full repaint.
            self.scr.redrawwin()
            self.head.pad.redrawwin()
            self.body.pad.redrawwin()

        indent = self.fix_positions()

        # --- 2. Screen Drawing (Highlighting, Scrollbar, Separator) ---

        if indent > 0 and self.pick_mode:
            self.scr.vline(self.body_base, 0, ' ', self.scroll_view_size)
            if self.pick_pos >= 0:
                pos = self.pick_pos - self.scroll_pos + self.body_base
                self.scr.addstr(pos, 0, '>', curses.A_REVERSE)

        if self.head.view_cnt < self.rows:
            self.scr.hline(self.head.view_cnt, 0, curses.ACS_HLINE, self.cols)
            ind_pos = self._scroll_indicator_col()
            if ind_pos >= 0:
                bot, cnt = ind_pos, 1
                if not self.opts.single_cell_scroll_indicator and 0 < ind_pos < self.cols-1:
                    # Proportional range indicator
                    width = self.scroll_view_size/self.body.row_cnt*self.cols
                    bot = max(int(round(ind_pos-width/2)), 1)
                    top = min(int(round(ind_pos+width/2)), self.cols-1)
                    cnt = max(top - bot, 1)

                for idx in range(bot, bot+cnt):
                    self.scr.addch(self.head.view_cnt, idx, curses.ACS_HLINE, curses.A_REVERSE)

        # Instead of self.scr.refresh(), use pnoutrefresh/doupdate for efficiency.
        # The 'redrawwin' above handles the forced repaint, so we just call 'noutrefresh'.
        self.scr.noutrefresh()

        # --- 3. Pad Drawing (Body and Head) ---

        if self.body_base < self.rows:
            if self.pick_mode:
                self.highlight_picked()

            self.body.pad.noutrefresh(
                self.scroll_pos, 0,
                self.body_base, indent, self.rows-1, self.cols-1
            )

        if self.rows > 0:
            last_row = min(self.head.view_cnt, self.rows)-1
            if last_row >= 0:
                self.head.pad.noutrefresh(
                    0, 0,
                    0, indent, last_row, self.cols-1
                )

        # --- 4. Final Update (Only one physical screen update) ---
        curses.doupdate()


    def answer(self, prompt='Type string [then Enter]', seed='', width=80, height=5, esc_abort=None):
        """
        Presents a modal dialog box with working horizontal scroll indicators.
        Uses opts.dialog_abort to determine ESC behavior and opts.dialog_return for submit key.

        :param esc_abort: DEPRECATED. Use opts.dialog_abort instead. If provided, overrides opts.dialog_abort.
        """
        # Handle deprecated esc_abort parameter for backward compatibility
        if esc_abort is not None:
            dialog_abort = 'ESC' if esc_abort else None
        else:
            dialog_abort = self.opts.dialog_abort
        def draw_rectangle(scr, r1, c1, r2, c2):
            """Draws a box using standard curses characters."""
            scr.border(0)
            for r in range(r1, r2 + 1):
                if r == r1 or r == r2:
                    # Draw horizontal lines
                    for c in range(c1 + 1, c2):
                        scr.addch(r, c, curses.ACS_HLINE)
                if r > r1 and r < r2:
                    # Draw vertical lines
                    scr.addch(r, c1, curses.ACS_VLINE)
                    scr.addch(r, c2, curses.ACS_VLINE)
            # Draw corners
            scr.addch(r1, c1, curses.ACS_ULCORNER)
            scr.addch(r1, c2, curses.ACS_URCORNER)
            scr.addch(r2, c1, curses.ACS_LLCORNER)
            scr.addch(r2, c2, curses.ACS_LRCORNER)

        input_string = list(seed)
        cursor_pos = len(input_string)
        v_scroll_top = 0
        last_esc_time = None  # For ESC-ESC tracking 

        def calculate_geometry(self):
            # ... (Geometry calculation logic remains the same) ...
            self.rows, self.cols = self.scr.getmaxyx()
            min_cols, min_rows = self.opts.min_cols_rows
            min_height_needed = max(height + 4, min_rows)
            min_cols_needed = max(30, min_cols)
            if self.rows < min_height_needed or self.cols < min_cols_needed:
                return False, None, None, None, None

            max_display_width = self.cols - 6
            text_win_width = min(width, max_display_width)
            row0 = self.rows // 2 - (height // 2 + 1)
            row9 = row0 + height + 1
            col0 = (self.cols - (text_win_width + 2)) // 2

            return True, row0, row9, col0, text_win_width

        success, row0, row9, col0, text_win_width = calculate_geometry(self)
        if not success:
            return seed

        # Set longer timeout for dialog - redraw every 5s for screen recovery
        # This prevents flicker (was 200ms) while recovering from corruption
        self.scr.timeout(5000)  # 5 second timeout for auto-refresh

        # DEBUG: Set to True to show redraw indicator in upper-left corner
        debug_show_redraws = self.opts.answer_show_redraws
        debug_redraw_toggle = False

        while True:
            try:
                success, row0, row9, col0, text_win_width = calculate_geometry(self)
                
                # --- RESIZE/TOO SMALL CHECK ---
                if not success:
                    min_cols, min_rows = self.opts.min_cols_rows
                    min_height_needed = max(height + 4, min_rows)
                    min_cols_needed = max(30, min_cols)
                    self.scr.clear()
                    msg = f"Min size: {min_cols_needed}x{min_height_needed}"
                    try:
                        self.scr.addstr(0, 0, msg, curses.A_REVERSE)
                    except curses.error:
                        pass  # Terminal too small even for message
                    self.scr.noutrefresh()
                    curses.doupdate()
                    key = self.scr.getch()
                    if key in [27]:
                        self.scr.timeout(ConsoleWindow.timeout_ms)
                        return None
                    if key == curses.KEY_RESIZE: curses.update_lines_cols()
                    continue

                self.scr.clear()

                # Draw the box using the imported rectangle function
                draw_rectangle(self.scr, row0, col0, row9, col0 + text_win_width + 1)

                # DEBUG: Toggle indicator to visualize redraws
                if debug_show_redraws:
                    debug_redraw_toggle = not debug_redraw_toggle
                    indicator = '*' if debug_redraw_toggle else '+'
                    self.scr.addstr(row0, col0, indicator)

                self.scr.addstr(row0, col0 + 1, prompt[:text_win_width])

                # --- Core Display and Scroll Indicator Logic ---

                wrapped_line_idx = cursor_pos // text_win_width
                cursor_offset_on_wrapped_line = cursor_pos % text_win_width

                # Vertical scroll adjustment
                if wrapped_line_idx < v_scroll_top:
                    v_scroll_top = wrapped_line_idx
                elif wrapped_line_idx >= v_scroll_top + height:
                    v_scroll_top = wrapped_line_idx - height + 1

                # Horizontal scroll start calculation
                h_scroll_start = max(0, cursor_offset_on_wrapped_line - text_win_width + 1)

                # Calculate total wrapped lines for overflow detection
                total_wrapped_lines = (len(input_string) + text_win_width - 1) // text_win_width
                if len(input_string) == 0:
                    total_wrapped_lines = 1
                
                # Display the visible lines
                for r in range(height):
                    current_wrapped_line_idx = v_scroll_top + r
                    
                    start_char_idx = current_wrapped_line_idx * text_win_width
                    end_char_idx = start_char_idx + text_win_width
                    
                    if start_char_idx > len(input_string) and r > 0:
                        break

                    raw_wrapped_line = "".join(input_string[start_char_idx:end_char_idx])
                    line_to_display = raw_wrapped_line
                    current_h_scroll_start = 0

                    is_cursor_line = (current_wrapped_line_idx == wrapped_line_idx)
                    
                    if is_cursor_line:
                        line_to_display = raw_wrapped_line[h_scroll_start:]
                        current_h_scroll_start = h_scroll_start
                        
                    # 1. Clear the content area (important for redraw integrity)
                    self.scr.addstr(row0 + 1 + r, col0 + 1, ' ' * text_win_width)
                    # 2. Display the text
                    self.scr.addstr(row0 + 1 + r, col0 + 1, line_to_display[:text_win_width])
                    
                    # --- SCROLL INDICATOR LOGIC ---
                    if is_cursor_line:
                        left_indicator = curses.ACS_VLINE 
                        right_indicator = curses.ACS_VLINE
                        
                        # Left Indicator Check
                        if current_h_scroll_start > 0:
                            # If content is scrolled right, show '<'
                            left_indicator = ord('<') 

                        # Right Indicator Check
                        full_line_len = len(raw_wrapped_line)
                        if full_line_len > current_h_scroll_start + text_win_width:
                            # If there's more content to the right, show '>'
                            right_indicator = ord('>') 
                        
                        # Draw Indicators (overwrite the border's vertical line)
                        self.scr.addch(row0 + 1 + r, col0, left_indicator)
                        self.scr.addch(row0 + 1 + r, col0 + text_win_width + 1, right_indicator)

                        # Highlight the cursor position
                        display_cursor_pos = cursor_pos - start_char_idx - current_h_scroll_start
                        char_at_cursor = line_to_display[display_cursor_pos] if display_cursor_pos < len(line_to_display) else " "

                        self.scr.addstr(row0 + 1 + r, col0 + 1 + display_cursor_pos,
                                        char_at_cursor, curses.A_REVERSE)

                        # Set the actual hardware cursor
                        self.scr.move(row0 + 1 + r, col0 + 1 + display_cursor_pos)

                # --- CORNER OVERFLOW INDICATORS ---
                # Upper left (one line down): show if scrolled down or scrolled right
                has_content_above = v_scroll_top > 0
                has_content_left = h_scroll_start > 0
                if has_content_above or has_content_left:
                    self.scr.addch(row0 + 1, col0, '◀', curses.A_BOLD)

                # Lower right (one line up): show if there's content below or to the right
                has_content_below = (v_scroll_top + height) < total_wrapped_lines
                # Check if cursor line has content beyond the visible window
                cursor_line_start = wrapped_line_idx * text_win_width
                cursor_line_end = cursor_line_start + text_win_width
                cursor_line_full_len = min(len(input_string), cursor_line_end) - cursor_line_start
                has_content_right = cursor_line_full_len > (h_scroll_start + text_win_width)
                if has_content_below or has_content_right:
                    self.scr.addch(row9 - 1, col0 + text_win_width + 1, '▶', curses.A_BOLD)

                # Footer and refresh
                submit_key = self.opts.dialog_return
                abort = ''
                if dialog_abort == 'ESC':
                    abort = ' or ESC to abort'
                elif dialog_abort == 'ESC-ESC':
                    abort = ' or ESC-ESC to abort'
                ending = f'{submit_key} to submit{abort}'
                self.scr.addstr(row9, col0 + 1 + text_win_width - len(ending), ending[:text_win_width])
                self.scr.noutrefresh()
                curses.doupdate()
                curses.curs_set(0)  # Hide hardware cursor; reverse video shows position

                key = self.scr.getch()

                # --- Key Handling Logic ---
                # Handle dialog_return (submit)
                if self.opts.dialog_return == 'ENTER' and key in [10, 13]:
                    curses.curs_set(0)
                    self.scr.timeout(ConsoleWindow.timeout_ms)
                    return "".join(input_string)
                elif self.opts.dialog_return == 'TAB' and key == 9:
                    curses.curs_set(0)
                    self.scr.timeout(ConsoleWindow.timeout_ms)
                    return "".join(input_string)

                # Handle dialog_abort (ESC and ESC-ESC)
                if key == 27:
                    if dialog_abort == 'ESC':
                        self.scr.timeout(ConsoleWindow.timeout_ms)
                        return None
                    elif dialog_abort == 'ESC-ESC':
                        current_time = time.time()
                        if last_esc_time is not None and (current_time - last_esc_time) <= 1.0:
                            self.scr.timeout(ConsoleWindow.timeout_ms)
                            return None  # Double ESC within timeout
                        last_esc_time = current_time
                        # Single ESC - just update time and continue
                
                elif key == curses.KEY_UP:
                    target_pos = cursor_pos - text_win_width
                    cursor_pos = max(0, target_pos)

                elif key == curses.KEY_DOWN:
                    target_pos = cursor_pos + text_win_width
                    cursor_pos = min(len(input_string), target_pos)
                        
                # ... [KEY_LEFT, KEY_RIGHT, HOME, END, edits, ASCII] ...
                elif key == curses.KEY_LEFT: cursor_pos = max(0, cursor_pos - 1)
                elif key == curses.KEY_RIGHT: cursor_pos = min(len(input_string), cursor_pos + 1)
                elif key == curses.KEY_HOME: cursor_pos = 0
                elif key == curses.KEY_END: cursor_pos = len(input_string)
                elif key in [curses.KEY_BACKSPACE, 127, 8]:
                    if cursor_pos > 0:
                        input_string.pop(cursor_pos - 1)
                        cursor_pos -= 1
                elif key == curses.KEY_DC:
                    if cursor_pos < len(input_string):
                        input_string.pop(cursor_pos)

                # Map special characters to space unless they're the dialog_return key
                elif key in [9, 10, 13]:
                    # Check if this is the dialog_return key
                    is_return_key = False
                    if self.opts.dialog_return == 'TAB' and key == 9:
                        is_return_key = True
                    elif self.opts.dialog_return == 'ENTER' and key in [10, 13]:
                        is_return_key = True

                    if not is_return_key:
                        # Convert to space
                        input_string.insert(cursor_pos, ' ')
                        cursor_pos += 1

                elif 32 <= key <= 126:
                    input_string.insert(cursor_pos, chr(key))
                    cursor_pos += 1
                
                # --- Explicit Resize Handler ---
                elif key == curses.KEY_RESIZE:
                    curses.update_lines_cols()
                    continue
                    
            except curses.error:
                # Catch exceptions from drawing outside bounds during resize
                self.scr.clear()
                curses.update_lines_cols()
                self.rows, self.cols = self.scr.getmaxyx()
                # Drain any pending resize events to prevent infinite loop
                self.scr.nodelay(True)  # Make getch() non-blocking
                while True:
                    key = self.scr.getch()
                    if key == -1:  # No more keys in queue
                        break
                self.scr.nodelay(False)  # Restore blocking mode
                continue


    def flash(self, message='', duration=2.0):
        """
        Displays a brief flash message in the center of the screen.
        Auto-dismisses after duration seconds without requiring user input.

        :param message: The message to display
        :param duration: How long to show the message in seconds (default 0.5)
        """

        if self.rows < 3 or self.cols < len(message) + 4:
            return

        # Calculate centered position
        msg_len = min(len(message), self.cols - 4)
        row = self.rows // 2
        col = (self.cols - msg_len - 2) // 2

        # Draw a simple box with the message
        self.scr.clear()
        try:
            # Top border
            self.scr.addstr(row - 1, col, '┌' + '─' * msg_len + '┐', curses.A_BOLD | curses.A_REVERSE)
            # Message
            self.scr.addstr(row, col, '│' + message[:msg_len] + '│', curses.A_BOLD | curses.A_REVERSE)
            # Bottom border
            self.scr.addstr(row + 1, col, '└' + '─' * msg_len + '┘', curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass  # Ignore if terminal too small

        self.scr.noutrefresh()
        curses.doupdate()
        time.sleep(duration)


    def alert(self, message='', title='ALERT', _height=None, _width=None):
        """
        Displays a blocking, modal alert box with a title and message.
        Auto-sizes based on content and terminal size with 1-cell border.

        Waits for the user to press **ENTER** to acknowledge and dismiss the box.

        :param message: The message body content.
        :param title: The title text for the alert box (defaults to 'ALERT')
        :param height: DEPRECATED - ignored
        :param width: DEPRECATED - ignored
        :type title: str
        :type message: str
        """
        def mod_key(key):
            """Internal function to map Enter/Key_Enter to an arbitrary key code 7 for Textbox.edit to exit."""
            return  7 if key in (10, curses.KEY_ENTER) else key

        # Auto-calculate dimensions with 1-cell border on all sides
        # Leave 1 cell on each side for reverse video border
        max_box_width = self.cols - 2  # 1 cell left, 1 cell right
        max_box_height = self.rows - 2  # 1 cell top, 1 cell bottom

        if max_box_width < 20 or max_box_height < 5:
            return  # Terminal too small

        # Calculate content width (box interior minus borders)
        content_width = max_box_width - 2  # Subtract box borders

        # Determine if title fits on box border, or needs to go inside
        footer_text = 'Press ENTER to ack'
        title_available_width = content_width - len(footer_text) - 2

        lines = []
        if len(title) > title_available_width:
            # Title too long - use "alert" as box title, put real title inside
            box_title = 'alert'
            # Wrap the actual title
            title_lines = textwrap.wrap(title, width=content_width)
            lines.extend(title_lines)
            lines.append('')  # Blank line separator
        else:
            # Title fits on box border
            box_title = title

        # Wrap message content
        if message:
            message_lines = textwrap.wrap(message, width=content_width)
            lines.extend(message_lines)

        # Calculate box dimensions - use full height with 1-cell border
        content_height = len(lines)
        box_height = max_box_height  # Use full available height

        # Calculate box position - 1 cell border on all sides
        row0 = 1  # 1 cell from top
        row9 = self.rows - 2  # 1 cell from bottom
        col0 = 1  # 1 cell from left
        col9 = self.cols - 2  # 1 cell from right

        # Clear screen normally (no reverse video)
        self.scr.clear()

        # Draw 1-cell reverse video border around the box area
        # Top and bottom borders (full width)
        self.scr.insstr(0, 0, ' '*self.cols, curses.A_REVERSE)
        self.scr.insstr(self.rows-1, 0, ' '*self.cols, curses.A_REVERSE)
        # Left and right borders
        for row in range(1, self.rows-1):
            self.scr.addch(row, 0, ' ', curses.A_REVERSE)
            self.scr.addch(row, self.cols-1, ' ', curses.A_REVERSE)

        # Draw box
        rectangle(self.scr, row0, col0, row9, col9)

        # Fill box interior with normal background (to override any reverse video)
        for row in range(row0+1, row9):
            self.scr.addstr(row, col0+1, ' '*(col9-col0-1))

        # Add title on top border
        self.scr.addstr(row0, col0+1, box_title[:content_width], curses.A_REVERSE)

        # Add footer on bottom border
        footer_pos = col0 + 1 + content_width - len(footer_text)
        self.scr.addstr(row9, footer_pos, footer_text[:content_width])

        # Create pad for scrollable content
        pad = curses.newpad(max(content_height, 1), content_width + 1)

        # Add lines to pad
        for idx, line in enumerate(lines):
            if idx < content_height:
                pad.addstr(idx, 0, line[:content_width])

        # Refresh screen
        self.scr.refresh()

        # Display content (scrollable if needed)
        visible_rows = box_height - 2  # Subtract top and bottom borders
        pad.refresh(0, 0, row0+1, col0+1, row0+visible_rows, col9-1)

        # Wait for ENTER using dummy Textbox
        win = curses.newwin(1, 1, row9-1, col9-2)
        curses.curs_set(0)  # Ensure cursor is off
        Textbox(win).edit(mod_key).strip()
        return

    def clear(self):
        """
        Clears all content from both the header and body pads and resets internal
        counters in preparation for adding new screen content.
        """
        self.scr.clear()
        self.head.pad.clear()
        self.body.pad.clear()
        self.head.texts, self.body.texts, self.last_pick_pos = [], [], -1
        self.head.text_attrs, self.body.text_attrs = [], []
        self.head.contexts, self.body.contexts = [], []
        self.head.row_cnt = self.body.row_cnt = 0

    def prompt(self, seconds=1.0):
        """
        Waits for user input for up to ``seconds``.

        Handles terminal resize events and built-in navigation keys, updating
        scroll/pick position as needed.

        :param seconds: The maximum time (float) to wait for input.
        :type seconds: float
        :returns: The key code if it is one of the application-defined ``keys``,
                  or None on timeout or if a navigation key was pressed.
        :rtype: int or None
        """
        global ctrl_c_flag
        ctl_b, ctl_d, ctl_f, ctl_u = 2, 4, 6, 21
        begin_mono = time.monotonic()
        while True:
            if time.monotonic() - begin_mono >= seconds:
                break
            while self.pending_keys:
                key = self.pending_keys.pop()
                if key in self.handled_keys:
                    return key

            key = self.scr.getch()
            if ctrl_c_flag:
                if key in self.handled_keys:
                    self.pending_keys.add(key)
                ctrl_c_flag = False # Reset flag
                if 0x3 in self.handled_keys:
                    return 0x3 # Return the ETX key code
                continue

            if key == curses.ERR:
                continue


            if key in (curses.KEY_RESIZE, ) or curses.is_term_resized(self.rows, self.cols):
                self._set_screen_dims()
                if not self._check_min_size():
                    # User pressed ESC to abort during size check
                    if 27 in self.handled_keys:
                        return 27
                break

            # App keys...
            # In passthrough mode, return all printable keys plus special editing keys
            # Special editing keys: backspace, arrows, home, end
            editing_keys = {curses.KEY_BACKSPACE, 127, 8, 263,  # backspace variants
                          curses.KEY_LEFT, curses.KEY_RIGHT,
                          curses.KEY_HOME, curses.KEY_END,
                          1, 5}  # Ctrl-A, Ctrl-E
            if self.passthrough_mode and (32 <= key <= 126 or key in editing_keys or key in self.handled_keys):
                # Update demo mode tracking for non-navigation keys
                if self.opts.demo_mode and key not in NAVIGATION_KEYS:
                    self.last_demo_key = self._format_key_for_demo(key)
                return key
            elif key in self.handled_keys:
                # Update demo mode tracking for non-navigation keys
                if self.opts.demo_mode and key not in NAVIGATION_KEYS:
                    self.last_demo_key = self._format_key_for_demo(key)
                return key # return for handling

            # Navigation Keys...
            # Clear demo mode indicator when any navigation key is pressed
            if self.opts.demo_mode and key in NAVIGATION_KEYS:
                self.last_demo_key = ''

            pos = self.pick_pos if self.pick_mode else self.scroll_pos
            delta = self.pick_size if self.pick_mode else 1
            was_pos = pos
            if key in (ord('k'), curses.KEY_UP):
                pos -= delta
            elif key in (ord('j'), curses.KEY_DOWN):
                pos += delta
            elif key in (ctl_b, curses.KEY_PPAGE):
                pos -= self.scroll_view_size
            elif key in (ctl_u, ):
                pos -= self.scroll_view_size//2
            elif key in (ctl_f, curses.KEY_NPAGE):
                pos += self.scroll_view_size
            elif key in (ctl_d, ):
                pos += self.scroll_view_size//2
            elif key in (ord('0'), curses.KEY_HOME):
                pos = 0
            elif key in (ord('$'), curses.KEY_END):
                pos = self.body.row_cnt - 1
            elif key in (ord('H'), ):
                pos = self.scroll_pos
            elif key in (ord('M'), ):
                pos = self.scroll_pos + self.scroll_view_size//2
            elif key in (ord('L'), ):
                pos = self.scroll_pos + self.scroll_view_size-1

            # Skip non-pickable lines in pick mode
            if self.pick_mode and pos != was_pos:
                # Determine direction of movement
                direction = 1 if pos > was_pos else -1

                # Find next pickable line in the direction of movement
                attempts = 0
                max_attempts = self.body.row_cnt + 1  # Prevent infinite loop

                while 0 <= pos < self.body.row_cnt and not self._is_pickable(pos) and attempts < max_attempts:
                    pos += direction
                    attempts += 1

                # If we went out of bounds or found no pickable line, stay at current position
                if pos < 0 or pos >= self.body.row_cnt or attempts >= max_attempts:
                    pos = was_pos

            if self.pick_mode:
                self.pick_pos = pos
            else:
                self.scroll_pos = pos
                self.pick_pos = pos

            self.fix_positions()

            if pos != was_pos:
                if self.opts.return_if_pos_change:
                    # Don't render with stale content; return immediately to allow full redraw
                    return None
                else:
                    # Only render here if we're not going to redraw immediately
                    self.render()
        return None

# =============================================================================
# Complete Screen Stack Integration Example
# =============================================================================
#
# This example shows how to build a multi-screen terminal application using
# Screen, ScreenStack, ConsoleWindow, and OptionSpinner.
#
# """
# from vappman.ConsoleWindow import (
#     ConsoleWindow, ConsoleWindowOpts, OptionSpinner,
#     Screen, ScreenStack, BasicHelpScreen, HOME_ST
# )
# import sys
#
# # 1. Define screen constants
# HOME_ST, MENU_ST, SETTINGS_ST, HELP_ST = 0, 1, 2, 3
# SCREENS = ['HOME', 'MENU', 'SETTINGS', 'HELP']
#
# # 2. Create custom Screen classes
# class HomeScreen(Screen):
#     def draw_screen(self):
#         self.win.add_header("=== HOME SCREEN ===")
#         self.win.add_body("Press 'm' for menu")
#         self.win.add_body("Press '?' for help")
#         self.win.add_body("Press 'q' to quit")
#
# class MenuScreen(Screen):
#     def draw_screen(self):
#         self.win.add_header("=== MENU ===")
#         self.win.add_body("Press 's' for settings")
#         self.win.add_body("Press ESC to go back")
#
# class SettingsScreen(Screen):
#     # Only allow navigation from MENU screen
#     come_from_whitelist = [MENU_ST]
#
#     def draw_screen(self):
#         self.win.add_header("=== SETTINGS ===")
#         self.win.add_body(f"Theme: {self.app.opts.theme}")
#         self.win.add_body("Press 't' to toggle theme")
#         self.win.add_body("Press ESC to go back")
#
# # 3. Main application class
# class MyApp:
#     def __init__(self):
#         # Setup OptionSpinner
#         self.spinner = OptionSpinner()
#         self.spinner.add_key('menu', 'm - open menu', genre='action')
#         self.spinner.add_key('settings', 's - open settings', genre='action')
#         self.spinner.add_key('help', '? - toggle help', vals=[False, True])
#         self.spinner.add_key('theme', 't - toggle theme', vals=['dark', 'light'])
#         self.spinner.add_key('quit', 'q - quit', genre='action', keys={ord('q'), 0x3})
#         self.opts = self.spinner.default_obj
#
#         # Setup ConsoleWindow
#         console_opts = ConsoleWindowOpts()
#         console_opts.keys = self.spinner.keys
#         console_opts.ctrl_c_terminates = False
#         self.win = ConsoleWindow(opts=console_opts)
#
#         # Initialize screen objects
#         self.screens = {
#             HOME_ST: HomeScreen(self),
#             MENU_ST: MenuScreen(self),
#             SETTINGS_ST: SettingsScreen(self),
#             HELP_ST: BasicHelpScreen(self)
#         }
#
#         # Create ScreenStack
#         self.ss = ScreenStack(self.win, self, SCREENS, self.screens)
#         self.prev_pos = 0
#
#     def navigate_to(self, screen_num):
#         """Navigate to a screen"""
#         result = self.ss.push(screen_num, self.prev_pos)
#         if result is not None:
#             self.prev_pos = result
#             return True
#         return False
#
#     def navigate_back(self):
#         """Navigate back"""
#         result = self.ss.pop()
#         if result is not None:
#             self.prev_pos = result
#             return True
#         return False
#
#     def handle_key(self, key):
#         """Handle key press"""
#         # Let OptionSpinner process the key
#         value = self.spinner.do_key(key, self.win)
#
#         # Handle actions
#         if self.opts.quit:
#             self.opts.quit = False
#             sys.exit(0)
#
#         if self.opts.menu:
#             self.opts.menu = False
#             self.navigate_to(MENU_ST)
#
#         if self.opts.settings and self.ss.is_curr(MENU_ST):
#             self.opts.settings = False
#             self.navigate_to(SETTINGS_ST)
#
#         # ESC key - go back
#         if key == 27 and self.ss.stack:
#             self.navigate_back()
#
#         return value
#
#     def run(self):
#         """Main loop"""
#         while True:
#             self.win.clear()
#
#             # Get current screen and draw it
#             current_screen = self.screens.get(self.ss.curr.num)
#             if current_screen:
#                 if self.opts.help:
#                     self.screens[HELP_ST].draw_screen()
#                 else:
#                     current_screen.draw_screen()
#
#             self.win.render()
#             key = self.win.prompt(seconds=5)
#             if key:
#                 self.handle_key(key)
#
# # 4. Run the app
# if __name__ == '__main__':
#     app = MyApp()
#     app.run()
# """

class Screen:
    """
    Base class for all screen types in a screen stack navigation system.

    Screen objects represent individual UI screens/views that can be stacked
    on top of each other, providing a navigation history similar to a web browser.

    Class Attributes (override in subclasses):
        come_from_whitelist (list[int] | None): Restricts which screens can navigate
            to this screen. None = any screen can navigate here, otherwise only screens
            in the list can navigate to this screen.
        is_terminal (bool): If True, this screen cannot be pushed onto the stack
            (i.e., it must replace the current screen entirely).
        cannot_stack_me (bool): If True, no other screens can be pushed on top
            of this screen. Useful for modal screens or final destinations.

    Instance Attributes:
        app: Reference to the main application instance
        win (ConsoleWindow): Reference to the console window for drawing
    """
    # Navigation control (class attributes - override in subclasses)
    come_from_whitelist = None  # None = can come from any screen, else list of screen numbers
    is_terminal = False         # True = cannot be pushed onto stack
    cannot_stack_me = False     # True = cannot have other screens pushed on top

    def __init__(self, app):
        """
        Initialize the screen with references to the application and window.
        Called once when screen is first created.

        Args:
            app: Main application instance (should have a 'win' attribute)
        """
        self.app = app  # Reference to main application instance
        self.win = app.win

    def draw_screen(self):
        """
        Draw screen-specific content (header and body).

        Override this method in subclasses to implement the screen's UI.
        Use self.win.add_header() and self.win.add_body() to populate content.

        Example:
            def draw_screen(self):
                self.win.add_header("My Screen Title")
                self.win.add_body("Screen content goes here")
        """
        pass

    def on_pause(self):
        """
        Called when another screen is about to be pushed on top of this one.

        Returns:
            True to allow being paused/covered, False to reject
        """
        return not self.cannot_stack_me

    def on_resume(self):
        """
        Called when this screen becomes the top screen again
        (after a screen that was on top of it was popped).

        Returns:
            True to allow resuming (typically always True)
        """
        return True

    def on_pop(self):
        """
        Called when this screen is being permanently removed from the stack.
        Must always succeed - use for cleanup only.

        Returns:
            Always returns True (cleanup cannot be rejected)
        """
        return True

    def get_spinner(self):
        """
        Find and return the OptionSpinner instance from the app.

        Searches through the app's attributes to find an OptionSpinner instance.
        Caches the result for performance.

        Returns:
            OptionSpinner: The spinner instance, or None if not found

        Example:
            spinner = self.get_spinner()
            if spinner:
                spinner.show_help_nav_keys(self.win)
        """
        # Check if we've already cached the spinner
        if hasattr(self, '_cached_spinner'):
            return self._cached_spinner

        # Search through app's attributes for an OptionSpinner instance
        for attr_name in dir(self.app):
            if not attr_name.startswith('_'):  # Skip private attributes
                try:
                    attr_value = getattr(self.app, attr_name)
                    if isinstance(attr_value, OptionSpinner):
                        self._cached_spinner = attr_value
                        return attr_value
                except (AttributeError, TypeError):
                    continue

        # Cache None if not found to avoid repeated searches
        self._cached_spinner = None
        return None

    def handle_action(self, action_name):
        """
        Dispatch action to screen-specific handler method.

        Looks for a method named '{action_name}_ACTION' (uppercase) and calls it
        if it exists. This provides a convention-based way to handle actions.

        Args:
            action_name (str): The action name to dispatch (e.g., 'quit', 'save')

        Returns:
            bool: True if action was handled (method exists), False otherwise

        Example:
            # In your Screen subclass:
            def quit_ACTION(self):
                sys.exit(0)

            # Then call:
            screen.handle_action('quit')  # Calls quit_ACTION()
        """
        method_name = f'{action_name}_ACTION'
        method = getattr(self, method_name, None)
        if method and callable(method):
            method()
            return True
        return False

# Default home screen constant (applications should define their own)
HOME_ST = 0

class ScreenStack:
    """
    A stack-based screen navigation system for terminal applications.

    Manages a stack of screens (like a browser history), allowing screens to be
    pushed onto and popped from the stack. Each screen can maintain its own state
    (scroll position, pick position, etc.) which is restored when returning to it.

    The ScreenStack integrates with Screen objects and ConsoleWindow to provide:
    - Navigation validation (come_from whitelist, terminal screens, etc.)
    - Lifecycle hooks (on_pause, on_resume, on_pop)
    - State preservation (scroll/pick positions)
    - Loop prevention (can't push same screen twice)

    Example usage:
        # 1. Define screen constants
        HOME_ST, SETTINGS_ST, HELP_ST = 0, 1, 2
        SCREENS = ['HOME', 'SETTINGS', 'HELP']

        # 2. Create Screen subclasses
        class HomeScreen(Screen):
            def draw_screen(self):
                self.win.add_header("Home Screen")
                self.win.add_body("Welcome to the app")

        class SettingsScreen(Screen):
            def draw_screen(self):
                self.win.add_header("Settings")
                self.win.add_body("Configure your settings here")

        # 3. Initialize screen objects
        screens = {
            HOME_ST: HomeScreen(app),
            SETTINGS_ST: SettingsScreen(app),
            HELP_ST: HelpScreen(app),
        }

        # 4. Create ScreenStack
        ss = ScreenStack(win, app, SCREENS, screens)

        # 5. Navigate between screens
        ss.push(SETTINGS_ST, 0)  # Go to settings
        ss.pop()                  # Go back to home
    """

    def __init__(self, win: ConsoleWindow, spins_obj: object, screens: tuple, screen_objects: dict = None):
        """
        Initialize the ScreenStack with a home screen.

        Args:
            win (ConsoleWindow): The console window instance
            spins_obj: Application object (typically holds OptionSpinner and state)
            screens (tuple): Tuple of screen names (e.g., ['HOME', 'SETTINGS', 'HELP'])
            screen_objects (dict): Dict mapping screen numbers to Screen instances
        """
        self.win = win
        self.obj = spins_obj
        self.screens = screens
        self.screen_objects = screen_objects or {}  # Dict of screen_num -> Screen instance
        self.stack = []
        self.curr = None
        # Push home screen (HOME_ST=0) as the initial screen
        self.push(HOME_ST, 0)

    def push(self, screen, prev_pos, force=False):
        """
        Push a new screen onto the stack with validation and loop prevention.

        Args:
            screen: Screen number to push
            prev_pos: Previous cursor position
            force: Skip validation hooks if True

        Returns:
            Previous position if successful, None if blocked by validation
        """
        # Loop prevention: Check if screen is already on the stack
        if not force and self.curr and screen == self.curr.num:
            # Trying to push the current screen again - ignore
            return None

        # Check if screen is already in the stack (deeper loop)
        if not force:
            for stacked_screen in self.stack:
                if stacked_screen.num == screen:
                    # Would create a loop - block it
                    return None

        from_screen_num = self.curr.num if self.curr else None
        new_screen_obj = self.screen_objects.get(screen) if self.screen_objects else None

        # Check navigation constraints
        if not force and new_screen_obj:
            # Check if screen is terminal (cannot be pushed)
            if new_screen_obj.is_terminal:
                return None

            # Check come_from whitelist
            if new_screen_obj.come_from_whitelist is not None:
                if from_screen_num not in new_screen_obj.come_from_whitelist:
                    # Navigation from this screen not allowed
                    return None

        # Call on_pause() on current screen (it's being covered)
        if not force and self.curr and self.screen_objects:
            current_screen_obj = self.screen_objects.get(from_screen_num)
            if current_screen_obj:
                if not current_screen_obj.on_pause():
                    # Current screen rejected being paused
                    return None

        # Navigation approved - proceed
        if self.curr:
            self.curr.pick_pos = self.win.pick_pos
            self.curr.scroll_pos = self.win.scroll_pos
            self.curr.prev_pos = prev_pos
            self.stack.append(self.curr)
        self.curr = SimpleNamespace(num=screen,
                  name=self.screens[screen], pick_pos=-1,
                                scroll_pos=-1, prev_pos=-1)
        self.win.pick_pos = self.win.scroll_pos = 0
        return 0

    def pop(self, force=False):
        """
        Pop the top screen from the stack.
        on_pop() is always called for cleanup (cannot be rejected).
        on_resume() is called on the screen being returned to (typically always succeeds).

        Args:
            force: Skip validation hooks if True

        Returns:
            Previous position if successful, None if stack is empty
        """
        if not self.stack:
            return None

        to_screen_num = self.stack[-1].num
        from_screen_num = self.curr.num if self.curr else None

        # Call on_pop() on current screen (it's being removed - always succeeds)
        if not force and self.curr and self.screen_objects:
            current_screen_obj = self.screen_objects.get(from_screen_num)
            if current_screen_obj:
                current_screen_obj.on_pop()  # Always called, cannot reject

        # Call on_resume() on the screen we're returning to
        if not force and self.screen_objects:
            prev_screen_obj = self.screen_objects.get(to_screen_num)
            if prev_screen_obj:
                if not prev_screen_obj.on_resume():
                    # Previous screen rejected resuming (rare, but allowed)
                    return None

        # Navigation approved - proceed
        self.curr = self.stack.pop()
        self.win.pick_pos = self.curr.pick_pos
        self.win.scroll_pos = self.curr.scroll_pos
        return self.curr.prev_pos

    def is_curr(self, screens):
        """
        Check if the current screen matches any of the given screen(s).

        Args:
            screens: A single screen (int or str) or a list/tuple of screens.
                    Int values are compared against screen numbers.
                    String values are compared against screen names.

        Returns:
            bool: True if current screen matches any of the provided screens

        Example:
            if ss.is_curr(HOME_ST):
                print("On home screen")
            if ss.is_curr([HOME_ST, SETTINGS_ST]):
                print("On home or settings")
            if ss.is_curr('HOME'):
                print("On home screen (by name)")
        """
        def test_one(screen):
            if isinstance(screen, int):
                return screen == self.curr.num
            return str(screen) == self.curr.name
        if isinstance(screens, (tuple, list)):
            for screen in screens:
                if test_one(screen):
                    return True
            return False
        return test_one(screen=screens)

    def act_in(self, action, screens=None):
        """
        Check if an action flag is set and optionally if we're on specific screen(s).

        This is a convenience method that:
        1. Gets the value of self.obj.{action}
        2. Resets self.obj.{action} to False
        3. Returns True only if the action was True AND (screens is None OR current screen matches)

        Useful for handling action flags from OptionSpinner with genre='action'.

        Args:
            action (str): Name of the action attribute to check (e.g., 'quit', 'save')
            screens: Optional screen filter (int, str, or list). If provided, action
                    only returns True if we're on one of these screens.

        Returns:
            bool: True if action was set and screen matches (if specified)

        Example:
            # In your main loop:
            if ss.act_in('quit'):
                sys.exit(0)
            if ss.act_in('save', HOME_ST):
                # Only save if we're on home screen
                save_data()
        """
        val = getattr(self.obj, action)
        setattr(self.obj, action, False)
        return val and (screens is None or self.is_curr(screens))

    def perform_actions(self, spinner):
        """
        Automatically handle all pending actions for the current screen.

        This method iterates through ALL action options from the OptionSpinner,
        clears any set flags, and calls the corresponding *_ACTION method if it
        exists on the current screen.

        IMPORTANT: This clears ALL action flags, even if the current screen doesn't
        have a handler. This prevents actions from having delayed/unexpected effects
        when navigating between screens.

        Args:
            spinner (OptionSpinner): The OptionSpinner instance containing action definitions

        Returns:
            int: Number of actions that were performed (called handlers)

        Example:
            # In your main loop (replaces manual action checking):
            while True:
                self.screens[screen_num].draw_screen()
                self.win.render()
                key = self.win.prompt()
                if key:
                    self.spinner.do_key(key, self.win)
                    self.ss.perform_actions(self.spinner)  # Handles all actions automatically

            # Old way (what this replaces):
            for action in ['quit', 'help', 'save', 'load']:
                if self.ss.act_in(action):
                    current_screen.handle_action(action)
        """
        current_screen = self.screen_objects.get(self.curr.num)
        if not current_screen:
            return 0  # No screen object to handle actions

        actions_performed = 0

        # Loop through ALL action options from the spinner
        for option_ns in spinner.options:
            if option_ns.genre == 'action':
                action_name = option_ns.attr

                # Check if this action is scoped to the current screen
                if hasattr(option_ns, 'effective_scope'):
                    if self.curr.num not in option_ns.effective_scope:
                        # This action is not valid for the current screen - skip it
                        # But still clear the flag if it was set
                        if hasattr(option_ns.obj, action_name):
                            setattr(option_ns.obj, action_name, False)
                        continue

                # Check if this action flag is set
                if hasattr(option_ns.obj, action_name):
                    action_value = getattr(option_ns.obj, action_name, False)

                    # ALWAYS clear the flag (prevents delayed/unexpected effects)
                    setattr(option_ns.obj, action_name, False)

                    # Only call the handler if the flag was set AND the method exists
                    if action_value:
                        method_name = f'{action_name}_ACTION'
                        method = getattr(current_screen, method_name, None)
                        if method and callable(method):
                            method()
                            actions_performed += 1

        return actions_performed


# Application-level helper methods for screen navigation
# ======================================================
# The following are example helper methods you can add to your main application class
# to simplify screen navigation. They wrap ScreenStack.push() and ScreenStack.pop()
# with your application-specific state management.
#
# Example implementation in your app class:
#
#   class MyApp:
#       def __init__(self):
#           self.ss = ScreenStack(...)
#           self.prev_pos = 0
#
#       def navigate_to(self, screen_num):
#           """Navigate to a screen with validation hooks."""
#           result = self.ss.push(screen_num, self.prev_pos)
#           if result is not None:
#               self.prev_pos = result
#               return True
#           return False
#
#       def navigate_back(self):
#           """Navigate back to previous screen."""
#           result = self.ss.pop()
#           if result is not None:
#               self.prev_pos = result
#               # Reset any cached data when going back
#               self.cached_data = None
#               return True
#           return False
#
#       def handle_escape(self):
#           """Handle ESC key - go back if possible."""
#           if self.ss.stack:
#               return self.navigate_back()
#           return False


class BasicHelpScreen(Screen):
    """
    Example help screen implementation.

    Displays navigation keys and help information from an OptionSpinner.
    Assumes the app object has a 'spinner' attribute (OptionSpinner instance).

    This is a reference implementation that can be used as-is or customized
    for your application's specific help screen needs.
    """
    def draw_screen(self):
        """
        Draw the help screen content.

        Displays:
        1. Navigation keys blurb (from OptionSpinner.show_help_nav_keys)
        2. Application options help (from OptionSpinner.show_help_body)
        """
        win = self.win
        self.win.set_pick_mode(False)
        spinner = self.get_spinner()
        if spinner:
            spinner.show_help_nav_keys(win)
            spinner.show_help_body(win)


if __name__ == '__main__':
    def main():
        """Test program"""
        def do_key(key):
            nonlocal spin, win, opts, pick_values
            value = spin.do_key(key, win)
            if key in (ord('p'), ord('s')):
                win.set_pick_mode(on=opts.pick_mode, pick_size=opts.pick_size)
                if not opts.pick_mode:
                    opts.prev_pick = pick_values[win.pick_pos//win.pick_size]
            elif key == ord('n'):
                win.alert(title='Info', message=f'got: {value}')
            elif opts.quit:
                opts.quit = False
                sys.exit(key)
            return value

        spin = OptionSpinner()
        spin.add_key('help_mode', '? - toggle help screen', vals=[False, True])
        spin.add_key('pick_mode', 'p - toggle pick mode, turn off to pick current line', vals=[False, True])
        spin.add_key('pick_size', 's - #rows in pick', vals=[1, 2, 3])
        spin.add_key('name', 'n - select name', prompt='Provide Your Name:')
        spin.add_key('mult', 'm - row multiplier', vals=[0.5, 0.9, 1.0, 1.1, 2, 4, 16])
        spin.add_key('quit', 'q,CTL-C - quit the app', genre='action', keys={0x3, ord('q')})
        opts = spin.default_obj

        console_opts = ConsoleWindowOpts()
        console_opts.head_line = True
        console_opts.keys = spin.keys
        console_opts.ctrl_c_terminates = False
        console_opts.body_rows = 4000
        console_opts.answer_show_redraws = True
        win = ConsoleWindow(opts=console_opts)

        opts.name = ""
        opts.prev_pick = 'n/a'
        pick_values = []
        for loop in range(100000000000):
            body_size = int(round(win.scroll_view_size*opts.mult))
            # body_size = 4000 # temp to test scroll pos indicator when big
            if opts.help_mode:
                win.set_pick_mode(False)
                spin.show_help_nav_keys(win)
                spin.show_help_body(win)
            else:
                win.set_pick_mode(opts.pick_mode, opts.pick_size)
                win.add_header(f'{time.monotonic():.3f} [p]ick={opts.pick_mode}'
                            + f' s:#rowsInPick={opts.pick_size} [n]ame [m]ult={opts.pick_size} ?=help [q]uit')
                win.add_header(f'Header: {loop} name="{opts.name}"  {opts.prev_pick=}')
                pick_values = []
                for idx, line in enumerate(range(body_size//opts.pick_size)):
                    value = f'{loop}.{line}'
                    win.put_body(f'Main pick: {value}')
                    pick_values.append(value)
                    for num in range(1, opts.pick_size):
                        win.draw(num+idx*opts.pick_size, 0, f'  addon: {loop}.{line}')
            win.render(redraw=bool(loop%2))
            _ = do_key(win.prompt(seconds=5))
            win.clear()

    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as exce:
        ConsoleWindow.stop_curses()
        print("exception:", str(exce))
        print(traceback.format_exc())
        if dump_str:
            print(dump_str)
