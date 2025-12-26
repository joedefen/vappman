#!/usr/bin/env python3
import subprocess
import time

class CommandRunner:
    def __init__(self, arg_vector, output_file):
        self.arg_vector = arg_vector
        self.output_file = output_file
        self.process = None
        self._file_handle = None

    def start(self):
        """Spawns the process and redirects stdout/stderr to the file."""
        self._file_handle = open(self.output_file, 'w')
        self.process = subprocess.Popen(
            self.arg_vector,
            stdout=self._file_handle,
            stderr=subprocess.STDOUT,  # Combine errors into the same file
            text=True
        )
        print(f"Process started with PID: {self.process.pid}")

    def is_running(self):
        """Polls the process to see if it is still active."""
        if self.process is None:
            return False
        
        # poll() returns None if running, or the return code if finished
        return self.process.poll() is None

    def get_return_code(self):
        """Returns the exit code, or None if still running."""
        return self.process.poll()

    def __del__(self):
        """Ensures the file handle is closed when the object is destroyed."""
        if self._file_handle:
            self._file_handle.close()

