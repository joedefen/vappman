#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive, visual thin layer atop appman
"""
# pylint: disable=broad-exception-caught,consider-using-with
# pylint: disable=too-many-instance-attributes,too-many-branches
# pylint: disable=too-many-return-statements,too-many-statements
# pylint: disable=consider-using-in,too-many-nested-blocks
# pylint: disable=wrong-import-position,disable=wrong-import-order
# import VirtEnv
# VirtEnv.ensure_venv(__name__)

import os
import sys
import re
import glob
import shutil
import subprocess
import traceback
import curses as cs
from vappman.PowerWindow import Window, OptionSpinner


class Vappman:
    """ Main class for curses atop appman"""
    singleton = None

    def __init__(self):
        # self.cmd_loop = CmdLoop(db=False) # just running as command
        assert not Vappman.singleton
        Vappman.singleton = self

        spin = self.spin = OptionSpinner()
        spin.add_key('help_mode', '? - toggle help screen', vals=[False, True])

        # EXPAND
        other = 'airtbou/qxscU'
        other_keys = set(ord(x) for x in other)
        other_keys.add(cs.KEY_ENTER)
        other_keys.add(27) # ESCAPE
        other_keys.add(10) # another form of ENTER
        self.opts = spin.default_obj

        self.actions = {} # currently available actions
        self.pick_app = '' # current picked app
        self.pick_is_installed = False
        self.prev_filter = '' # string
        self.filter = None # compiled pattern
        self.check_preqreqs()
        self.apps = self.cmd_dict('appman list')
        self.installs = self.get_installed() # dict keyed by app
        self.appman_dir = self.get_appman_dir()
        self.dot_desktop_dir = self.get_dot_desktop_dir()
        self.terminal_emulator = None
        self.win = Window(head_line=True, body_rows=len(self.apps)+20, head_rows=10,
                          keys=spin.keys ^ other_keys, mod_pick=self.mod_pick)

    @staticmethod
    def check_preqreqs():
        """ Check that needed programs are installed. """
        ok = True
        for prog in 'curl grep jq sed wget appman'.split():
            if shutil.which(prog) is None:
                ok = False
                print(f'ERROR: cannot find {prog!r} on $PATH')
                if prog == 'appman':
                    print('Install appman with:')
                    print("""mkdir -p ~/.local/bin && cd /tmp &&"""
                          """ wget https://raw.githubusercontent.com/ivan-hc/AM/main/APP-MANAGER"""
                          """ -O appman && chmod a+x ./appman && mv ./appman ~/.local/bin/appman""")
        if not ok:
            sys.exit(1)

    def cmd_dict(self, cmd, start='◆ '):
        """ Get lines with the given start."""
        # Define the command to run
        command = cmd.split()
        # Run the command and capture the output
        result = subprocess.run(command, stdout=subprocess.PIPE, text=True, check=True)
        lines = result.stdout.splitlines()
        rv = {}
        for line in lines:
            if line.startswith(start):
                wd1 = self.get_word1(line)
                if wd1:
                    rv[wd1] = line
        return rv

    @staticmethod
    def get_word1(line):
        """ Get words[1] from a string. """
        words = line.split(maxsplit=3)
        return '' if len(words) < 1 else words[1]

    def get_installed(self):
        """ Get the list of lines of installed apps """
        rv = self.cmd_dict('appman files --byname')
        return rv

    @staticmethod
    def get_appman_dir():
        """ Try to figure out where the apps are stored. """

        appman_dir = None, None
        try:
            config_dir = os.getenv('XDG_CONFIG_HOME')
            if not config_dir:
                config_dir = os.path.join(os.getenv('HOME'), '.config')
            config_file = os.path.join(config_dir, 'appman', 'appman-config')
            with open(config_file, 'r', encoding='utf-8') as fh:
                appman_dir = fh.read().strip()
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

    def main_loop(self):
        """ TBD """

        self.opts.name = "[hit 'n' to enter name]"
        while True:
            if self.opts.help_mode:
                self.win.set_pick_mode(False)
                self.spin.show_help_nav_keys(self.win)
                self.spin.show_help_body(self.win)
                # EXPAND
                lines = [
                    'ALWAYS AVAILABLE:',
                    '   q or x - quit program (CTL-C disabled)',
                    '   a - about (more info about app)',
                    '   s - sync (update appman itself)',
                    '   c - clean (remove unneeded files/folters)',
                    '   U - update ALL installed apps',
                    '   / - filter apps',
                    '   ENTER = install, remove, or return from help',
                    '   ESC = clear filter and jump to top',
                    'CONTEXT SENSITIVE:',
                    '   i - install uninstalled app',
                    '   r - remove installed app',
                    '   b - backup installed app',
                    '   u - update installed app',
                    '   t - test by opening a terminal emulator and launching the app'
                    '   o - overwrite app from its backup',

                ]
                for line in lines:
                    self.win.put_body(line)
            else:
                def wanted(line):
                    return not self.filter or self.filter.search(line)
                def version_of(app):
                    # ◆  krita      |  5.2.2   |  appimage-type2  |  355   MiB
                    fields = self.installs[app].split('|')
                    if len(fields) >= 2:
                        return fields[1].strip()
                    return '?version?'

                # self.win.set_pick_mode(self.opts.pick_mode, self.opts.pick_size)
                self.win.set_pick_mode(True)
                self.win.add_header(self.get_keys_line(), attr=cs.A_BOLD)
                for app, line in self.installs.items():
                    if app in self.apps:
                        line = self.apps[app]
                    if wanted(line[2:]):
                        line = f'✔✔✔ {app} [{version_of(app)}] :{line.split(':', maxsplit=1)[1]}'
                        self.win.add_body(line)
                for app, line in self.apps.items():
                    if app not in self.installs and wanted(line[2:]):
                        self.win.add_body(line)
            self.win.render()

            _ = self.do_key(self.win.prompt(seconds=300))
            self.win.clear()

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
        line += f' ?:help quit about sync clean Upd /{self.prev_filter}  '
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
                actions['b'] = 'bkup'
                actions['o'] = 'overwr'
                actions['u'] = 'upd'
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

    def run_appman(self, cmd):
        """ Run a 'appman' command """
        Window.stop_curses()
        os.system(f'clear; stty sane; {cmd};'
                  + r' /bin/echo -e "\n\n===== Press ENTER for menu ====> \c"; read FOO')
        self.installs = self.get_installed()
        Window._start_curses()

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
                # [ terminator', ],
                # [ alacritty', ],
                # [ termite', ],
                # [ urxvt', ],
                # [ sakura', ],
                # [ tilix', ],
                # [ kitty', ],
                # [ hyper', ],
                # [ guake', ],
                # [ yakuake', ],
            ]
            for maybe in maybes:
                if shutil.which(maybe[0]):
                    self.terminal_emulator = maybe
                    break
        if self.terminal_emulator:
            try:
                trial = []
                for wd in self.terminal_emulator:
                    trial.append(wd.replace('{command}', executable))
                subprocess.Popen(trial)
                return None
            except Exception:
                return trial
        return trial

    def launch_app(self, app):
        """ Try to run an app."""
        # First dig out where it might be installed as a .desktop file
        # by searching the 'remove' script
        def get_unique_words_from_file(file_path):
            seen_words = set()
            with open(file_path, 'r', encoding='utf-8') as file:
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

        self.launch_app(self.pick_app)

    def do_key(self, key):
        """ TBD """
        if not key:
            return True
        if key == cs.KEY_ENTER or key == 10: # Handle ENTER
            if self.opts.help_mode:
                self.opts.help_mode = False
                return True
            if self.pick_is_installed:
                key = ord('r') # remove installed app
            else:
                key = ord('i') # install uninstalled app

        if key in self.spin.keys:
            value = self.spin.do_key(key, self.win)
            return value

        if key == 27: # ESCAPE
            self.prev_filter = ''
            self.filter = None
            self.win.pick_pos = 0
            return None

        if key in (ord('q'), ord('x')):
            self.win.stop_curses()
            os.system('clear; stty sane')
            sys.exit(0)

        if key == ord('i') and not self.pick_is_installed:
            self.run_appman(f'appman install {self.pick_app}')
            return None

        if key == ord('r') and self.pick_is_installed:
            self.run_appman(f'appman remove {self.pick_app}')
            return None

        if key == ord('t') and self.pick_is_installed:
            self.launch_app(self.pick_app)
            return None

        if key == ord('s'):
            self.run_appman('appman sync')
        if key == ord('c'):
            self.run_appman('appman clean')
        if key == ord('b'):
            self.run_appman(f'appman backup {self.pick_app}')
        if key == ord('o'):
            self.run_appman(f'appman overwrite {self.pick_app}')
        if key == ord('a'):
            self.run_appman(f'appman about {self.pick_app}')
        if key == ord('u'):
            self.run_appman(f'appman update {self.pick_app}')
        if key == ord('U'):
            self.run_appman('appman update')
        # EXPAND

        if key == ord('/'):
            # pylint: disable=protected-access
            start_filter = self.prev_filter

            prefix = ''
            while True:
                pattern = self.win.answer(f'{prefix}Enter filter regex:', seed=self.prev_filter)
                self.prev_filter = pattern

                pattern.strip()
                if not pattern:
                    self.filter = None
                    break

                try:
                    if re.match(r'^[\-\w\s]*$', pattern):
                        words = pattern.split()
                        self.filter = re.compile(r'\b' + r'(|.*\b)'.join(words), re.IGNORECASE)
                        break
                    self.filter = re.compile(pattern, re.IGNORECASE)
                    break
                except Exception:
                    prefix = 'Bad regex: '

            if start_filter != self.prev_filter:
                # when filter changes, move to top
                self.win.pick_pos = 0

            return None
        return None


def main():
    """ The program """

    appman = Vappman()
    appman.main_loop()

if __name__ == '__main__':

    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as exce:
        Window.stop_curses()
        print("exception:", str(exce))
        print(traceback.format_exc())
#       if dump_str:
#           print(dump_str)
