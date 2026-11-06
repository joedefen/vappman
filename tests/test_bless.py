"""The half of the release gate that belongs to *this* project.

`bless` itself is tested once, in the repository that emits it
([`../../blessd/tests/test_bless.py`](../../blessd/tests/test_bless.py)): the
branch plan, the refusals, the prompt, the index check and the emitter are the
same wherever the gate is vendored.  What is not the same is the identity it
derives from this tree -- read at start-up, never written into the tool -- and
the inspector it runs before an upload, [`inspect_dist.py`](inspect_dist.py),
which asserts this project's metadata.  Those two are pinned here.
"""

import importlib.machinery
import importlib.util
import io
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


bless = load_module('bless_gate', ROOT / 'bless')
inspect_dist = load_module('inspect_dist', ROOT / 'tests' / 'inspect_dist.py')

PROJECT = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
VERSION = (ROOT / 'vappman' / '__init__.py').read_text(encoding='utf-8')
VERSION = next(line.split('"')[1] for line in VERSION.splitlines()
               if line.startswith('__version__'))


# --- the identity the vendored gate derives from this tree -----------------

def test_this_tree_derives_its_own_identity():
    name = PROJECT['name']

    assert bless.PROJECT['name'] == name
    assert bless.PROJECT['module'] == name.replace('-', '_')
    assert bless.PROJECT['console'] in list(PROJECT['scripts'])
    assert bless.PROJECT['console'] == 'vappman'
    assert bless.PROJECT['inspector'] == 'tests/inspect_dist.py'
    # This tree keeps a development branch, so publish aligns both.
    assert bless.PROJECT['branches'] == ('main', 'dev')
    assert bless.PYPI_URL == f'https://pypi.org/pypi/{name}/json'
    assert bless.TESTPYPI_URL == f'https://test.pypi.org/pypi/{name}/json'
    assert bless.read_version() == VERSION


def test_the_console_script_reports_the_release_number(monkeypatch, capsys):
    """What `bless` runs in the smoke venv: `vappman --version`, no root needed."""
    from vappman.main import main

    monkeypatch.setattr(sys, 'argv', ['vappman', '--version'])
    with pytest.raises(SystemExit) as stopped:
        main()

    assert stopped.value.code == 0
    assert capsys.readouterr().out.strip() == f'vappman {VERSION}'


# --- the shared inspector ------------------------------------------------

def make_wheel(path, *, summary=None, dependencies=None, include_tests=False,
               modules=True):
    metadata = [
        'Metadata-Version: 2.4',
        'Name: vappman',
        f'Version: {VERSION}',
        f'Summary: {summary or PROJECT["description"]}',
        f'Requires-Python: {PROJECT["requires-python"]}',
        *[f'Requires-Dist: {dependency}' for dependency in
          (dependencies if dependencies is not None
           else PROJECT['dependencies'])],
        f'Keywords: {", ".join(PROJECT.get("keywords", []))}',
        'License-Expression: MIT',
        'License-File: LICENSE',
        '',
        'A description body.',
    ]
    names = ([f'vappman/{module.name}'
              for module in (ROOT / 'vappman').glob('*.py')] if modules else [])
    names.append(f'vappman-{VERSION}.dist-info/licenses/LICENSE')
    if include_tests:
        names.append('tests/test_smoke.py')
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(f'vappman-{VERSION}.dist-info/METADATA',
                         '\n'.join(metadata))
        for name in names:
            archive.writestr(name, '')
    return path


def make_sdist(path, *, version=VERSION, include_tests=False):
    base = f'vappman-{version}'
    members = {
        f'{base}/pyproject.toml': '',
        f'{base}/README.md': '',
        f'{base}/LICENSE': '',
        f'{base}/vappman/__init__.py': f'__version__ = "{version}"\n',
        f'{base}/vappman/main.py': '',
    }
    if include_tests:
        members[f'{base}/tests/test_smoke.py'] = ''
    with tarfile.open(path, 'w:gz') as archive:
        for name, text in members.items():
            payload = text.encode('utf-8')
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return path


def test_a_correct_wheel_and_sdist_pass(tmp_path):
    inspect_dist.check_all(make_wheel(tmp_path / 'ok.whl'),
                           make_sdist(tmp_path / 'ok.tar.gz'))


def test_the_inspector_rejects_a_summary_that_is_not_this_project(tmp_path):
    wheel = make_wheel(tmp_path / 'summary.whl',
                       summary='A GTK tray applet for power management')
    with pytest.raises(inspect_dist.DistributionError) as caught:
        inspect_dist.check_wheel(wheel)
    assert 'Summary' in str(caught.value)


def test_the_inspector_rejects_an_undeclared_runtime_dependency(tmp_path):
    wheel = make_wheel(tmp_path / 'extra.whl',
                       dependencies=[*PROJECT['dependencies'], 'pydbus>=0.6.0'])
    with pytest.raises(inspect_dist.DistributionError) as caught:
        inspect_dist.check_wheel(wheel)
    assert 'Requires-Dist' in str(caught.value)


def test_the_inspector_keeps_wheel_contents_honest(tmp_path):
    with_tests = make_wheel(tmp_path / 'tests.whl', include_tests=True)
    with pytest.raises(inspect_dist.DistributionError, match='tests/'):
        inspect_dist.check_wheel(with_tests)

    bare = make_wheel(tmp_path / 'bare.whl', modules=False)
    with pytest.raises(inspect_dist.DistributionError, match='missing'):
        inspect_dist.check_wheel(bare)


def test_the_sdist_must_carry_the_package_and_its_version(tmp_path):
    mismatch = make_sdist(tmp_path / 'old.tar.gz', version='1.0.0')
    with pytest.raises(inspect_dist.DistributionError, match='1.0.0'):
        inspect_dist.check_sdist(mismatch)

    # The rehearsal overrides the version, and only that.
    inspect_dist.check_sdist(make_sdist(tmp_path / 'old.tar.gz',
                                        version='3.2.0.99.0'),
                             version='3.2.0.99.0')
