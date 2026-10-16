#!/usr/bin/env python3
"""
E1.8 — no number on a slide without a logged method.

Scans the pitch/slide source (markdown, or text exported from the deck) for
numeric claims and checks each against docs/results_log.md.

  python3 ci/slide_trace_check.py docs/pitch.md

Exit 1 on an untraceable figure. Run it before every rehearsal, and again
on 28 Oct before packing.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join("harness", "analysis"))
from results_writer import read_rows  # noqa: E402

# Numbers that are never claims about our system's performance.
IGNORE_CONTEXT = re.compile(
    r"(19|20)\d{2}|section|phase|stage|figure|table|page|item|step|"
    r"\b(oct|nov|sep)\b|version|v\d|\bno\.\b", re.I)

NUMBER = re.compile(r"""
    (?P<num>
        \d+(?:\.\d+)?\s*(?:%|ms|s\b|fps|FPS|°C|m\b|mm|minutes?|mins?|hours?|hrs?)
        | \d+\s*/\s*\d+
        | \b\d{2,}\b
    )
""", re.X)

# Words that make a number a performance claim rather than a description.
CLAIM_WORDS = (
    "latency", "delay", "accuracy", "rate", "fps", "frame", "success",
    "precision", "recall", "false", "offset", "temperature", "battery",
    "hallucination", "error", "match", "recall", "warning", "throughput",
    "detect", "alert", "turns", "wer", "word error",
)


def logged_numbers():
    nums = set()
    for r in read_rows():
        for m in NUMBER.finditer(r["value"]):
            nums.add(m.group("num").replace(" ", "").lower())
    return nums


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: slide_trace_check.py <slides.md> [more.md ...]")

    logged = logged_numbers()
    if not logged:
        sys.exit("results_log.md has no numeric values. Measure first.")

    untraced, checked = [], 0
    for path in sys.argv[1:]:
        if not os.path.exists(path):
            print(f"skip (missing): {path}")
            continue
        for i, line in enumerate(open(path, encoding="utf-8"), 1):
            low = line.lower()
            if not any(w in low for w in CLAIM_WORDS):
                continue
            if IGNORE_CONTEXT.search(line):
                continue
            for m in NUMBER.finditer(line):
                n = m.group("num").replace(" ", "").lower()
                checked += 1
                if n not in logged:
                    untraced.append((path, i, n, line.strip()[:88]))

    print(f"checked {checked} numeric claim(s) against "
          f"{len(logged)} logged value(s)\n")

    if untraced:
        print("UNTRACEABLE FIGURES — these cannot go on a slide:\n")
        for path, ln, n, text in untraced:
            print(f"  {path}:{ln}  \"{n}\"\n     {text}\n")
        print("Either measure it and log it with results_writer.py, "
              "or remove it from the slide.")
        sys.exit(1)

    print("every numeric claim traces to a logged result")


if __name__ == "__main__":
    main()
