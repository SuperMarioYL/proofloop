# Changelog

## [0.2.0] - 2026-09-12

### Fixed

- `PROOFLOOP_OUT_DIR` and `PROOFLOOP_MAX_ITER` are now honored by the CLI (explicit `--out-dir` / `--max-iter` flags override them). v0.1.0's option defaults silently shadowed both documented env vars: artifacts were written to the CWD and the iteration cap was ignored.
- `proofloop prove` against an unreachable or rejecting LLM endpoint now prints one clean `error:` line and exits 2 instead of dumping a raw openai/httpx traceback with exit 1.
- The co-iteration loop stops after the first attempt when the Lean oracle cannot run at all (e.g. `lean` missing). A repair cannot install a toolchain; v0.1.0 burned the full `--max-iter` budget of paid API calls feeding the same "lean not found" diagnostic back to the model.
- `~` in `--lean` / `PROOFLOOP_LEAN` and `--out-dir` is now expanded: a working lean binary under `~` is no longer reported "not found", and `--out-dir '~/proofs'` no longer creates a literal `./~` directory next to the CWD.
- The README quickstart installs this product: `uvx --from git+https://github.com/SuperMarioYL/proofloop proofloop …`. PyPI hosts an unrelated project named `proofloop` (Knowlytix agentic-AI testing, no console scripts), so the bare `uvx proofloop` form used by v0.1.0 installed foreign software and failed on clean machines.

### Added

- `examples/library.jsonl` — a claims library of 10 classic theorems (`id` / `claim` / Python `code` / Lean `proof`). Every reference proof type-checks under Lean 4.10.0; the test suite re-verifies them wherever `lean` is on PATH.
- `proofloop bench [--library PATH] [--stub] [--out-dir DIR] [--max-iter N]` — runs the co-iteration loop over a claims library and writes `leaderboard.json` (per-claim `proof_passed` + `iterations`; summary success rate / mean iterations / backend / checked_at). The leaderboard is generated per run; no real-LLM numbers are checked into the repo.

### Changed

- Version surfaces (pyproject.toml, `proofloop.__version__`, web/site.json `meta.content_version`) lockstep at 0.2.0.

## [0.1.0] - 2026-08-21

Initial release: `proofloop prove "<claim>"` co-iterates Python + Lean 4 drafts against the `lean` oracle (admit policy, per-iteration trace, `--trace` rendering), writes `out.lean` / `out.py` / `certificate.json`, and ships an offline `--stub` demo path.
