/-!
  ProofLoop bundled example — the sum of the first n naturals.

  Claim: the sum of the first n naturals 1 + 2 + ... + n equals n*(n+1)/2.
  Equivalently, 2 * (1 + 2 + ... + n) = n * (n + 1).

  This file is the reference proof the agent aims to produce. It type-checks
  under bare `lean` (no Mathlib dependency) — exactly what ProofLoop's
  co-iteration loop converges to and writes to `out.lean`.
-/

/-- Sum of 1 + 2 + ... + n (the first n positive naturals). -/
def sumTo : Nat → Nat
  | 0 => 0
  | n + 1 => sumTo n + (n + 1)

theorem sum_naturals (n : Nat) : 2 * sumTo n = n * (n + 1) := by
  induction n with
  | zero => rfl
  | succ k ih =>
    show 2 * (sumTo k + (k + 1)) = (k + 1) * (k + 1 + 1)
    rw [Nat.mul_add, ih, show (k + 1 + 1) = (k + 2) from rfl,
        Nat.mul_add (k + 1) k 2, Nat.mul_comm (k + 1) k,
        Nat.mul_comm (k + 1) 2]
