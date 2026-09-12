"""Tests for the co-iteration loop and its supporting primitives.

These run without an API key, the ``openai`` package, or a Lean toolchain:
the loop is driven by fakes that implement the same backend protocols, and
the ``--stub`` demo path is exercised end-to-end.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofloop import agent, certificate, config, lean
from proofloop.agent import Draft, parse_draft


def _fence(draft: Draft) -> str:
    return f"```python\n{draft.code}\n```\n```lean\n{draft.proof}\n```"


# --- parse_draft -----------------------------------------------------------

def test_parse_draft_extracts_both_blocks() -> None:
    text = (
        "Here you go:\n"
        "```python\nx = 1\n```\n"
        "and the proof:\n"
        "```lean\ntheorem t : True := by trivial\n```\n"
    )
    draft = parse_draft(text)
    assert draft.code == "x = 1"
    assert draft.proof == "theorem t : True := by trivial"


def test_parse_draft_tolerates_either_order_and_extra_whitespace() -> None:
    text = "```lean\nproof here\n```\n\n```python\ncode here\n```"
    draft = parse_draft(text)
    assert draft.proof == "proof here"
    assert draft.code == "code here"


def test_parse_draft_missing_blocks_yield_empty_strings() -> None:
    draft = parse_draft("no fenced blocks at all")
    assert draft == Draft(code="", proof="")


# --- has_admit / admit policy ---------------------------------------------

def test_has_admit_flags_sorry_and_admit() -> None:
    assert lean.has_admit("theorem t : p := by sorry")
    assert lean.has_admit("  admit  ")
    assert not lean.has_admit("theorem t : True := by trivial")


# --- fakes for the loop -----------------------------------------------------

class _FakeLLM:
    """Serves drafts in order, repeating the last when exhausted."""

    def __init__(self, drafts: list[Draft]) -> None:
        self._drafts = list(drafts)
        self._i = 0
        self.generate_calls = 0
        self.repair_calls = 0

    def generate(self, claim: str) -> str:
        self.generate_calls += 1
        return self._next()

    def repair(self, draft: Draft, error: str) -> str:
        self.repair_calls += 1
        return self._next()

    def _next(self) -> str:
        idx = min(self._i, len(self._drafts) - 1)
        self._i += 1
        return _fence(self._drafts[idx])


class _FakeLean:
    """Mirrors the admit-policy: sorry/admit -> reject, otherwise accept."""

    VERSION = "lean 4 (fake)"

    def check(self, proof: str) -> lean.LeanResult:
        if lean.has_admit(proof):
            return lean.LeanResult(
                ok=False, stderr="error: 'sorry' is not allowed", version=self.VERSION, available=True
            )
        return lean.LeanResult(ok=True, stderr="", version=self.VERSION, available=True)


_GOOD = Draft(code="def f():\n    return 1", proof="theorem t : True := by trivial")
_BAD = Draft(code="def f():\n    return 1", proof="theorem t : p := by sorry")


# --- co_iterate ------------------------------------------------------------

def test_co_iterate_converges_after_repair() -> None:
    llm = _FakeLLM([_BAD, _GOOD])
    checker = _FakeLean()
    steps: list[tuple[int, bool]] = []

    cert = agent.co_iterate(
        "a claim",
        llm=llm,
        lean=checker,
        max_iterations=8,
        on_step=lambda i, d, r: steps.append((i, r.ok)),
    )

    assert cert.proof_passed is True
    assert cert.lean_version == _FakeLean.VERSION
    assert len(cert.iterations) == 2
    assert cert.iterations[0].lean_ok is False
    assert cert.iterations[0].lean_stderr  # the oracle error was recorded
    assert cert.iterations[1].lean_ok is True
    # the surviving draft is the good one
    assert cert.code == _GOOD.code
    assert cert.proof == _GOOD.proof
    # the trace callback saw both steps in order
    assert steps == [(1, False), (2, True)]


def test_co_iterate_gives_up_after_max_iter_without_success() -> None:
    llm = _FakeLLM([_BAD])  # always admits the goal
    checker = _FakeLean()

    cert = agent.co_iterate("a claim", llm=llm, lean=checker, max_iterations=3)

    assert cert.proof_passed is False
    assert len(cert.iterations) == 3
    assert all(it.lean_ok is False for it in cert.iterations)
    assert llm.generate_calls == 1
    assert llm.repair_calls == 2  # one generate + (max_iter - 1) repairs = 3 drafts


def test_co_iterate_converges_on_first_draft() -> None:
    llm = _FakeLLM([_GOOD])
    checker = _FakeLean()
    cert = agent.co_iterate("a claim", llm=llm, lean=checker, max_iterations=8)
    assert cert.proof_passed is True
    assert len(cert.iterations) == 1
    assert llm.repair_calls == 0


# --- certificate emit -------------------------------------------------------

def test_emit_writes_three_artifacts(tmp_path: Path) -> None:
    cert = agent.co_iterate(
        "sum of first n naturals", llm=_FakeLLM([_GOOD]), lean=_FakeLean(), max_iterations=4
    )
    lean_path, py_path, cert_path = certificate.emit(cert, str(tmp_path))

    assert lean_path.read_text() == _GOOD.proof + "\n"
    assert py_path.read_text() == _GOOD.code + "\n"
    data = json.loads(cert_path.read_text())
    assert data["claim"] == "sum of first n naturals"
    assert data["proof_passed"] is True
    assert data["lean_version"] == _FakeLean.VERSION
    assert len(data["iterations"]) == 1
    assert data["iterations"][0]["lean_ok"] is True
    assert data["iterations"][0]["code"] == _GOOD.code
    assert data["iterations"][0]["proof"] == _GOOD.proof
    assert "checked_at" in data and data["checked_at"]


def test_emit_creates_out_dir_if_missing(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "deep"
    cert = agent.co_iterate("c", llm=_FakeLLM([_GOOD]), lean=_FakeLean(), max_iterations=4)
    _, _, cert_path = certificate.emit(cert, str(out))
    assert cert_path.exists()


# --- the --stub demo path (end to end) -------------------------------------

def test_demo_backend_converges_with_demo_checker() -> None:
    llm = agent.DemoBackend()
    checker = lean.DemoLeanChecker()
    cert = agent.co_iterate(
        "the sum of the first n naturals is n(n+1)/2",
        llm=llm,
        lean=checker,
        max_iterations=4,
    )
    assert cert.proof_passed is True
    assert len(cert.iterations) == 2  # bad (sorry) -> repair -> good
    assert cert.iterations[0].lean_ok is False
    assert cert.iterations[1].lean_ok is True
    assert "sorry" in cert.iterations[0].proof
    assert "sorry" not in cert.iterations[1].proof
    assert "def sum_naturals" in cert.code or "sum_naturals" in cert.code


# --- config ----------------------------------------------------------------

def test_config_from_env_reads_keys_and_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROOFLOOP_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-key")
    monkeypatch.setenv("PROOFLOOP_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("PROOFLOOP_MODEL", "deepseek-chat")
    monkeypatch.setenv("PROOFLOOP_MAX_ITER", "5")
    monkeypatch.setenv("PROOFLOOP_LEAN", "/usr/local/bin/lean")

    cfg = config.Config.from_env()
    assert cfg.api_key == "fallback-key"
    assert cfg.base_url == "https://api.deepseek.com/v1"
    assert cfg.model == "deepseek-chat"
    assert cfg.max_iterations == 5
    assert cfg.lean_path == "/usr/local/bin/lean"


def test_config_max_iter_falls_back_on_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROOFLOOP_MAX_ITER", "not-a-number")
    cfg = config.Config.from_env()
    assert cfg.max_iterations == config.DEFAULT_MAX_ITER


# --- LeanChecker unavailable path ----------------------------------------

class _UnavailableLean:
    """Oracle that cannot run at all (e.g. the lean binary is missing)."""

    def check(self, proof: str) -> lean.LeanResult:
        return lean.LeanResult(
            ok=False, stderr="lean not found at 'x'", version="", available=False
        )


def test_co_iterate_stops_when_oracle_unavailable() -> None:
    # A repair cannot install a toolchain: the loop must stop after recording
    # the first attempt instead of burning max_iter LLM calls on the same
    # "lean not found" diagnostic (v0.1.0 ran 1 generate + 7 repairs here).
    llm = _FakeLLM([_GOOD])
    cert = agent.co_iterate(
        "a claim", llm=llm, lean=_UnavailableLean(), max_iterations=8
    )
    assert cert.proof_passed is False
    assert len(cert.iterations) == 1
    assert llm.repair_calls == 0
    assert "not found" in cert.iterations[0].lean_stderr


def test_lean_checker_reports_unavailable_for_missing_binary() -> None:
    # A path guaranteed not to exist on PATH, so the check short-circuits to
    # "lean not found" regardless of whether Lean is installed on the host.
    checker = lean.LeanChecker(lean_path="proofloop-no-such-lean-binary-xyz")
    result = checker.check("theorem t : True := by trivial")
    assert result.available is False
    assert result.ok is False
    assert "not found" in result.stderr


def test_lean_checker_rejects_admitted_proofs_before_running() -> None:
    checker = lean.LeanChecker(lean_path="proofloop-no-such-lean-binary-xyz")
    result = checker.check("theorem t : p := by sorry")
    # The admit-policy gate fires before the missing-binary check.
    assert result.ok is False
    assert "admit" in result.stderr.lower()
