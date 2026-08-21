"""ProofLoop bundled example — the sum of the first n naturals.

Reference implementation matching ``examples/sum_naturals.lean``.

    >>> sum_naturals(10)
    55
    >>> sum_naturals(100)
    5050
"""


def sum_naturals(n: int) -> int:
    """Return the sum of the first n naturals 1 + 2 + ... + n.

    Equals n*(n+1)//2, the closed form proved in the sibling Lean file.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    return n * (n + 1) // 2


if __name__ == "__main__":
    for n in (0, 1, 10, 100):
        print(f"sum_naturals({n}) = {sum_naturals(n)}")
