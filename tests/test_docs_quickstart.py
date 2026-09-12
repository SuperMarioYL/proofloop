"""The README quickstart must install THIS product — regression guard.

PyPI's `proofloop` name belongs to an unrelated project (Knowlytix
agentic-AI testing, Apache-2.0, no console scripts), so the bare
`uvx proofloop` / `pip install proofloop` forms install foreign software and
fail on a clean machine. The quickstart must carry the git-based install
form instead.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

GIT_FORM = "uvx --from git+https://github.com/SuperMarioYL/proofloop proofloop"


def _read(name: str) -> str:
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def test_readmes_avoid_the_foreign_pypi_name_forms() -> None:
    for name in ("README.md", "README.en.md"):
        text = _read(name)
        assert "uvx proofloop" not in text, (
            f"{name}: bare `uvx proofloop` installs the unrelated foreign PyPI package"
        )
        assert "pip install proofloop" not in text, (
            f"{name}: bare `pip install proofloop` installs the unrelated foreign PyPI package"
        )


def test_readmes_quickstart_uses_the_git_install_form() -> None:
    for name in ("README.md", "README.en.md"):
        assert GIT_FORM in _read(name), f"{name}: quickstart must use the git-based install"
