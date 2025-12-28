#!/usr/bin/env python3
"""
Test that demonstrates scope subtraction working correctly.
"""
import sys
sys.path.insert(0, '/home/joe/Projects/vappman')

from types import SimpleNamespace
from vappman.ConsoleWindow import OptionSpinner

# Define screen constants
HOME_ST, SETTINGS_ST, HELP_ST = 0, 1, 2
SCREENS = ('HOME', 'SETTINGS', 'HELP')


def test_scope_subtraction_works():
    """Test that later add_key() calls properly subtract from earlier ones."""
    print("\n=== Demonstrating Scope Subtraction ===\n")

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

    # Step 1: Define ESC globally (all screens)
    print("Step 1: Define ESC for all screens")
    spinner.add_key('quit_global', 'ESC - Quit/Back', keys=27, genre='action')
    quit_global = spinner.attr_to_option['quit_global']
    print(f"  quit_global scope: {sorted(quit_global.effective_scope)} = {[SCREENS[s] for s in sorted(quit_global.effective_scope)]}")
    assert quit_global.effective_scope == {0, 1, 2}, "Should apply to all screens"

    # Step 2: Define ESC specifically for HELP screen
    # This should SUBTRACT HELP from the global scope
    print("\nStep 2: Define ESC specifically for HELP screen")
    print("  (This should subtract HELP from global scope)")
    spinner.add_key('quit_help', 'ESC - Back from Help', keys=27, genre='action', scope=HELP_ST)
    quit_help = spinner.attr_to_option['quit_help']

    print(f"  quit_global scope after: {sorted(quit_global.effective_scope)} = {[SCREENS[s] for s in sorted(quit_global.effective_scope)]}")
    print(f"  quit_help scope: {sorted(quit_help.effective_scope)} = {[SCREENS[s] for s in sorted(quit_help.effective_scope)]}")

    # Verify subtraction worked
    assert quit_global.effective_scope == {HOME_ST, SETTINGS_ST}, f"Global should exclude HELP, got {quit_global.effective_scope}"
    assert quit_help.effective_scope == {HELP_ST}, f"Help-specific should only include HELP, got {quit_help.effective_scope}"
    print("\n✓ Scope subtraction worked!")

    # Step 3: Verify key_scopes mapping is correct
    print("\nStep 3: Verify key_scopes mapping")
    esc_key = 27
    for screen_num in range(3):
        option_ns = spinner.key_scopes.get((esc_key, screen_num))
        if option_ns:
            print(f"  Screen {screen_num} ({SCREENS[screen_num]}): ESC -> {option_ns.attr}")

    assert spinner.key_scopes[(esc_key, HOME_ST)] == quit_global
    assert spinner.key_scopes[(esc_key, SETTINGS_ST)] == quit_global
    assert spinner.key_scopes[(esc_key, HELP_ST)] == quit_help
    print("✓ Key mappings are correct!")

    # Step 4: Define 'h' for HOME and SETTINGS
    print("\nStep 4: Define 'h' for HOME and SETTINGS")
    spinner.add_key('help_action', 'h - Help', keys=ord('h'), genre='action', scope=[HOME_ST, SETTINGS_ST])
    help_action = spinner.attr_to_option['help_action']
    print(f"  help_action scope: {sorted(help_action.effective_scope)} = {[SCREENS[s] for s in sorted(help_action.effective_scope)]}")

    # Step 5: Override 'h' for just HOME screen
    print("\nStep 5: Override 'h' for just HOME screen")
    spinner.add_key('home_help', 'h - Home Help', keys=ord('h'), genre='action', scope=HOME_ST)
    home_help = spinner.attr_to_option['home_help']

    print(f"  help_action scope after: {sorted(help_action.effective_scope)} = {[SCREENS[s] for s in sorted(help_action.effective_scope)]}")
    print(f"  home_help scope: {sorted(home_help.effective_scope)} = {[SCREENS[s] for s in sorted(home_help.effective_scope)]}")

    assert help_action.effective_scope == {SETTINGS_ST}, f"Should only have SETTINGS, got {help_action.effective_scope}"
    assert home_help.effective_scope == {HOME_ST}, f"Should only have HOME, got {home_help.effective_scope}"
    print("✓ Partial scope subtraction worked!")

    print("\n" + "="*60)
    print("Scope subtraction feature working correctly! ✓")
    print("="*60 + "\n")


if __name__ == '__main__':
    try:
        test_scope_subtraction_works()
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
