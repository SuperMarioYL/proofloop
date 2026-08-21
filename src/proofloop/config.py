"""Configuration for ProofLoop, loaded from environment variables.

ProofLoop speaks to any OpenAI-compatible endpoint (OpenAI, DeepSeek, GLM,
Qwen) so it can be driven by the provider the user already has a key for.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_LEAN = "lean"
DEFAULT_MAX_ITER = 8
DEFAULT_OUT_DIR = "."

# Environment variables that toggle the LLM endpoint. Documented in the README
# config table; keep the names here as the single source of truth for the CLI.
ENV_API_KEY = "PROOFLOOP_API_KEY"
ENV_FALLBACK_KEY = "OPENAI_API_KEY"
ENV_BASE_URL = "PROOFLOOP_BASE_URL"
ENV_MODEL = "PROOFLOOP_MODEL"
ENV_LEAN = "PROOFLOOP_LEAN"
ENV_MAX_ITER = "PROOFLOOP_MAX_ITER"
ENV_OUT_DIR = "PROOFLOOP_OUT_DIR"


@dataclass(frozen=True)
class Config:
    """Resolved ProofLoop configuration.

    ``api_key`` is ``None`` when neither ``PROOFLOOP_API_KEY`` nor
    ``OPENAI_API_KEY`` is set; the CLI surfaces this as a hard error before
    any network call unless ``--stub`` is requested.
    """

    api_key: str | None
    base_url: str
    model: str
    lean_path: str
    max_iterations: int
    out_dir: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        e = env if env is not None else os.environ
        raw_iter = e.get(ENV_MAX_ITER, str(DEFAULT_MAX_ITER))
        try:
            max_iterations = int(raw_iter)
        except ValueError:
            max_iterations = DEFAULT_MAX_ITER
        return cls(
            api_key=e.get(ENV_API_KEY) or e.get(ENV_FALLBACK_KEY),
            base_url=e.get(ENV_BASE_URL, DEFAULT_BASE_URL),
            model=e.get(ENV_MODEL, DEFAULT_MODEL),
            lean_path=e.get(ENV_LEAN, DEFAULT_LEAN),
            max_iterations=max_iterations,
            out_dir=e.get(ENV_OUT_DIR, DEFAULT_OUT_DIR),
        )
