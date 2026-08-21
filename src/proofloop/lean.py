"""Lean 4 type-checker interface — the ground-truth oracle.

Lean is the compiler the agent iterates against. ``proof_passed`` in a
certificate is asserted *only* after :func:`LeanChecker.check` reports the proof
type-checks. An admitted proof (``sorry`` / ``admit``) is treated as a failure
regardless of the compiler exit code — a hole is not a certificate.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Bare-names tactics that admit a goal without proving it. A proof using any of
# these is rejected before the compiler is even consulted.
_ADMIT_RE = re.compile(r"\b(?:sorry|admit)\b")


@dataclass(frozen=True)
class LeanResult:
    """Verdict of checking one proof draft."""

    ok: bool
    stderr: str
    version: str
    available: bool


def has_admit(proof: str) -> bool:
    """True if the proof leaves a goal admitted (``sorry``/``admit``)."""
    return bool(_ADMIT_RE.search(proof))


class LeanChecker:
    """Real Lean 4 checker via the ``lean`` binary (managed by ``elan``)."""

    def __init__(self, lean_path: str = "lean") -> None:
        self._lean_path = lean_path
        self._version: str | None = None

    def check(self, proof: str) -> LeanResult:
        # Policy gate: an admitted goal is not a certificate, even though bare
        # `lean` would exit 0 with a warning on `sorry`. Reject up front.
        if has_admit(proof):
            return LeanResult(
                ok=False,
                stderr=(
                    "proof uses 'sorry'/'admit' — admitted goals are not "
                    "machine-checkable certificates"
                ),
                version="",
                available=True,
            )

        if shutil.which(self._lean_path) is None:
            return LeanResult(
                ok=False,
                stderr=(
                    f"lean not found at '{self._lean_path}' — install Lean 4 "
                    "via `elan default 4.10` or set PROOFLOOP_LEAN"
                ),
                version="",
                available=False,
            )

        with tempfile.TemporaryDirectory(prefix="proofloop-") as tmp:
            src = Path(tmp) / "check.lean"
            src.write_text(proof, encoding="utf-8")
            proc = subprocess.run(
                [self._lean_path, str(src)],
                capture_output=True,
                text=True,
                timeout=120,
            )
        stderr = (proc.stderr or "").strip()
        if proc.returncode != 0 and not stderr:
            stderr = f"lean exited {proc.returncode}"
        return LeanResult(
            ok=proc.returncode == 0,
            stderr=stderr,
            version=self._detect_version(),
            available=True,
        )

    def _detect_version(self) -> str:
        if self._version is not None:
            return self._version
        if shutil.which(self._lean_path) is None:
            self._version = ""
            return self._version
        try:
            proc = subprocess.run(
                [self._lean_path, "--version"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            # `lean --version` prints a single line like
            # "Lean (version 4.10.0, ...)".
            self._version = (proc.stdout or proc.stderr or "").strip().splitlines()[0]
        except (IndexError, subprocess.SubprocessError):
            self._version = ""
        return self._version


class DemoLeanChecker:
    """Stand-in oracle for ``--stub`` runs (no Lean toolchain required).

    It applies the same admit-policy as the real checker and otherwise passes
    a proof that is free of admitted goals. This lets the co-iteration loop run
    end-to-end on a bundled example without an API key or a Lean install.
    """

    VERSION = "lean 4 (stub)"

    def check(self, proof: str) -> LeanResult:
        if has_admit(proof):
            return LeanResult(
                ok=False,
                stderr="error: 'sorry' is not allowed — admitted goals are not proofs",
                version=self.VERSION,
                available=True,
            )
        return LeanResult(ok=True, stderr="", version=self.VERSION, available=True)
