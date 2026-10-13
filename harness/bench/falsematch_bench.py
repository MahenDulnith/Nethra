#!/usr/bin/env python3
"""
D1.8 — pairwise false-match rate WITH a confidence interval.

Measured over COMPARISON PAIRS, not subject counts. With k people and m
samples each you get k*m*(m-1)/2 genuine pairs and far more impostor pairs,
which is how you get a denominator large enough to say anything.

Input: a directory of .npy embedding files named <person>_<n>.npy,
exported from the device, or produced by running the ONNX model on a
consented volunteer image set on the laptop.

Usage:
  python3 harness/bench/falsematch_bench.py harness/fixtures/faces --high 0.82
"""
import argparse
import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
from confidence_interval import describe, wilson  # noqa: E402


def load(folder):
    people = {}
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith(".npy"):
            continue
        person = fn.rsplit("_", 1)[0]
        v = np.load(os.path.join(folder, fn)).astype(np.float64).ravel()
        n = np.linalg.norm(v)
        if n == 0:
            continue
        people.setdefault(person, []).append(v / n)
    return people


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--high", type=float, default=0.82)
    ap.add_argument("--medium", type=float, default=0.68)
    args = ap.parse_args()

    people = load(args.folder)
    if len(people) < 2:
        sys.exit("need at least 2 people to form impostor pairs")

    genuine, impostor = [], []
    for person, vecs in people.items():
        for a, b in itertools.combinations(vecs, 2):
            genuine.append(float(a @ b))
    for p1, p2 in itertools.combinations(people.keys(), 2):
        for a in people[p1]:
            for b in people[p2]:
                impostor.append(float(a @ b))

    genuine = np.array(genuine)
    impostor = np.array(impostor)

    fm_high = int((impostor >= args.high).sum())
    fm_med = int((impostor >= args.medium).sum())
    fnm_high = int((genuine < args.high).sum())

    print(f"people: {len(people)}   genuine pairs: {len(genuine)}   "
          f"impostor pairs: {len(impostor)}\n")
    print(f"genuine  cosine: mean {genuine.mean():.3f}  min {genuine.min():.3f}")
    print(f"impostor cosine: mean {impostor.mean():.3f}  max {impostor.max():.3f}\n")

    print(describe(fm_high, len(impostor), f"FALSE MATCH @ high={args.high}"))
    print()
    print(describe(fm_med, len(impostor), f"false match @ medium={args.medium}"))
    print()
    print(describe(fnm_high, len(genuine), f"false NON-match @ high={args.high}"))

    _, _, hi = wilson(fm_high, len(impostor))
    print("\n--- row for docs/results_log.md ---")
    print(f"| face false-match rate | {fm_high}/{len(impostor)}, 95% CI upper "
          f"{hi*100:.3f}% | pairwise cosine over {len(people)} consented people, "
          f"threshold {args.high} | |")
    print("\nNOTE: a false NON-match costs a missed greeting. A false match "
          "costs calling someone by the wrong name. They are not symmetric, "
          "and the threshold is set high for that reason.")


if __name__ == "__main__":
    main()
