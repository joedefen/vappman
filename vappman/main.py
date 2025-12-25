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
from types import SimpleNamespace
import curses as cs
from .ConsoleWindow import (
    ConsoleWindow, OptionSpinner, ConsoleWindowOpts,
    Screen, ScreenStack, BasicHelpScreen, Context
)
from .PersistentState import PersistentState

# Screen constants
HOME_ST, HELP_ST = 0, 1
SCREENS = ['HOME', 'HELP']

class Prerequisites:
    """ Detect / install prereqs """
    def __init__(self):
        self.has_am = False
        self.has_appman = False

    def detect_package_manager(self):
        """
        Detect the system's package manager.

        Returns:
            tuple: (package_manager_name, install_command_template)
                   or (None, None) if unsupported
        """
        # Check for various package managers in order of preference
        pkg_managers = [
            ('apt', 'sudo apt-get update && sudo apt-get install -y {packages}'),
            ('dnf', 'sudo dnf install -y {packages}'),
            ('yum', 'sudo yum install -y {packages}'),
            ('pacman', 'sudo pacman -S --noconfirm {packages}'),
            ('zypper', 'sudo zypper install -y {packages}'),
            ('emerge', 'sudo emerge {packages}'),
            ('apk', 'sudo apk add {packages}'),
        ]

        for pm_name, cmd_template in pkg_managers:
            if shutil.which(pm_name):
                return (pm_name, cmd_template)

        return (None, None)

    def install_dependencies(self, missing):
        """
        Offer to install missing dependencies using the system package manager.

        Args:
            missing (set): Set of missing program names

        Returns:
            bool: True if installation succeeded or user declined, False on error
        """
        if not missing:
            return True

        pm_name, install_cmd_template = self.detect_package_manager()

        if not pm_name:
            print(f'\nERROR: Cannot find supported package manager.')
            print(f'Missing dependencies: {", ".join(sorted(missing))}')
            print('Please install them manually using your system package manager.')
            return False

        # Map common program names to package names for different distros
        # Some programs have different package names on different distros
        package_map = {
            'curl': 'curl',
            'grep': 'grep',
            'jq': 'jq',
            'sed': 'sed',
            'wget': 'wget',
        }

        packages = [package_map.get(prog, prog) for prog in missing]

        print(f'\n⚠️  Missing dependencies: {", ".join(sorted(missing))}')
        print(f'\nDetected package manager: {pm_name}')

        response = input(f'\nInstall missing dependencies? [y/N]: ').strip().lower()

        if response not in ('y', 'yes'):
            print('Installation cancelled.')
            return False

        # Build and execute the install command
        install_cmd = install_cmd_template.format(packages=' '.join(packages))
        print(f'\nRunning: {install_cmd}')

        try:
            result = subprocess.run(install_cmd, shell=True, check=False)
            if result.returncode != 0:
                print(f'\n❌ Installation failed with exit code {result.returncode}')
                return False
            print(f'\n✅ Dependencies installed successfully!')
            return True
        except Exception as exc:
            print(f'\n❌ Installation failed: {exc}')
            return False

    def install_am_appman(self):
        """
        Offer to install AM/appman using the official installer.

        Returns:
            bool: True if installation succeeded or user declined, False on error
        """
        print('\n⚠️  AM/appman is not installed.')
        print('\nAM is a powerful AppImage package manager that allows you to:')
        print('  • Install and manage 2500+ AppImages, Soarpkgs, and AppBundles')
        print('  • Update apps with a single command')
        print('  • Sandbox untrusted applications')
        print('  • Create snapshots and rollbacks')

        response = input('\nInstall AM/appman now? [y/N]: ').strip().lower()

        if response not in ('y', 'yes'):
            print('Installation cancelled.')
            return False

        # Check if wget or curl is available
        if not shutil.which('wget'):
            print('\n❌ wget is required to download the AM installer.')
            print('Please install wget first.')
            return False

        installer_url = 'https://raw.githubusercontent.com/ivan-hc/AM/main/AM-INSTALLER'
        install_cmd = (
            f'wget -q {installer_url} && '
            f'chmod a+x ./AM-INSTALLER && '
            f'./AM-INSTALLER && '
            f'rm ./AM-INSTALLER'
        )

        print(f'\nRunning: {install_cmd}')

        try:
            result = subprocess.run(install_cmd, shell=True, check=False)
            if result.returncode != 0:
                print(f'\n❌ AM installation failed with exit code {result.returncode}')
                return False
            print(f'\n✅ AM/appman installed successfully!')
            return True
        except Exception as exc:
            print(f'\n❌ AM installation failed: {exc}')
            return False

    def check_preqreqs(self):
        """
        Check that needed programs are installed.
        Offers to install missing dependencies and AM/appman if not found.
        """
        print('Checking prerequisites...')

        missing = set()
        self.has_am = bool(shutil.which('am') is not None)
        self.has_appman = bool(shutil.which('appman') is not None)

        for prog in 'curl grep jq sed wget'.split():
            if shutil.which(prog) is None:
                missing.add(prog)

        # Handle missing dependencies
        if missing:
            if not self.install_dependencies(missing):
                print('\n❌ Cannot proceed without required dependencies.')
                sys.exit(1)

            # Verify installation
            still_missing = set()
            for prog in missing:
                if shutil.which(prog) is None:
                    still_missing.add(prog)

            if still_missing:
                print(f'\n❌ Still missing after installation: {", ".join(sorted(still_missing))}')
                sys.exit(1)

        # Handle missing AM/appman
        if not self.has_am and not self.has_appman:
            if not self.install_am_appman():
                print('\n❌ Cannot proceed without AM/appman.')
                print('\nManual installation instructions:')
                print('  wget -q https://raw.githubusercontent.com/ivan-hc/AM/main/AM-INSTALLER')
                print('  chmod a+x ./AM-INSTALLER')
                print('  ./AM-INSTALLER')
                print('  rm ./AM-INSTALLER')
                sys.exit(1)

            # After successful installation, exit so user can restart vappman
            print('\n✅ Installation complete!')
            print('\nPlease restart vappman to begin using it.')
            sys.exit(0)

        print('✅ All prerequisites satisfied.')

    def cmd_dict(self, cmd, start=r'\s*◆\s'):
        """ Get lines with the given start put into a dict keyed by the
            1st word.
        """
        def parse_app_list(lines):
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
            current_global = False
            
            # Process line by line
            # lines = input_text.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Determine context (Global vs Local)
                if 'BY "AM"' in line:
                    current_global = True
                    continue
                elif 'AS "APPMAN"' in line:
                    current_global = False
                    continue
                    
                # Identify data lines (they start with the diamond symbol ◆)
                if line.startswith('◆'):
                    # Remove the symbol and split by pipe '|'
                    # We strip whitespace and also remove the '*' indicator for libfuse2
                    parts = [p.strip().rstrip('*') for p in line[1:].split('|')]
                    
                    if len(parts) >= 3:
                        name = parts[0]
                        version = parts[1]
                        app_type = parts[2]
                        
                        # Store as a SimpleNamespace for dot-notation access
                        apps[name] = SimpleNamespace(
                                        version=version,
                                        app_type=shorten(app_type),
                                        global_status=current_global,
                                        synopsis=None,
                                        raw=line
                                    )
                    else:
                        mat = re.match(r'\s*([^\s]+)\s+:\s+([^\s].*)', line[1:])
                        if mat:
                            apps[mat.group(1)] = SimpleNamespace(
                                                    version=None,
                                                    app_type=None,
                                                    global_status=None,
                                                    synopsis=mat.group(2),
                                                    raw=line
                                                )
                        
            return apps
        # Define the command to run
        command = ['appman' if self.has_appman else 'am']
        command += cmd.split()
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
        # ansi_escape_pattern = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        rv = parse_app_list(lines)
        return rv

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
        win.set_demo_mode(app.opts.demo_mode)

        title = "APPMAN"
        if not app.has_appman:
            title = "AM-SYSTEM" if app.opts.in_system_mode else 'AM-USER'
            if app.disk_state.in_system_mode != app.opts.in_system_mode:
                app.disk_state.in_system_mode = app.opts.in_system_mode
                app.disk_state.save()
        if app.disk_state.max_backups != app.opts.max_backups:
            app.disk_state.max_backups = app.opts.max_backups
            app.disk_state.save()


        # Show installed apps first
        idx = 0
        for appname, ns in app.installs.items():
            ns2 = app.apps[appname] if appname in app.apps else None
            if ns2 and wanted(ns.raw[2:]):
                where = "S" if ns.global_status else "u"
                checks = f'✔⋅{where}'
                app_ver = f'{appname} [{ns.version}]  '
                fill = '⋅' if idx % 3 == 1 else ''
                idx += 1
                line = f'{checks} {ns.app_type:<4} ⋅ {app_ver:{fill}<30} : {ns2.synopsis}'
                win.add_body(line, context=Context("installed", app=appname, ver=ns.version))

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
            if context.genre == 'installed':
                header2 = ' [r]mv [u]pd [b]kup [o]verwr [t]est'
            elif context.genre == 'uninstalled':
                header2 = ' [i]nstall'
            header2 += f' [a]bout #:maxBkUp={app.opts.max_backups}'
        
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
        self.disk_state = PersistentState('vappman', in_system_mode=False, max_backups=1)

        self.actions = {} # currently available actions
        self.prev_filter = '' # string
        self.filter = None # compiled pattern
        self.apps = self.cmd_dict('list')
        self.installs = self.get_installed() # dict keyed by app
        self.appman_dir = self.get_appman_dir()
        self.dot_desktop_dir = self.get_dot_desktop_dir()
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
            self.opts.in_system_mode = self.disk_state.in_system_mode
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


    @staticmethod
    def get_word1(line):
        """ Get words[1] from a string (e.g. '◆  appname ...' -> 'appname'). """
        words = line.split(maxsplit=3)
        return '' if len(words) < 2 else words[1]

    def get_installed(self):
        """ Get the list of lines of installed apps """
        rv = self.cmd_dict('files --byname')
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
            print('    Check if contents of ~/.config/appman/appman-config'
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
            if not self.opts.in_system_mode and subcommand == 'install':
                subcommand = '--user'
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
