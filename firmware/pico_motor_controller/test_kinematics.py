"""Simple no-hardware kinematics checks for BuddyBot Pico firmware."""

from kinematics import kinematics


def _approx_equal(a, b, eps=1e-6):
    return abs(a - b) <= eps


def _all_zero(values):
    return all(_approx_equal(value, 0.0) for value in values)


def test_pure_forward():
    wheels = kinematics.robot_to_wheel_velocities(0.3, 0.0, 0.0)
    values = [wheels["left"], wheels["right"], wheels["back"]]
    passed = abs(values[0]) > 0 and abs(values[1]) > 0 and not _all_zero(values)
    return passed, wheels


def test_pure_rotate():
    wheels = kinematics.robot_to_wheel_velocities(0.0, 0.0, 0.5)
    values = [abs(wheels["left"]), abs(wheels["right"]), abs(wheels["back"])]
    passed = _approx_equal(values[0], values[1]) and _approx_equal(values[1], values[2])
    return passed, wheels


def test_strafe_left():
    wheels = kinematics.robot_to_wheel_velocities(0.0, 0.3, 0.0)
    values = [wheels["left"], wheels["right"], wheels["back"]]
    passed = len({round(value, 6) for value in values}) > 1 and any(value < 0 for value in values)
    return passed, wheels


def test_zero_command():
    wheels = kinematics.robot_to_wheel_velocities(0.0, 0.0, 0.0)
    values = [wheels["left"], wheels["right"], wheels["back"]]
    passed = _all_zero(values)
    return passed, wheels


def main():
    cases = [
        ("pure_forward", test_pure_forward),
        ("pure_rotate", test_pure_rotate),
        ("strafe_left", test_strafe_left),
        ("zero_command", test_zero_command),
    ]
    failures = 0
    for name, fn in cases:
        passed, wheels = fn()
        status = "PASS" if passed else "FAIL"
        print(f"{status} {name}: {wheels}")
        if not passed:
            failures += 1

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
