#!/usr/bin/env python3
"""Validate the repository-level Zed package and native client matrix."""

from __future__ import annotations

import json
import pathlib
import re
import sys
import tomllib


REQUIRED_TARGETS: dict[str, tuple[str, str]] = {
    "c": ("clients/c", "CMakeLists.txt"),
    "cpp": ("clients/cpp", "CMakeLists.txt"),
    "zig": ("clients/zig", "build.zig"),
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

PACKAGE_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
VCS_COMMIT = re.compile(r"^[A-Za-z0-9._+:/-]{7,128}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_lock_provenance(manifest: dict, lock: dict) -> None:
    """Require immutable artifact identity for every locked Zed package.

    Lock format v1 permits an empty package list for dependency-free projects.
    A dependency-bearing manifest cannot use that shape as resolution evidence:
    every direct requirement must have a canonical lock entry, and every entry
    must pin the archive bytes and source revision required by the current Zed
    lock schema.
    """

    dependencies = manifest.get("dependencies", {})
    require(isinstance(dependencies, dict), ".zpkg.toml dependencies must be a table")
    require(
        all(
            isinstance(name, str)
            and name.count("/") == 1
            and all(PACKAGE_SLUG.fullmatch(part) for part in name.split("/"))
            for name in dependencies
        ),
        ".zpkg.toml dependency coordinates must be org/name slugs",
    )

    packages = lock.get("package", [])
    require(isinstance(packages, list), ".zpkg.lock package entries must be an array")
    locked: dict[str, dict] = {}
    for index, package in enumerate(packages):
        label = f".zpkg.lock package[{index}]"
        require(isinstance(package, dict), f"{label} must be a table")
        org = package.get("org")
        name = package.get("name")
        require(
            isinstance(org, str)
            and PACKAGE_SLUG.fullmatch(org) is not None
            and isinstance(name, str)
            and PACKAGE_SLUG.fullmatch(name) is not None,
            f"{label} must contain canonical org/name slugs",
        )
        coordinate = f"{org}/{name}"
        require(coordinate not in locked, f"duplicate locked package coordinate: {coordinate}")
        require(
            isinstance(package.get("version"), str) and bool(package["version"]),
            f"{label} must pin a version",
        )
        require(
            isinstance(package.get("sha256"), str)
            and SHA256.fullmatch(package["sha256"]) is not None,
            f"{label} must pin a lowercase SHA-256",
        )
        size = package.get("size")
        require(
            isinstance(size, int) and not isinstance(size, bool) and size > 0,
            f"{label} must pin a positive artifact size",
        )
        require(
            package.get("format") in {"tar.gz", "zip"},
            f"{label} must pin tar.gz or zip format",
        )
        require(
            isinstance(package.get("vcs_tag"), str) and bool(package["vcs_tag"]),
            f"{label} must pin a VCS tag",
        )
        require(
            isinstance(package.get("vcs_commit"), str)
            and VCS_COMMIT.fullmatch(package["vcs_commit"]) is not None,
            f"{label} must pin an immutable VCS commit",
        )
        require(
            isinstance(package.get("source"), str) and bool(package["source"]),
            f"{label} must record its resolver source",
        )
        locked[coordinate] = package

    missing = sorted(set(dependencies).difference(locked))
    require(
        not missing,
        "dependency-bearing .zpkg.lock is incomplete; missing canonical entries: "
        + ", ".join(missing),
    )


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    manifest_path = root / ".zpkg.toml"
    lock_path = root / ".zpkg.lock"

    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    with lock_path.open("rb") as handle:
        lock = tomllib.load(handle)

    require(lock.get("version") == 1, ".zpkg.lock must use lock format version 1")
    validate_lock_provenance(manifest, lock)
    require(
        manifest.get("dependencies") == {"zed-pkg/zed-interfaces": "^0.1.0"},
        "zed-clients must depend only on zed-pkg/zed-interfaces",
    )

    targets = manifest.get("targets")
    require(isinstance(targets, dict), ".zpkg.toml must contain a targets table")
    require(
        set(targets) == {"repository", *REQUIRED_TARGETS},
        "Zed publish targets must be the canonical language packages plus repository",
    )

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
        f"{len(REQUIRED_TARGETS)} language SDK targets plus repository packaging"
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
