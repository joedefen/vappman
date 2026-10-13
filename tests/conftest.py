"""Pytest configuration for the vappman test suite.

A couple of scripts under ``tests/`` are interactive curses demos rather than
automated tests (they construct a real ``ConsoleWindow`` and/or block on
keyboard input). They are excluded from collection so the automated suite
stays headless and CI-safe. Run them manually when you want to poke at the
TUI by hand.
"""

collect_ignore = [
    "test_abut.py",
    "test_scoped_keys.py",
]
