"""The proof certificate — the primitive ProofLoop emits.

A ``ProofCertificate`` is the durable artifact: it carries the claim, the
generated code, the proof source, the Lean version that checked it, the
per-iteration trace, and ``proof_passed`` which is asserted *only* after Lean
exits 0. :func:`emit` writes the three on-disk artifacts (``out.lean``,
``out.py``, ``certificate.json``).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .lean import LeanResult


def _now_iso8601() -> str:
    # ISO 8601, UTC, second precision — stable across runs for replay.
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Iteration:
    """One round of the co-iteration loop: a draft and the oracle's verdict."""

    code: str
    proof: str
    lean_ok: bool
    lean_stderr: str


@dataclass
class ProofCertificate:
    """The full record of one ``proofloop prove`` run."""

    claim: str
    code: str
    proof: str
    lean_version: str
    proof_passed: bool
    iterations: list[Iteration] = field(default_factory=list)
    checked_at: str = ""
    model: str = ""

    def __post_init__(self) -> None:
        if not self.checked_at:
            self.checked_at = _now_iso8601()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Stable, human-friendly key ordering for the on-disk JSON.
        ordered: dict[str, Any] = {k: data[k] for k in (
            "claim",
            "proof_passed",
            "lean_version",
            "checked_at",
            "model",
            "code",
            "proof",
            "iterations",
        )}
        return ordered


def _iteration_from(lean_result: LeanResult, code: str, proof: str) -> Iteration:
    return Iteration(
        code=code,
        proof=proof,
        lean_ok=lean_result.ok,
        lean_stderr=lean_result.stderr,
    )


# Exposed for the agent module to build iterations without coupling to the
# private constructor shape.
build_iteration: Callable[..., Iteration] = _iteration_from


def emit(cert: ProofCertificate, out_dir: str = ".") -> tuple[Path, Path, Path]:
    """Write ``out.lean``, ``out.py``, ``certificate.json`` into ``out_dir``.

    Returns the three written paths so the CLI can report them.
    """
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    lean_path = base / "out.lean"
    py_path = base / "out.py"
    cert_path = base / "certificate.json"

    lean_path.write_text(cert.proof + ("\n" if cert.proof and not cert.proof.endswith("\n") else ""), encoding="utf-8")
    py_path.write_text(cert.code + ("\n" if cert.code and not cert.code.endswith("\n") else ""), encoding="utf-8")
    cert_path.write_text(
        json.dumps(cert.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return lean_path, py_path, cert_path
