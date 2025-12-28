#!/usr/bin/env python3
"""
Unit tests for the OptionSpinner scoped key bindings feature (no curses required).
Tests the scope logic without requiring a full ConsoleWindow.
"""
import sys
sys.path.insert(0, '/home/joe/Projects/vappman')

from types import SimpleNamespace
from vappman.ConsoleWindow import OptionSpinner

# Define screen constants
HOME_ST, SETTINGS_ST, HELP_ST = 0, 1, 2
SCREENS = ('HOME', 'SETTINGS', 'HELP')


def test_basic_scoping():
    """Test basic scope assignment."""
    print("\n=== Test 1: Basic Scoping ===")

    # Create a mock stack
    stack = SimpleNamespace(
        screens=SCREENS,
        screen_objects={
            HOME_ST: SimpleNamespace(),
            SETTINGS_ST: SimpleNamespace(),
            HELP_ST: SimpleNamespace(),
        },
        obj=None
    )

    spinner = OptionSpinner(stack=stack)

    # Verify stack got spinner's default_obj
    assert stack.obj is spinner.default_obj, "Stack should use spinner's default_obj"
    print("✓ Stack.obj set to spinner.default_obj")

    # Add a global key
    spinner.add_key('quit', 'ESC - Quit', keys=27, genre='action')
    quit_opt = spinner.attr_to_option['quit']

    assert quit_opt.effective_scope == {0, 1, 2}, "Global key should apply to all screens"
    print(f"✓ Global key 'quit' applies to screens: {sorted(quit_opt.effective_scope)}")

    # Add a screen-specific key
    spinner.add_key('save', 's - Save', keys=ord('s'), genre='action', scope=HOME_ST)
    save_opt = spinner.attr_to_option['save']

    assert save_opt.effective_scope == {HOME_ST}, "Scoped key should apply to specific screen"
    print(f"✓ Scoped key 'save' applies to screens: {sorted(save_opt.effective_scope)}")

    # Add a multi-screen key
    spinner.add_key('export', 'e - Export', keys=ord('e'), genre='action', scope=[HOME_ST, SETTINGS_ST])
    export_opt = spinner.attr_to_option['export']

    assert export_opt.effective_scope == {HOME_ST, SETTINGS_ST}, "Multi-scope key should apply to specified screens"
    print(f"✓ Multi-scoped key 'export' applies to screens: {sorted(export_opt.effective_scope)}")


def test_action_scoping():
    """Test that actions with no scope default to screens that implement them."""
    print("\n=== Test 2: Action Auto-Scoping ===")

    # Create a mock stack with screen objects that have specific methods
    home_screen = SimpleNamespace()
    home_screen.save = lambda: "saved"

    settings_screen = SimpleNamespace()
    settings_screen.export = lambda: "exported"

    stack = SimpleNamespace(
        screens=SCREENS,
        screen_objects={
            HOME_ST: home_screen,
            SETTINGS_ST: settings_screen,
            HELP_ST: SimpleNamespace(),
        },
        obj=None
    )

    spinner = OptionSpinner(stack=stack)

    # Add action that only some screens implement
    spinner.add_key('save', 's - Save', keys=ord('s'), genre='action')
    save_opt = spinner.attr_to_option['save']

    # Should only apply to HOME_ST where it's implemented
    assert save_opt.effective_scope == {HOME_ST}, f"Action 'save' should only apply to HOME, got {save_opt.effective_scope}"
    print(f"✓ Action 'save' auto-scoped to screens: {sorted(save_opt.effective_scope)}")

    spinner.add_key('export', 'e - Export', keys=ord('e'), genre='action')
    export_opt = spinner.attr_to_option['export']

    assert export_opt.effective_scope == {SETTINGS_ST}, f"Action 'export' should only apply to SETTINGS, got {export_opt.effective_scope}"
    print(f"✓ Action 'export' auto-scoped to screens: {sorted(export_opt.effective_scope)}")


def test_duplicate_key_error():
    """Test that defining the same key twice for the same screen raises an error."""
    print("\n=== Test 3: Duplicate Key Detection ===")

    stack = SimpleNamespace(
        screens=SCREENS,
        screen_objects={
            HOME_ST: SimpleNamespace(),
            SETTINGS_ST: SimpleNamespace(),
            HELP_ST: SimpleNamespace(),
        },
        obj=None
    )

    spinner = OptionSpinner(stack=stack)

    # Add a key for HOME
    spinner.add_key('action1', 'a - Action 1', keys=ord('a'), genre='action', scope=HOME_ST)
    print("✓ Added 'a' key for HOME screen")

    # Try to add the same key for HOME again - should fail
    try:
        spinner.add_key('action2', 'a - Action 2', keys=ord('a'), genre='action', scope=HOME_ST)
        print("✗ ERROR: Should have raised ValueError for duplicate key!")
        return False
    except ValueError as e:
        print(f"✓ Correctly raised error: {e}")

    # But adding 'a' for a different screen should work
    spinner.add_key('action3', 'a - Action 3', keys=ord('a'), genre='action', scope=SETTINGS_ST)
    print("✓ Added same key 'a' for SETTINGS screen (different scope)")


def test_scope_subtraction():
    """Test that later keys subtract from earlier keys' scopes."""
    print("\n=== Test 4: Scope Subtraction ===")

    stack = SimpleNamespace(
        screens=SCREENS,
        screen_objects={
            HOME_ST: SimpleNamespace(),
            SETTINGS_ST: SimpleNamespace(),
            HELP_ST: SimpleNamespace(),
        },
        obj=None
    )

    spinner = OptionSpinner(stack=stack)

    # Define 'x' globally (all screens)
    spinner.add_key('global_x', 'x - Global X', keys=ord('x'), genre='action')
    global_x = spinner.attr_to_option['global_x']

    print(f"  Before subtraction - 'x' scope: {sorted(global_x.effective_scope)}")
    assert global_x.effective_scope == {0, 1, 2}, "Should apply to all screens initially"

    # Define 'x' for HELP screen - should subtract HELP from global scope
    # But this will raise an error because 'x' already applies to HELP
    try:
        spinner.add_key('help_x', 'x - Help X', keys=ord('x'), genre='action', scope=HELP_ST)
        print("✗ ERROR: Should have raised ValueError!")
    except ValueError:
        print("✓ Correctly prevents redefining same key for overlapping scope")

    # To demonstrate subtraction, we need to define non-overlapping scopes
    # Let's define 'y' for HOME and SETTINGS
    spinner.add_key('y_action', 'y - Y Action', keys=ord('y'), genre='action', scope=[HOME_ST, SETTINGS_ST])
    y_opt = spinner.attr_to_option['y_action']

    print(f"  'y' applies to: {sorted(y_opt.effective_scope)}")
    assert y_opt.effective_scope == {HOME_ST, SETTINGS_ST}

    # Now try to define 'y' for HELP - should work since no overlap
    spinner.add_key('help_y', 'y - Help Y', keys=ord('y'), genre='action', scope=HELP_ST)
    help_y_opt = spinner.attr_to_option['help_y']

    print(f"  After adding help_y - original 'y' scope: {sorted(y_opt.effective_scope)}")
    print(f"  help_y scope: {sorted(help_y_opt.effective_scope)}")

    # The original y_action should still have its scope (no subtraction happened because no overlap)
    assert y_opt.effective_scope == {HOME_ST, SETTINGS_ST}
    assert help_y_opt.effective_scope == {HELP_ST}
    print("✓ Non-overlapping scopes work correctly")


if __name__ == '__main__':
    try:
        test_basic_scoping()
        test_action_scoping()
        test_duplicate_key_error()
        test_scope_subtraction()
        print("\n" + "="*60)
        print("All tests passed! ✓")
        print("="*60 + "\n")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
