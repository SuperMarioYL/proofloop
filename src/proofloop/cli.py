"""ProofLoop CLI — ``proofloop prove "<claim>"``.

Wires config → LLM backend + Lean oracle → :func:`proofloop.agent.co_iterate`
→ :func:`proofloop.certificate.emit`. With ``--trace`` each draft→error→repair
step is rendered so the user can watch the loop converge.
"""

from __future__ import annotations

import textwrap
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from . import __version__, agent, certificate, config, lean

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
    max_iter: int = typer.Option(
        8, "--max-iter", min=1, max=64, help="Maximum co-iteration attempts before giving up."
    ),
    out_dir: str = typer.Option(
        ".", "--out-dir", help="Directory for out.lean / out.py / certificate.json."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="Override PROOFLOOP_MODEL (e.g. gpt-4o-mini, deepseek-chat)."
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", help="Override PROOFLOOP_BASE_URL (OpenAI-compatible endpoint)."
    ),
    lean_path: Optional[str] = typer.Option(
        None, "--lean", help="Override the `lean` binary path (default: lean on PATH)."
    ),
) -> None:
    """Generate code + a Lean proof for CLAIM, iterating until the proof type-checks."""
    cfg = config.Config.from_env()
    eff_model = model or cfg.model
    eff_base_url = base_url or cfg.base_url
    eff_lean = lean_path or cfg.lean_path
    out = out_dir or cfg.out_dir

    if stub:
        llm: agent.LLMBackend = agent.DemoBackend()
        lean_checker: lean.LeanBackend = lean.DemoLeanChecker()
        cert_model = "demo (stub)"
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
        cert_model = eff_model

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

    cert = agent.co_iterate(
        claim,
        llm=llm,
        lean=lean_checker,
        max_iterations=max_iter,
        on_step=on_step if trace else None,
    )
    cert.model = cert_model

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


if __name__ == "__main__":
    app()
