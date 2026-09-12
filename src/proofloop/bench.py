"""Convergence benchmark over a claims library — the m3 first slice.

A claims library is a JSONL file where each line is one theorem:
``{"id": ..., "claim": ..., "code": ..., "proof": ...}``. The bundled
``examples/library.jsonl`` reference proofs are machine-checked against Lean
at build time; :func:`run_bench` measures how the co-iteration loop converges
on the same claims with a configured backend, and the leaderboard records
what the oracle — not the model — accepted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import agent
from .agent import LeanBackend
from .certificate import ProofCertificate

_REQUIRED_FIELDS = ("id", "claim", "code", "proof")


@dataclass(frozen=True)
class Claim:
    """One library entry: a claim with its reference implementation and proof."""

    id: str
    claim: str
    code: str
    proof: str


def load_library(path: str | Path) -> list[Claim]:
    """Parse a claims library JSONL file.

    Every line must be a JSON object with non-empty ``id``, ``claim``,
    ``code`` and ``proof`` fields; a malformed line aborts the load with the
    offending line number so a hand-edited library fails loudly.
    """
    file = Path(path)
    try:
        text = file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{path}: cannot read claims library ({exc})") from exc

    claims: list[Claim] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: not valid JSON ({exc.msg})") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{lineno}: expected a JSON object")
        missing = [k for k in _REQUIRED_FIELDS if not str(row.get(k) or "").strip()]
        if missing:
            raise ValueError(f"{path}:{lineno}: missing field(s): {', '.join(missing)}")
        claims.append(
            Claim(
                id=str(row["id"]),
                claim=str(row["claim"]),
                code=str(row["code"]),
                proof=str(row["proof"]),
            )
        )
    if not claims:
        raise ValueError(f"{path}: no claims found")
    return claims


def run_bench(
    claims: list[Claim],
    *,
    llm: agent.LLMBackend,
    lean: LeanBackend,
    max_iterations: int = 8,
    iterate: Callable[..., ProofCertificate] = agent.co_iterate,
) -> list[ProofCertificate]:
    """Run the co-iteration loop over every claim, one certificate per claim.

    ``iterate`` defaults to :func:`agent.co_iterate`; the CLI injects its
    transport-error wrapper so LLM failures surface as clean CLI errors
    instead of raw tracebacks.
    """
    return [
        iterate(c.claim, llm=llm, lean=lean, max_iterations=max_iterations) for c in claims
    ]


def summarize(
    claims: list[Claim],
    certs: list[ProofCertificate],
    *,
    backend: str,
) -> dict:
    """Fold per-claim certificates into the leaderboard summary."""
    n = len(claims)
    passed = sum(1 for cert in certs if cert.proof_passed)
    total_iterations = sum(len(cert.iterations) for cert in certs)
    return {
        "backend": backend,
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "claims": n,
        "passed": passed,
        "success_rate": (passed / n) if n else 0.0,
        "mean_iterations": (total_iterations / n) if n else 0.0,
        "results": [
            {
                "id": claim.id,
                "claim": claim.claim,
                "proof_passed": cert.proof_passed,
                "iterations": len(cert.iterations),
                "lean_version": cert.lean_version,
            }
            for claim, cert in zip(claims, certs)
        ],
    }


def write_leaderboard(summary: dict, out_dir: str = ".") -> Path:
    """Write the leaderboard JSON into ``out_dir`` and return its path."""
    base = Path(out_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    path = base / "leaderboard.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
