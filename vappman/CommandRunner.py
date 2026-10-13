#!/usr/bin/env python3
"""Background command execution helper.

Runs a subprocess whose combined stdout/stderr is streamed to a temporary
file. When the process finishes, the temp file is atomically moved into
its final destination so readers never observe a partially written file.
"""
import os
import subprocess

class CommandRunner:
    """Run a command in the background, finalizing output atomically."""

    def __init__(self, arg_vector, final_destination):
        self.arg_vector = arg_vector
        self.final_destination = final_destination
        self.temp_file = final_destination + ".tmp"
        self.process = None
        self._file_handle = None

    def start(self):
        """Spawn the process, redirecting stdout/stderr to the temp file."""
        self._file_handle = open(self.temp_file, 'w', encoding='utf-8')
        self.process = subprocess.Popen(
            self.arg_vector,
            stdout=self._file_handle,
            stderr=subprocess.STDOUT,
            text=True
        )

    def is_running(self):
        """Return True while the process runs; finalize output on exit."""
        if self.process is None:
            return False
        status = self.process.poll()
        if status is not None:
            self._finalize_file()
            return False
        return True

    def _finalize_file(self):
        """Close the handle and atomically promote the temp file."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
        if os.path.exists(self.temp_file):
            os.replace(self.temp_file, self.final_destination)

    def get_return_code(self):
        """Return the exit code, or None if still running."""
        return self.process.poll() if self.process else None
