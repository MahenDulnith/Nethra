#!/usr/bin/env python3
"""
E1.2 — blocks new feature files after the freeze.

Install as a pre-commit hook on 25 Oct:
  cp ci/freeze_guard.py .git/hooks/pre-commit
  chmod +x .git/hooks/pre-commit

After the freeze, a commit may ONLY touch existing source files, docs,
config, or tests. A NEW .kt source file is a new feature, and new features
are what break demos on the 28th.

Override for a genuine emergency:
  FREEZE_OVERRIDE=1 git commit -m "..."
(the override is logged into the commit message trailer by convention —
write why in the message, because someone will ask on the 30th)
"""
import os
import subprocess
import sys

FREEZE_TAG = "freeze-25oct"
ALLOWED_NEW = (".md", ".yaml", ".yml", ".json", ".txt", ".png", ".jpg", ".mp4")
ALLOWED_NEW_DIRS = ("docs/", "config/", "harness/fixtures/", "hardware/")


def frozen():
    r = subprocess.run(["git", "tag", "-l", FREEZE_TAG],
                       capture_output=True, text=True)
    return FREEZE_TAG in r.stdout


def staged_new_files():
    r = subprocess.run(["git", "diff", "--cached", "--name-status", "--diff-filter=A"],
                       capture_output=True, text=True)
    return [ln.split("\t", 1)[1] for ln in r.stdout.strip().splitlines() if "\t" in ln]


def main():
    if os.environ.get("FREEZE_OVERRIDE") == "1":
        print("freeze_guard: OVERRIDDEN — say why in the commit message")
        return 0
    if not frozen():
        return 0

    blocked = []
    for f in staged_new_files():
        if f.startswith(ALLOWED_NEW_DIRS) or f.endswith(ALLOWED_NEW):
            continue
        if "/test/" in f or "/androidTest/" in f:
            continue      # a new test is always allowed
        blocked.append(f)

    if blocked:
        print("\nFREEZE IN EFFECT — new source files are blocked\n")
        for f in blocked:
            print("   " + f)
        print("\nAfter 25 Oct: bug fixes to existing files only.")
        print("Everything that goes wrong on the 29th will be something that")
        print("changed after the freeze. If this is genuinely a fix, put it in")
        print("an existing file. If it is a feature, it waits for Phase 2.\n")
        print("Emergency override: FREEZE_OVERRIDE=1 git commit ...\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
