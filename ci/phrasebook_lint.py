#!/usr/bin/env python3
"""
A1.7 — fails the build if any spoken string contains a forbidden phrase.
This is what makes "it is safe to cross" unbuildable.
Run: python3 ci/phrasebook_lint.py
"""
import sys, yaml

PATH = "config/phrasebook.yaml"
doc = yaml.safe_load(open(PATH, encoding="utf-8"))
forbidden = [f.lower() for f in doc.get("_forbidden", [])]
if not forbidden:
    print("FAIL: _forbidden list is empty — the lint would pass anything")
    sys.exit(1)

bad = []

def walk(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "_forbidden":
                continue
            walk(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}[{i}]")
    elif isinstance(node, str):
        low = node.lower()
        for f in forbidden:
            if f in low:
                bad.append((path, f, node.strip()[:70]))

walk(doc, "")

if bad:
    print("PHRASEBOOK LINT FAILED — forbidden phrasing reached a spoken string\n")
    for path, f, text in bad:
        print(f'  {path}\n    contains "{f}"\n    in: "{text}"\n')
    sys.exit(1)

print(f"phrasebook lint OK  ({len(forbidden)} forbidden phrases checked)")
sys.exit(0)
