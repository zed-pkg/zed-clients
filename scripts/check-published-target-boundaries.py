#!/usr/bin/env python3
"""Reject published Rust target dependencies that escape their Zed artifact root."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".zpkg.toml"
DEPENDENCY_TABLES = {"dependencies", "dev-dependencies", "build-dependencies"}


def fail(message: str) -> None:
    raise ValueError(message)


def dependency_tables(value: object, prefix: str = ""):
    if not isinstance(value, dict):
        return
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if key in DEPENDENCY_TABLES and isinstance(child, dict):
            yield path, child
        if isinstance(child, dict):
            yield from dependency_tables(child, path)


def check_cargo_target(root: Path, target_name: str, target_dir: str) -> None:
    target_root = (root / target_dir).resolve()
    cargo = target_root / "Cargo.toml"
    if not cargo.is_file():
        fail(f"{target_name}: missing {cargo.relative_to(root)}")

    with cargo.open("rb") as handle:
        document = tomllib.load(handle)

    for table_name, dependencies in dependency_tables(document):
        for dependency_name, declaration in dependencies.items():
            if not isinstance(declaration, dict) or "path" not in declaration:
                continue
            raw_path = declaration["path"]
            if not isinstance(raw_path, str) or not raw_path:
                fail(
                    f"{target_name}: {table_name}.{dependency_name} has invalid path dependency"
                )
            resolved = (cargo.parent / raw_path).resolve()
            try:
                resolved.relative_to(target_root)
            except ValueError as error:
                fail(
                    f"{target_name}: {table_name}.{dependency_name} path {raw_path!r} "
                    f"escapes staged target artifact {target_dir!r}"
                ) from error


def main() -> int:
    with MANIFEST.open("rb") as handle:
        manifest = tomllib.load(handle)
    targets = manifest.get("targets")
    if not isinstance(targets, dict):
        fail(".zpkg.toml must define targets")

    checked = 0
    for target_name in ("rust", "rust-wasm"):
        target = targets.get(target_name)
        if not isinstance(target, dict):
            fail(f".zpkg.toml missing target {target_name!r}")
        target_dir = target.get("dir")
        if not isinstance(target_dir, str) or not target_dir:
            fail(f"target {target_name!r} has invalid dir")
        check_cargo_target(ROOT, target_name, target_dir)
        checked += 1

    print(f"published Rust target boundaries OK: {checked} Cargo targets are self-contained")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f"published target boundary check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
