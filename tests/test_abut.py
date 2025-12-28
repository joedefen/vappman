#!/usr/bin/env python3
"""
Test script for the ConsoleWindow abut feature.
Demonstrates different abut configurations in pick_mode.
"""
import sys
sys.path.insert(0, '/home/joe/Projects/vappman')

from vappman.ConsoleWindow import ConsoleWindow, ConsoleWindowOpts, Context


def test_abut_feature():
    """Test the abut feature with various configurations."""

    opts = ConsoleWindowOpts(
        pick_mode=True,
        pick_size=1,
    )

    win = ConsoleWindow(opts=opts)

    win.put_head("ConsoleWindow abut Feature Test")
    win.put_head("=" * 50)
    win.put_head("Navigate with j/k or arrow keys. Press 'q' to quit.")
    win.put_head("")
    win.put_head("Line 100 has abut=[-20, 30] (can see 20 before, 30 after)")

    # Add 200 lines to the body
    for i in range(200):
        if i == 100:
            # Line 100 has abut=[-20, 30]
            ctx = Context(
                genre='special',
                pickable=True,
                abut=[-20, 30]
            )
            win.put_body(f">>> Line {i:3d} - WITH ABUT [-20, 30] <<<", context=ctx)
        else:
            ctx = Context(genre='normal', pickable=True)
            win.put_body(f"    Line {i:3d}", context=ctx)

    # Position at line 100
    win.pick_pos = 100

    # Main loop
    win.calc()
    while True:
        win.render_once()
        key = win.prompt()

        if key == ord('q') or key == ord('Q'):
            break
        elif key == ord('j') or key == 259:  # DOWN arrow
            win.fix_positions(delta=1)
        elif key == ord('k') or key == 258:  # UP arrow
            win.fix_positions(delta=-1)
        elif key == ord('d'):
            win.fix_positions(delta=10)
        elif key == ord('u'):
            win.fix_positions(delta=-10)

    win.teardown()


def test_abut_variations():
    """Test different abut value formats."""

    opts = ConsoleWindowOpts(
        pick_mode=True,
        pick_size=1,
    )

    win = ConsoleWindow(opts=opts)

    win.put_head("ConsoleWindow abut Variations Test")
    win.put_head("=" * 50)
    win.put_head("Different lines have different abut values")
    win.put_head("Navigate with j/k. Press 'q' to quit.")

    # Add lines with various abut configurations
    for i in range(100):
        ctx = None
        if i == 10:
            # Only show 5 lines before this one
            ctx = Context(genre='test', pickable=True, abut=-5)
            win.put_body(f">>> Line {i:2d} - abut=-5 (5 before, 0 after) <<<", context=ctx)
        elif i == 30:
            # Only show 10 lines after this one
            ctx = Context(genre='test', pickable=True, abut=10)
            win.put_body(f">>> Line {i:2d} - abut=10 (0 before, 10 after) <<<", context=ctx)
        elif i == 50:
            # Show 3 before and 7 after
            ctx = Context(genre='test', pickable=True, abut=[-3, 7])
            win.put_body(f">>> Line {i:2d} - abut=[-3, 7] <<<", context=ctx)
        elif i == 70:
            # Test with list containing both positive and negative
            ctx = Context(genre='test', pickable=True, abut=[-8, 3, -2, 12, -5])
            win.put_body(f">>> Line {i:2d} - abut=[-8,3,-2,12,-5] (min=-8, max=12) <<<", context=ctx)
        else:
            ctx = Context(genre='normal', pickable=True)
            win.put_body(f"    Line {i:2d}", context=ctx)

    win.pick_pos = 10
    win.calc()

    while True:
        win.render_once()
        key = win.prompt()

        if key == ord('q') or key == ord('Q'):
            break
        elif key == ord('j') or key == 259:  # DOWN arrow
            win.fix_positions(delta=1)
        elif key == ord('k') or key == 258:  # UP arrow
            win.fix_positions(delta=-1)

    win.teardown()


if __name__ == '__main__':
    print("Test 1: Basic abut feature")
    print("Press Enter to start...")
    input()
    test_abut_feature()

    print("\n\nTest 2: Abut variations")
    print("Press Enter to start...")
    input()
    test_abut_variations()

    print("\n\nAll tests completed!")
