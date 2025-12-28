#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
"""
# pylint: disable=broad-exception-caught,consider-using-with
# pylint: disable=too-many-instance-attributes,too-many-branches
# pylint: disable=too-many-return-statements,too-many-statements
# pylint: disable=consider-using-in,too-many-nested-blocks
# pylint: disable=wrong-import-position,disable=wrong-import-order
# pylint: disable=line-too-long,protected-access,invalid-name

import sys
import re
import shutil
import subprocess
from types import SimpleNamespace

class Prerequisites:
    """ Detect / install prereqs """
    def __init__(self):
        self.has_am = False
        self.has_appman = False

    def detect_package_manager(self):
        """
        Detect the system's package manager.

        Returns:
            tuple: (package_manager_name, install_command_template)
                   or (None, None) if unsupported
        """
        # Check for various package managers in order of preference
        pkg_managers = [
            ('apt', 'sudo apt-get update && sudo apt-get install -y {packages}'),
            ('dnf', 'sudo dnf install -y {packages}'),
            ('yum', 'sudo yum install -y {packages}'),
            ('pacman', 'sudo pacman -S --noconfirm {packages}'),
            ('zypper', 'sudo zypper install -y {packages}'),
            ('emerge', 'sudo emerge {packages}'),
            ('apk', 'sudo apk add {packages}'),
        ]

        for pm_name, cmd_template in pkg_managers:
            if shutil.which(pm_name):
                return (pm_name, cmd_template)

        return (None, None)

    def install_dependencies(self, missing, skip_prompt=False):
        """
        Offer to install missing dependencies using the system package manager.

        Args:
            missing (set): Set of missing program names or package names
            skip_prompt (bool): If True, skip confirmation prompt and install directly

        Returns:
            bool: True if installation succeeded or user declined, False on error
        """
        if not missing:
            return True

        pm_name, install_cmd_template = self.detect_package_manager()

        if not pm_name:
            print(f'\nERROR: Cannot find supported package manager.')
            print(f'Missing dependencies: {", ".join(sorted(missing))}')
            print('Please install them manually using your system package manager.')
            return False

        packages = sorted(missing)

        if not skip_prompt:
            print(f'\n⚠️  Missing dependencies: {", ".join(packages)}')
            print(f'\nDetected package manager: {pm_name}')

            response = input(f'\nInstall missing dependencies? [y/N]: ').strip().lower()

            if response not in ('y', 'yes'):
                print('Installation cancelled.')
                return False
        else:
            print(f'\nInstalling: {", ".join(packages)}')
            print(f'Using package manager: {pm_name}')

        # Build and execute the install command
        install_cmd = install_cmd_template.format(packages=' '.join(packages))
        print(f'\nRunning: {install_cmd}')

        try:
            result = subprocess.run(install_cmd, shell=True, check=False)
            if result.returncode != 0:
                print(f'\n❌ Installation failed with exit code {result.returncode}')
                if pm_name == 'apt':
                    print('\nTip: If you see repository errors, try:')
                    print('  - Check for problematic PPAs in /etc/apt/sources.list.d/')
                    print('  - Remove outdated PPAs that block apt operations')
                return False
            print(f'\n✅ Dependencies installed successfully!')
            return True
        except Exception as exc:
            print(f'\n❌ Installation failed: {exc}')
            return False

    def install_am_appman(self):
        """
        Offer to install AM/appman using the official installer.

        Returns:
            bool: True if installation succeeded or user declined, False on error
        """
        print('\n⚠️  AM/appman is not installed.')
        print('\nAM is a powerful AppImage package manager that allows you to:')
        print('  • Install and manage 2500+ AppImages, Soarpkgs, and AppBundles')
        print('  • Update apps with a single command')
        print('  • Sandbox untrusted applications')
        print('  • Create snapshots and rollbacks')

        response = input('\nInstall AM/appman now? [y/N]: ').strip().lower()

        if response not in ('y', 'yes'):
            print('Installation cancelled.')
            return False

        # Check if wget or curl is available
        if not shutil.which('wget'):
            print('\n❌ wget is required to download the AM installer.')
            print('Please install wget first.')
            return False

        installer_url = 'https://raw.githubusercontent.com/ivan-hc/AM/main/AM-INSTALLER'
        install_cmd = (
            f'wget -q {installer_url} && '
            f'chmod a+x ./AM-INSTALLER && '
            f'./AM-INSTALLER && '
            f'rm ./AM-INSTALLER'
        )

        print(f'\nRunning: {install_cmd}')

        try:
            result = subprocess.run(install_cmd, shell=True, check=False)
            if result.returncode != 0:
                print(f'\n❌ AM installation failed with exit code {result.returncode}')
                return False
            print(f'\n✅ AM/appman installed successfully!')
            return True
        except Exception as exc:
            print(f'\n❌ AM installation failed: {exc}')
            return False

    def check_preqreqs(self):
        """
        Check that needed programs are installed.
        Offers to install missing dependencies and AM/appman if not found.
        """
        print('Checking prerequisites...')

        # Core dependencies (required) - from AM documentation
        core_deps = {
            'curl': 'curl',      # to check URLs
            'grep': 'grep',      # to check files
            'sed': 'sed',        # to edit/adapt installed files
            'wget': 'wget',      # to download programs and update AM
            'cat': 'coreutils',  # part of coreutils
            'chmod': 'coreutils',  # part of coreutils
            'chown': 'coreutils',  # part of coreutils
        }

        # Optional dependencies - from AM documentation
        optional_deps = {
            'ar': 'binutils',    # extracts .deb packages
            'less': 'less',      # to read long lists
            'unzip': 'unzip',    # to extract .zip packages
            'tar': 'tar',        # to extract .tar* packages
            'zsync': 'zsync',    # required by very few programs
        }

        missing_core = set()
        missing_optional = set()
        self.has_am = bool(shutil.which('am') is not None)
        self.has_appman = bool(shutil.which('appman') is not None)

        # Check for sudo or doas
        has_sudo = shutil.which('sudo') is not None
        has_doas = shutil.which('doas') is not None
        if not has_sudo and not has_doas:
            print('\n⚠️  WARNING: Neither "sudo" nor "doas" found.')
            print('    System-level operations may not work correctly.')

        # Check core dependencies
        for prog in core_deps:
            if shutil.which(prog) is None:
                missing_core.add(prog)

        # Check optional dependencies
        for prog in optional_deps:
            if shutil.which(prog) is None:
                missing_optional.add(prog)

        # Handle missing core dependencies
        if missing_core:
            # Map programs to their package names
            packages_needed = set()
            for prog in missing_core:
                packages_needed.add(core_deps[prog])

            if not self.install_dependencies(packages_needed):
                print('\n❌ Cannot proceed without required core dependencies.')
                sys.exit(1)

            # Verify installation
            still_missing = set()
            for prog in missing_core:
                if shutil.which(prog) is None:
                    still_missing.add(prog)

            if still_missing:
                print(f'\n❌ Still missing after installation: {", ".join(sorted(still_missing))}')
                sys.exit(1)

        # Handle missing optional dependencies (pause but don't block)
        optional_install_failed = False
        if missing_optional:
            packages_needed = set()
            for prog in missing_optional:
                packages_needed.add(optional_deps[prog])

            print(f'\n⚠️  Optional dependencies missing: {", ".join(sorted(missing_optional))}')
            print('    Some features may not work without these packages.')

            response = input(f'\nInstall optional dependencies? [y/N]: ').strip().lower()
            if response in ('y', 'yes'):
                if not self.install_dependencies(packages_needed, skip_prompt=True):
                    optional_install_failed = True
            else:
                print('Continuing without optional dependencies...')
                input('Press Enter to continue...')

        # Handle missing AM/appman
        if not self.has_am and not self.has_appman:
            if not self.install_am_appman():
                print('\n❌ Cannot proceed without AM/appman.')
                print('\nManual installation instructions:')
                print('  wget -q https://raw.githubusercontent.com/ivan-hc/AM/main/AM-INSTALLER')
                print('  chmod a+x ./AM-INSTALLER')
                print('  ./AM-INSTALLER')
                print('  rm ./AM-INSTALLER')
                sys.exit(1)

            # After successful installation, exit so user can restart vappman
            print('\n✅ Installation complete!')
            print('\nPlease restart vappman to begin using it.')
            sys.exit(0)

        if optional_install_failed:
            print('⚠️  Core prerequisites satisfied (optional dependencies had issues).')
        else:
            print('✅ All prerequisites satisfied.')
