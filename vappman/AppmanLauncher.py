#!/usr/bin/env python3
"""
- Smart Discovery: Instead of relying on the remove script (which might be missing
  or malformed), find_desktop_files proactively scans the standard Linux directories
  for -AM.desktop files.
- The "Duplicate" Problem: You mentioned seeing multiple files like firefox-stable-AM (1).desktop.
  My code sorts these by modification time and picks the newest one, which is usually
  the intended version.
- Terminal Logic: I've cleaned up the string replacement logic to avoid double-quoting
  issues that often crash terminal launches.
- Loose Coupling: The launcher takes AppmanVars as an argument (vars_inst).
  This means the launcher knows "where" things are without having to re-calculate the paths itself.
"""
import os
import subprocess
import shutil
import glob
from pathlib import Path
from typing import Optional, List

class AppmanLauncher:
    def __init__(self, vars_inst):
        self.vars = vars_inst  # Instance of AppmanVars
        self.terminal_emulator: Optional[List[str]] = None
        
        # Standard locations for .desktop files
        self.desktop_search_paths = [
            Path.home() / ".local/share/applications",
            Path.home() / ".local/share/plasma_icons",
            Path("/usr/local/share/applications"),
            Path("/usr/share/applications")
        ]

    def _find_terminal(self) -> Optional[List[str]]:
        """Locates a terminal emulator and returns its command template."""
        if self.terminal_emulator:
            return self.terminal_emulator

        maybes = [
            ['konsole', '--noclose', '-e', '{command}'],
            ['gnome-terminal', '--', 'bash', '-c', '{command}; exec bash'],
            ['xfce4-terminal', '--hold', '--command={command}'],
            ['lxterminal', '-e', "bash -c '{command}; echo; read -p \"Press Enter to close...\"'"],
            ['alacritty', '--hold', '-e', 'sh', '-c', '{command}'],
            ['kitty', '--hold', '/bin/sh', '-c', '{command}'],
            ['terminator', '-e', 'bash -c "{command}; bash"'],
            ['tilix', '-e', 'sh -c "{command}; exec $SHELL"'],
        ]

        for cmd_list in maybes:
            if shutil.which(cmd_list[0]):
                self.terminal_emulator = cmd_list
                return self.terminal_emulator
        return None

    def launch_desktop_file(self, desktop_file_path: str) -> bool:
        """Launch via xdg-open. Returns True on success."""
        try:
            subprocess.Popen(
                ['xdg-open', str(desktop_file_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True
            )
            return True
        except Exception:
            return False

    def launch_in_terminal(self, executable: str, show_command: bool = False) -> bool:
        """Finds a terminal and runs the executable inside it.

        Args:
            executable: Command to execute
            show_command: If True, echo the command before running it
        """
        term = self._find_terminal()
        if not term:
            return False

        try:
            # Build the actual command to run
            if show_command:
                # Most terminal templates already wrap in bash/sh -c, so just use shell operators
                # For terminals that don't (like konsole -e), we need explicit bash invocation
                # Check if this terminal already has shell wrapping
                term_cmd_str = ' '.join(term)

                if 'bash -c' in term_cmd_str or 'sh -c' in term_cmd_str:
                    # Terminal already wraps in shell, just use shell operators
                    # Escape for shell safety - use simpler approach without complex quoting
                    safe_exec = executable.replace("'", "'\\''")
                    # Use simple concatenation to avoid variable expansion issues
                    command = f"echo '+ {safe_exec}'; echo; {executable}; echo; echo '════════════════════════════════════════'; echo 'Exit code: '$?; echo 'vappman test complete - close terminal when ready'; echo '════════════════════════════════════════'; read -p ''"
                else:
                    # Terminal doesn't wrap in shell (like konsole), so we need to
                    safe_exec = executable.replace('"', '\\"')
                    command = f'bash -c "echo + {safe_exec}; echo; {executable}; echo; echo ════════════════════════════════════════; echo Exit code: $?; echo vappman test complete - close terminal when ready; echo ════════════════════════════════════════; read -p \'\'"'
            else:
                command = executable

            # Construct the command by replacing the placeholder
            cmd = [part.replace('{command}', str(command)) for part in term]
            # Don't use start_new_session here - it breaks polkit authentication
            # The terminal window provides sufficient isolation
            # Preserve environment for polkit to work in Wayland/Sway
            env = os.environ.copy()
            subprocess.Popen(cmd, env=env)
            return True
        except Exception:
            return False

    def _get_smart_test_command(self, app_name: str, executable: str) -> str:
        """Generate a smart test command based on app type.

        For CLI tools that need input (like cat, grep), provide sensible test args.
        For others, just run them (GUI apps will launch, CLI will show help or run).
        """
        # Common CLI utilities that hang without input
        cli_tools_with_args = {
            'cat': '--help',
            'grep': '--help',
            'sed': '--help',
            'awk': '--version',
            'find': '--help',
            'wc': '--help',
            'sort': '--help',
            'head': '--help',
            'tail': '--help',
            'cut': '--help',
            'tr': '--help',
            'uniq': '--help',
        }

        if app_name in cli_tools_with_args:
            return f"{executable} {cli_tools_with_args[app_name]}"

        # For everything else, just run it
        # GUI apps will launch, CLI apps will show their help or run normally
        return executable

    def launch_test_in_terminal(self, app_name: str, executable: str) -> bool:
        """Launch app test in terminal with smart command and visible echo.

        Args:
            app_name: Name of the app (for smart test logic)
            executable: Full path or command to execute

        Returns:
            True if launched successfully, False otherwise
        """
        test_cmd = self._get_smart_test_command(app_name, executable)
        return self.launch_in_terminal(test_cmd, show_command=True)

    def find_desktop_files(self, app_name: str) -> List[Path]:
        """Search system for -AM.desktop files related to the app."""
        found = []
        # Pattern matches: appname-AM.desktop or appname-stable-AM.desktop etc.
        pattern = f"{app_name}*-AM*.desktop"
        
        for base_path in self.desktop_search_paths:
            if base_path.exists():
                # Search recursively for the pattern
                matches = list(base_path.glob(pattern))
                found.extend(matches)
        
        # Sort by modification time so we can prioritize the newest if needed
        found.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return found

    def launch_app(self, app_name: str):
        """Main entry point: Try .desktop first, then binary."""
        
        # 1. Try to find and launch a .desktop file
        desktop_files = self.find_desktop_files(app_name)
        if desktop_files:
            # We take the first one (newest based on our sort)
            if self.launch_desktop_file(str(desktop_files[0])):
                return

        # 2. Fallback: Try to find binary in the appman install dir
        loc = self.vars.where_is(app_name)
        if loc:
            # Look for executables in the app folder
            # Usually appman puts binaries in a 'bin' subfolder or the root
            possible_bins = list(loc.path.glob(f"**/{app_name}"))
            for bin_path in possible_bins:
                if os.access(bin_path, os.X_OK):
                    if self.launch_in_terminal(str(bin_path)):
                        return

        print(f"Error: Could not find a way to launch {app_name}")
