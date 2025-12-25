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

    def install_dependencies(self, missing):
        """
        Offer to install missing dependencies using the system package manager.

        Args:
            missing (set): Set of missing program names

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

        # Map common program names to package names for different distros
        # Some programs have different package names on different distros
        package_map = {
            'curl': 'curl',
            'grep': 'grep',
            'jq': 'jq',
            'sed': 'sed',
            'wget': 'wget',
        }

        packages = [package_map.get(prog, prog) for prog in missing]

        print(f'\n⚠️  Missing dependencies: {", ".join(sorted(missing))}')
        print(f'\nDetected package manager: {pm_name}')

        response = input(f'\nInstall missing dependencies? [y/N]: ').strip().lower()

        if response not in ('y', 'yes'):
            print('Installation cancelled.')
            return False

        # Build and execute the install command
        install_cmd = install_cmd_template.format(packages=' '.join(packages))
        print(f'\nRunning: {install_cmd}')

        try:
            result = subprocess.run(install_cmd, shell=True, check=False)
            if result.returncode != 0:
                print(f'\n❌ Installation failed with exit code {result.returncode}')
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

        missing = set()
        self.has_am = bool(shutil.which('am') is not None)
        self.has_appman = bool(shutil.which('appman') is not None)

        for prog in 'curl grep jq sed wget'.split():
            if shutil.which(prog) is None:
                missing.add(prog)

        # Handle missing dependencies
        if missing:
            if not self.install_dependencies(missing):
                print('\n❌ Cannot proceed without required dependencies.')
                sys.exit(1)

            # Verify installation
            still_missing = set()
            for prog in missing:
                if shutil.which(prog) is None:
                    still_missing.add(prog)

            if still_missing:
                print(f'\n❌ Still missing after installation: {", ".join(sorted(still_missing))}')
                sys.exit(1)

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

        print('✅ All prerequisites satisfied.')
