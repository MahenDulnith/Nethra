#!/usr/bin/env python3
"""
Wilson score interval. Needed because the project's most important rates
are near zero, and "0 errors in 25 trials" is not a zero error rate.

Reproduces the master-spec figure: 0/25 bounds the error rate below ~12%.
"""
import math


def wilson(successes: int, n: int, z: float = 1.96):
    """Returns (point, lower, upper) for a proportion."""
    if n == 0:
        return 0.0, 0.0, 1.0
    p = successes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


def rule_of_three(n: int) -> float:
    """Upper bound on a rate after n trials with ZERO observed events."""
    return 3.0 / n if n else 1.0


def describe(successes: int, n: int, label: str = "rate") -> str:
    p, lo, hi = wilson(successes, n)
    s = f"{label}: {successes}/{n} = {p*100:.2f}%  (95% CI {lo*100:.2f}%–{hi*100:.2f}%)"
    if successes == 0:
        s += f"\n  zero observed in {n} trials bounds the true rate below " \
             f"{rule_of_three(n)*100:.1f}% — NOT zero"
    return s


if __name__ == "__main__":
    print(describe(0, 25, "false-match rate"))
    print()
    print(describe(0, 2000, "false-match rate"))
