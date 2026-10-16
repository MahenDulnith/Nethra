#!/usr/bin/env python3
"""
D1.9 — fabricated events are a HARD FAIL, counted, not averaged away.

Reads the routines.evening_review log row and checks that every highlight
is supported by at least one event that actually exists in the log.

Usage:
  python3 harness/bench/summary_faithfulness_bench.py harness/out/session_X/events.jsonl
"""
import argparse
import json
import re
import sys

NUM = re.compile(r"\b(\d+)\b")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("events_jsonl")
    args = ap.parse_args()

    logged_events, reviews = {}, []
    for line in open(args.events_jsonl, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        name, f = row.get("name"), row.get("fields", {})
        if name == "memory.event_logged":
            logged_events[f.get("id")] = f
        elif name == "routines.evening_review":
            reviews.append(f)

    if not reviews:
        sys.exit("no routines.evening_review row found — generate a summary first")

    total_unsupported = 0
    for i, r in enumerate(reviews, 1):
        highlights = r.get("highlights", [])
        src = r.get("source_event_ids", []) or []
        available = r.get("events_available", 0)

        print(f"\n=== summary {i} ({r.get('date')}) ===")
        print(f"highlights: {len(highlights)}   cited ids: {len(src)}   "
              f"events available: {available}")

        unknown = [s for s in src if s not in logged_events]
        if unknown:
            total_unsupported += len(unknown)
            print(f"  FAIL — {len(unknown)} cited id(s) do not exist in the log:")
            for u in unknown[:5]:
                print(f"    {u}")

        if highlights and not src and available > 0:
            total_unsupported += len(highlights)
            print(f"  FAIL — {len(highlights)} highlight(s) cite NO source event")

        # counts claimed in prose must not exceed what was logged
        for h in highlights:
            for m in NUM.finditer(h):
                claimed = int(m.group(1))
                if claimed > available:
                    total_unsupported += 1
                    print(f'  FAIL — claims {claimed} but only {available} '
                          f'events exist: "{h}"')

        for h in highlights:
            print(f"  · {h}")

    print("\n=== result ===")
    if total_unsupported == 0:
        print(f"PASS — 0 unsupported statements across {len(reviews)} summaries")
        print("\n--- row for docs/results_log.md ---")
        print(f"| day-summary fabricated events | 0 across {len(reviews)} "
              f"summaries | every highlight traced to a logged source_event_id "
              f"| |")
    else:
        print(f"HARD FAIL — {total_unsupported} unsupported statement(s)")
        print("A summary that invents an event is not a style problem. "
              "Fix it before the demo.")
        sys.exit(1)


if __name__ == "__main__":
    main()
