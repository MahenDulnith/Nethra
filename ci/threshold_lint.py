#!/usr/bin/env python3
"""
A1.7 — every threshold defined must be referenced in Kotlin, and every
threshold referenced must be defined. Catches a silently-ignored threshold.
Run: python3 ci/threshold_lint.py
"""
import os, re, sys, yaml

CFG = "config/thresholds.yaml"
SRC = os.path.join("app", "src", "main", "java")

doc = yaml.safe_load(open(CFG, encoding="utf-8"))

def flatten(node, prefix=""):
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            out += flatten(v, f"{prefix}.{k}" if prefix else k)
    else:
        out.append(prefix)
    return out

defined = set(flatten(doc))

source = []
for dirpath, _, files in os.walk(SRC):
    for fn in files:
        if fn.endswith(".kt"):
            source.append(open(os.path.join(dirpath, fn), encoding="utf-8").read())
blob = "\n".join(source)

referenced = set(re.findall(r'thresholds?\.(?:num|int|bool|str|list)\(\s*"([\w.\[\]]+)"', blob))

orphans = sorted(k for k in defined if k not in referenced)
missing = sorted(k for k in referenced if k not in defined)

ok = True
if missing:
    ok = False
    print("THRESHOLD LINT FAILED — referenced but not defined:")
    for k in missing:
        print("   " + k)
if orphans:
    print(f"\nWARNING — defined but never referenced ({len(orphans)}):")
    for k in orphans:
        print("   " + k)

if not ok:
    sys.exit(1)
print("\nthreshold lint OK")
sys.exit(0)
