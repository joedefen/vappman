#!/usr/bin/env python3
import os
import shutil
from pathlib import Path
from typing import NamedTuple, Optional, List

class AppLocation(NamedTuple):
    """ Helper to describing where an app is """
    sys_path: Path  # Path to system storage dir or None
    usr_path: Path  # Path to user storage dir or None

class AppmanVars:
    """ Encapsulates the places / functions we need to know
    about to observe, manage am/appman. """
    def __init__(self):
        self.system_app_dir = Path("/opt")
        xdg_config = os.getenv('XDG_CONFIG_HOME')
        self._config_base = Path(xdg_config) if xdg_config else Path.home() / ".config"
        self._mode_file = self._config_base / "appman" / "appman-mode"
        self.snapshot_base = Path.home() / ".am-snapshots"
        self.user_app_dir = self._find_user_app_dir()

    def is_user_mode(self) -> bool:
        """Returns True if appman-mode file exists."""
        return self._mode_file.exists()

    def is_system_mode(self) -> bool:
        """Returns True if appman-mode file exists."""
        return not self.is_user_mode()

    def set_system_mode_cheat(self, enable: bool):
        """Sets the mode by creating or removing the appman-mode file."""
        try:
            if enable:
                if self._mode_file.exists():
                    self._mode_file.unlink()
            else:
                self._mode_file.parent.mkdir(parents=True, exist_ok=True)
                self._mode_file.touch()
        except OSError as e:
            print(f"Error changing appman mode: {e}")

    def get_snapshots(self, app: str, prune: int = -1) -> List[Path]:
        """
        Returns snapshot paths for an app, newest first.
        If prune > 0, deletes snapshots older than the 'prune' count.
        """
        app_snapshot_dir = self.snapshot_base / app
        
        if not app_snapshot_dir.exists():
            return []

        # Get all subdirectories, sorted by modification time (newest first)
        # .stat().st_mtime is the standard way to get the last modified timestamp
        snapshots = sorted(
            [d for d in app_snapshot_dir.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        if prune > 0 and len(snapshots) > prune:
            to_keep = snapshots[:prune]
            to_discard = snapshots[prune:]
            
            for old_snapshot in to_discard:
                try:
                    shutil.rmtree(old_snapshot)
                except OSError as e:
                    print(f"Warning: Could not prune {old_snapshot}: {e}")
            
            return to_keep

        return snapshots

    def _find_user_app_dir(self) -> Optional[Path]:
        """Locates the user's appman directory via config file."""
        try:
            config_file = self._config_base / "appman" / "appman-config"
            if not config_file.exists(): return None
            raw_path = config_file.read_text(encoding='utf-8').strip()
            path_obj = Path(raw_path)
            if not path_obj.is_absolute():
                path_obj = Path.home() / raw_path
            return path_obj if path_obj.is_dir() else None
        except Exception:
            return None

    def where_is(self, app_name: str) -> Optional[AppLocation]:
        """Checks both user and system directories for a specific app folder."""
        usr_path, sys_path = None, None
        if self.user_app_dir:
            tmp = self.user_app_dir / app_name
            if tmp.exists():
                usr_path = tmp

        tmp = self.system_app_dir / app_name
        if tmp.exists():
            sys_path = tmp

        return AppLocation(usr_path=usr_path, sys_path=sys_path)
