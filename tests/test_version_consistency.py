"""Version lockstep: every live surface reads the same version.

CHANGELOG.md legitimately records history (including 0.1.0); every other
source surface must carry the current version. The CLI-binary check is
guarded with skipUnless so environments without the console script stay
green.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import proofloop

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED = "0.2.0"

_SKIP_DIRS = {".git", ".venv", "venv", "dist", "build", "__pycache__", ".pytest_cache", "node_modules"}
_TEXT_SUFFIXES = {".py", ".toml", ".json", ".md", ".yml", ".yaml", ".cfg", ".txt", ".tape"}


def test_pyproject_version_matches() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(rf'^version = "{re.escape(EXPECTED)}"$', pyproject, re.MULTILINE)


def test_package_dunder_version_matches() -> None:
    assert proofloop.__version__ == EXPECTED


def test_site_json_content_version_matches() -> None:
    site = json.loads((REPO_ROOT / "web" / "site.json").read_text(encoding="utf-8"))
    assert site["meta"]["content_version"] == EXPECTED


def test_changelog_records_both_versions() -> None:
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.1.0]" in changelog
    assert "## [0.2.0]" in changelog


@unittest.skipUnless(shutil.which("proofloop"), "proofloop console script not on PATH")
def test_cli_version_flag_matches() -> None:
    exe = shutil.which("proofloop")
    assert exe is not None
    out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0
    assert f"proofloop {EXPECTED}" in out.stdout


def test_no_stale_version_strings_outside_the_changelog() -> None:
    # Live version surfaces carry the bare form ("0.1.0" in pyproject/__init__/
    # site.json); "v0.1.0" (the git-tag form) is a legitimate historical
    # reference in comments, so only the bare form is a stale-surface smell.
    # This test file itself is skipped: it necessarily names the old version
    # in the assertion message and regex discussion.
    stale = re.compile(r"(?<![v\d.])0\.1\.0")
    self_rel = Path("tests/test_version_consistency.py")
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
            continue
        rel = path.relative_to(REPO_ROOT)
        if rel.name == "CHANGELOG.md" or rel == self_rel:
            continue
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not stale.search(text), f"stale version string in {rel}"
