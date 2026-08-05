#!/usr/bin/env python3
"""Validate the repository-level Zed package and native client matrix."""

from __future__ import annotations

import json
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
    "elixir": ("clients/elixir", "mix.exs"),
    "java": ("clients/java", "pom.xml"),
    "kotlin": ("clients/kotlin", "pom.xml"),
    "ruby": ("clients/ruby", "zed_pkg_client.gemspec"),
    "php": ("clients/php", "composer.json"),
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
    require(
        manifest.get("dependencies") == {"zed-pkg/zed-interfaces": "^0.1.0"},
        "zed-clients must depend only on zed-pkg/zed-interfaces",
    )

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
    require(
        targets["kotlin"].get("native", {}).get("package")
        == "tech.zpkg:zed-client-kotlin",
        "Kotlin coordinates must remain tech.zpkg:zed-client-kotlin",
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

    package_json = json.loads(
        (root / "clients/typescript/package.json").read_text(encoding="utf-8")
    )
    exports = package_json.get("exports")
    require(isinstance(exports, dict), "TypeScript package must declare exports")
    for runtime in ("nodejs", "deno", "bun", "edge"):
        require(f"./{runtime}" in exports, f"missing TypeScript {runtime} export")
        require(
            (root / "clients/typescript/src/runtimes" / runtime / "index.ts").is_file(),
            f"missing TypeScript {runtime} runtime entry point",
        )

    print(
        "zed-clients release set is coherent: "
        f"{len(REQUIRED_TARGETS)} native SDK targets plus repository packaging"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        AssertionError,
        json.JSONDecodeError,
        OSError,
        KeyError,
        TypeError,
        tomllib.TOMLDecodeError,
    ) as error:
        print(f"client matrix validation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
