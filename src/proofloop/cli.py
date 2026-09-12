"""ProofLoop CLI — ``proofloop prove "<claim>"`` and ``proofloop bench``.

Wires config → LLM backend + Lean oracle → :func:`proofloop.agent.co_iterate`
→ :func:`proofloop.certificate.emit`. With ``--trace`` each draft→error→repair
step is rendered so the user can watch the loop converge. ``bench`` runs the
same loop over a claims library and writes a convergence leaderboard.
"""

from __future__ import annotations

import functools
import textwrap
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__, agent, bench, certificate, config, lean

app = typer.Typer(
    name="proofloop",
    help="Math-coding agent that emits code with machine-checkable Lean proof certificates.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"proofloop {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(  # noqa: B008 — typer option signature
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed ProofLoop version and exit.",
    ),
) -> None:
    """ProofLoop — co-iterate Lean proofs until they type-check."""


def _preview(text: str, limit: int = 4) -> str:
    lines = text.splitlines()
    if len(lines) <= limit:
        return textwrap.indent(text, "  ")
    shown = "\n".join(lines[:limit])
    return textwrap.indent(f"{shown}\n  … ({len(lines) - limit} more lines)", "  ")


def _co_iterate(
    claim: str,
    *,
    llm: agent.LLMBackend,
    lean: lean.LeanBackend,
    max_iterations: int,
    on_step: agent.StepCallback | None = None,
    endpoint: str,
) -> certificate.ProofCertificate:
    """Run the loop, mapping LLM transport failures to the CLI error contract.

    An unreachable endpoint, a rejected key or a wrong model name must surface
    as one clean ``error:`` line + exit 2 — like every other CLI error — not a
    raw openai/httpx traceback.
    """
    try:
        from openai import OpenAIError  # deferred: not needed for --stub or tests
    except ImportError:  # openai is a declared dependency; guard exotic envs only
        OpenAIError = ()  # type: ignore[assignment]

    try:
        return agent.co_iterate(
            claim, llm=llm, lean=lean, max_iterations=max_iterations, on_step=on_step
        )
    except OpenAIError as exc:  # type: ignore[misc]
        console.print(f"[red]error[/]: LLM request to {endpoint} failed: {exc}")
        raise typer.Exit(code=2) from exc


@app.command()
def prove(
    claim: str = typer.Argument(..., help="The mathematical claim to implement and prove."),
    trace: bool = typer.Option(
        False, "--trace", help="Render each draft -> error -> repair step as it happens."
    ),
    stub: bool = typer.Option(
        False,
        "--stub",
        help="Use the bundled canned responses (no API key, no Lean) to try the loop shape.",
    ),
    max_iter: Optional[int] = typer.Option(
        None,
        "--max-iter",
        min=1,
        max=64,
        help="Maximum co-iteration attempts (default: PROOFLOOP_MAX_ITER, else 8).",
    ),
    out_dir: Optional[str] = typer.Option(
        None,
        "--out-dir",
        help="Directory for out.lean / out.py / certificate.json (default: PROOFLOOP_OUT_DIR, else .).",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="Override PROOFLOOP_MODEL (e.g. gpt-4o-mini, deepseek-chat)."
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", help="Override PROOFLOOP_BASE_URL (OpenAI-compatible endpoint)."
    ),
    lean_path: Optional[str] = typer.Option(
        None, "--lean", help="Override the `lean` binary path (default: PROOFLOOP_LEAN, else lean on PATH)."
    ),
) -> None:
    """Generate code + a Lean proof for CLAIM, iterating until the proof type-checks."""
    cfg = config.Config.from_env()
    iterations = max_iter if max_iter is not None else cfg.max_iterations
    out = out_dir or cfg.out_dir
    eff_model = model or cfg.model
    eff_base_url = base_url or cfg.base_url
    eff_lean = lean_path or cfg.lean_path

    if stub:
        llm: agent.LLMBackend = agent.DemoBackend()
        lean_checker: lean.LeanBackend = lean.DemoLeanChecker()
        backend_label = "demo (stub)"
    else:
        if not cfg.api_key:
            console.print(
                "[red]error[/]: no API key. Set [bold]PROOFLOOP_API_KEY[/] "
                "(or OPENAI_API_KEY), or run with [bold]--stub[/] to try the loop "
                "without a key."
            )
            raise typer.Exit(code=2)
        llm = agent.LLMClient(api_key=cfg.api_key, base_url=eff_base_url, model=eff_model)
        lean_checker = lean.LeanChecker(lean_path=eff_lean)
        backend_label = eff_model

    def on_step(idx: int, draft: agent.Draft, result: lean.LeanResult) -> None:
        status = "[green]✓ type-checks[/]" if result.ok else "[red]✗ rejected[/]"
        body_parts = [
            f"[bold]oracle[/]: {result.version or 'lean'}",
            f"[bold]proof draft[/]:\n{_preview(draft.proof)}",
        ]
        if result.stderr:
            body_parts.append(f"[bold]stderr[/]:\n{textwrap.indent(result.stderr, '  ')}")
        console.print(
            Panel(
                "\n\n".join(body_parts),
                title=f"iteration {idx} — {status}",
                border_style="blue",
            )
        )

    cert = _co_iterate(
        claim,
        llm=llm,
        lean=lean_checker,
        max_iterations=iterations,
        on_step=on_step if trace else None,
        endpoint=f"{eff_model} at {eff_base_url}",
    )
    cert.model = backend_label

    paths = certificate.emit(cert, out)

    if cert.proof_passed:
        console.print(
            f"[green]✓ proof passed[/] after {len(cert.iterations)} iteration(s) "
            f"— checked by {cert.lean_version or 'lean'}."
        )
    else:
        console.print(
            f"[red]✗ proof did not type-check[/] after {len(cert.iterations)} "
            "iteration(s). certificate.json records the last error."
        )
    console.print(f"  out.lean       : {paths[0]}")
    console.print(f"  out.py         : {paths[1]}")
    console.print(f"  certificate    : {paths[2]}")


@app.command("bench")
def bench_command(
    library: str = typer.Option(
        "examples/library.jsonl",
        "--library",
        help="Claims library JSONL (id, claim, code, proof per line).",
    ),
    stub: bool = typer.Option(
        False,
        "--stub",
        help="Use the bundled canned responses (no API key, no Lean) to exercise the harness.",
    ),
    max_iter: Optional[int] = typer.Option(
        None,
        "--max-iter",
        min=1,
        max=64,
        help="Maximum co-iteration attempts per claim (default: PROOFLOOP_MAX_ITER, else 8).",
    ),
    out_dir: Optional[str] = typer.Option(
        None,
        "--out-dir",
        help="Directory for leaderboard.json (default: PROOFLOOP_OUT_DIR, else .).",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="Override PROOFLOOP_MODEL (e.g. gpt-4o-mini, deepseek-chat)."
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", help="Override PROOFLOOP_BASE_URL (OpenAI-compatible endpoint)."
    ),
    lean_path: Optional[str] = typer.Option(
        None, "--lean", help="Override the `lean` binary path (default: PROOFLOOP_LEAN, else lean on PATH)."
    ),
) -> None:
    """Run the co-iteration loop over a claims library and write a convergence leaderboard.

    Real runs call the configured LLM once per draft/repair for every claim —
    budget accordingly. Use --stub for an offline demo of the harness (the
    leaderboard then reflects the bundled canned responses, not real
    convergence).
    """
    cfg = config.Config.from_env()
    iterations = max_iter if max_iter is not None else cfg.max_iterations
    out = out_dir or cfg.out_dir
    eff_model = model or cfg.model
    eff_base_url = base_url or cfg.base_url
    eff_lean = lean_path or cfg.lean_path

    if stub:
        llm: agent.LLMBackend = agent.DemoBackend()
        lean_checker: lean.LeanBackend = lean.DemoLeanChecker()
        backend_label = "demo (stub)"
    else:
        if not cfg.api_key:
            console.print(
                "[red]error[/]: no API key. Set [bold]PROOFLOOP_API_KEY[/] "
                "(or OPENAI_API_KEY), or run with [bold]--stub[/] to try the loop "
                "without a key."
            )
            raise typer.Exit(code=2)
        llm = agent.LLMClient(api_key=cfg.api_key, base_url=eff_base_url, model=eff_model)
        lean_checker = lean.LeanChecker(lean_path=eff_lean)
        backend_label = eff_model

    try:
        claims = bench.load_library(library)
    except (OSError, ValueError) as exc:
        console.print(f"[red]error[/]: cannot load claims library: {exc}")
        raise typer.Exit(code=2) from exc

    rows = bench.run_bench(
        claims,
        llm=llm,
        lean=lean_checker,
        max_iterations=iterations,
        iterate=functools.partial(_co_iterate, endpoint=f"{eff_model} at {eff_base_url}"),
    )
    summary = bench.summarize(claims, rows, backend=backend_label)
    leaderboard = bench.write_leaderboard(summary, out)

    table = Table(title=f"ProofLoop bench — {summary['passed']}/{summary['claims']} converged")
    table.add_column("claim", style="bold")
    table.add_column("passed")
    table.add_column("iterations", justify="right")
    table.add_column("checker")
    for result in summary["results"]:
        table.add_row(
            result["id"],
            "[green]✓[/]" if result["proof_passed"] else "[red]✗[/]",
            str(result["iterations"]),
            result["lean_version"] or "lean",
        )
    console.print(table)
    console.print(
        f"  success rate  : {summary['passed']}/{summary['claims']} "
        f"({summary['success_rate']:.0%})"
    )
    console.print(f"  mean iters    : {summary['mean_iterations']:.2f}")
    console.print(f"  backend       : {backend_label}")
    console.print(f"  leaderboard   : {leaderboard}")


if __name__ == "__main__":
    app()
