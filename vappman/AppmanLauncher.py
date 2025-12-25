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
                close_fds=True
            )
            return True
        except Exception:
            return False

    def launch_in_terminal(self, executable: str) -> bool:
        """Finds a terminal and runs the executable inside it."""
        term = self._find_terminal()
        if not term:
            return False

        try:
            # Construct the command by replacing the placeholder
            cmd = [part.replace('{command}', str(executable)) for part in term]
            subprocess.Popen(cmd)
            return True
        except Exception:
            return False

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
