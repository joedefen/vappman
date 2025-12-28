#!/usr/bin/env python3
"""
Test that the initialization order works without circular dependency.
No curses required - just tests the object creation order.
"""
import sys
sys.path.insert(0, '/home/joe/Projects/vappman')

from types import SimpleNamespace


def test_init_order():
    """Test initialization order without circular dependency."""

    print("\n=== Testing Initialization Order (No Curses) ===\n")

    # Mock ConsoleWindow (just the parts we need)
    class MockConsoleWindow:
        def __init__(self):
            self.handled_keys = set()
            print("  ✓ MockConsoleWindow created")

        def set_handled_keys(self, keys):
            if hasattr(keys, 'keys'):
                self.handled_keys = set(keys.keys) if keys.keys else set()
            elif isinstance(keys, (set, list)):
                self.handled_keys = set(keys)
            else:
                self.handled_keys = set()
            print(f"  ✓ set_handled_keys() called: {len(self.handled_keys)} keys")

    # Import real classes
    from vappman.ConsoleWindow import OptionSpinner

    SCREENS = ('HOME', 'SETTINGS', 'HELP')
    HOME_ST, SETTINGS_ST, HELP_ST = 0, 1, 2

    # Mock ScreenStack
    class MockScreenStack:
        def __init__(self, win, obj, screens):
            self.win = win
            self.obj = obj
            self.screens = screens
            self.screen_objects = {}
            print("  ✓ MockScreenStack created")

    # Step 1: Create ConsoleWindow (no keys)
    print("Step 1: Create ConsoleWindow (no keys)")
    win = MockConsoleWindow()
    assert win.handled_keys == set()

    # Step 2: Create ScreenStack (obj=None)
    print("\nStep 2: Create ScreenStack (obj=None)")
    stack = MockScreenStack(win, None, SCREENS)
    assert stack.obj is None

    # Step 3: Create OptionSpinner (fills stack.obj)
    print("\nStep 3: Create OptionSpinner (fills stack.obj)")
    spinner = OptionSpinner(stack=stack)
    assert stack.obj is spinner.default_obj
    print(f"  ✓ stack.obj now set to spinner.default_obj")

    # Step 4: Add keys to spinner
    print("\nStep 4: Add keys to spinner")
    spinner.add_key('quit', 'ESC - Quit', keys=27, genre='action')
    spinner.add_key('help', 'h - Help', keys=ord('h'), genre='action')
    spinner.add_key('save', 's - Save', keys=ord('s'), genre='action', scope=HOME_ST)
    print(f"  ✓ Added 3 keys: {sorted(spinner.keys)}")
    assert 27 in spinner.keys
    assert ord('h') in spinner.keys
    assert ord('s') in spinner.keys

    # Step 5: Set handled_keys on ConsoleWindow
    print("\nStep 5: Set handled_keys on ConsoleWindow")
    win.set_handled_keys(spinner)
    assert win.handled_keys == spinner.keys
    print(f"  ✓ ConsoleWindow.handled_keys = {sorted(win.handled_keys)}")

    print("\n" + "="*60)
    print("SUCCESS! No circular dependency.")
    print("="*60)
    print("\nInitialization order:")
    print("  1. ConsoleWindow (keys=None)")
    print("  2. ScreenStack (obj=None)")
    print("  3. OptionSpinner (fills stack.obj)")
    print("  4. Add keys to spinner")
    print("  5. win.set_handled_keys(spinner)")
    print("\nNo objects need each other during __init__!")


if __name__ == '__main__':
    try:
        test_init_order()
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
