# vappman: working on the source tree

This is the developer companion to [`README.md`](README.md), which documents the
app.  Here we document the two things a maintainer needs and a user does not:
the **test gate** and the **release gate** (`./bless`).

## Layout and single sources of truth

| Path | Owns |
| --- | --- |
| [`vappman/__init__.py`](vappman/__init__.py) | `__version__`, and nothing else. The build backend reads it, `--version` prints it, `bless` reads the line without importing. |
| [`vappman/Appearance.py`](vappman/Appearance.py) | Semantic colour roles: `console_window.Theme` pair ids, the mono attribute fallback, and the process-wide colour switch. |
| [`pyproject.toml`](pyproject.toml) | Name, description, keywords, `requires-python`, runtime dependencies, the SPDX `license` and `license-files`, the `dev` extra, pytest and ruff configuration. |
| [`bless`](bless) | The release gate. Copied verbatim from `pwr-tray`; it holds no copy of this project's identity. |
| [`tests/inspect_dist.py`](tests/inspect_dist.py) | The distribution inspector. `bless` refuses to upload a wheel and sdist it has not inspected with this file. |
| [`.github/workflows/tests.yml`](.github/workflows/tests.yml) | CI: installs `.[test]` and runs `pytest` on Python 3.10 -- 3.13. |
| [`.gitignore`](.gitignore) | Keeps gate artifacts (`build/`, `dist/`, `.coverage`, caches) out of `git status`, because the gate refuses a dirty tree. |

The version lives in exactly one place.  `pyproject.toml` declares
`dynamic = ["version"]`, so flit reads `vappman/__init__.py`; a
`X.Y.Z.99.N` rehearsal rewrites that line only inside a throwaway copy.

No `[tool.bless]` table is needed: everything is derived from what is already
there -- `NAME = vappman`, `MODULE = vappman`, the console script from the first
`[project.scripts]` entry (also `vappman`), and the inspector at
`tests/inspect_dist.py`.

## The test gate

Install what the gate needs (this is the interpreter that must run `bless`,
too):

    python -m pip install -e '.[dev]'

Then the three commands `bless` runs, in the same order, on the same
interpreter:

    python -m ruff check .
    python -m compileall -q vappman tests
    python -m pytest -q --cov=vappman --cov-report=term-missing

Today that is 54 tests at 30% coverage.  Coverage is *reported*, not enforced;
see FUTURE ENHANCEMENTS.

The ruff selection is committed rather than inherited
(`[tool.ruff.lint] select = ["E4", "E7", "E9", "F"]`) so that no user or global
configuration can change what the gate enforces.  It is deliberately the
conservative core, not a style position.

## The release gate: `./bless`

`./bless` takes no arguments and has no flag that skips a stage.  It always runs
everything, then prints what it has in hand and asks one question:

    ====> Enter test or publish or quit:

Only `test` and `publish` are accepted, spelled in full; anything else is asked
again.  Enter, `quit` or Ctrl-C stops with nothing tagged, uploaded or pushed.

**Stages, in order**

1. **preflight** -- clean tree, the `vX.Y.Z` tag absent, `twine>=7` and
   `packaging>=26` present.
2. **index check** -- refuses if `__version__` is already on PyPI, printing
   every published version, before anything is built or uploaded.
3. **gates** -- the three commands above.
4. **build** -- into `build/bless-<version>/`, wiped first, so no older
   artifact can be sent by mistake.
5. **inspect** -- `tests/inspect_dist.py` against the wheel and the sdist.
6. **check** -- `twine check --strict` on both files.
7. **smoke** -- installs the built wheel into a throwaway venv and runs
   `vappman --version`, which must print the version being released.  This is
   why the CLI has `--version` ([`main()`](vappman/main.py:1036)).
8. **branch plan** -- refuses a detached HEAD, a third branch, diverged
   `main`/`dev`, or a push that would not fast-forward.

**`test`** is the rehearsal and never spends the working version.  It copies the
tree to `build/bless-test-<version>/src`, rewrites `__version__` to
`X.Y.Z.99.N` (99 keeps it clear of real releases; `N` is one past the highest
suffix TestPyPI already holds for that base), builds, inspects and smoke-tests
the copy, and uploads only to `test.pypi.org`.  No tag, no branch, no push.  It
prints the install line, which needs `python -m pip cache purge` first and
`--extra-index-url https://pypi.org/simple/`, because TestPyPI carries no
dependencies.

**`publish`** fast-forwards `main` and `dev` to one commit, tags `vX.Y.Z`,
uploads the two inspected files to PyPI, verifies the index, and pushes `main`,
`dev` and the tag.

**Credentials** are resolved per index -- `TWINE_PASSWORD` for PyPI,
`TWINE_TESTPYPI_PASSWORD` for TestPyPI, each overruling the `~/.pypirc` section
whose `repository` matches that index's upload URL -- so a PyPI token is never
spent on a rehearsal.  A missing credential is a refusal before `twine` starts.

**Verification** reads the index back after an upload.  The read is
cache-busted and patient (up to a quarter of an hour), because both indexes list
new releases through a CDN that lags; a release that is not listed yet is
reported as lag with the project page to check, never as a failed upload, since
an accepted upload cannot be withdrawn.

There is no CI publish job, on purpose: the upload is irreversible and is run by
the owner from the development tree, so the safety lives in one inspectable
command.  CI stays a gate.

One interpreter caveat: `bless` imports `tomllib`, so it needs **Python 3.11+**
to run, even though vappman itself supports 3.10.

## What the inspector asserts

[`tests/inspect_dist.py`](tests/inspect_dist.py) is the one implementation, used
by `bless` now and by CI later; expectations are read from `pyproject.toml` and
the package, never from the artifact under test.

* **wheel** -- `Name`, `Version`, `Summary`, `Requires-Python`, `Keywords`,
  `License-Expression` and the *runtime* `Requires-Dist` names match
  `pyproject.toml`; every declared `license-files` entry is listed in
  `License-File`; every `vappman/*.py` is present; a `LICENSE` is carried; no
  `tests/`, no `.venv`, no `__pycache__`, no `.pyc`.
* **sdist** -- carries `pyproject.toml`, `README.md`, `LICENSE`,
  `vappman/__init__.py`, `vappman/main.py`; the `__version__` inside the sdist
  equals the artifact version; no venv or bytecode.  The sdist is deliberately
  lean: flit's default payload is enough and `tests/` need not ride along.

Run it by hand on any built pair:

    python tests/inspect_dist.py dist/vappman-2.2.1-py3-none-any.whl \
                                dist/vappman-2.2.1.tar.gz

## Releasing, in three steps

1. Bump `__version__` in [`vappman/__init__.py`](vappman/__init__.py) and commit.
2. Run `./bless`.  The gate runs in full.
3. Answer `test` to rehearse on TestPyPI, then run `./bless` again and answer
   `publish` -- or go straight to `publish`.

`main` and `dev` must both exist and both track origin; `publish` leaves them at
the tagged commit.  Everything else about the release is one of the stages above.

## FUTURE ENHANCEMENTS

Deferred work, in the order it is worth doing.  None of it is required for the
gate to be correct; all of it is known and chosen.

### 1. Bring CI up to the gate's standard

`.github/workflows/tests.yml` runs `pytest` and nothing else, so a tree can be
green in CI and still refused by `bless` (lint, build, inspection, smoke).
Add a job that installs `.[dev]`, runs `ruff check .` and `compileall`, then
`python -m build`, `tests/inspect_dist.py` on the pair, and `twine check
--strict` -- the same commands, not equivalents.  Keep it credential-free.

### 2. Regression tests for the tooling itself

The gate is load-bearing and currently untested here.  Port, adapted:

* `test_repo_hygiene.py` -- the ruff configuration lives in the repository; CI
  runs lint, tests and a packaging smoke test; a coverage floor is wired and
  cannot quietly disappear; `README`/`README-DEV` name the release gate; no
  documented command uploads a whole `dist/` directory.
* `test_bless.py`-style tests -- import `bless` as a module and stub its
  stages: identity derivation, preflight refusals, the duplicate check running
  before any build, the prompt accepting only `test`/`publish`, the
  `X.Y.Z.99.N` arithmetic, the patient verifier's lag handling.  These are what
  keep a future re-copy of `bless` honest.

### 3. Enforce a coverage floor

`--cov` prints 29% and ignores it.  Add `[tool.coverage.run]` (source, omit) and
`[tool.coverage.report] fail_under`, set just below the current number, and
ratchet it as tests grow.  Without this the coverage gate is advisory.

### 4. Tighten the lint ratchet

`E4`/`E7`/`E9`/`F` is ruff's own default selection, so the committed config
matches the tool rather than trimming it -- but it is a floor, not a target.  A
broader selection (`E`, `W`, `F`, `I`, `UP`, `B`) reports 101 findings here, 57
of them auto-fixable: mostly line length (38), import sorting (22) and
`typing` modernisation.  Adopt them in slices with `per-file-ignores` where the
curses/TUI code genuinely needs them, never by trimming the selection to make a
commit pass.

### 5. Decide how `bless` handles Python 3.10

`bless` needs 3.11+ (`tomllib`), while the package supports 3.10 and CI tests
it.  Either state and enforce the interpreter for releases, or add a `tomli`
fallback upstream in `pwr-tray` and re-copy the file -- the second keeps the
"copy verbatim, never edit" rule intact.

### 6. Trim what the rehearsal copies

`COPY_EXCLUDES` in [`bless`](bless) does not know about `images/`, so every
`test` run copies 18 MB of screenshots into `build/bless-test-*/src`.  Fix it
upstream as a `[tool.bless]` exclude, or keep screenshots out of the tree the
copy traverses.

### 7. Theme switching (deferred by design)

Phase 1 colours only two semantic roles, through `console_window.Theme` pair
ids: installed rows use `INFO` and the inline install/remove confirmations use
`DANGER`. No theme picker, CLI flag or preference is shipped yet. The role ids
are the seam: adding a picker later should not touch the draw code.

Decisions to settle first:

* **Persistence.** [`PersistentState.load()`](vappman/PersistentState.py:33)
  requires the key set to match exactly, so adding `theme`/`colors` to its
  defaults would reset an existing `install_opts`, `database` and
  `max_backups` on first run. Either keep appearance in a separate store
  (adapting console-window's two-method `ThemeStore` protocol) or relax
  `load()` to merge missing keys and add a migration test.
* **Mono.** `dark-mono`/`light-mono` are still colour themes; a true no-colour
  appearance needs the `MONO_ROLES` path already in
  [`Appearance.py`](vappman/Appearance.py) plus a pseudo-entry in the picker.
* **Picker scope.** console-window's generic picker previews every role;
  vappman uses only `DANGER`/`INFO`. Decide whether to show the generic theme
  swatches or a vappman-specific role table.
* **Key.** `t` already means "test" on installed rows
  ([`main.py`](vappman/main.py:596)). Pick `T`, or expose the picker only from
  Help, and bind `spin_theme` explicitly so the hint line is true.
* **CLI/env.** `--theme`, `--no-color` and `NO_COLOR` need a precedence rule:
  explicit flag, then environment, then remembered preference.
