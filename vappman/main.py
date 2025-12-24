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

*   One-command setup: Don't have appman (or am)? vappman will now set it up for you.
    -If a user runs vappman and appman isn't found, offering to install it
     (and its core dependencies like curl, zsync, etc.) removes the
     biggest barrier to entry.
    - The Pitch: "Experience 2500+ Linux apps with zero setup—vappman now bootstraps
      your entire AppImage management environment."

*   Security First: Integrated sandboxing support—run untrusted apps in a click.
    - appman has built-in support for sandboxing via the -ias or --sandbox flags
      (often using Firejail).
    - High Value: Add a b (for "Box") or S (for "Sandbox") key.
    - Why? Security is the #1 concern for AppImage users. A TUI that lets you
      "Search -> Highlight -> Install with Sandbox" is a power-user's dream.

*   More than AppImages: Full support for the NeoDB ecosystem (Soarpkgs, AppBundles).
    - The current appman help shows it's no longer just for standard AppImages. It now handles:
    - Soarpkgs: High-performance static binaries.
    - AppBundles: PELF-based portable apps.
    - Python AppImages: Side-by-side Python versions.
    - The Feature: Add a "Repo Toggle" or a "Global Search" (using appman -q --all)
      so users can discover these formats without needing to know the CLI flags.
*   Safe Updates: One-key snapshots and rollbacks.
    appman supports -b (backup) and --rollback (downgrade).
    - The Feature: In the "Installed Apps" view, let users hit B to take a snapshot or
      L (Legacy/List) to see available rollbacks for that specific app.
    - Why? This is the "Time Machine" for Linux apps. If an update breaks a tool,
      vappman could be the easiest way to fix it.
* 5. Metadata & "About" Integration
    - Your README mentions vappman covers (-a) about, but making this instant is key.
    - Improvement: A side-pane or a toggleable window that shows the appman -a info for
      the currently highlighted app before the user even hits a key to install.
---
      
Based on the ivan-hc/AM repository and recent updates, there is a very clear distinction—and a significant
branding shift—that provides you with the perfect "excuse" for a vappman revamp.
1. The Core Issue: AM vs. AppMan

The developer has effectively merged the logic into a single codebase, but uses two different "entry points" depending on user privilege:
 * am (The Flagship): Intended for users with root/sudo access.
   It installs apps system-wide (e.g., in /opt) by default.
 * appman (The Rootless Side): A "portable" version of the same script.
   If you rename the main APP-MANAGER script to appman, it automatically switches to "AppMan mode,"
   installing everything locally in $HOME without requiring sudo.

The "Revamp" Opportunity: Currently, vappman is hardcoded to look for appman.
  - If a user has installed the full am suite, vappman might not even "see" it or work with it properly.

2. Does it make sense to change? Yes.

   -To stay relevant with Ivan-HC’s ecosystem, vappman should transition from being a "wrapper for AppMan" to a "TUI for AM/AppMan."

The "High Value" Roadmap for your Re-announcement:

  - Auto-Detection & Support for am: vappman should check for am first, then appman. If am is present,
    it should use it (perhaps adding a toggle for --user mode). This broadens your user base to everyone using the main AM project.

  - The "Bootstrap" Installer: Since Ivan-HC now provides a unified AM-INSTALLER script,
    vappman can offer to run it if neither is found. This makes vappman a "zero-dependency" entry point for new users.

  - Sandboxing Integration (Version 9+ Feature): The latest AM (v9.3+) now supports sandboxing
    during installation in one go. Adding a "Secure Install" key (using -ias) in vappman is a major
    feature that aligns with the current development of the backend.

  - Snapshot Management: AM has introduced named snapshots (v8.4). vappman could allow users to manage
    these backups visually, which is much more intuitive than the CLI.

Suggested Re-announcement Pitch: "The AM/AppMan Unified Interface"
   - Headline: Re-introducing vappman: Now a complete TUI for the "AM" Application Manager ecosystem.
   - The Narrative: " I’ve rebuilt vappman to be the ultimate visual dashboard for both. Whether you’re a
      power user installing system-wide with am or a local user with appman, vappman now handles the heavy lifting."

New Feature Highlights:
    - Dual-Engine Support: Automatically detects and works with either am or appman.
    - One-Click Sandboxing: Leverage the new AM 9.3+ sandboxing features directly from the TUI.
    - Visual Snapshots: Manage your app backups and rollbacks without memorizing CLI flags.
    - The 'Zero-to-App' Experience: If you don't have the backend installed,
      vappman will now bootstrap the official AM-INSTALLER for you.

    Why this works: It stops being "just another tool" and starts being the "Official-feeling TUI"
    for a very active and popular project. It solves the confusion between am and appman for the user by abstracting it away.

    
That testing hurdle is actually a common "developer’s trap." You’re trying to test two distinct system states on one machine, which leads to "configuration drift"—where your tests for `appman` start failing because `am` left a file in `/opt` or vice versa.

The good news is that because the `APP-MANAGER` script is now unified, you can "spoof" the environments without actually needing two machines or deep system changes.

---

### 1. The "Poor Man's" Sandbox: Binary Aliasing

Since the backend script behaves differently based on its **filename**, you can test the logic on one system by simply creating two symlinks to the same source script in a local testing directory.

1. Download the master script: `wget https://raw.githubusercontent.com/ivan-hc/AM/main/APP-MANAGER`
2. Create two symlinks:
* `ln -s APP-MANAGER am`
* `ln -s APP-MANAGER appman`


3. **The Trick:** Modify your `vappman` test environment to point its `$PATH` to this local folder first. You can then toggle which one `vappman` "sees" by just deleting/renaming the symlinks.

### 2. The Professional Fix: Containerization (Distrobox)

If you want to be 100% sure without messing up your host, use **Distrobox**. It is a tool that lets you run any Linux distro inside your terminal with full access to your home directory, but a separate system area (`/opt`, `/usr/bin`).

* **Setup:** Create two containers:
* `distrobox create -n am-test --image fedora`
* `distrobox create -n appman-test --image fedora`


* **Workflow:**
* In `am-test`, run the `AM` installer (System mode).
* In `appman-test`, run the `AppMan` installer (User mode).


* **Why this wins:** You can have two terminal tabs open simultaneously—one acting as a "System Mode" machine and one as a "User Mode" machine. You just run `vappman` inside them, and they will behave exactly like real-world installs.

### 3. Spoofing via Environment Variables

If you want to automate your testing, you can add a "Debug Mode" to `vappman` that overrides the discovery logic.

```python
# Pseudo-code for your vappman overhaul
VAPPMAN_FORCE_MODE = os.getenv("VAPPMAN_TEST_MODE") # 'am' or 'appman'

if VAPPMAN_FORCE_MODE == 'am':
    active_manager = "am"
    needs_sudo = True
elif VAPPMAN_FORCE_MODE == 'appman':
    active_manager = "appman"
    needs_sudo = False
else:
    # ... your normal auto-discovery logic

```

This lets you test both code paths by just running `VAPPMAN_TEST_MODE=am vappman`.

---

### The Final "Excuse" for the Re-Announcement

Combining everything we've discussed, here is your high-value pitch:

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
import glob
import shutil
import shlex
import subprocess
import traceback
import curses as cs
from .ConsoleWindow import (
    ConsoleWindow, OptionSpinner, ConsoleWindowOpts,
    Screen, ScreenStack, BasicHelpScreen, HOME_ST
)

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

        def version_of(appname):
            # ◆  krita      |  5.2.2   |  appimage-type2  |  355   MiB
            fields = app.installs[appname].split('|')
            if len(fields) >= 2:
                return fields[1].strip()
            return '?version?'

        win.set_pick_mode(True)
        win.add_header(app.get_keys_line(), attr=cs.A_BOLD)

        # Show installed apps first
        for appname, line in app.installs.items():
            if appname in app.apps:
                line = app.apps[appname]
            if wanted(line[2:]):
                line = f'✔✔✔ {appname} [{version_of(appname)}] :{line.split(":", maxsplit=1)[1]}'
                win.add_body(line)

        # Then show available (not installed) apps
        for appname, line in app.apps.items():
            if appname not in app.installs and wanted(line[2:]):
                win.add_body(line)
                
    def installed_run_appman(self, verb):
        app = self.app
        if app.pick_is_installed:
            app.run_appman(verb, app.pick_app)
            return None

    def remove_ACTION(self):
        """ TBD """
        return self.installed_run_appman('remove')

    def update_ACTION(self):
        """ TBD """
        return self.installed_run_appman('update')

    def backup_ACTION(self):
        """ TBD """
        return self.installed_run_appman('backup')

    def overwrite_ACTION(self):
        """ TBD """
        self.installed_run_appman('overwrite')

    def about_ACTION(self):
        """ TBD """
        app = self.app
        return app.run_appman('about', app.pick_app)

    def test_ACTION(self):
        """ TBD """
        app = self.app
        if app.pick_is_installed:
            app.launch_app(app.pick_app)
    
    def default_ACTION(self):
        """ TBD """
        if self.app.pick_is_installed:
           return self.remove_ACTION()
        return self.install_ACTION()

    #################################
    def install_ACTION(self):
        """ TBD """
        app = self.app
        if not app.pick_is_installed:
            app.run_appman('install', app.pick_app)

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
    def escape_ACTION(self):
        """ TBD """
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
                                     seed=app.prev_filter)
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


class Vappman:
    """ Main class for curses atop appman"""
    singleton = None

    def __init__(self):
        # self.cmd_loop = CmdLoop(db=False) # just running as command
        assert not Vappman.singleton
        Vappman.singleton = self

        spin = self.spin = OptionSpinner()
        spin.add_key('quit', 'q,x - quit program (CTL-C disabled)',
                     genre='action', keys='qx')
        spin.add_key('help', '? - toggle help screen', genre='action')

        spin.add_key('sync', 's - sync (update appman itself)', genre='action')
        spin.add_key('clean', 'c - clean (remove unneeded files/folders)', genre='action')
        spin.add_key('update_all', 'U - update ALL installed apps', genre='action')
        spin.add_key('reinstall_all', 'R - reinstall ALL apps w updated install script', genre='action')
        spin.add_key('slash', '/ - filter apps by keywords or regex', genre='action')
        spin.add_key('escape', 'ESC - clear filter and jump to top', genre='action', keys=27)

        spin.add_key('install', 'i - install uninstalled app', genre='action')
        spin.add_key('default', 'ENTER - install/uninstall app',
                     genre='action', keys=[cs.KEY_ENTER, 10])
        spin.add_key('remove', 'r - remove installed app', genre='action')
        spin.add_key('about', 'a - about (more info about app)', genre='action')

        spin.add_key('backup', 'b - backup installed app', genre='action')
        spin.add_key('update', 'u - update_installed app', genre='action')
        spin.add_key('overwrite', 'o - overwrite app from its backup', genre='action')
        spin.add_key('test', 't - test (open a terminal and run app', genre='action')


        # EXPAND
        # other_keys = set([cs.KEY_ENTER, 10])
        # other_keys.add(27) # ESCAPE
        # other_keys.add(10) # another form of ENTER
        self.opts = spin.default_obj

        self.actions = {} # currently available actions
        self.pick_app = '' # current picked app
        self.pick_is_installed = False
        self.prev_filter = '' # string
        self.filter = None # compiled pattern
        self.apps = self.cmd_dict('appman list')
        self.installs = self.get_installed() # dict keyed by app
        self.appman_dir = self.get_appman_dir()
        self.dot_desktop_dir = self.get_dot_desktop_dir()
        self.terminal_emulator = None
        win_opts = ConsoleWindowOpts()
        win_opts.head_line=True
        win_opts.body_rows=len(self.apps)+20
        win_opts.head_rows = 10
        win_opts.keys = spin.keys
        win_opts.mod_pick = self.mod_pick
        win_opts.pick_attr = cs.A_BOLD|cs.A_UNDERLINE
        win_opts.dialog_abort = True
        win_opts.ctrl_c_terminates = False
        self.win = ConsoleWindow(win_opts)
        self.has_am = None

        # Initialize screens and screen stack
        self.screens = {
            HOME_ST: HomeScreen(self),
            HELP_ST: VappmanHelpScreen(self),
        }
        self.ss = ScreenStack(self.win, self.opts, SCREENS, self.screens)
        self.prev_pos = 0
        self.next_prompt_seconds = [0.1, 0.1]  # Initial fast renders, then slow down

    def check_preqreqs(self):
        """ Check that needed programs are installed. """
        missing = set()
        self.has_am = bool (shutil.which('am') is not None
                       or shutil.which('appman') is not None)
        for prog in 'curl grep jq sed wget'.split():
            if shutil.which(prog) is None:
                missing.add(prog)
                
        if missing:
                print(f'ERROR: cannot find {missing} on $PATH')

        if not self.has_am:
            print('Install appman/am with:')
            print("""wget -q https://raw.githubusercontent.com/ivan-hc/AM/main/AM-INSTALLER"""
                  """ && chmod a+x ./AM-INSTALLER && ./AM-INSTALLER && rm ./AM-INSTALLER""")

        if not self.has_am or missing:
            sys.exit(1)

    def cmd_dict(self, cmd, start=r'\s*◆\s'):
        """ Get lines with the given start put into a dict keyed by the
            1st word.
        """
        # Define the command to run
        command = cmd.split()
        # Run the command and capture the output
        try:
            # Capture as bytes first, then decode with error handling
            result = subprocess.run(command, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, check=False)
        except Exception as exc:
            ConsoleWindow.stop_curses()
            print(f'FAILED: {command}: {exc}')
            sys.exit(1)

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
        ansi_escape_pattern = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        rv = {}
        prev_wd1 = None
        for line in lines:
            line = ansi_escape_pattern.sub('', line) # get clean text
            if re.match(start, line):
                line = line.strip()
                wd1 = self.get_word1(line)
                if wd1:
                    rv[wd1] = line
                    prev_wd1 = wd1
            elif prev_wd1 and line.startswith(' '):
                line = line.strip()
                if line:
                    rv[prev_wd1] += ' ' + line
                else:
                    prev_wd1 = None
            else:
                prev_wd1 = None

        return rv

    @staticmethod
    def get_word1(line):
        """ Get words[1] from a string (e.g. '◆  appname ...' -> 'appname'). """
        words = line.split(maxsplit=3)
        return '' if len(words) < 2 else words[1]

    def get_installed(self):
        """ Get the list of lines of installed apps """
        rv = self.cmd_dict('appman files --byname')
        return rv

    @staticmethod
    def get_appman_dir():
        """ Try to figure out where the apps are stored. """

        appman_dir = None
        try:
            config_dir = os.getenv('XDG_CONFIG_HOME')
            if not config_dir:
                config_dir = os.path.join(os.getenv('HOME'), '.config')
            config_file = os.path.join(config_dir, 'appman', 'appman-config')
            with open(config_file, 'r', encoding='utf-8', errors='replace') as fh:
                appman_dir = fh.read().strip()
            # appman-config may contain either an absolute path or a home-relative path;
            # use as-is if absolute, otherwise join to HOME.
            if not os.path.isabs(appman_dir):
                appman_dir = os.path.join(os.getenv('HOME'), appman_dir)
            os.listdir(appman_dir)
            return appman_dir
        except Exception as exc:
            print(f'NOTE: cannot get appman dir; tried below {appman_dir!r}; {exc}')
            print('    Check if contents of ~/config/appman/appman-config'
                  + ' is the subdir of $HOME w your appman apps')
            return None

    @staticmethod
    def get_dot_desktop_dir():
        """ Try to figure out where the .desktop files are stored. """

        try:
            data_dir = os.getenv('XDG_DATA_HOME')
            if not data_dir:
                data_dir = os.path.join(os.getenv('HOME'), '.local', 'share')
            dot_dir = os.path.join(data_dir, 'applications')
            os.listdir(dot_dir)
            return dot_dir
        except Exception as exc:
            print(f'NOTE: cannot get .desktop dir; tried below {data_dir!r}; {exc}')
            print('    Check if contents of ~/.local/share/applications for .desktop files')
            return None

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

#               # Handle escape
#               if self.ss.act_in('escape'):
#                   self.handle_escape()

                # Handle help mode navigation
#               if self.opts.help_mode:
#                   if self.ss.curr.num != HELP_ST:
#                       self.navigate_to(HELP_ST)
#               else:
#                   if self.ss.curr.num == HELP_ST:
#                       self.navigate_back()

                # Delegate key handling to old do_key for now
                # (will refactor actions to screen classes later)
#           if key == cs.KEY_ENTER or key == 10: # Handle ENTER
#               if self.opts.help_mode:
#                   self.opts.help_mode = False
#                   return True

                if key in self.spin.keys:
                    _ = self.spin.do_key(key, self.win)
                    # return value

                # Actions delegated to screen classes - automatically handled
                self.ss.perform_actions(self.spin)

            win.clear()

    def get_keys_line(self):
        """ TBD """
        # EXPAND
        line = ''
        for key, verb in self.actions.items():
            if key[0] == verb[0]:
                line += f' {verb}'
            else:
                line += f' {key}:{verb}'
        # or EXPAND
        line += f' about ❚ sync clean Upd ReInst quit ?:help /{self.prev_filter}  '
        # for action in self.actions:
            # line += f' {action[0]}:{action}'
        return line[1:]

    def get_actions(self, line):
        """ Determine the type of the current line and available commands."""
        app, actions = '', {}
        lines = self.win.body.texts
        if 0 <= self.win.pick_pos < len(lines):
            line = lines[self.win.pick_pos]
            app = self.get_word1(line)
            self.pick_is_installed = bool(app in self.installs)
            # EXPAND
            if self.pick_is_installed:
                actions['r'] = 'rmv'
                actions['u'] = 'upd'
                actions['b'] = 'bkup'
                actions['o'] = 'overwr'
                actions['t'] = 'test'
            else:
                actions['i'] = 'install'

        return app, actions

    @staticmethod
    def mod_pick(line):
        """ Callback to modify the "pick line" being highlighed;
            We use it to alter the state
        """
        this = Vappman.singleton
        this.pick_app, this.actions = this.get_actions(line)
        header = this.get_keys_line()
        # ASSUME line ends in /....
        parts = header.split('/', maxsplit=1)
        wds = parts[0].split()
        this.win.head.pad.move(0, 0)
        for wd in wds:
            if wd[0]in ('<', '|', '❚'):
                this.win.add_header(wd + ' ', resume=True)
                continue
            if wd:
                this.win.add_header(wd[0], attr=cs.A_BOLD|cs.A_UNDERLINE, resume=True)
            if wd[1:]:
                this.win.add_header(wd[1:] + ' ', resume=True)

        this.win.add_header('/', attr=cs.A_BOLD+cs.A_UNDERLINE, resume=True)
        if len(parts) > 1 and parts[1]:
            this.win.add_header(f'{parts[1]}', resume=True)
        _, col = this.win.head.pad.getyx()
        pad = ' ' * (this.win.get_pad_width()-col)
        this.win.add_header(pad, resume=True)
        return line

    def old_run_appman(self, cmd):
        """ Run a 'appman' command """
        ConsoleWindow.stop_curses()
        os.system(f'clear; stty sane; /bin/echo + {shlex.quote(cmd)}; {shlex.quote(cmd)};'
                  + r' /bin/echo -e "\n\n===== Press ENTER to return to vappman ====> \c"; read FOO')
        self.installs = self.get_installed()
        ConsoleWindow._start_curses()

    def run_appman(self, subcommand: str, app: str = None):
        """ Run an 'appman' command using subprocess. """

        # 1. Build the command list
        cmd = ['appman', subcommand]
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

    @staticmethod
    def launch_desktop_file(desktop_file_path):
        """ Launch the .desktop file using xdg-open in a detached process """
        try:
            trial = ['xdg-open', desktop_file_path]
            subprocess.Popen(trial,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
            return None
        except Exception:
            return trial

    def launch_in_terminal(self, executable):
        """ Find a terminal emulator"""
        if not self.terminal_emulator:
            maybes = [
                [ 'konsole', '--noclose', '-e', '"{command}"'],
                [ 'gnome-terminal', '--', 'bash', '-c', '"{command}"; exec bash' ],
                [ 'xfce4-terminal', '--hold', '--command="{command}"' ],
                [ 'lxterminal', '-e', """bash -c '"{command}"; echo; read -p "Press Enter to close..."'"""],
                [ 'alacritty', '--hold', '-e', 'sh', '-c', '"{command}"' ],
                [ 'guake', '--new-tab', '--execute-command="sh -c \'{command} ; exec $SHELL\'"' ],
                [ 'tilix', '-e', 'sh -c "{command} ; exec $SHELL"' ],
                [ 'sakura', '-x', 'sh -c "{command} ; bash"' ],
                [ 'terminator', '-e', 'bash -c " {command} ; bash "' ],
                [ 'kitty', '--hold', '/bin/sh', '-c', '"{command}"' ],
                # [ hyper', ], # cannot be supported
                # [ yakuake', ], # cannot be supported
            ]
            for maybe in maybes:
                if shutil.which(maybe[0]):
                    self.terminal_emulator = maybe
                    break
        # On success return None; on failure return the attempted argument list
        if not self.terminal_emulator:
            return None
        trial = []
        if self.terminal_emulator:
            try:
                for wd in self.terminal_emulator:
                    trial.append(wd.replace('{command}', executable))
                subprocess.Popen(trial)
                return None
            except Exception:
                return trial
        return None

    def launch_app(self, app):
        """ Try to run an app."""
        # First dig out where it might be installed as a .desktop file
        # by searching the 'remove' script
        def get_unique_words_from_file(file_path):
            seen_words = set()
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                for line in file:
                    line_words = line.split()
                    for word in line_words:
                        if word not in seen_words:
                            seen_words.add(word)
            return seen_words

        failures = []
        executables = []
        try:
            for globname in get_unique_words_from_file(
                    os.path.join(self.appman_dir, app, 'remove')):
                results = glob.glob(globname)
                if '/share/applications/AM-ZZZ' in globname:
                    for result in results:
                        if result.endswith('.desktop'):
                            failure = self.launch_desktop_file(result)
                            if failure:
                                failures.append(' '.join(failure))
                            return
                elif '/.local/bin/' in globname:
                    for result in results:
                        if os.access(result, os.X_OK):
                            executables.append(result)
            for executable in executables:
                failure = self.launch_in_terminal(executable)
                if failure:
                    failures.append(' '.join(failure))
                return
        except Exception as exc:
            failures += f'cannot find .desktop/executable to run [{exc}]'
        if failures:
            message = ' '.join([f'Cannot launch {app}'] + failures)
            self.win.alert(message=message)

    def do_key(self, key):
        """ TBD """

        return None


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
