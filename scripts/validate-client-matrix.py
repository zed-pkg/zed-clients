#!/usr/bin/env python3
"""Validate the repository-level Zed package and native client matrix."""

from __future__ import annotations

import pathlib
import sys
import tomllib


REQUIRED_TARGETS: dict[str, tuple[str, str]] = {
    "nodejs": ("clients/typescript", "package.json"),
    "python": ("clients/python", "pyproject.toml"),
    "golang": ("clients/go", "go.mod"),
    "rust": ("clients/rust", "Cargo.toml"),
    "rust-wasm": ("clients/wasm", "Cargo.toml"),
    "dart": ("clients/dart", "pubspec.yaml"),
    "gleam": ("clients/gleam", "gleam.toml"),
    "erlang": ("clients/erlang", "rebar.config"),
    "java": ("clients/java", "pom.xml"),
    "swift": ("clients/swift", "Package.swift"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    manifest_path = root / ".zpkg.toml"
    lock_path = root / ".zpkg.lock"

    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    with lock_path.open("rb") as handle:
        lock = tomllib.load(handle)

    require(lock.get("version") == 1, ".zpkg.lock must use lock format version 1")
    targets = manifest.get("targets")
    require(isinstance(targets, dict), ".zpkg.toml must contain a targets table")

    for target, (directory, native_manifest) in REQUIRED_TARGETS.items():
        target_config = targets.get(target)
        require(isinstance(target_config, dict), f"missing target {target!r}")
        require(
            target_config.get("dir") == directory,
            f"target {target!r} must point to {directory!r}",
        )
        require(
            (root / directory / native_manifest).is_file(),
            f"target {target!r} is missing {directory}/{native_manifest}",
        )

    require(
        targets.get("repository", {}).get("dir") == ".",
        "repository target must package the repository root",
    )
    require(
        targets["golang"].get("native", {}).get("package", "").endswith(
            "/clients/go"
        ),
        "Go native package must use the clients/go module path",
    )
    require(
        targets["golang"].get("native", {}).get("tag_format")
        == "clients/go/v{version}",
        "Go releases must use clients/go/v{version} tags",
    )
    require(
        targets["java"].get("native", {}).get("package") == "tech.zpkg:zed-client",
        "Java coordinates must remain tech.zpkg:zed-client",
    )

    nested_locks = sorted((root / "clients").glob("**/.zpkg.lock"))
    require(
        not nested_locks,
        "client packages must share the root lock; nested locks found: "
        + ", ".join(str(path.relative_to(root)) for path in nested_locks),
    )

    readme = (root / "README.md").read_text(encoding="utf-8")
    for directory, _ in REQUIRED_TARGETS.values():
        require(
            f"[{directory}/]({directory}/)" in readme,
            f"README matrix is missing {directory}",
        )

    print(
        "zed-clients release set is coherent: "
        f"{len(REQUIRED_TARGETS)} native SDK targets plus repository packaging"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        print(f"client matrix validation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
