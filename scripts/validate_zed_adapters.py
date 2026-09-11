#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
ALLOWED = {"node", "java", "none"}
EXPECTED = {
    "c": "none",
    "cpp": "none",
    "zig": "none",
    "nodejs": "node",
    "python": "none",
    "golang": "none",
    "rust": "none",
    "rust-wasm": "node",
    "dart": "none",
    "gleam": "none",
    "erlang": "none",
    "elixir": "none",
    "java": "java",
    "kotlin": "java",
    "ruby": "none",
    "php": "none",
    "swift": "none",
}


def fail(message: str) -> None:
    print(f"zed-adapters: {message}", file=sys.stderr)
    raise SystemExit(1)


with (ROOT / ".zpkg.toml").open("rb") as handle:
    manifest = tomllib.load(handle)

targets = manifest.get("targets", {})
actual_language_targets = set(targets) - {"repository"}
if actual_language_targets != set(EXPECTED):
    fail(
        "language target drift: "
        f"expected {sorted(EXPECTED)}, got {sorted(actual_language_targets)}"
    )

for target, expected in EXPECTED.items():
    adapter = targets[target].get("adapter")
    if adapter not in ALLOWED:
        fail(
            f"target {target!r} uses unsupported adapter {adapter!r}; "
            "expected node, java, or none"
        )
    if adapter != expected:
        fail(f"target {target!r} must use adapter {expected!r}, got {adapter!r}")

install_adapter = manifest.get("install", {}).get("adapter")
if install_adapter is not None and install_adapter not in ALLOWED:
    fail(f"install.adapter is unsupported: {install_adapter!r}")

print("zed-adapters: ok")
