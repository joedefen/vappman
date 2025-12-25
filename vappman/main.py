#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive, visual thin layer atop appman

TODOs:
-   Feature	appman  CLI	            vappman Status	Re-announcement Value
-   Bootstrapping	N/A	            Missing	        Critical (Ease of use)
-   Sandboxing	    -ias	        Missing	        High (Security)
-   NeoDB Support	--soarpkg, etc.	Missing	        Medium (Content)
-   Snapshots	    -b, -o	        Partially (Manual)	High (Safety)
-   Icon Theme      Sync	--icons	Missing	        Low (Aesthetics)

**"vappman 1.0: The Bridge to the Unified AM Ecosystem"**

* **Intelligent Auto-Discovery:** No more manual configuration. `vappman` automatically detects if you're using `am` (System) or `appman` (User) and adapts the UI.
* **The 'Safe-Sudo' Flow:** It only asks for root permissions when you are performing a system-wide action. Your TUI remains unprivileged and safe.
* **Unified App View:** See your system-wide apps and local apps in one scannable list, with visual indicators for where they are stored.
* **Seamless Onboarding:** Don't have the manager? `vappman` will bootstrap the official environment for you with one click.

**Would you like me to draft the "Bootstrap" logic code for you, so you can see how `vappman` would offer to install the manager if it's missing?**
"""
# pylint: disable=broad-exception-caught,consider-using-with
# pylint: disable=too-many-instance-attributes,too-many-branches
# pylint: disable=too-many-return-statements,too-many-statements
# pylint: disable=consider-using-in,too-many-nested-blocks
# pylint: disable=wrong-import-position,disable=wrong-import-order
# pylint: disable=line-too-long,protected-access,invalid-name

import os
import sys
import re
import shutil
import shlex
import subprocess
import traceback
from types import SimpleNamespace
import curses as cs
from .ConsoleWindow import (
    ConsoleWindow, OptionSpinner, ConsoleWindowOpts,
    Screen, ScreenStack, BasicHelpScreen, Context
)
from .PersistentState import PersistentState
from .AppmanVars import AppmanVars, AppLocation
from .AppmanLauncher import AppmanLauncher
from .Prerequisites import Prerequisites

# Screen constants
HOME_ST, HELP_ST = 0, 1
SCREENS = ['HOME', 'HELP']

class VappmanScreen(Screen):
    """ Base class for all VappmanScreens"""
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

    def draw_screen(self):
        """Draw the home screen with app list"""
        app = self.app
        win = self.win

        def wanted(line):
            return not app.filter or app.filter.search(line)

        win.set_pick_mode(True)
        win.set_demo_mode(app.opts.demo_mode)

        title = "APPMAN"
        if not app.has_appman:
            title = "S:AM-SYSTEM" if app.opts.in_system_mode else 'S:AM-USER'
            if app.appman.is_system_mode() != app.opts.in_system_mode:
                app.appman.set_system_mode(app.opts.in_system_mode)
                app.installs = app.get_installed()
        if app.disk_state.max_backups != app.opts.max_backups:
            app.disk_state.max_backups = app.opts.max_backups
            app.disk_state.save()


        # Show installed apps first
        idx = 0
        for appname, ns in app.installs.items():
            ns2 = app.apps.get(appname, None)
            if ns2 and wanted(ns.raw[2:]):
                where = "S" if 'S' in ns.where else "⋅"
                where += "U" if 'U' in ns.where else "⋅"
                checks = f'✔{where}'
                pad = 30 - len(f'{appname} {ns.version}')
                fill = '⋅' if idx % 3 == 1 else ''
                app_ver = f'{appname}   {"":{fill}>{pad}} {ns.version}'
                idx += 1
                line = f'{checks} {ns.app_type:<4} ⋅ {app_ver}  {ns2.synopsis}'
                status = "installed" if app.opts.in_system_mode or 'U' in where else "uninstalled"
                win.add_body(line, context=Context(status, app=appname, ver=ns.version))

        # Then show available (not installed) apps
        for appname, ns in app.apps.items():
            if appname not in app.installs and wanted(ns.raw[2:]):
                fill = '⋅' if idx % 3 == 1 else ''
                idx += 1
                win.add_body(f'{ns.raw[:1]:<3} {appname:{fill}<20}  {ns.synopsis}',
                             context=Context("uninstalled", app=appname, ver=ns.version))
                

        header1 = f'{title}  {app.get_keys_line()}'


        # Use fancy header formatting to highlight keys automatically
        win.add_fancy_header(header1, app.opts.fancy_header)

        # Build dynamic action keys (e.g., " [r]mv [u]pd [b]kup")
        # Get base header line and combine with dynamic actions
        header2, context = '', self.win.get_picked_context()
        if context:
            mode = 'Sys' if app.opts.in_system_mode else 'Usr'
            header2 = f' #:maxBkUp={app.opts.max_backups}   '
            if context.genre == 'installed':
                header2 += ' [r]mv [u]pd [b]kup [o]verwr [t]est'
            elif context.genre == 'uninstalled':
                header2 += ' [i]nstall'
            header2 += f' [a]bout'
        
        win.add_fancy_header(header2, app.opts.fancy_header)
                
    def appman_on_installed(self, verb):
        """ TBD """
        context = self.win.get_picked_context()
        if context and context.genre == 'installed':
            self.app.run_appman(verb, context.app)

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

    def about_ACTION(self):
        """ TBD """
        context = self.win.get_picked_context()
        if context:
            self.app.run_appman('about', context.app)

    def test_ACTION(self):
        """ TBD """
        context = self.win.get_picked_context()
        if context and context.genre == 'installed':
            self.app.launch_app(context.app)
    
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
            self.app.run_appman('install', context.app)

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
        app.prev_filter = ''
        app.filter = None
        app.win.pick_pos = 0

    def slash_ACTION(self):
        """ TBD """
        app = self.app
        # pylint: disable=protected-access
        start_filter = app.prev_filter
        prefix = ''
        while True:
            pattern = app.win.answer(f'{prefix}Enter filter regex:',
                                     seed=app.prev_filter, height=1)
            if pattern is None:
                app.prev_filter = start_filter
                return None # they gave up
            app.prev_filter = pattern
            pattern.strip()
            if not pattern:
                app.filter = None
                break
            try:
                if re.match(r'^[\-\w\s]*$', pattern):
                    words = pattern.split()
                    app.filter = re.compile(r'\b' + r'(|.*\b)'.join(words), re.IGNORECASE)
                    break
                app.filter = re.compile(pattern, re.IGNORECASE)
                break
            except Exception:
                prefix = 'Bad regex: '
        if start_filter != app.prev_filter: # when filter changes, move to top
            app.win.pick_pos = 0

        return None


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
        self.disk_state = PersistentState('vappman', max_backups=1)
        self.appman = AppmanVars()
        self.launcher = AppmanLauncher()

        self.actions = {} # currently available actions
        self.prev_filter = '' # string
        self.filter = None # compiled pattern
        self.apps = self.cmd_dict('list')
        self.installs = self.get_installed() # dict keyed by app
        self.terminal_emulator = None
        self.has_am = None

        self.prev_pos = 0
        self.next_prompt_seconds = [0.1, 0.1]  # Initial fast renders, then slow down

        win_opts = ConsoleWindowOpts()
        win_opts.head_line=True
        win_opts.body_rows=len(self.apps)+20
        win_opts.head_rows = 10
        win_opts.pick_attr = cs.A_BOLD|cs.A_UNDERLINE
        win_opts.dialog_abort = True
        win_opts.ctrl_c_terminates = False
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
        spin.add_key('fancy_header', '_ - fancy header mode', vals=['Underline', 'Reverse', 'Off'])
        spin.add_key('demo_mode', '* - demo_mode', vals=[False, True])
        if not self.has_appman:
            spin.add_key('in_system_mode', 'S - AM system mode', vals=[False, True])
            self.opts.in_system_mode = self.appman.is_system_mode()
        spin.add_key('max_backups', '# - max backups per app', vals=[1, 2, -1])
        self.opts.max_backups = self.disk_state.max_backups


        spin.add_key('sync', 's - sync (update appman itself)', genre='action')
        spin.add_key('clean', 'c - clean (remove unneeded files/folders)', genre='action')
        spin.add_key('update_all', 'U - update ALL installed apps', genre='action')
        spin.add_key('reinstall_all', 'R - reinstall ALL apps w updated install script', genre='action')
        spin.add_key('slash', '/ - filter apps by keywords or regex', genre='action')
        spin.add_key('escape_filter', 'ESC - clear filter and jump to top', genre='action', keys=27)

        spin.add_key('install', 'i - install uninstalled app', genre='action')
        spin.add_key('default', 'ENTER - install/uninstall app',
                     genre='action', keys=[cs.KEY_ENTER, 10])
        spin.add_key('remove', 'r - remove installed app', genre='action')
        spin.add_key('about', 'a - about (more info about app)', genre='action')

        spin.add_key('backup', 'b - backup installed app', genre='action')
        spin.add_key('update', 'u - update_installed app', genre='action')
        spin.add_key('overwrite', 'o - overwrite app from its backup', genre='action')
        spin.add_key('test', 't - test (open a terminal and run app', genre='action')
        spin.add_key('escape_help', 'ESC - leave help (return to prior screen)',
                      genre='action', keys=27, scope=HELP_ST)
        self.win.set_handled_keys(self.spin)


    def cmd_dict(self, cmd, start=r'\s*◆\s'):
        """ Get lines with the given start put into a dict keyed by the
            1st word.
        """
        def parse_app_list(lines):
            nonlocal current_in_user_mode
            def shorten(raw_type):
                TYPE_MAP = {
                    "appimage": "AppI",
                    "dynamic-binary": "DyBi",
                    "static-binary": "StBi",
                    "bash-script": "Bash",
                    "python-script": "Pyth",
                }

                # Strip the libfuse2 '*' if present
                clean_type = raw_type.lower().rstrip('*')
                # Return mapped value or first 4 chars if unknown
                return TYPE_MAP.get(clean_type, clean_type[:4].capitalize())

            apps = {}
            where = None
            
            # Process line by line
            # lines = input_text.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                # Determine to reset location (Global vs Local)
                if 'HAVE INSTALLED' in line:
                    where = None # Cannot trust what is said
                    
                # Identify data lines (they start with the diamond symbol ◆)
                if line.startswith('◆'):
                    # Remove the symbol and split by pipe '|'
                    # We strip whitespace and also remove the '*' indicator for libfuse2
                    parts = [p.strip().rstrip('*') for p in line[1:].split('|')]
                    
                    if len(parts) >= 3:
                        name = parts[0]
                        version = parts[1]
                        app_type = parts[2]
                        location = self.appman.where_is(name)
                        where = 'S' if location.sys_path else ''
                        where += 'U' if location.usr_path else ''
                        
                        # Store as a SimpleNamespace for dot-notation access
                        ns = apps.get(name, None)
                        if ns:  # we have both user and system apps
                            if current_in_user_mode:
                                ns.version=version
                        else:
                            apps[name] = SimpleNamespace(
                                            version=version,
                                            app_type=shorten(app_type),
                                            where=where,
                                            synopsis=None,
                                            raw=line
                                        )
                    else:
                        mat = re.match(r'\s*([^\s]+)\s+:\s+([^\s].*)', line[1:])
                        if mat:
                            apps[mat.group(1)] = SimpleNamespace(
                                                    version=None,
                                                    app_type=None,
                                                    where='',
                                                    synopsis=mat.group(2),
                                                    raw=line
                                                )
                        
            return apps
        # Define the command to run
        command = ['appman' if self.has_appman else 'am']
        command += cmd.split()
        current_in_user_mode = None
        if 'files' in cmd.split():
            current_in_user_mode = self.appman.is_user_mode()
            if current_in_user_mode is True:
                # temp: promote to system mode to get all apps
                self.appman.set_system_mode(True)

        # Run the command and capture the output
        try:
            # Capture as bytes first, then decode with error handling
            result = subprocess.run(command, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, check=False)
        except Exception as exc:
            ConsoleWindow.stop_curses()
            if current_in_user_mode is True:
                self.appman.set_system_mode(False)
            print(f'FAILED: {command}: {exc}')
            sys.exit(1)
        if current_in_user_mode is True:
            self.appman.set_system_mode(False)

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

        lines = output.splitlines()
        # ansi_escape_pattern = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        rv = parse_app_list(lines)
        return rv

    def get_installed(self):
        """ Get the list of lines of installed apps """
        rv = self.cmd_dict('files --byname')
        return rv

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
        self.prev_filter = ''
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

            # Adjust prompt timing (fast initially, then slower)
            self.next_prompt_seconds.pop(0)
            if not self.next_prompt_seconds:
                self.next_prompt_seconds = [3.0]

            if key is not None:
                # Let OptionSpinner process the key
                self.spin.do_key(key, win)

                # Handle quit
                if self.opts.quit:
                    self.opts.quit = False
                    break

                # Actions delegated to screen classes - automatically handled
                self.ss.perform_actions(self.spin)

            win.clear()

    def get_keys_line(self):
        """ Build header line with fancy formatting markup (static actions only) """
        # Static actions with markup for fancy headers
        line = '[s]ync [c]lean [U]pd [R]eInst [q]uit ?:help'
        # Only show filter pattern if it's non-empty
        if self.prev_filter:
            line += f' /{self.prev_filter}'
        line += '  '
        return line


    def run_appman(self, subcommand: str, app: str = None):
        """ Run an 'appman' command using subprocess. """

        # 1. Build the command list
        if self.has_appman:
            cmd = ['appman']
        else:
            cmd = ['am']
        cmd.append(subcommand)
        if app:
            cmd.append(app)

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
        self.installs = self.get_installed()
        ConsoleWindow._start_curses()

def main():
    """ The program """
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
