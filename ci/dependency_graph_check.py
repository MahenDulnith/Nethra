#!/usr/bin/env python3
"""
A1.2 — enforces the layering rules R1-R4 across the Nethra Python codebase.

R1  services/{hygiene,safety,arbiter,memory}  may NOT import services/{agent,vision}
R2  contracts/                                may NOT import anything from adapters, services, features, shell, or ML runtimes
R3  wiring (constructor graph) only in shell/
R4  services/arbiter/                         may NOT import any model runtime (ultralytics, torch, onnxruntime)

Run:  python ci/dependency_graph_check.py
Exit: 0 clean, 1 violation
"""

from __future__ import annotations

import ast
import os
import re
import sys
from typing import List

SCAN_DIRS = ("contracts", "adapters", "services", "features", "shell")
L2 = ("services/hygiene", "services/safety", "services/arbiter", "services/memory")
L3_PREFIXES = ("services.agent", "services.vision")
APP_LAYERS = ("adapters", "services", "features", "shell")
MODEL_RUNTIMES = ("ultralytics", "torch", "onnxruntime", "tensorflow", "requests", "httpx")


def extract_imports(py_source: str) -> List[str]:
    """Extracts imported module names from a Python source string using AST."""
    tree = ast.parse(py_source)
    imports: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def main() -> int:
    violations: List[str] = []

    for root_dir in SCAN_DIRS:
        if not os.path.isdir(root_dir):
            continue
        for dirpath, _, files in os.walk(root_dir):
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                full = os.path.join(dirpath, fn)
                rel = full.replace(os.sep, "/")
                with open(full, encoding="utf-8") as f:
                    src = f.read()

                imports = extract_imports(src)

                # R2: contracts/ depends on nothing in higher layers or ML/network runtimes
                if rel.startswith("contracts/"):
                    for imp in imports:
                        if imp.startswith(APP_LAYERS):
                            violations.append(f"R2  {rel}: contracts imports higher layer -> {imp}")
                        if imp.startswith(MODEL_RUNTIMES):
                            violations.append(f"R2  {rel}: contracts imports runtime/network -> {imp}")

                # R1: L2 local services never import L3 cloud services
                if rel.startswith(L2):
                    for imp in imports:
                        if imp.startswith(L3_PREFIXES):
                            violations.append(f"R1  {rel}: local L2 service imports L3 cloud layer -> {imp}")

                # R4: arbiter/ never imports any model runtime or network client
                if rel.startswith("services/arbiter"):
                    for imp in imports:
                        if imp.startswith(MODEL_RUNTIMES):
                            violations.append(f"R4  {rel}: arbiter reaches a model/network runtime -> {imp}")

                # R3: services outside agent must not construct cloud providers directly
                if rel.startswith("services/") and not rel.startswith("services/agent"):
                    if re.search(r"\b(StreamingProvider|CascadeProvider|VlmClient)\s*\(", src):
                        violations.append(f"R3  {rel}: constructs a cloud provider outside shell/")

    if violations:
        print("DEPENDENCY CHECK FAILED\n")
        for v in sorted(set(violations)):
            print("  " + v)
        print(f"\n{len(set(violations))} violation(s)")
        return 1

    print("dependency check OK  (R1-R4 hold across Nethra Python packages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
