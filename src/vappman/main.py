#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive, visual thin layer atop appman
"""
# pylint: disable=broad-exception-caught,consider-using-with
# pylint: disable=too-many-instance-attributes,too-many-branches
# pylint: disable=too-many-return-statements,too-many-statements

# pylint: disable=wrong-import-position,disable=wrong-import-order
# import VirtEnv
# VirtEnv.ensure_venv(__name__)

import os
import sys
import re
import shutil
import subprocess
import traceback
import copy
import shutil
import curses as cs
from types import SimpleNamespace
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
        other = 'airbou/qscU'
        other_keys = set(ord(x) for x in other)
        other_keys.add(cs.KEY_ENTER)
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
                    '   q - quit program (CTL-C disabled)',
                    '   a - about (more info about app)',
                    '   s - sync (update appman itself)',
                    '   c - clean (remove unneeded files/folters)',
                    '   U - update ALL installed apps',
                    '   / - filter apps',
                    '   ENTER = install, remove, or return from help',
                    'CONTEXT SENSITIVE:',
                    '   i - install uninstalled app',
                    '   r - remove installed app',
                    '   b - backup installed app',
                    '   u - update installed app',
                    '   o - overwrite app from its backup',

                ]
                for line in lines:
                    self.win.put_body(line)
            else:
                def wanted(line):
                    return not self.filter or self.filter.search(line)

                # self.win.set_pick_mode(self.opts.pick_mode, self.opts.pick_size)
                self.win.set_pick_mode(True)
                self.win.add_header(self.get_keys_line(), attr=cs.A_BOLD)
                for app, line in self.installs.items():
                    if app in self.apps:
                        line = self.apps[app]
                    if wanted(line):
                        line = '✔✔✔' + line[1:]
                        self.win.add_body(line)
                for app, line in self.apps.items():
                    if app not in self.installs and wanted(line):
                        self.win.add_body(line)
            self.win.render()

            _ = self.do_key(self.win.prompt(seconds=300))
            self.win.clear()

    def get_keys_line(self):
        """ TBD """
        # EXPAND
        filt = self.prev_filter if self.prev_filter else '{No-Filt}'
        line = 'KEYS:'
        for key, verb in self.actions.items():
            line += f' {key}:{verb}'
        # or EXPAND
        line += f' ?:help q:quit a:about s:sync c:clean U:upd /{filt}  '
        # for action in self.actions:
            # line += f' {action[0]}:{action}'
        return line

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
        keys_line = this.get_keys_line().ljust(this.win.get_pad_width())
        this.win.head.pad.addstr(0, 0, keys_line, cs.A_BOLD)

        return line
#       #IF WE WANT TO DO SOMETHING ON THE LINE...
#       suffix = ''
#       for action in actions:
#           suffix += f' {action[0]}:{action}'
#       block_char = "\u2588"
#       suffix = f'{block_char*5} {suffix}'
#       over = len(line) + len(suffix) - this.win.get_pad_width()
#       if over < 0:
#           line += ' '*(-over)
#       elif over > 0:
#           line = line[0:-over]

#       return line + suffix
    def run_appman(self, cmd):
        Window.stop_curses()
        os.system(f'clear; stty sane; {cmd};'
                  + ' /bin/echo -e "\n\n===== Press ENTER for menu ====> \c"; read FOO')
        self.installs = self.get_installed()
        Window._start_curses()

    def do_key(self, key):
        """ TBD """
        if not key:
            return True
        if key == cs.KEY_ENTER or key == 10: # Handle ENTER
            if self.opts.help_mode:
                self.opts.help_mode = False
                return True
            elif self.pick_is_installed:
                key = ord('r') # removed installed app
            else:
                key = ord('i') # install uninstalled app

        if key in self.spin.keys:
            value = self.spin.do_key(key, self.win)
            return value
        
        if key == ord('q'):
            self.win.stop_curses()
            os.system('clear; stty sane')
            sys.exit(0)

        if key == ord('i') and not self.pick_is_installed:
            self.run_appman(f'appman install {self.pick_app}')
            return None

        if key == ord('r') and self.pick_is_installed:
            self.run_appman(f'appman remove {self.pick_app}')
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
            self.run_appman(f'appman update')
        # EXPAND

        if key == ord('/'):
            # pylint: disable=protected-access

            prefix = ''
            while True:
                pattern = self.win.answer(f'{prefix}Enter filter regex:', seed=self.prev_filter)
                self.prev_filter = pattern

                pattern.strip()
                if not pattern:
                    self.filter = None
                    return None

                try:
                    if re.match(r'^[\-\w\s]*$', pattern):
                        words = pattern.split()
                        self.filter = re.compile(r'\b' + r'\b.*'.join(words), re.IGNORECASE)
                        return None
                    self.filter = re.compile(pattern, re.IGNORECASE)
                    return None
                except Exception:
                    prefix = 'Bad regex: '

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
