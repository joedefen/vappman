#!/usr/bin/env python3
"""
Example demonstrating how to break the circular dependency during initialization.

Initialization order:
1. Create ConsoleWindow (without keys)
2. Create ScreenStack (with win, but obj=None)
3. Create OptionSpinner (with stack reference)
4. Create Screen objects (with app that has spinner)
5. Set handled_keys on ConsoleWindow
"""
import sys
sys.path.insert(0, '/home/joe/Projects/vappman')

from types import SimpleNamespace
from vappman.ConsoleWindow import (
    ConsoleWindow, ConsoleWindowOpts, OptionSpinner,
    ScreenStack, Screen
)

# Define screen constants
HOME_ST, SETTINGS_ST, HELP_ST = 0, 1, 2
SCREENS = ('HOME', 'SETTINGS', 'HELP')


class HomeScreen(Screen):
    def draw_screen(self):
        self.win.put_head("Home Screen")
        self.win.put_body("Welcome!")


class SettingsScreen(Screen):
    def draw_screen(self):
        self.win.put_head("Settings")
        self.win.put_body("Configure...")


class HelpScreen(Screen):
    def draw_screen(self):
        self.win.put_head("Help")
        if self.stack and self.stack.stack:
            prev_screen = self.stack.stack[-1].num
            screen_filter = [prev_screen, HELP_ST]
        else:
            screen_filter = None
        self.app.spinner.show_help_body(self.win, screen_filter=screen_filter)


def main():
    """Demonstrate proper initialization order."""

    print("\n=== Initialization Order Demo ===\n")

    # Step 1: Create ConsoleWindow WITHOUT keys (no spinner yet)
    print("1. Creating ConsoleWindow (keys=None)...")
    opts = ConsoleWindowOpts(pick_mode=False)
    win = ConsoleWindow(opts=opts)
    print("   ✓ ConsoleWindow created")
    print(f"   handled_keys = {win.handled_keys}")

    # Step 2: Create ScreenStack with None obj (will be filled by spinner)
    print("\n2. Creating ScreenStack (obj=None)...")
    stack = ScreenStack(win, None, SCREENS)
    print("   ✓ ScreenStack created")
    print(f"   stack.obj = {stack.obj}")

    # Step 3: Create OptionSpinner with stack reference
    print("\n3. Creating OptionSpinner (stack=stack)...")
    spinner = OptionSpinner(stack=stack)
    print("   ✓ OptionSpinner created")
    print(f"   stack.obj = {stack.obj} (now set!)")

    # Step 4: Create app namespace
    print("\n4. Creating app namespace...")
    app = SimpleNamespace()
    app.spinner = spinner
    app.win = win
    app.stack = stack
    print("   ✓ App namespace created")

    # Step 5: Create Screen objects
    print("\n5. Creating Screen objects...")
    screens = {
        HOME_ST: HomeScreen(app),
        SETTINGS_ST: SettingsScreen(app),
        HELP_ST: HelpScreen(app),
    }
    stack.screen_objects = screens
    for screen in screens.values():
        screen.app = app
        screen.stack = stack
    print("   ✓ Screen objects created")

    # Step 6: Register keys with OptionSpinner
    print("\n6. Registering keys with OptionSpinner...")
    spinner.add_key('quit', 'ESC - Quit', keys=27, genre='action')
    spinner.add_key('help', 'h - Help', keys=ord('h'), genre='action')
    spinner.add_key('save', 's - Save', keys=ord('s'), genre='action', scope=HOME_ST)
    print("   ✓ Keys registered")
    print(f"   spinner.keys = {spinner.keys}")

    # Step 7: NOW set handled_keys on ConsoleWindow
    print("\n7. Setting handled_keys on ConsoleWindow...")
    win.set_handled_keys(spinner)
    print("   ✓ handled_keys set")
    print(f"   win.handled_keys = {win.handled_keys}")

    print("\n=== Initialization Complete! ===\n")
    print("No circular dependency!")
    print("\nThe order was:")
    print("  ConsoleWindow → ScreenStack → OptionSpinner → Screens → set_handled_keys()")

    win.teardown()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
