"""CLI contract tests — option/env wiring, error contracts, path handling.

Run through typer.testing.CliRunner with the --stub backends or a refused
loopback endpoint: no API key, no Lean toolchain, no reachable network.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

from typer.testing import CliRunner

from proofloop import lean as lean_mod
from proofloop.cli import app

runner = CliRunner()

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_cert(cwd: Path) -> dict:
    return json.loads((cwd / "certificate.json").read_text(encoding="utf-8"))


# --- documented env overrides are honored (v0.1.0 ignored both) ------------


def test_prove_honors_proofloop_max_iter_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PROOFLOOP_MAX_ITER", "1")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["prove", "a claim", "--stub"])
    assert result.exit_code == 0
    cert = _read_cert(tmp_path)
    assert len(cert["iterations"]) == 1  # v0.1.0: 2 — the env cap was ignored
    assert cert["proof_passed"] is False  # v0.1.0: True — the sorry draft "converged"


def test_prove_honors_proofloop_out_dir_env(tmp_path: Path, monkeypatch) -> None:
    expected = tmp_path / "expected"
    monkeypatch.setenv("PROOFLOOP_OUT_DIR", str(expected))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["prove", "a claim", "--stub"])
    assert result.exit_code == 0
    assert (expected / "certificate.json").exists()  # v0.1.0: written to the CWD
    assert not (tmp_path / "certificate.json").exists()


def test_prove_flag_overrides_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PROOFLOOP_MAX_ITER", "1")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["prove", "a claim", "--stub", "--max-iter", "3"])
    assert result.exit_code == 0
    cert = _read_cert(tmp_path)
    assert len(cert["iterations"]) == 2  # flag wins: the stub demo converges in 2
    assert cert["proof_passed"] is True


# --- clean error contract ----------------------------------------------------


def test_prove_without_api_key_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("PROOFLOOP_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = runner.invoke(app, ["prove", "a claim"])
    assert result.exit_code == 2
    assert "no API key" in result.output


def test_prove_unreachable_endpoint_is_clean_error(tmp_path: Path, monkeypatch) -> None:
    # Loopback port 1: nothing listens, connection refused instantly.
    # v0.1.0 dumped a raw openai/httpx traceback and exited 1.
    monkeypatch.setenv("PROOFLOOP_API_KEY", "dummy")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["prove", "a claim", "--base-url", "http://127.0.0.1:1"])
    assert result.exit_code == 2
    assert "error:" in result.output
    assert "127.0.0.1:1" in result.output
    assert "Traceback" not in result.output
    assert not (tmp_path / "certificate.json").exists()


# --- tilde path expansion -----------------------------------------------------


def _fake_lean_script(home: Path) -> None:
    bindir = home / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    script = bindir / "lean"
    script.write_text("#!/bin/sh\necho 'Lean (version 4.10.0, test)'\nexit 0\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_lean_checker_expands_tilde(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _fake_lean_script(tmp_path)
    checker = lean_mod.LeanChecker("~/bin/lean")  # v0.1.0: "lean not found"
    result = checker.check("theorem t : True := by trivial")
    assert result.available is True
    assert result.ok is True
    assert result.version.startswith("Lean (version 4.10.0")


def test_prove_out_dir_expands_tilde(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["prove", "a claim", "--stub", "--out-dir", "~/proofs"])
    assert result.exit_code == 0
    # v0.1.0 created a literal './~' directory next to the CWD instead.
    assert (tmp_path / "proofs" / "certificate.json").exists()
    assert not (tmp_path / "~").exists()


# --- bench ----------------------------------------------------------------------


def test_bench_stub_writes_leaderboard(tmp_path: Path) -> None:
    out = tmp_path / "bench-out"
    result = runner.invoke(
        app,
        [
            "bench",
            "--stub",
            "--out-dir",
            str(out),
            "--library",
            str(_REPO_ROOT / "examples" / "library.jsonl"),
        ],
    )
    assert result.exit_code == 0
    data = json.loads((out / "leaderboard.json").read_text(encoding="utf-8"))
    assert data["backend"] == "demo (stub)"
    assert data["claims"] == 10
    assert data["passed"] == 10
    assert data["mean_iterations"] == 2.0
    assert len(data["results"]) == 10
    assert {r["proof_passed"] for r in data["results"]} == {True}


def test_bench_default_library_ships_in_repo() -> None:
    assert (_REPO_ROOT / "examples" / "library.jsonl").exists()


def test_bench_rejects_malformed_library(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"id": "x", "claim": "c", "code": "x=1"}\n', encoding="utf-8")
    result = runner.invoke(app, ["bench", "--stub", "--library", str(bad)])
    assert result.exit_code == 2
    assert "error:" in result.output
    assert "proof" in result.output
