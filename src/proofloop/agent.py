"""The co-iteration loop — ProofLoop's core primitive.

The agent drafts code + Lean proof in one shot, hands the proof to the Lean
oracle, and on failure feeds the oracle's error back to the model for another
draft. Lean is the compiler the loop iterates against; the model never gets to
self-certify. :func:`co_iterate` is the single place that owns this loop.

Backends are injectable so the loop can be driven by a real OpenAI-compatible
endpoint (:class:`LLMClient`), by the bundled canned responses used for
``--stub`` demos (:class:`DemoBackend`), or by fakes in the test suite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Protocol

from . import prompts
from .certificate import (
    Iteration,
    ProofCertificate,
    build_iteration,
)
from .lean import LeanResult

# Fenced-block extraction. The prompt contract is exactly one ```python and
# one ```lean block; we tolerate either order and extra whitespace.
_CODE_RE = re.compile(r"```python[ \t]*\n(.*?)```", re.DOTALL)
_LEAN_RE = re.compile(r"```lean[ \t]*\n(.*?)```", re.DOTALL)


@dataclass
class Draft:
    """One model draft: a Python implementation paired with a Lean proof."""

    code: str
    proof: str


def parse_draft(text: str) -> Draft:
    """Split a model response into its code and Lean proof blocks.

    A missing block yields an empty string, which the Lean oracle will reject
    (empty proof → not a valid certificate), keeping the loop honest.
    """
    code_match = _CODE_RE.search(text)
    lean_match = _LEAN_RE.search(text)
    code = code_match.group(1).strip() if code_match else ""
    proof = lean_match.group(1).strip() if lean_match else ""
    return Draft(code=code, proof=proof)


class LLMBackend(Protocol):
    """What the loop needs from a model: a first draft and a repair draft."""

    def generate(self, claim: str) -> str: ...
    def repair(self, draft: Draft, error: str) -> str: ...


class LeanBackend(Protocol):
    """What the loop needs from the oracle: a verdict on one proof."""

    def check(self, proof: str) -> LeanResult: ...


StepCallback = Callable[[int, Draft, LeanResult], None]


def co_iterate(
    claim: str,
    *,
    llm: LLMBackend,
    lean: LeanBackend,
    max_iterations: int = 8,
    on_step: StepCallback | None = None,
) -> ProofCertificate:
    """Run the draft → check → repair loop until Lean type-checks or budget runs out.

    On success the returned certificate has ``proof_passed=True`` (asserted
    *only* because the oracle returned ``ok``). On exhaustion the certificate
    still records every attempt so the user can see what failed. An oracle
    that could not run at all (``available=False``, e.g. lean missing) is
    terminal — a repair cannot install a toolchain — so the loop stops after
    recording that attempt instead of burning the budget on repairs.
    """
    iterations: list[Iteration] = []

    raw = llm.generate(claim)
    draft = parse_draft(raw)
    result = lean.check(draft.proof)
    iterations.append(build_iteration(result, draft.code, draft.proof))
    if on_step is not None:
        on_step(1, draft, result)

    steps = 1
    while not result.ok and result.available and steps < max_iterations:
        raw = llm.repair(draft, result.stderr)
        draft = parse_draft(raw)
        result = lean.check(draft.proof)
        iterations.append(build_iteration(result, draft.code, draft.proof))
        steps += 1
        if on_step is not None:
            on_step(steps, draft, result)

    return ProofCertificate(
        claim=claim,
        code=draft.code,
        proof=draft.proof,
        lean_version=result.version,
        proof_passed=result.ok,
        iterations=iterations,
    )


class LLMClient:
    """OpenAI-compatible backend (OpenAI, DeepSeek, GLM, Qwen via ``base_url``).

    The ``openai`` import is deferred to call time so the package imports and
    the test suite run without the dependency installed (tests inject fakes).
    """

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from openai import OpenAI  # deferred: not needed for --stub or tests

            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def _complete(self, system: str, user: str) -> str:
        resp = self._ensure_client().chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    def generate(self, claim: str) -> str:
        return self._complete(prompts.SYSTEM_PROMPT, prompts.build_user_prompt(claim))

    def repair(self, draft: Draft, error: str) -> str:
        return self._complete(
            prompts.REPAIR_SYSTEM_PROMPT,
            prompts.build_repair_prompt(draft, error),
        )


# --- bundled demo content (for --stub) -------------------------------------
# The canonical example: the sum of the first n naturals equals n*(n+1)/2.
# This is the same claim shipped in examples/sum_naturals.{lean,py}. The bad
# draft leaves the goal admitted (`sorry`), which the oracle rejects; the repair
# draft supplies the real proof. No network or Lean toolchain is needed.

_DEMO_PY = (
    "def sum_naturals(n: int) -> int:\n"
    '    """Sum of the first n naturals 1 + 2 + ... + n; equals n*(n+1)//2."""\n'
    "    return n * (n + 1) // 2\n"
)

_DEMO_LEAN_BAD = (
    "-- Claim: the sum of the first n naturals 1 + 2 + ... + n equals n*(n+1)/2.\n"
    "-- Equivalently, 2 * (1 + 2 + ... + n) = n * (n + 1).\n"
    "def sumTo : Nat → Nat\n"
    "  | 0 => 0\n"
    "  | n + 1 => sumTo n + (n + 1)\n"
    "\n"
    "theorem sum_naturals (n : Nat) : 2 * sumTo n = n * (n + 1) := by\n"
    "  sorry\n"
)

_DEMO_LEAN_GOOD = (
    "-- Claim: the sum of the first n naturals 1 + 2 + ... + n equals n*(n+1)/2.\n"
    "-- Equivalently, 2 * (1 + 2 + ... + n) = n * (n + 1).\n"
    "def sumTo : Nat → Nat\n"
    "  | 0 => 0\n"
    "  | n + 1 => sumTo n + (n + 1)\n"
    "\n"
    "theorem sum_naturals (n : Nat) : 2 * sumTo n = n * (n + 1) := by\n"
    "  induction n with\n"
    "  | zero => rfl\n"
    "  | succ k ih =>\n"
    "    show 2 * (sumTo k + (k + 1)) = (k + 1) * (k + 1 + 1)\n"
    "    rw [Nat.mul_add, ih, show (k + 1 + 1) = (k + 2) from rfl,\n"
    "        Nat.mul_add (k + 1) k 2, Nat.mul_comm (k + 1) k,\n"
    "        Nat.mul_comm (k + 1) 2]\n"
)


def _fence(lang: str, body: str) -> str:
    return f"```{lang}\n{body}\n```\n"


class DemoBackend:
    """Canned LLM backend for ``--stub`` runs.

    Produces a draft that admits the goal, then a repair draft with the real
    proof — so the co-iteration loop converges in two steps without any API
    key. Only the bundled sum_naturals example is supported; the claim is
    echoed into a comment so the run reads naturally.
    """

    def __init__(self) -> None:
        self._repaired = False

    def generate(self, claim: str) -> str:
        self._repaired = False
        return _fence("python", _DEMO_PY) + _fence("lean", _DEMO_LEAN_BAD)

    def repair(self, draft: Draft, error: str) -> str:
        self._repaired = True
        return _fence("python", _DEMO_PY) + _fence("lean", _DEMO_LEAN_GOOD)
