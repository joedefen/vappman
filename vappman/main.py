#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive, visual thin layer atop appman/am

"""
# pylint: disable=broad-exception-caught,consider-using-with
# pylint: disable=too-many-instance-attributes,too-many-branches
# pylint: disable=too-many-return-statements,too-many-statements
# pylint: disable=consider-using-in,too-many-nested-blocks
# pylint: disable=wrong-import-position,disable=wrong-import-order
# pylint: disable=line-too-long,protected-access,invalid-name
# pylint: disable=too-many-locals

import os
import sys
import re
import shlex
import subprocess
import traceback
import textwrap
import argparse
import time
from types import SimpleNamespace
import curses as cs
from console_window import (
    ConsoleWindow, OptionSpinner, ConsoleWindowOpts,
    Screen, ScreenStack, BasicHelpScreen, Context,
    IncrementalSearchBar
)
from .PersistentState import PersistentState
from .AppmanVars import AppmanVars, AppLocation
from .AppmanLauncher import AppmanLauncher
from .Prerequisites import Prerequisites
from .VappmanListCache import AppCacheManager
from . import AppimageDoctor

# Screen constants
HOME_ST, HELP_ST = 0, 1
SCREENS = ['HOME', 'HELP']

class VappmanScreen(Screen):
    """ Base class for all VappmanScreens"""
    app: 'Vappman'  # Type hint for IDE support

    def quit_ACTION(self):
        """ TBD """
        self.win.stop_curses()
        os.system('clear; stty sane')
        sys.exit(0)

    def help_ACTION(self):
        """ TBD """
        app, win = self.app, self.app.win
        app.ss.push(HELP_ST, win.pick_pos)


class HomeScreen(VappmanScreen):
    """Main home screen showing installed and available apps"""

    @staticmethod
    def is_sandboxed(info):
        """ Given the 'info' namespace for an installed app,
        return whether sandboxed """
        return bool(info and info.app_type and '🔒' in info.app_type)

    def add_folded_synopsis_lines(self, fold_offset, wrapped_lines, num=1):
        """
        Add wrapped synopsis continuation lines as TRANSIENT context lines.

        Used to display long synopsis text across multiple indented lines
        when an app is selected (at pick position). Lines are marked as
        TRANSIENT so they appear/disappear with selection.

        Note: Expects pre-wrapped lines from textwrap.wrap() with initial_indent
        and subsequent_indent parameters. Skips the first line (already on main line)
        and shows continuation lines which should already be sized for fold_offset width.

        :param fold_offset: Horizontal position where continuation text should start
        :param wrapped_lines: Pre-wrapped lines from textwrap.wrap() with indent params
        :param num: Maximum number of continuation lines to display (default: 1)
        """
        def make_indent(amount, corner):
            rv = ' '*4
            if amount > 6:
                rv = ' ' * (amount-5)
                rv += ' ╰── ' if corner else ' │    '
            return rv

        win = self.win

        # Skip first line (already shown on main line), add up to 'max' continuation lines
        # Continuation lines are already sized correctly from textwrap's subsequent_indent
        indent = make_indent(2+fold_offset, False)
        lines = wrapped_lines[1:1+num]
        for line in lines[:-1]:
            # Indent to fold_offset position
            win.add_body(indent + line, context=Context("TRANSIENT"))
        indent = make_indent(2+fold_offset, True)
        if len(lines) > 0:
            win.add_body(indent + wrapped_lines[-1], context=Context("TRANSIENT"))


    def get_folded_synopsis(self, offset1, offset2, text):
        """ TBD """
        width = self.win.cols - 2 - offset2
        initial_indent = offset1 - offset2
        # Use textwrap with initial_indent for first line, subsequent_indent for continuations
        if width > offset1:
            wraps = textwrap.wrap(
                text,
                width=width,
                initial_indent=' '*initial_indent
            )
            if wraps:
                wraps[0] = wraps[0][initial_indent:]
            return wraps
        return [text]


    def draw_screen(self):
        """Draw the home screen with app list  ⮜–⮞
        """
        app = self.app
        win = self.win
        all_dbs = bool(app.opts.database == 'ALL')

        def wanted(ns):
            nonlocal app, all_dbs
            if not all_dbs and app.opts.database != ns.db:
                return False
            if not app.filter:
                return True
            if not ns:
                return False
            return app.filter.search(ns.appname + ' @' + ns.db + ' ' + ns.synopsis)

        win.set_pick_mode(True)
        win.set_demo_mode(app.opts.demo_mode)

        title = "APPMAN"
        if not app.has_appman:
            was_in_system_mode = app.in_system_mode 
            app.in_system_mode = app.appman.is_system_mode()
            title = 'm:AM-SYSTEM' if app.in_system_mode else 'm:AM-USER'
            if was_in_system_mode != app.in_system_mode:
                app.installs, app.installs_by_appname = app.get_installed(repull=False)
        # Save persistent state if any options changed
        app.disk_state.save_if_changed(app.opts)


        #############################################
        # Show INSTALLED apps first
        #############################################
        idx = 0
        for (appname, db), ns in app.installs.items():
            # ns2 = app.basics.get(appname, None)
            if ns and wanted(ns):
                where = "S" if 'S' in ns.where else '─' # "⋅"
                where += "U" if 'U' in ns.where else '─' # "⋅"
                check = '🔒' if self.is_sandboxed(ns) else ' ✔'
                checks = f'{check}{where}'
                # name = f'{appname}⮜{ns.db}⮞' if all_dbs else appname
                name = f'{appname} ﹫{ns.db}' if all_dbs else appname
                wid = 18 if all_dbs else 10
                line = f'{checks} '
                fold_offset = len(line) + wid
                line += f'{name:<{wid}} '
                first_synopsis_offset = len(line)

                if idx == win.pick_pos:
                    wraps = self.get_folded_synopsis(first_synopsis_offset, fold_offset, ns.synopsis)
                    line += wraps[0]
                else:
                    line += ns.synopsis

                status = "installed" if app.in_system_mode or 'U' in where else "uninstalled"
                win.add_body(line, context=Context(status, info=ns))

                if idx == win.pick_pos:
                    #wraps.append(f'🅥 {ns.version} {ns.app_type}')
                    wraps.append(f'🠞 {ns.version} {ns.app_type}')
                    self.add_folded_synopsis_lines(fold_offset, wraps, num=2)
                    # line = f'{"":<13}  ╰── {ns.version} {ns.app_type}'
                    # win.add_body(line, context=Context("TRANSIENT"))
                idx += 1

        #############################################
        # Show UNINSTALLED apps afterwards
        #############################################
        for (appname, db), ns in app.apps_by_name_db.items():
            if (appname, db) not in app.installs and wanted(ns):
                fill = '⋅' if idx % 3 == 100 else ''
                # name = f'{appname}⮜{ns.db}⮞' if all_dbs else appname
                name = f'{appname} @{ns.db}' if all_dbs else appname
                wid = 18 if all_dbs else 10
                line = f'{"◆":>4} '
                fold_offset = len(line) + wid
                line += f'{name:{fill}<{wid}}  '
                first_synopsis_offset = len(line)

                # Calculate offsets for uninstalled apps
                if idx == win.pick_pos:
                    wraps = self.get_folded_synopsis(first_synopsis_offset, fold_offset, ns.synopsis)
                    line += wraps[0]
                else:
                    line += ns.synopsis

                win.add_body(line, context=Context("uninstalled", info=ns))

                if idx == win.pick_pos:
                    self.add_folded_synopsis_lines(fold_offset, wraps)

                idx += 1

        #############################################
        # Create HEADER LINES
        #############################################
        header1 = f'{title}  {app.get_keys_line()}'
        # Use fancy header formatting to highlight keys automatically
        win.add_fancy_header(header1, app.opts.fancy_header)

        # Build dynamic action keys (e.g., " [r]mv [u]pd [b]kup")
        # Get base header line and combine with dynamic actions
        header2, context = '', self.win.get_picked_context()
        if context:
            # mode = 'Sys' if app.opts.in_system_mode else 'Usr'
            header2 = f' #:maxBkUp={app.opts.max_backups}   '
            if context.genre == 'installed':
                header2 += ' [r]mv [u]pd C:icons [b]kup [a]bout'
                cnt = len(app.appman.get_snapshots(
                            context.info.appname, app.opts.max_backups))
                if cnt:
                    header2 += f' [o]verwr/{cnt}'
                sandboxed = self.is_sandboxed(context.info)
                # header2 += ' S:' + ('-🔒' if sandboxed else '+🔒')
                header2 += ' S:' + ('unbox' if sandboxed else 'box')
                header2 += ' [t]est'
            elif context.genre == 'uninstalled':
                conflicts = app.installs_by_appname.get(context.info.appname, None)
                if conflicts:
                    header2 += f' install-conflicts={conflicts}'
                else:
                    header2 += f' [i]nstall [a]bout O:opts={app.opts.install_opts}'

        win.add_fancy_header(header2, app.opts.fancy_header)

    def appman_on_installed(self, verb):
        """ TBD """
        context = self.win.get_picked_context()
        if context and context.genre == 'installed':
            self.app.run_appman(verb, context.info)

    def remove_ACTION(self):
        """ TBD """
        return self.appman_on_installed('remove')

    def update_ACTION(self):
        """ TBD """
        return self.appman_on_installed('update')

    def backup_ACTION(self):
        """ TBD """
        return self.appman_on_installed('backup')

    def overwrite_ACTION(self):
        """ TBD """
        self.appman_on_installed('overwrite')

    def sandbox_ACTION(self):
        """ TBD """
        context = self.win.get_picked_context()

        if context.genre == "installed":
            if self.is_sandboxed(context.info):
                verb = '--disable-sandbox'
            else:
                verb = '--sandbox'
            self.appman_on_installed(verb)

    def icons_ACTION(self):
        """ TBD """
        self.appman_on_installed('--icons')

    def about_ACTION(self):
        """ TBD """
        context = self.win.get_picked_context()
        if context:
            self.app.run_appman('about', context.info)

    def test_ACTION(self):
        """ TBD """
        context = self.win.get_picked_context()
        if context and context.genre == 'installed':
            self.app.launcher.launch_test_in_terminal(
                context.info.appname,
                context.info.appname
            )

    def default_ACTION(self):
        """ TBD """
        context = self.win.get_picked_context()
        if context and context.genre == 'installed':
            return self.remove_ACTION()
        if context and context.genre == 'uninstalled':
            return self.install_ACTION()

    #################################
    def install_ACTION(self):
        """ TBD """
        context = self.win.get_picked_context()
        if context and context.genre == 'uninstalled':
            self.app.run_appman('install', context.info)

    #################################
    def reinstall_ACTION(self):
        """ TBD """
        return self.app.run_appman('reinstall')

    def sync_ACTION(self):
        """ TBD """
        return self.app.run_appman('sync')

    def clean_ACTION(self):
        """ TBD """
        return self.app.run_appman('clean')

    def update_all_ACTION(self):
        """ TBD """
        return self.app.run_appman('update')

    def reinstall_all_ACTION(self):
        """ TBD """
        return self.app.run_appman('reinstall')

    #################################
    def escape_filter_ACTION(self):
        """ Clear filter and jump to top """
        app = self.app
        app.search_bar._text = ''  # Clear search bar text
        app.filter = None
        app.win.pick_pos = 0

    def slash_ACTION(self):
        """ Enter search-as-you-type mode """
        app = self.app
        # Start search with current filter text
        app.search_bar.start(app.search_bar.text)
        # Enable pass-through mode so all printable keys are returned
        app.win.passthrough_mode = True
        return None

    def toggle_system_mode_ACTION(self):
        """ Switch between user and system mode """
        app = self.app
        if app.in_system_mode:
            return app.run_appman('--user')
        return app.run_appman('--system')


class VappmanHelpScreen(BasicHelpScreen):
    """Help screen with vappman-specific additions"""

    def draw_screen(self):
        """Draw help screen with extra vappman info"""
        # Call parent to show standard help
        super().draw_screen()

    def escape_help_ACTION(self):
        """ Leave Help (return to prior screen) """
        app = self.app
        app.ss.pop()


class Vappman(Prerequisites):
    """ Main class for curses atop appman"""
    singleton = None

    def __init__(self):
        # self.cmd_loop = CmdLoop(db=False) # just running as command
        super().__init__()
        assert not Vappman.singleton
        Vappman.singleton = self

        self.check_preqreqs()
        print(f'{self.has_am=}')
        print(f'{self.has_appman=}')
        self.disk_state = PersistentState('vappman',
                      max_backups=1, install_opts='', database='am')
        self.appman = AppmanVars()
        self.launcher = AppmanLauncher(self.appman)

        self.actions = {} # currently available actions
        self.filter = None # compiled pattern

        # Initialize incremental search bar with callbacks
        self.search_bar = IncrementalSearchBar(
            on_change=lambda text: self.compile_filter(text),
            on_accept=lambda text: self._on_search_accept(text),
            on_cancel=lambda text: self._on_search_cancel(text)
        )
        # self.basics, _ = self.cmd_dict('list')
        self.terminal_emulator = None
        self.has_am = None

        self.prev_pos = 0
        self.next_prompt_seconds = [0.1, 0.1]  # Initial fast renders, then slow down
        self.cache_mgr = AppCacheManager()
        self.apps_to_list = self.cache_mgr.get_apps()
        self.apps_by_name_db = self.cache_mgr.apps_by_key
        self.saved_outputs = {}
        self.installs, self.installs_by_appname = self.get_installed() # dict keyed by app
        self.in_system_mode = self.appman.is_system_mode()

        win_opts = ConsoleWindowOpts()
        win_opts.head_line=True
        win_opts.body_rows=len(self.apps_by_name_db)+1000
        win_opts.head_rows = 10
        win_opts.pick_attr = cs.A_BOLD|cs.A_UNDERLINE
        win_opts.dialog_abort = True
        win_opts.ctrl_c_terminates = False
        win_opts.min_cols_rows = (60, 10)

        self.win = ConsoleWindow(win_opts)

        # Initialize screens and screen stack
        self.screens = {
            HOME_ST: HomeScreen(self),
            HELP_ST: VappmanHelpScreen(self),
        }
        self.ss = ScreenStack(self.win, None, SCREENS, self.screens)

        spin = self.spin = OptionSpinner(stack=self.ss)
        self.opts = spin.default_obj
        spin.add_key('quit', 'q,x - quit program (CTL-C disabled)',
                     genre='action', keys='qx')
        spin.add_key('help', '? - enter help screen', genre='action')
        dbs = sorted(list(self.cache_mgr.dbs))
        spin.add_key('database', 'd - select app database', vals=['ALL'] + dbs)

        spin.add_key('fancy_header', '_ - fancy header mode', vals=['Underline', 'Reverse', 'Off'])
        spin.add_key('demo_mode', '* - demo_mode', vals=[False, True])
        if not self.has_appman:
            spin.add_key('toggle_system_mode', 'm - toggle system mode', genre='action')
        spin.add_key('max_backups', '# - max backups per app', vals=[-1, 2, 1])
        self.opts.max_backups = self.disk_state.max_backups
        self.opts.install_opts = self.disk_state.install_opts
        self.opts.database = self.disk_state.database


        spin.add_key('sync', 's - sync (update appman itself)', genre='action')
        spin.add_key('clean', 'c - clean (remove unneeded files/folders)', genre='action')
        spin.add_key('update_all', 'U - update ALL installed apps', genre='action')
        spin.add_key('reinstall_all', 'R - reinstall ALL apps w updated install script', genre='action')
        spin.add_key('slash', '/ - filter apps by keywords or regex', genre='action')
        spin.add_key('escape_filter', 'ESC - clear filter and jump to top', genre='action', keys=27)

        spin.add_key('install', 'i - install uninstalled app', genre='action')
        spin.add_key('install_opts', 'O - install options', vals=[
                                '', 'icons', 'sandbox', 'icons,sandbox'])
        spin.add_key('default', 'ENTER - install/uninstall app',
                     genre='action', keys=[cs.KEY_ENTER, 10])
        spin.add_key('remove', 'r - remove installed app', genre='action')

        spin.add_key('sandbox', 'S - Sandbox/Unsandbox app', genre='action')
        spin.add_key('icons', 'C - appimage given local icon themes', genre='action')

        spin.add_key('about', 'a - about (more info about app)', genre='action')

        spin.add_key('backup', 'b - backup installed app', genre='action')
        spin.add_key('update', 'u - update_installed app', genre='action')
        spin.add_key('overwrite', 'o - overwrite app from its backup', genre='action')
        spin.add_key('test', 't - test (open a terminal and run app', genre='action')
        spin.add_key('escape_help', 'ESC - leave help (return to prior screen)',
                      genre='action', keys=27, scope=HELP_ST)
        self.win.set_handled_keys(self.spin)


    def cmd_dict(self, cmd, repull=True):
        """ Get lines with the given start put into a dict keyed by the
            1st word.
        """
        def parse_app_list(lines):
            nonlocal switch_to_system_mode
            installs, installs_by_appname = {}, {}
            local = True if self.has_appman else False
            has_db_column = False

            # Process line by line
            # lines = input_text.strip().split('\n')

            for line in lines:
                line = line.strip()
                # Determine to reset location (Global vs Local)
                if not self.has_appman and 'HAVE INSTALLED' in line:
                    local = bool('LOCAL' in line)

                # Check column headers to see if DB column is present
                # Header line looks like: " - APPNAME | DB | VERSION | TYPE | SIZE"
                # or without DB: " - APPNAME | VERSION | TYPE | SIZE"
                if line.startswith('- APPNAME'):
                    has_db_column = bool('| DB' in line or '|DB' in line)

                # Identify data lines (they start with the diamond symbol ◆)
                if line.startswith('◆'):
                    # Remove the symbol and split by pipe '|'
                    # We strip whitespace and also remove the '*' indicator for libfuse2
                    parts = [p.strip().rstrip('*') for p in line[1:].split('|')]

                    if len(parts) in (4, 5):
                        name = parts[0]
                        if name in ('am', 'appman', ):
                            continue

                        # Use header info to determine column layout
                        if has_db_column and len(parts) == 5:
                            db = parts[1]
                            version = parts[2]
                            app_type = parts[3]
                        else:
                            db = 'am'
                            version = parts[1]
                            app_type = parts[2]
                        # size = parts[3 or 4]

                        where = 'S' if not local else ''
                        where += 'U' if local else ''

                        # Store as a SimpleNamespace for dot-notation access
                        ns = installs.get((name, db), None)
                        if ns:  # we have both user and system apps
                            if switch_to_system_mode and local:
                                ns.version=version
                            ns.where += where
                        else:
                            installs[(name,db)] = SimpleNamespace(appname=name, db=db,
                                        version=version, app_type=app_type,
                                        where=where, synopsis=None, raw=line)

                        if name in installs_by_appname:
                            installs_by_appname[name].add(db)
                        else:
                            installs_by_appname[name] = set([db])

            return installs, installs_by_appname
        # Define the command to run
        command = ['appman' if self.has_appman else 'am']
        command += cmd.split()
        output_key = ' '.join(command)
        switch_to_system_mode = not self.has_appman and self.appman.is_user_mode()

        output = self.saved_outputs.get(output_key, None)
        if repull or not output:
            if 'files' in cmd.split():
                if switch_to_system_mode is True:
                    # temp: promote to system mode to get all apps
                    self.appman.set_system_mode_cheat(True)

            # Run the command and capture the output
            try:
                # Capture as bytes first, then decode with error handling
                result = subprocess.run(command, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, check=False)
            except Exception as exc:
                ConsoleWindow.stop_curses()
                if switch_to_system_mode is True:
                    self.appman.set_system_mode_cheat(False)
                print(f'FAILED: {command}: {exc}')
                sys.exit(1)
            if switch_to_system_mode is True:
                self.appman.set_system_mode_cheat(False)

            if result.returncode != 0:
                print(f'WARNING: {command}: {result.returncode=}')

            # Decode with multiple fallback strategies
            try:
                output = result.stdout.decode('utf-8', errors='replace')
            except Exception:
                try:
                    output = result.stdout.decode('latin-1', errors='replace')
                except Exception:
                    output = str(result.stdout, errors='replace')
            if output:
                self.saved_outputs[output_key] = output

        lines = output.splitlines()
        # ansi_escape_pattern = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        rv = parse_app_list(lines)
        return rv

    def get_installed(self, repull=True):
        """ Get the list of lines of installed apps """
        rv, installs_by_appname = self.cmd_dict('files --byname', repull=repull)
        for app_db_key, info in rv.items():
            basic = self.apps_by_name_db.get(app_db_key, None)
            if basic:
                info.synopsis = basic.synopsis
        return rv, installs_by_appname

    def navigate_to(self, screen_num):
        """Navigate to a screen with validation hooks."""
        result = self.ss.push(screen_num, self.prev_pos)
        if result is not None:
            self.prev_pos = result
            return True
        return False

    def navigate_back(self):
        """Navigate back to previous screen."""
        result = self.ss.pop()
        if result is not None:
            self.prev_pos = result
            return True
        return False

    def handle_escape(self):
        """Handle ESC key - clear filter or go back."""
        if self.ss.stack:
            return self.navigate_back()
        # If no stack, clear filter and jump to top
        self.search_bar._text = ''
        self.filter = None
        self.win.pick_pos = 0
        return True

    def main_loop(self):
        """Main application loop using screen stack navigation."""
        win = self.win

        while True:
            # Get and draw current screen
            screen_num = self.ss.curr.num
            self.screens[screen_num].draw_screen()

            win.render()
            key = win.prompt(seconds=self.next_prompt_seconds[0])
            if self.cache_mgr.check_for_updates(): # this happens once at most
                self.apps_by_name_db = self.cache_mgr.apps_by_key
                self.installs, self.installs_by_appname = self.get_installed(repull=False)

            # Adjust prompt timing (fast initially, then slower)
            self.next_prompt_seconds.pop(0)
            if not self.next_prompt_seconds:
                self.next_prompt_seconds = [3.0]

            if key is not None:
                # Handle search mode keys first (MUST be before spin.do_key)
                if self.search_bar.handle_key(key):
                    # Key was handled by search bar, skip normal processing
                    pass
                else:
                    # Normal mode - let OptionSpinner process the key
                    self.spin.do_key(key, win)

                    # Handle quit
                    if self.opts.quit:
                        self.opts.quit = False
                        break

                    # Actions delegated to screen classes - automatically handled
                    self.ss.perform_actions(self.spin)

            win.clear()

    def _on_search_accept(self, text):
        """Callback when search is accepted (ENTER pressed)"""
        self.win.passthrough_mode = False
        # Jump to top if filter changed
        if self.search_bar._start_text != text:
            self.win.pick_pos = 0

    def _on_search_cancel(self, text):
        """Callback when search is cancelled (ESC pressed)"""
        self.win.passthrough_mode = False
        # Filter already restored by on_change callback

    def compile_filter(self, pattern):
        """Compile filter pattern and update display immediately"""
        pattern = pattern.strip()
        if not pattern:
            self.filter = None
            return
        try:
            if re.match(r'^[\-\w\s]*$', pattern):
                words = pattern.split()
                self.filter = re.compile(r'\b' + r'(|.*\b)'.join(words), re.IGNORECASE)
            else:
                self.filter = re.compile(pattern, re.IGNORECASE)
        except Exception:
            self.filter = None  # Invalid regex - show no matches

    def get_keys_line(self):
        """ Build header line with fancy formatting markup (static actions only) """
        # Static actions with markup for fancy headers
        line = f'[s]ync [c]lean [U]pd [R]eInst [q]uit ?:help  [d]b={self.opts.database}'
        # Add search bar display string
        line += self.search_bar.get_display_string(prefix=' /')
        line += '  '
        return line


    def run_appman(self, subcommand: str, info: SimpleNamespace = None):
        """ Run an 'appman' command using subprocess. """

        appname = info.appname if info else None
        # 1. Build the command list
        cmd = ['appman' if self.has_appman else 'am']
        cmd.append(subcommand)
        if subcommand == 'install':
            for opt in self.opts.install_opts.strip().split(','):
                if opt:
                    cmd.append(f'--{opt}')

        if subcommand in ('install', 'about'):
            if info and info.db != 'am':
                appname += f'.{info.db}'
        if appname:
            cmd.append(appname)

        # 2. Stop curses environment
        ConsoleWindow.stop_curses()
        os.system('clear; stty sane')

        # 3. Print the command being executed for user confirmation/debugging
        # Using ' '.join(shlex.quote(arg) for arg in cmd_list) ensures the printed command is safely quotable
        # in case any arg has spaces, though it won't affect the execution below.
        cmd_str = '+ ' + ' '.join(shlex.quote(p) for p in cmd)
        print(cmd_str)

        try:
            # 4. Execute the command
            # run() is generally preferred over call() or Popen() for simple execution
            # check=True raises CalledProcessError if the command returns a non-zero exit code
            # We don't use 'shell=True' here, which is safer and avoids shell quoting issues
            subprocess.run(cmd, check=True)

        except subprocess.CalledProcessError as e:
            # Handle errors if the command fails
            print(f"ERROR: failed {cmd_str!r} :: {e}")
        except FileNotFoundError:
            # Handle case where 'appman' executable isn't found
            print("ERROR: 'appman' command not found. Ensure it is in your PATH.")

        # 5. Wait for user input to return (similar to your original 'read FOO')
        input('\n\n===== Press ENTER to return to vappman ====> ')

        # 6. Update installs and restart curses environment
        self.installs, self.installs_by_appname = self.get_installed()
        ConsoleWindow._start_curses()

def main():
    """ The program """
    parser = argparse.ArgumentParser( prog='vappman',
        description='Interactive TUI for appman - application manager',
        epilog='Run without options to start the interactive TUI')
    parser.add_argument( '--doctor', '--system-check',
        action='store_true', dest='check_appimage',
        help='Check system for AppImage compatibility issues')
    parser.add_argument('--no-startup-check', action='store_true',
        help='Skip quick AppImage compatibility check on startup')
    parser.add_argument('--prereq', '--prerequisites',
        action='store_true', dest='prereq_only',
        help='Check and install prerequisites only, then exit')

    args = parser.parse_args()

    # Handle standalone mode (--prereq and/or --doctor)
    standalone_mode = args.check_appimage or args.prereq_only

    if standalone_mode:
        exit_code = 0

        # Run prerequisite check if requested
        if args.prereq_only:
            prereq = Prerequisites()
            prereq.check_preqreqs()
            print()  # Blank line separator

        # Run AppImage doctor check if requested
        if args.check_appimage:
            result = AppimageDoctor.main()
            if result != 0:
                exit_code = result

        # Final summary message
        if args.prereq_only and args.check_appimage:
            print('\n' + '='*60)
            print('System check complete.')
            print('='*60)
        elif args.prereq_only:
            print('\nPrerequisite check complete.')

        sys.exit(exit_code)

    # Quick startup check for critical AppImage issues (unless disabled)
    if not args.no_startup_check:
        has_critical, status_lines = AppimageDoctor.quick_check()

        # Always show the check results
        print("AppImage compatibility check:")
        for line in status_lines:
            print(line)

        if has_critical:
            print("\n⚠ Critical issues found! Run 'vappman --check-appimage' for detailed fixes")
            print("Starting TUI in 3 seconds...")
            time.sleep(3)
        print()

    try:
        appman = Vappman()
        appman.main_loop()
    except KeyboardInterrupt:
        pass
    except Exception as exce:
        ConsoleWindow.stop_curses()
        print("exception:", str(exce))
        print(traceback.format_exc())

if __name__ == '__main__':
    main()
