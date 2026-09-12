"""Claims-library and bench-harness tests.

Offline: the loop is driven by the same fake-backend pattern as
tests/test_agent.py. The reference-proof check at the bottom runs only where
a real `lean` is on PATH (skipUnless) — the bundled proofs were
machine-checked against Lean 4.10.0 at build time.
"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

import pytest

from proofloop import agent, bench, lean
from proofloop.agent import Draft

REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY = REPO_ROOT / "examples" / "library.jsonl"


def _fence(draft: Draft) -> str:
    return f"```python\n{draft.code}\n```\n```lean\n{draft.proof}\n```"


class _QueueLLM:
    """Serves drafts from one queue in call order, repeating the last."""

    def __init__(self, drafts: list[Draft]) -> None:
        self._drafts = list(drafts)
        self._i = 0
        self.generate_calls = 0
        self.repair_calls = 0

    def _next(self) -> str:
        idx = min(self._i, len(self._drafts) - 1)
        self._i += 1
        return _fence(self._drafts[idx])

    def generate(self, claim: str) -> str:
        self.generate_calls += 1
        return self._next()

    def repair(self, draft: Draft, error: str) -> str:
        self.repair_calls += 1
        return self._next()


class _FakeLean:
    """Mirrors the admit policy: sorry/admit -> reject, otherwise accept."""

    VERSION = "lean 4 (fake)"

    def check(self, proof: str) -> lean.LeanResult:
        if lean.has_admit(proof):
            return lean.LeanResult(
                ok=False, stderr="error: 'sorry' is not allowed", version=self.VERSION, available=True
            )
        return lean.LeanResult(ok=True, stderr="", version=self.VERSION, available=True)


class _UnavailableLean:
    """Oracle that cannot run at all (e.g. the lean binary is missing)."""

    def check(self, proof: str) -> lean.LeanResult:
        return lean.LeanResult(ok=False, stderr="lean not found", version="", available=False)


_GOOD = Draft(code="def f():\n    return 1", proof="theorem t : True := by trivial")
_BAD = Draft(code="def f():\n    return 1", proof="theorem t : p := by sorry")


# --- load_library -----------------------------------------------------------


def test_load_library_parses_the_bundled_library() -> None:
    claims = bench.load_library(LIBRARY)
    assert len(claims) == 10
    ids = {c.id for c in claims}
    assert "sum_naturals" in ids
    for claim in claims:
        assert claim.claim and claim.code and claim.proof
        assert "sorry" not in claim.proof


def test_load_library_rejects_malformed_lines(tmp_path: Path) -> None:
    lib = tmp_path / "lib.jsonl"
    lib.write_text(
        '{"id": "ok", "claim": "c", "code": "x=1", "proof": "theorem t : True := by trivial"}\n'
        '{"id": "bad", "claim": "c", "code": "x=1"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="2: missing"):
        bench.load_library(lib)


def test_load_library_rejects_non_json_line(tmp_path: Path) -> None:
    lib = tmp_path / "lib.jsonl"
    lib.write_text("not json at all\n", encoding="utf-8")
    with pytest.raises(ValueError, match="1: not valid JSON"):
        bench.load_library(lib)


def test_load_library_rejects_empty_library(tmp_path: Path) -> None:
    lib = tmp_path / "lib.jsonl"
    lib.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no claims"):
        bench.load_library(lib)


# --- run_bench + summarize --------------------------------------------------


def _claims() -> list[bench.Claim]:
    return [
        bench.Claim(id="one-shot", claim="claim A", code="a=1", proof="theorem a : True := by trivial"),
        bench.Claim(id="third-try", claim="claim B", code="b=1", proof="theorem b : True := by trivial"),
        bench.Claim(id="never", claim="claim C", code="c=1", proof="theorem c : True := by trivial"),
    ]


def test_run_bench_summary_statistics() -> None:
    # Queue across the three claims, in order: A good; B bad,bad,good; C bad forever.
    claims = _claims()
    certs = bench.run_bench(
        claims,
        llm=_QueueLLM([_GOOD, _BAD, _BAD, _GOOD, _BAD]),
        lean=_FakeLean(),
        max_iterations=5,
    )
    summary = bench.summarize(claims, certs, backend="fake")
    assert summary["backend"] == "fake"
    assert summary["claims"] == 3
    assert summary["passed"] == 2
    assert summary["success_rate"] == pytest.approx(2 / 3)
    assert summary["mean_iterations"] == pytest.approx((1 + 3 + 5) / 3)
    by_id = {r["id"]: r for r in summary["results"]}
    assert by_id["one-shot"]["proof_passed"] is True
    assert by_id["one-shot"]["iterations"] == 1
    assert by_id["third-try"]["proof_passed"] is True
    assert by_id["third-try"]["iterations"] == 3
    assert by_id["never"]["proof_passed"] is False
    assert by_id["never"]["iterations"] == 5
    assert by_id["one-shot"]["lean_version"] == _FakeLean.VERSION
    assert summary["checked_at"]


def test_run_bench_stops_early_when_oracle_unavailable() -> None:
    claims = _claims()
    certs = bench.run_bench(claims, llm=_QueueLLM([_GOOD]), lean=_UnavailableLean(), max_iterations=8)
    for claim, cert in zip(claims, certs):
        assert cert.proof_passed is False
        assert len(cert.iterations) == 1  # m6 contract holds inside bench too


# --- write_leaderboard --------------------------------------------------------


def test_write_leaderboard_round_trips(tmp_path: Path) -> None:
    claims = _claims()[:1]
    certs = bench.run_bench(claims, llm=_QueueLLM([_GOOD]), lean=_FakeLean(), max_iterations=4)
    summary = bench.summarize(claims, certs, backend="fake")
    path = bench.write_leaderboard(summary, str(tmp_path / "out"))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == summary
    assert data["results"][0]["id"] == "one-shot"


# --- reference proofs vs the real oracle ---------------------------------------


@unittest.skipUnless(shutil.which("lean"), "lean toolchain not on PATH")
def test_library_reference_proofs_type_check() -> None:
    checker = lean.LeanChecker()
    for claim in bench.load_library(LIBRARY):
        result = checker.check(claim.proof)
        assert result.ok, f"{claim.id} did not type-check: {result.stderr}"
