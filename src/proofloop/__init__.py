"""ProofLoop — a math-coding agent that emits code with machine-checkable Lean proof certificates.

Importing this package is intentionally dependency-free: the optional
``openai`` / ``typer`` / ``rich`` imports live behind the modules that need
them, so ``import proofloop`` (and the test suite) work without them.
"""

from __future__ import annotations

__version__ = "0.2.0"

__all__ = ["__version__"]
