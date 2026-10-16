#!/usr/bin/env python3
"""
E1.8 — THE only writer of docs/results_log.md.

A row without a method cannot be written. That is the whole point: it makes
the rule structural instead of a thing someone remembers on a good day.

Use:
  python3 harness/analysis/results_writer.py \
      --metric "glass-to-haptic latency" \
      --value "median 310 ms, p95 480 ms" \
      --method "frame.captured -> haptic.motor.start, 40 trials, real hardware" \
      --trials 40 --build dev-1760812345

  python3 harness/analysis/results_writer.py --verify     # audit every row
  python3 harness/analysis/results_writer.py --list       # print the table
"""
import argparse
import datetime
import os
import re
import sys

LOG = os.path.join("docs", "results_log.md")

HEADER = """# Results Log

Every measured number this project produces, with the method that produced it.

**Rules (master spec section 13.1):**
1. Every number has a method: what was measured, where the clock started and
   stopped, how many trials, on which build, on which device.
2. Latency is median and 95th percentile. Never a mean alone, never a best case.
3. A single stage is never reported as the total.
4. Accuracy carries its denominator.
5. Rates near zero carry a confidence interval.
6. **This file is the only source for slides.** A figure not here does not go
   on a slide or into a viva answer.

Rows are written ONLY by `harness/analysis/results_writer.py`.

| Metric | Value | Method | Trials | Build | Date |
|---|---|---|---|---|---|
"""

ROW = re.compile(r"^\|\s*(?!Metric\b)(?!-)(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|"
                 r"\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")

# A value that is a bare latency number with no spread is rejected: rule 2.
BARE_LATENCY = re.compile(r"^\s*[\d.]+\s*(ms|s|sec|seconds|milliseconds)\s*$", re.I)
LATENCY_WORDS = ("latency", "delay", "offset", "barge", "time to", "glass-to")


def ensure_log():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    if not os.path.exists(LOG) or os.path.getsize(LOG) == 0:
        with open(LOG, "w", encoding="utf-8") as f:
            f.write(HEADER)


def validate(metric, value, method, trials):
    errs = []
    if len(method.strip()) < 15:
        errs.append("method is too short to be a method — say what was measured, "
                    "where the clock started and stopped, and on what")
    if any(w in metric.lower() for w in LATENCY_WORDS) and BARE_LATENCY.match(value):
        errs.append(f'"{value}" is a bare latency figure. Rule 2: report median '
                    f'AND p95 (e.g. "median 310 ms, p95 480 ms")')
    if "/" not in value and "%" in value and "CI" not in value.upper():
        errs.append("a percentage needs its denominator, and a near-zero rate "
                    "needs a confidence interval (rules 4 and 5)")
    if trials is None and "CI" not in value.upper() and "/" not in value:
        errs.append("--trials is required unless the value already carries a "
                    "denominator or an interval")
    return errs


def add(args):
    ensure_log()
    errs = validate(args.metric, args.value, args.method, args.trials)
    if errs and not args.force:
        print("ROW REJECTED:\n")
        for e in errs:
            print("  - " + e)
        print("\nFix the row, or pass --force and justify it in the method text.")
        sys.exit(1)

    date = args.date or datetime.date.today().isoformat()
    trials = str(args.trials) if args.trials is not None else "—"
    row = (f"| {args.metric} | {args.value} | {args.method} | "
           f"{trials} | {args.build or '—'} | {date} |\n")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(row)
    print("written:\n  " + row.strip())


def read_rows():
    if not os.path.exists(LOG):
        return []
    out = []
    for line in open(LOG, encoding="utf-8"):
        m = ROW.match(line.rstrip("\n"))
        if m and m.group(1).strip() not in ("Metric",):
            out.append(dict(zip(
                ("metric", "value", "method", "trials", "build", "date"),
                [g.strip() for g in m.groups()]
            )))
    return out


def verify(_args):
    rows = read_rows()
    if not rows:
        sys.exit("results_log.md has no rows. Nothing can go on a slide yet.")
    bad = 0
    for r in rows:
        errs = validate(r["metric"], r["value"], r["method"],
                        None if r["trials"] in ("—", "") else 1)
        if errs:
            bad += 1
            print(f'\nROW: {r["metric"]}')
            for e in errs:
                print("   - " + e)
    print(f"\n{len(rows)} rows, {bad} with problems")
    sys.exit(1 if bad else 0)


def listing(_args):
    for r in read_rows():
        print(f'{r["metric"]:<38} {r["value"]:<34} ({r["trials"]} trials, {r["date"]})')


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--metric"); p.add_argument("--value")
    p.add_argument("--method"); p.add_argument("--trials", type=int)
    p.add_argument("--build"); p.add_argument("--date")
    p.add_argument("--force", action="store_true")
    p.add_argument("--verify", action="store_true")
    p.add_argument("--list", action="store_true")
    a = p.parse_args()
    if a.verify: verify(a)
    elif a.list: listing(a)
    elif a.metric and a.value and a.method: add(a)
    else: p.error("need --metric, --value and --method (or --verify / --list)")


if __name__ == "__main__":
    main()
