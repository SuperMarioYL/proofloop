"""Prompt templates for the co-iteration loop.

The LLM is asked to emit exactly two fenced blocks — a ``python`` block and a
``lean`` block — which :func:`proofloop.agent.parse_draft` extracts. Keeping the
output contract in one place lets the draft and repair turns share a parser.
"""

from __future__ import annotations

# ``Draft`` appears only in string annotations below (PEP 563), so there is no
# import here — prompts and agent must not form an import cycle.

SYSTEM_PROMPT = """\
You are ProofLoop, a mathematical coding agent.

Given a mathematical claim, you produce TWO artifacts:

1. A Python implementation of the claim, in a fenced ```python block.
2. A Lean 4 theorem statement WITH a complete proof, in a fenced ```lean block.

Hard rules:
- The Lean theorem must state the same claim as the Python code computes.
- The proof must be complete and syntactically valid Lean 4. NEVER use `sorry` \
or `admit` — an admitted goal is not a proof and will be rejected.
- Prefer plain Lean 4 (stdlib only) so the proof checks with a bare `lean` \
invocation. Only reach for Mathlib if the claim genuinely needs it.
- Prefer elementary tactics: `induction`, `simp`, `decide`, `rfl`, `rw`, \
`Nat.*` lemmas.
- Output ONLY the two fenced blocks. No prose, no explanation, no commentary.
"""

REPAIR_SYSTEM_PROMPT = """\
You are ProofLoop, a mathematical coding agent.

The previous Lean proof FAILED to type-check. The Lean compiler error output is \
shown below. Fix the proof so it type-checks under `lean`.

Hard rules:
- NEVER use `sorry` or `admit` — an admitted goal is not a proof.
- Keep the Python block if it was correct; otherwise fix it too.
- Output ONLY the two fenced blocks (```python then ```lean). No prose.
"""


def build_user_prompt(claim: str) -> str:
    return (
        f"Claim: {claim}\n\n"
        "Produce the Python implementation and the Lean 4 theorem with proof."
    )


def build_repair_prompt(draft: "Draft", error: str) -> str:
    return (
        "Previous Lean proof:\n"
        f"```lean\n{draft.proof}\n```\n\n"
        "Previous Python code:\n"
        f"```python\n{draft.code}\n```\n\n"
        "Lean type-check error:\n"
        f"```\n{error}\n```\n\n"
        "Fix the proof so it type-checks. Output the two fenced blocks."
    )
