#!/usr/bin/env python3
"""
D1.3 — recall accuracy on a scripted day, with the denominator.

Fixture format, harness/fixtures/scripted_day.json:
{
  "events": [
    {"id":"e1","minute":480,"type":"PLACE","summary":"arrived at the library",
     "location":"library","people":[],"source":"AUTO_LOGGED"},
    {"id":"e2","minute":495,"type":"USER_NOTE",
     "summary":"my keys are in the side pocket of my bag","source":"USER_STATED"}
  ],
  "questions": [
    {"q":"where did I leave my keys","expect":["e2"]},
    {"q":"where was I this morning","expect":["e1"]}
  ]
}

Usage:
  python3 harness/bench/memory_recall_bench.py harness/fixtures/scripted_day.json
"""
import argparse
import json
import math
import re

DIM = 256
STOP = {"where", "did", "i", "the", "my", "a", "an", "is", "was", "leave", "left",
        "put", "who", "what", "when", "do", "does", "have", "had", "me", "on",
        "in", "at", "to", "of", "it", "that", "this", "today", "yesterday"}


def normalise(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t.lower())).strip()


def embed(text):
    """Mirrors TextEmbedder.kt exactly. If one changes, change both."""
    v = [0.0] * DIM
    s = normalise(text)

    def idx(h):
        return ((h % DIM) + DIM) % DIM

    def jhash(s):
        h = 0
        for ch in s:
            h = (31 * h + ord(ch)) & 0xFFFFFFFF
        return h - 0x100000000 if h >= 0x80000000 else h

    if len(s) < 3:
        for w in s.split(" "):
            if w:
                v[idx(jhash(w))] += 1.0
    else:
        for i in range(len(s) - 2):
            v[idx(jhash(s[i:i + 3]))] += 1.0
    for w in s.split(" "):
        if len(w) > 2:
            v[idx(jhash(w) * 31)] += 2.0

    mag = math.sqrt(sum(x * x for x in v))
    return [x / mag for x in v] if mag else v


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fixture")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--min-sim", type=float, default=0.18)
    args = ap.parse_args()

    doc = json.load(open(args.fixture))
    events = doc["events"]
    questions = doc["questions"]

    index = {}
    for e in events:
        text = " ".join(filter(None, [
            e["summary"], e.get("location"), " ".join(e.get("people", []))
        ]))
        index[e["id"]] = embed(text)

    hit_at_1 = 0
    hit_at_k = 0
    misses = []

    for q in questions:
        words = [w for w in normalise(q["q"]).split(" ")
                 if len(w) > 2 and w not in STOP]
        # stage 1 — keyword filter, same order as HybridRetriever
        cands = [e["id"] for e in events if any(
            w in normalise(" ".join(filter(None, [
                e["summary"], e.get("location"),
                " ".join(e.get("people", []))])))
            for w in words)] or [e["id"] for e in events]

        qv = embed(q["q"])
        ranked = sorted(
            ((eid, cosine(qv, index[eid])) for eid in cands),
            key=lambda p: -p[1]
        )
        ranked = [(i, s) for i, s in ranked if s >= args.min_sim][:args.top_k]
        got = [i for i, _ in ranked]

        if got and got[0] in q["expect"]:
            hit_at_1 += 1
        if any(g in q["expect"] for g in got):
            hit_at_k += 1
        else:
            misses.append((q["q"], q["expect"], ranked[:3]))

    n = len(questions)
    print(f"questions: {n}   events: {len(events)}\n")
    print(f"hit@1       : {hit_at_1}/{n} = {hit_at_1/n*100:.1f}%")
    print(f"hit@{args.top_k:<8}: {hit_at_k}/{n} = {hit_at_k/n*100:.1f}%")

    if misses:
        print(f"\n--- {len(misses)} misses ---")
        for q, exp, got in misses:
            print(f'  "{q}"\n    expected {exp}\n    got      {got}')

    print("\n--- row for docs/results_log.md ---")
    print(f"| memory recall hit@1 | {hit_at_1}/{n} = {hit_at_1/n*100:.1f}% | "
          f"scripted day, {len(events)} events, {n} questions, hybrid "
          f"filter-then-rank | |")
    if n < 20:
        print(f"\nWARNING: D1.3 requires 20+ questions. You have {n}.")


if __name__ == "__main__":
    main()
