#!/usr/bin/env python3
""" AppImage system compatibility checker."""
import subprocess
from pathlib import Path

from console_window import Glyphs


def warn_mark():
    """The two-cell 'pay attention' badge for console output."""
    return Glyphs.get('star_glow')


class AppImageIssue:
    """Represents a system compatibility issue for AppImages"""
    def __init__(self, name: str, description: str, severity: str, fix_commands: dict[str, str]):
        self.name = name
        self.description = description
        self.severity = severity  # 'critical', 'warning', 'info'
        self.fix_commands = fix_commands  # distro -> command mapping


def get_distro() -> tuple[str, str]:
    """Detect Linux distribution."""
    try:
        with open('/etc/os-release') as f:
            info = {}
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    info[key] = value.strip('"')
            return info.get('ID', 'unknown'), info.get('PRETTY_NAME', 'Unknown Linux')
    except Exception:
        return 'unknown', 'Unknown Linux'


def check_fuse() -> AppImageIssue | None:
    """Check if libfuse2 is installed (required for type 2 AppImages)"""
    fuse_paths = [
        Path('/usr/lib/x86_64-linux-gnu/libfuse.so.2'),
        Path('/usr/lib64/libfuse.so.2'),
        Path('/lib/x86_64-linux-gnu/libfuse.so.2'),
        Path('/lib64/libfuse.so.2'),
    ]

    try: # Also try finding with ldconfig
        result = subprocess.run(['ldconfig', '-p'], capture_output=True, text=True, timeout=2)
        if 'libfuse.so.2' in result.stdout:
            return None
    except Exception:
        pass

    for path in fuse_paths:
        if path.exists():
            return None

    return AppImageIssue( # can't find fuse2
        name='libfuse2',
        description='libfuse2 is not installed (required for most AppImages)',
        severity='critical',
        fix_commands={
            'ubuntu': 'sudo apt install libfuse2',
            'debian': 'sudo apt install libfuse2',
            'linuxmint': 'sudo apt install libfuse2',
            'pop': 'sudo apt install libfuse2',
            'fedora': 'sudo dnf install fuse-libs',
            'rhel': 'sudo dnf install fuse-libs',
            'centos': 'sudo yum install fuse-libs',
            'arch': 'sudo pacman -S fuse2',
            'manjaro': 'sudo pacman -S fuse2',
            'opensuse': 'sudo zypper install libfuse2',
            'default': 'Install libfuse2 or fuse-libs package for your distribution',
        }
    )


def check_user_namespaces() -> AppImageIssue | None:
    """Check if unprivileged user namespaces are enabled (needed for sandboxed AppImages)"""
    try:
        userns_file = Path('/proc/sys/kernel/unprivileged_userns_clone')
        if userns_file.exists():
            with open(userns_file) as f:
                if f.read().strip() != '1':
                    return AppImageIssue(
                        name='user_namespaces',
                        description='Unprivileged user namespaces are disabled (sandboxed AppImages will fail)',
                        severity='warning',
                        fix_commands={
                            'ubuntu': 'sudo sysctl -w kernel.unprivileged_userns_clone=1\n'
                                     'To make permanent: echo "kernel.unprivileged_userns_clone=1" | sudo tee /etc/sysctl.d/00-local-userns.conf',
                            'debian': 'sudo sysctl -w kernel.unprivileged_userns_clone=1\n'
                                     'To make permanent: echo "kernel.unprivileged_userns_clone=1" | sudo tee /etc/sysctl.d/00-local-userns.conf',
                            'default': 'sudo sysctl -w kernel.unprivileged_userns_clone=1',
                        }
                    )
    except Exception:
        pass
    return None


def check_tmp_noexec() -> AppImageIssue | None:
    """Check if /tmp is mounted with noexec (prevents AppImages from running)"""
    try:
        result = subprocess.run(['mount'], capture_output=True, text=True, timeout=2)
        for line in result.stdout.split('\n'):
            if ' /tmp ' in line or line.startswith('/tmp '):
                if 'noexec' in line:
                    return AppImageIssue(
                        name='tmp_noexec',
                        description='/tmp is mounted with noexec flag (AppImages cannot execute)',
                        severity='critical',
                        fix_commands={
                            'default': 'Remount /tmp: sudo mount -o remount,exec /tmp\n'
                                      'Or set TMPDIR to another location: export TMPDIR=$HOME/tmp',
                        }
                    )
    except Exception:
        pass
    return None


def check_apparmor() -> AppImageIssue | None:
    """Check for AppArmor restrictions that might block AppImages"""
    try:
        # Check if AppArmor is active
        result = subprocess.run(['aa-status'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and 'profiles are in enforce mode' in result.stdout:
            return AppImageIssue(
                name='apparmor',
                description='AppArmor is active (may require profile adjustments for some AppImages)',
                severity='info',
                fix_commands={
                    'default': 'If AppImages fail, check: sudo dmesg | grep -i apparmor\n'
                              'May need to adjust AppArmor profiles or run: sudo aa-complain /path/to/appimage',
                }
            )
    except FileNotFoundError:
        pass # AppArmor probably not installed
    except Exception:
        pass
    return None


def check_selinux() -> AppImageIssue | None:
    """Check for SELinux restrictions that might block AppImages"""
    try:
        result = subprocess.run(['getenforce'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            mode = result.stdout.strip().lower()
            if mode == 'enforcing':
                return AppImageIssue(
                    name='selinux',
                    description='SELinux is in enforcing mode (may block AppImage execution)',
                    severity='warning',
                    fix_commands={
                        'fedora': 'If AppImages fail, check: sudo ausearch -m avc -ts recent\n'
                                 'Temporarily set permissive: sudo setenforce 0\n'
                                 'Or add SELinux policy for AppImages',
                        'rhel': 'If AppImages fail, check: sudo ausearch -m avc -ts recent\n'
                               'Temporarily set permissive: sudo setenforce 0\n'
                               'Or add SELinux policy for AppImages',
                        'centos': 'If AppImages fail, check: sudo ausearch -m avc -ts recent\n'
                                 'Temporarily set permissive: sudo setenforce 0\n'
                                 'Or add SELinux policy for AppImages',
                        'default': 'If AppImages fail, check SELinux logs: sudo ausearch -m avc -ts recent\n'
                                  'Temporarily set permissive mode: sudo setenforce 0\n'
                                  'To make permanent (not recommended): edit /etc/selinux/config',
                    }
                )
            elif mode == 'permissive':
                return AppImageIssue(
                    name='selinux',
                    description='SELinux is in permissive mode (logging but not blocking)',
                    severity='info',
                    fix_commands={
                        'default': 'SELinux is permissive - AppImages should work but violations are logged',
                    }
                )
    except FileNotFoundError:
        # getenforce not found, SELinux probably not installed
        pass
    except Exception:
        pass
    return None


def run_checks() -> list[AppImageIssue]:
    """ Run all AppImage compatibility checks."""
    checks = [
        check_fuse,
        check_user_namespaces,
        check_tmp_noexec,
        check_apparmor,
        check_selinux,
    ]

    issues = []
    for check in checks:
        issue = check()
        if issue:
            issues.append(issue)

    return issues


def format_report(issues: list[AppImageIssue], distro_id: str, distro_name: str, verbose: bool = True) -> str:
    """ Format appimage issues into a readable report.

    Args:
     *  issues: List of detected issues
     *  distro_id: Distribution ID (e.g., 'ubuntu')
     *  distro_name: Distribution name (e.g., 'Ubuntu 22.04')
     *  verbose: If True, include detailed fix instructions

    Returns:
        Formatted report string
    """
    if not issues:
        return f"✓ System appears ready to run AppImages ({distro_name})"

    lines = []
    lines.append(f"AppImage Compatibility Check ({distro_name})")
    lines.append("=" * 60)

    critical = [i for i in issues if i.severity == 'critical']
    warnings = [i for i in issues if i.severity == 'warning']
    infos = [i for i in issues if i.severity == 'info']

    if critical:
        lines.append(f"\n{warn_mark()} CRITICAL ISSUES (AppImages will likely not work):")
        for issue in critical:
            lines.append(f"\n  • {issue.description}")
            if verbose:
                fix = issue.fix_commands.get(distro_id) or issue.fix_commands.get('default', 'No fix available')
                lines.append(f"    Fix: {fix}")

    if warnings:
        lines.append(f"\n{warn_mark()} WARNINGS (Some AppImages may fail):")
        for issue in warnings:
            lines.append(f"\n  • {issue.description}")
            if verbose:
                fix = issue.fix_commands.get(distro_id) or issue.fix_commands.get('default', 'No fix available')
                lines.append(f"    Fix: {fix}")

    if infos:
        lines.append("\nℹ INFO:")
        for issue in infos:
            lines.append(f"\n  • {issue.description}")
            if verbose:
                fix = issue.fix_commands.get(distro_id) or issue.fix_commands.get('default', 'No fix available')
                lines.append(f"    Note: {fix}")

    return "\n".join(lines)


def quick_check() -> tuple[bool, list[str]]:
    """Quick startup check - reports all issues with individual status lines."""

    checks_info = [
        ('libfuse2', check_fuse),
        ('user namespaces', check_user_namespaces),
        ('/tmp noexec', check_tmp_noexec),
        ('AppArmor', check_apparmor),
        ('SELinux', check_selinux),
    ]

    distro_id, _ = get_distro()
    status_lines = []
    has_critical = False

    for check_name, check_func in checks_info:
        issue = check_func()
        if issue:
            if issue.severity == 'critical':
                has_critical = True
                fix = issue.fix_commands.get(distro_id) or issue.fix_commands.get('default', '')
                fix_cmd = fix.split('\n')[0] if fix else 'Check system configuration'
                status_lines.append(f"  ✗ {check_name}: {issue.description}")
                status_lines.append(f"    Fix: {fix_cmd}")
            elif issue.severity == 'warning':
                status_lines.append(f"  {warn_mark()} {check_name}: {issue.description}")
            else:
                status_lines.append(f"  ℹ {check_name}: {issue.description}")
        else:
            status_lines.append(f"  ✓ {check_name}: OK")

    return has_critical, status_lines


def main():
    """Command-line interface for AppImage doctor"""
    distro_id, distro_name = get_distro()

    has_critical, status_lines = quick_check()

    print(f"AppImage Compatibility Check ({distro_name})")
    print("=" * 60)
    for line in status_lines:
        print(line)
    print()

    issues = run_checks()
    if issues:
        print("Detailed Information:")
        print("-" * 60)
        for issue in issues:
            if issue.severity == 'critical':
                fix = issue.fix_commands.get(distro_id) or issue.fix_commands.get('default', 'No fix available')
                print(f"\n✗ {issue.name}:")
                print(f"  {issue.description}")
                print(f"  Fix: {fix}")
            elif issue.severity == 'warning':
                fix = issue.fix_commands.get(distro_id) or issue.fix_commands.get('default', 'No fix available')
                print(f"\n{warn_mark()} {issue.name}:")
                print(f"  {issue.description}")
                print(f"  Suggestion: {fix}")
    else:
        print("All checks passed! Your system is ready to run AppImages.")

    if any(i.severity == 'critical' for i in issues):
        return 2
    elif any(i.severity == 'warning' for i in issues):
        return 1
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
