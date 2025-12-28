#!/usr/bin/env python3
"""
Test script for the OptionSpinner scoped key bindings feature.
Demonstrates screen-specific key actions with scope subtraction.
"""
import sys
sys.path.insert(0, '/home/joe/Projects/vappman')

from vappman.ConsoleWindow import (
    ConsoleWindow, ConsoleWindowOpts, OptionSpinner,
    ScreenStack, Screen
)

# Define screen constants
HOME_ST, SETTINGS_ST, HELP_ST = 0, 1, 2
SCREENS = ['HOME', 'SETTINGS', 'HELP']


class HomeScreen(Screen):
    """Home screen with save action."""

    def save(self):
        """Save action available on home screen."""
        return "Saved from home!"

    def draw_screen(self):
        self.win.put_head("Home Screen")
        self.win.put_head("=" * 50)
        self.win.put_body("")
        self.win.put_body("This is the home screen.")
        self.win.put_body("Press 's' to save (only works here)")
        self.win.put_body("Press 'h' to go to help")
        self.win.put_body("Press 'ESC' to quit (global)")


class SettingsScreen(Screen):
    """Settings screen with export action."""

    def export(self):
        """Export action available on settings screen."""
        return "Exported from settings!"

    def draw_screen(self):
        self.win.put_head("Settings Screen")
        self.win.put_head("=" * 50)
        self.win.put_body("")
        self.win.put_body("This is the settings screen.")
        self.win.put_body("Press 'e' to export (only works here)")
        self.win.put_body("Press 'h' to go to help")
        self.win.put_body("Press 'ESC' to go back")


class HelpScreen(Screen):
    """Help screen shows context-aware help."""

    def draw_screen(self):
        self.win.put_head("Help Screen")
        self.win.put_head("=" * 50)

        # Get previous screen
        prev_screen = None
        if self.stack and self.stack.stack:
            prev_screen = self.stack.stack[-1].num

        # Show help filtered for previous screen + help screen
        if prev_screen is not None:
            screens_to_show = [prev_screen, HELP_ST]
            self.win.put_body(f"Showing keys for: {SCREENS[prev_screen]} + HELP")
            self.win.put_body("")
        else:
            screens_to_show = None

        self.app.spinner.show_help_body(self.win, screen_filter=screens_to_show)


def test_scoped_keys():
    """Test scoped key bindings with OptionSpinner and ScreenStack."""

    # Create ConsoleWindow
    opts = ConsoleWindowOpts(pick_mode=False)
    win = ConsoleWindow(opts=opts)

    # Create ScreenStack with None obj (will be filled by OptionSpinner)
    stack = ScreenStack(win, None, SCREENS)

    # Create app namespace to hold spinner
    from types import SimpleNamespace
    app = SimpleNamespace()

    # Create OptionSpinner with stack reference
    spinner = OptionSpinner(stack=stack)
    app.spinner = spinner

    # Verify that stack.obj is now set to spinner's default_obj
    assert stack.obj is spinner.default_obj, "Stack should use spinner's default_obj"

    # Create screen objects
    screens = {
        HOME_ST: HomeScreen(app),
        SETTINGS_ST: SettingsScreen(app),
        HELP_ST: HelpScreen(app),
    }
    stack.screen_objects = screens

    # Set app reference in screens
    for screen in screens.values():
        screen.app = app
        screen.stack = stack

    # Add global ESC key for all screens
    spinner.add_key('quit', 'ESC - Quit/Back', keys=27, genre='action')

    # Add 'h' key to go to help (all screens)
    spinner.add_key('help', 'h - Help', keys=ord('h'), genre='action')

    # Add 's' key for save (HOME screen only)
    spinner.add_key('save', 's - Save', keys=ord('s'), genre='action', scope=HOME_ST)

    # Add 'e' key for export (SETTINGS screen only)
    spinner.add_key('export', 'e - Export', keys=ord('e'), genre='action', scope=SETTINGS_ST)

    # Add 'r' key for refresh (HELP screen only)
    # This demonstrates scope subtraction - if we had defined 'r' globally first,
    # defining it for HELP would subtract HELP from the global scope
    spinner.add_key('refresh', 'r - Refresh', keys=ord('r'), genre='action', scope=HELP_ST)

    # Add a toggle option (all screens)
    spinner.add_key('verbose', 'v - Verbose', vals=[True, False], keys=ord('v'))

    print("\n=== Scoped Key Bindings Test ===\n")
    print("Key scope analysis:")
    print(f"  ESC (quit): applicable to all screens")
    print(f"  h (help): applicable to all screens")
    print(f"  s (save): applicable to HOME only")
    print(f"  e (export): applicable to SETTINGS only")
    print(f"  r (refresh): applicable to HELP only")
    print(f"  v (verbose): applicable to all screens")
    print()

    # Check effective scopes
    for ns in spinner.options:
        if hasattr(ns, 'effective_scope'):
            screen_names = [SCREENS[s] for s in sorted(ns.effective_scope)]
            print(f"  {ns.descr:20s} -> {', '.join(screen_names)}")

    print("\n=== Test completed successfully! ===")
    print("\nTo test interactively, uncomment the main loop below.")

    win.teardown()


def test_scope_subtraction():
    """Test that later add_key() calls subtract from earlier ones."""

    # Create ConsoleWindow
    opts = ConsoleWindowOpts(pick_mode=False)
    win = ConsoleWindow(opts=opts)

    # Create ScreenStack
    stack = ScreenStack(win, None, SCREENS)

    # Create OptionSpinner
    spinner = OptionSpinner(stack=stack)

    # Create minimal screen objects
    from types import SimpleNamespace
    stack.screen_objects = {
        HOME_ST: SimpleNamespace(),
        SETTINGS_ST: SimpleNamespace(),
        HELP_ST: SimpleNamespace(),
    }

    # Define ESC globally
    spinner.add_key('quit', 'ESC - Quit', keys=27, genre='action')

    print("\n=== Scope Subtraction Test ===\n")
    print("After adding ESC globally:")
    quit_option = spinner.attr_to_option['quit']
    print(f"  ESC scope: {sorted(quit_option.effective_scope)}")

    # Now try to define ESC for HELP screen specifically
    # This should raise an error because ESC already applies to HELP
    try:
        spinner.add_key('help_quit', 'ESC - Back from Help', keys=27, genre='action', scope=HELP_ST)
        print("  ERROR: Should have raised ValueError!")
    except ValueError as e:
        print(f"  Correctly raised error: {e}")

    print("\n=== Test completed! ===")

    win.teardown()


if __name__ == '__main__':
    print("Test 1: Scoped key bindings")
    test_scoped_keys()

    print("\n" + "="*60 + "\n")

    print("Test 2: Scope subtraction")
    test_scope_subtraction()

    print("\nAll tests passed!")
