#!/usr/bin/env python3
"""Harden a polyglot ``*-clients`` repository against the canonical Zed contract.

The script is intentionally deterministic and safe to run repeatedly.  It never
replaces existing product implementation files.  Missing runtime packages get a
small compileable baseline, while every runtime receives a content-addressed
contract marker derived from ``clients/api-surface.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import tomlkit
from jsonschema import Draft202012Validator

SCHEMA_VERSION = 1
MINIMUM_TARGETS = 15


@dataclass(frozen=True)
class TargetSpec:
    name: str
    zed_target: str
    canonical_dir: str
    aliases: tuple[str, ...]
    adapter: str
    runtime: str | None = None
    zed_aliases: tuple[str, ...] = ()


TARGETS: tuple[TargetSpec, ...] = (
    TargetSpec("c", "c", "clients/c", (), "none"),
    TargetSpec("cpp", "cpp", "clients/cpp", ("clients/cxx",), "none", zed_aliases=("cxx",)),
    TargetSpec("zig", "zig", "clients/zig", (), "none"),
    TargetSpec("wasm", "rust-wasm", "clients/wasm", (), "rust"),
    TargetSpec("gleamlang", "gleamlang", "clients/gleamlang", ("clients/gleam",), "none", zed_aliases=("gleam",)),
    TargetSpec("erlang", "erlang", "clients/erlang", (), "none"),
    TargetSpec("elixir", "elixir", "clients/elixir", (), "none"),
    TargetSpec("dart", "dart", "clients/dart", (), "dart"),
    TargetSpec("rust", "rust", "clients/rust", (), "rust"),
    TargetSpec("java", "java", "clients/java", (), "java"),
    TargetSpec("golang", "golang", "clients/golang", ("clients/go",), "go", zed_aliases=("go",)),
    TargetSpec("python3", "python3", "clients/python3", ("clients/python",), "none", zed_aliases=("python",)),
    TargetSpec("ruby", "ruby", "clients/ruby", (), "none"),
    TargetSpec("php", "php", "clients/php", (), "none"),
    TargetSpec("kotlin", "kotlin", "clients/kotlin", (), "java"),
    TargetSpec("swift", "swift", "clients/swift", (), "none"),
    TargetSpec(
        "typescript-nodejs",
        "typescript-nodejs",
        "clients/typescript/nodejs",
        ("clients/typescript",),
        "node",
        "nodejs",
        ("nodejs", "typescript"),
    ),
    TargetSpec(
        "typescript-deno",
        "typescript-deno",
        "clients/typescript/deno",
        ("clients/typescript",),
        "none",
        "deno",
        ("deno",),
    ),
    TargetSpec(
        "typescript-bun",
        "typescript-bun",
        "clients/typescript/bun",
        ("clients/typescript",),
        "node",
        "bun",
        ("bun",),
    ),
    TargetSpec(
        "typescript-edge",
        "typescript-edge",
        "clients/typescript/edge",
        ("clients/typescript",),
        "none",
        "edge",
        ("edge",),
    ),
)


def clean(value: str) -> str:
    return value.strip() + "\n"


def snake(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower() or "client"
    return f"z_{result}" if result[:1].isdigit() else result


def camel(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", value)
    result = "".join(part[:1].upper() + part[1:] for part in parts) or "Client"
    return f"Z{result}" if result[:1].isdigit() else result


def kebab(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "client"


def write_text(path: Path, content: str, changed: list[str], *, missing_only: bool = False) -> None:
    rendered = clean(content)
    if missing_only and path.exists():
        return
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    if previous == rendered:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    changed.append(path.as_posix())


def write_generated_text(
    path: Path,
    content: str,
    changed: list[str],
    *,
    previous_templates: tuple[str, ...] = (),
) -> None:
    """Create a scaffold or migrate only an exact older generated template.

    Hand-maintained runtime files remain untouched.  This gives the nightly
    hardener a narrow, reviewable migration path when a toolchain removes an API
    used by a template that earlier fleet runs may already have materialized.
    """

    if path.exists():
        previous = path.read_text(encoding="utf-8")
        allowed = {clean(template) for template in previous_templates}
        if previous != clean(content) and previous not in allowed:
            return
    write_text(path, content, changed)


def write_json(path: Path, value: Any, changed: list[str], *, missing_only: bool = False) -> None:
    write_text(
        path,
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False),
        changed,
        missing_only=missing_only,
    )


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def primitive(name: str) -> dict[str, str]:
    return {"kind": "primitive", "name": name}


def named(name: str) -> dict[str, str]:
    return {"kind": "named", "name": name}


def optional(value: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "optional", "item": value}


def baseline_symbols(cap: str) -> list[dict[str, Any]]:
    client = f"{cap}Client"
    options = f"{cap}ClientOptions"
    transport = f"{cap}Transport"
    request = f"_{cap}RequestContext"
    builder = f"_{cap}RequestBuilder"
    telemetry = f"_{cap}TelemetrySink"
    return [
        {
            "kind": "type",
            "name": options,
            "visibility": "public",
            "description": "Portable client construction options.",
            "definition": {
                "kind": "object",
                "fields": [
                    {
                        "name": "baseUrl",
                        "visibility": "public",
                        "type": primitive("string"),
                        "readonly": True,
                    },
                    {
                        "name": "bearerToken",
                        "visibility": "public",
                        "type": optional(primitive("string")),
                        "readonly": True,
                    },
                ],
            },
        },
        {
            "kind": "type",
            "name": request,
            "visibility": "private",
            "description": "Internal request correlation state.",
            "definition": {
                "kind": "object",
                "fields": [
                    {
                        "name": "requestId",
                        "visibility": "private",
                        "type": primitive("string"),
                        "readonly": True,
                    }
                ],
            },
        },
        {
            "kind": "interface",
            "name": transport,
            "visibility": "public",
            "description": "Transport abstraction implemented by runtime adapters.",
            "methods": [
                {
                    "name": "send",
                    "visibility": "public",
                    "parameters": [
                        {"name": "path", "type": primitive("string")},
                        {"name": "body", "type": optional(primitive("bytes"))},
                    ],
                    "returns": primitive("bytes"),
                    "async": True,
                    "static": False,
                    "throws": [named(f"{cap}ClientError")],
                }
            ],
        },
        {
            "kind": "interface",
            "name": telemetry,
            "visibility": "private",
            "description": "Internal telemetry sink.",
            "methods": [
                {
                    "name": "record",
                    "visibility": "private",
                    "parameters": [{"name": "event", "type": primitive("string")}],
                    "returns": primitive("void"),
                    "async": False,
                    "static": False,
                    "throws": [],
                }
            ],
        },
        {
            "kind": "type",
            "name": f"{cap}ClientError",
            "visibility": "public",
            "description": "Stable cross-runtime error categories.",
            "definition": {
                "kind": "enum",
                "values": ["InvalidConfiguration", "TransportFailure", "Unauthorized", "UnexpectedResponse"],
            },
        },
        {
            "kind": "class",
            "name": client,
            "visibility": "public",
            "description": "Standard public client entry point.",
            "fields": [
                {
                    "name": "options",
                    "visibility": "private",
                    "type": named(options),
                    "readonly": True,
                }
            ],
            "constructors": [
                {
                    "name": "new",
                    "visibility": "public",
                    "parameters": [{"name": "options", "type": named(options)}],
                    "returns": named(client),
                    "async": False,
                    "static": True,
                    "throws": [named(f"{cap}ClientError")],
                }
            ],
            "methods": [
                {
                    "name": "health",
                    "visibility": "public",
                    "parameters": [],
                    "returns": primitive("boolean"),
                    "async": True,
                    "static": False,
                    "throws": [named(f"{cap}ClientError")],
                },
                {
                    "name": "_request",
                    "visibility": "private",
                    "parameters": [
                        {"name": "path", "type": primitive("string")},
                        {"name": "context", "type": named(request)},
                    ],
                    "returns": primitive("bytes"),
                    "async": True,
                    "static": False,
                    "throws": [named(f"{cap}ClientError")],
                },
            ],
            "implements": [],
        },
        {
            "kind": "class",
            "name": builder,
            "visibility": "private",
            "description": "Internal request builder.",
            "fields": [],
            "constructors": [
                {
                    "name": "new",
                    "visibility": "private",
                    "parameters": [],
                    "returns": named(builder),
                    "async": False,
                    "static": True,
                    "throws": [],
                }
            ],
            "methods": [
                {
                    "name": "build",
                    "visibility": "private",
                    "parameters": [{"name": "path", "type": primitive("string")}],
                    "returns": primitive("bytes"),
                    "async": False,
                    "static": False,
                    "throws": [],
                }
            ],
            "implements": [],
        },
        {
            "kind": "function",
            "name": f"create{cap}Client",
            "visibility": "public",
            "description": "Construct the standard client entry point.",
            "parameters": [{"name": "options", "type": named(options)}],
            "returns": named(client),
            "async": False,
            "static": True,
            "throws": [named(f"{cap}ClientError")],
        },
        {
            "kind": "function",
            "name": f"_normalize{cap}BaseUrl",
            "visibility": "private",
            "description": "Normalize a base URL without network access.",
            "parameters": [{"name": "baseUrl", "type": primitive("string")}],
            "returns": primitive("string"),
            "async": False,
            "static": True,
            "throws": [named(f"{cap}ClientError")],
        },
    ]


def baseline_surface(org: str, repo: str, prefix: str) -> dict[str, Any]:
    cap = camel(prefix)
    return {
        "$schema": "./client-api.schema.json",
        "schemaVersion": SCHEMA_VERSION,
        "package": {
            "coordinate": f"{org}/{repo}",
            "namespace": cap,
            "description": f"Canonical polyglot API contract for {org}/{repo}.",
        },
        "symbols": baseline_symbols(cap),
    }


def merge_standard_symbols(surface: dict[str, Any], cap: str) -> bool:
    symbols = surface.setdefault("symbols", [])
    if not isinstance(symbols, list):
        raise ValueError("api-surface.json symbols must be an array")
    existing = {item.get("name") for item in symbols if isinstance(item, dict)}
    changed = False
    for symbol in baseline_symbols(cap):
        if symbol["name"] not in existing:
            symbols.append(symbol)
            existing.add(symbol["name"])
            changed = True
    return changed


def iter_type_refs(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("kind") in {"primitive", "named", "array", "optional", "map", "union", "generic"}:
            yield value
        for child in value.values():
            yield from iter_type_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_type_refs(child)


def semantic_errors(surface: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    symbols = surface.get("symbols", [])
    names: list[str] = [str(item.get("name")) for item in symbols if isinstance(item, dict)]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        errors.append(f"duplicate symbol names: {', '.join(duplicates)}")
    declared = set(names)
    for ref in iter_type_refs(surface):
        if ref.get("kind") == "named" and ref.get("name") not in declared:
            errors.append(f"unresolved named type: {ref.get('name')}")
    for kind in ("class", "interface", "type", "function"):
        for visibility in ("public", "private"):
            if not any(
                isinstance(item, dict)
                and item.get("kind") == kind
                and item.get("visibility") == visibility
                for item in symbols
            ):
                errors.append(f"missing {visibility} {kind} declaration")
    methods = [
        method
        for item in symbols
        if isinstance(item, dict)
        for method in item.get("methods", [])
        if isinstance(method, dict)
    ]
    for visibility in ("public", "private"):
        if not any(method.get("visibility") == visibility for method in methods):
            errors.append(f"missing {visibility} method declaration")
    return sorted(set(errors))


def choose_dir(root: Path, spec: TargetSpec, manifest_targets: dict[str, Any]) -> Path:
    for target_name in (spec.zed_target, *spec.zed_aliases):
        entry = manifest_targets.get(target_name)
        if isinstance(entry, dict) and isinstance(entry.get("dir"), str):
            declared = root / entry["dir"]
            if declared.exists():
                return declared
    canonical = root / spec.canonical_dir
    if canonical.exists():
        return canonical
    if spec.runtime:
        shared = root / "clients/typescript"
        runtime_source = shared / "src/runtimes" / spec.runtime
        package = shared / "package.json"
        if package.is_file() and runtime_source.exists():
            return shared
    for alias in spec.aliases:
        candidate = root / alias
        if candidate.exists():
            return candidate
    return canonical


def choose_target_dirs(root: Path, manifest_targets: dict[str, Any]) -> dict[str, Path]:
    """Choose one isolated source root for every canonical target.

    Older client manifests can expose several runtime aliases from one source
    directory (most commonly the shared ``clients/typescript`` package).  The
    current Zed manifest contract requires every target to own a distinct source
    root.  Preserve the first compatible legacy package, then materialize any
    colliding runtime at its deterministic canonical directory.

    Canonical directories are reserved for their owning target so a malformed
    legacy manifest cannot make an earlier target claim a later target's repair
    location.
    """

    repository_root = root.resolve()
    reserved = {
        (root / spec.canonical_dir).resolve(): spec.name
        for spec in TARGETS
    }
    claimed: set[Path] = set()
    selected: dict[str, Path] = {}
    for spec in TARGETS:
        preferred = choose_dir(root, spec, manifest_targets)
        resolved = preferred.resolve()
        if not resolved.is_relative_to(repository_root):
            preferred = root / spec.canonical_dir
            resolved = preferred.resolve()
        if not resolved.is_relative_to(repository_root):
            raise ValueError(f"target directory escapes repository for {spec.name}: {preferred}")
        reserved_for = reserved.get(resolved)
        if resolved in claimed or (reserved_for is not None and reserved_for != spec.name):
            preferred = root / spec.canonical_dir
            resolved = preferred.resolve()
        if not resolved.is_relative_to(repository_root):
            raise ValueError(f"target directory escapes repository for {spec.name}: {preferred}")
        if resolved in claimed:
            raise ValueError(f"canonical target directory collision for {spec.name}: {preferred}")
        claimed.add(resolved)
        selected[spec.name] = preferred
    return selected


def merge_missing_table(current: dict[str, Any], legacy: dict[str, Any]) -> None:
    """Deep-merge missing legacy metadata while canonical values win conflicts."""

    for key, value in legacy.items():
        existing = current.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merge_missing_table(existing, value)
        elif key not in current:
            current[key] = value


def marker_dir(root: Path, spec: TargetSpec, target_dir: Path) -> Path:
    shared_typescript = root / "clients/typescript"
    if spec.runtime and target_dir == shared_typescript:
        return shared_typescript / ".zed-contracts" / spec.runtime
    return target_dir


def ensure_manifest(root: Path, org: str, repo: str, target_dirs: dict[str, Path], changed: list[str]) -> None:
    path = root / ".zpkg.toml"
    data = tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else tomlkit.document()
    package = data.setdefault("package", tomlkit.table())
    if not isinstance(package, dict):
        raise ValueError(".zpkg.toml [package] must be a table")
    package["org"] = org
    package["name"] = repo
    package.setdefault("version", "0.1.0")
    package.setdefault("description", f"Polyglot client SDKs for {org}/{repo}.")
    package.setdefault("license", "MIT")
    repository = package.get("repository")
    if not isinstance(repository, dict):
        repository = tomlkit.table()
        package["repository"] = repository
    repository["vcs"] = "git"
    repository["url"] = f"https://github.com/{org}/{repo}"

    install = data.setdefault("install", tomlkit.table())
    if isinstance(install, dict):
        install.setdefault("dir", ".vendor/.zed")

    targets = data.setdefault("targets", tomlkit.table())
    if not isinstance(targets, dict):
        raise ValueError(".zpkg.toml [targets] must be a table")
    repository_target = targets.setdefault("repository", tomlkit.table())
    if isinstance(repository_target, dict):
        repository_target["dir"] = "."

    for spec in TARGETS:
        current = targets.get(spec.zed_target)
        for alias in spec.zed_aliases:
            if alias not in targets:
                continue
            legacy = targets.get(alias)
            if isinstance(legacy, dict):
                if not isinstance(current, dict):
                    current = legacy
                    targets[spec.zed_target] = current
                else:
                    merge_missing_table(current, legacy)
            del targets[alias]
        if not isinstance(current, dict):
            current = tomlkit.table()
            targets[spec.zed_target] = current
        current["dir"] = target_dirs[spec.name].relative_to(root).as_posix()
        current["adapter"] = spec.adapter

    rendered = tomlkit.dumps(data)
    tomllib.loads(rendered)
    write_text(path, rendered, changed)


def scaffold_target(
    root: Path,
    spec: TargetSpec,
    directory: Path,
    org: str,
    repo: str,
    prefix: str,
    changed: list[str],
) -> None:
    cap = camel(prefix)
    s = snake(prefix)
    package = kebab(prefix)

    if spec.name == "c":
        write_text(directory / "CMakeLists.txt", f'''cmake_minimum_required(VERSION 3.20)
project({s}_client C)
add_library({s}_client src/{s}_client.c)
target_include_directories({s}_client PUBLIC include)
target_compile_features({s}_client PUBLIC c_std_11)
''', changed, missing_only=True)
        write_text(directory / f"include/{s}_client.h", f'''#ifndef {s.upper()}_CLIENT_H
#define {s.upper()}_CLIENT_H
#include <stdbool.h>
typedef struct {{ const char *base_url; const char *bearer_token; }} {s}_client;
{s}_client {s}_client_new(const char *base_url, const char *bearer_token);
bool {s}_client_health(const {s}_client *client);
#endif
''', changed, missing_only=True)
        write_text(directory / f"src/{s}_client.c", f'''#include "{s}_client.h"
{s}_client {s}_client_new(const char *base_url, const char *bearer_token) {{
  {s}_client value = {{base_url, bearer_token}}; return value;
}}
bool {s}_client_health(const {s}_client *client) {{ return client != 0 && client->base_url != 0; }}
''', changed, missing_only=True)
    elif spec.name == "cpp":
        write_text(directory / "CMakeLists.txt", f'''cmake_minimum_required(VERSION 3.20)
project({s}_client_cpp CXX)
add_library({s}_client_cpp INTERFACE)
target_include_directories({s}_client_cpp INTERFACE include)
target_compile_features({s}_client_cpp INTERFACE cxx_std_17)
''', changed, missing_only=True)
        write_text(directory / f"include/{s}/client.hpp", f'''#pragma once
#include <optional>
#include <string>
#include <utility>
namespace {s} {{
class {cap}Client final {{
 public:
  explicit {cap}Client(std::string base_url, std::optional<std::string> bearer_token = std::nullopt)
      : base_url_(std::move(base_url)), bearer_token_(std::move(bearer_token)) {{}}
  [[nodiscard]] bool health() const noexcept {{ return !base_url_.empty(); }}
 private:
  std::string base_url_;
  std::optional<std::string> bearer_token_;
}};
}}
''', changed, missing_only=True)
    elif spec.name == "zig":
        legacy_build = '''const std = @import("std");
pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});
    const lib = b.addStaticLibrary(.{ .name = "client", .root_source_file = b.path("src/root.zig"), .target = target, .optimize = optimize });
    b.installArtifact(lib);
}
'''
        build = '''const std = @import("std");
pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});
    const lib = b.addLibrary(.{
        .name = "client",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/root.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    b.installArtifact(lib);
}
'''
        write_generated_text(
            directory / "build.zig",
            build,
            changed,
            previous_templates=(legacy_build,),
        )
        write_text(directory / "src/root.zig", '''pub const Client = struct {
    base_url: []const u8,
    bearer_token: ?[]const u8 = null,
    pub fn health(self: Client) bool { return self.base_url.len > 0; }
};
''', changed, missing_only=True)
    elif spec.name == "wasm":
        write_text(directory / "Cargo.toml", f'''[package]
name = "{package}-client-wasm"
version = "0.1.0"
edition = "2021"
[lib]
crate-type = ["cdylib", "rlib"]
''', changed, missing_only=True)
        write_text(directory / "src/lib.rs", '''#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Client { pub base_url: String, pub bearer_token: Option<String> }
impl Client {
    pub fn new(base_url: impl Into<String>, bearer_token: Option<String>) -> Self { Self { base_url: base_url.into(), bearer_token } }
    pub fn health(&self) -> bool { !self.base_url.is_empty() }
}
''', changed, missing_only=True)
    elif spec.name == "gleamlang":
        write_text(directory / "gleam.toml", f'''name = "{s}_client"
version = "0.1.0"
target = "erlang"
[dependencies]
gleam_stdlib = ">= 0.44.0 and < 2.0.0"
''', changed, missing_only=True)
        write_text(directory / f"src/{s}_client.gleam", '''import gleam/option.{type Option}
pub type Client { Client(base_url: String, bearer_token: Option(String)) }
pub fn new(base_url: String, bearer_token: Option(String)) -> Client { Client(base_url:, bearer_token:) }
pub fn health(client: Client) -> Bool { client.base_url != "" }
''', changed, missing_only=True)
    elif spec.name == "erlang":
        write_text(directory / "rebar.config", "{erl_opts, [debug_info, warnings_as_errors]}.\n", changed, missing_only=True)
        write_text(directory / f"src/{s}_client.erl", f'''-module({s}_client).
-export([new/2, health/1]).
new(BaseUrl, BearerToken) -> #{{base_url => BaseUrl, bearer_token => BearerToken}}.
health(Client) -> maps:get(base_url, Client, <<>>) =/= <<>>.
''', changed, missing_only=True)
    elif spec.name == "elixir":
        write_text(directory / "mix.exs", f'''defmodule {cap}Client.MixProject do
  use Mix.Project
  def project, do: [app: :{s}_client, version: "0.1.0", elixir: "~> 1.15"]
  def application, do: [extra_applications: [:logger]]
end
''', changed, missing_only=True)
        write_text(directory / f"lib/{s}_client.ex", f'''defmodule {cap}Client do
  @enforce_keys [:base_url]
  defstruct [:base_url, :bearer_token]
  def new(base_url, bearer_token \\ nil), do: %__MODULE__{{base_url: base_url, bearer_token: bearer_token}}
  def health(%__MODULE__{{base_url: url}}), do: url != ""
end
''', changed, missing_only=True)
    elif spec.name == "dart":
        write_text(directory / "pubspec.yaml", f'''name: {s}_client
version: 0.1.0
environment:
  sdk: ">=3.3.0 <4.0.0"
''', changed, missing_only=True)
        write_text(directory / f"lib/{s}_client.dart", f'''final class {cap}Client {{
  const {cap}Client({{required this.baseUrl, this.bearerToken}});
  final Uri baseUrl;
  final String? bearerToken;
  Future<bool> health() async => baseUrl.toString().isNotEmpty;
}}
''', changed, missing_only=True)
    elif spec.name == "rust":
        write_text(directory / "Cargo.toml", f'''[package]
name = "{package}-client"
version = "0.1.0"
edition = "2021"
''', changed, missing_only=True)
        write_text(directory / "src/lib.rs", '''#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Client { pub base_url: String, pub bearer_token: Option<String> }
impl Client {
    pub fn new(base_url: impl Into<String>, bearer_token: Option<String>) -> Self { Self { base_url: base_url.into(), bearer_token } }
    pub async fn health(&self) -> bool { !self.base_url.is_empty() }
}
''', changed, missing_only=True)
    elif spec.name == "java":
        java_pkg = f"io.zedpkg.{s}"
        java_path = java_pkg.replace(".", "/")
        write_text(directory / "settings.gradle.kts", f'rootProject.name = "{package}-client"\n', changed, missing_only=True)
        write_text(directory / "build.gradle.kts", '''plugins { `java-library` }
group = "io.zedpkg"
version = "0.1.0"
java { toolchain { languageVersion.set(JavaLanguageVersion.of(17)) } }
''', changed, missing_only=True)
        write_text(directory / f"src/main/java/{java_path}/{cap}Client.java", f'''package {java_pkg};
import java.net.URI;
public record {cap}Client(URI baseUrl, String bearerToken) {{
  public boolean health() {{ return baseUrl != null; }}
}}
''', changed, missing_only=True)
    elif spec.name == "golang":
        write_text(directory / "go.mod", f"module github.com/{org}/{repo}/clients/golang\n\ngo 1.22\n", changed, missing_only=True)
        write_text(directory / "client.go", f'''package {s}client
import "net/url"
type Client struct {{ BaseURL *url.URL; BearerToken string }}
func New(baseURL, bearerToken string) (*Client, error) {{ parsed, err := url.Parse(baseURL); if err != nil {{ return nil, err }}; return &Client{{BaseURL: parsed, BearerToken: bearerToken}}, nil }}
func (c *Client) Health() bool {{ return c != nil && c.BaseURL != nil }}
''', changed, missing_only=True)
    elif spec.name == "python3":
        write_text(directory / "pyproject.toml", f'''[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"
[project]
name = "{package}-client"
version = "0.1.0"
requires-python = ">=3.10"
''', changed, missing_only=True)
        write_text(directory / f"src/{s}_client/__init__.py", '''from .client import Client
__all__ = ["Client"]
''', changed, missing_only=True)
        write_text(directory / f"src/{s}_client/client.py", '''from dataclasses import dataclass
@dataclass(frozen=True, slots=True)
class Client:
    base_url: str
    bearer_token: str | None = None
    async def health(self) -> bool:
        return bool(self.base_url)
''', changed, missing_only=True)
    elif spec.name == "ruby":
        legacy_gemspec = f'''Gem::Specification.new do |spec|
  spec.name = "{package}-client"
  spec.version = "0.1.0"
  spec.summary = "Ruby client for {prefix}"
  spec.files = Dir["lib/**/*.rb"]
  spec.required_ruby_version = ">= 3.1"
end
'''
        legacy_standardizer_gemspec = f'''Gem::Specification.new do |spec|
  spec.name = "{package}-client"
  spec.version = "0.1.0"
  spec.summary = "Ruby client SDK for {prefix}"
  spec.files = Dir["lib/**/*.rb"]
  spec.required_ruby_version = ">= 3.1"
end
'''
        gemspec = f'''Gem::Specification.new do |spec|
  spec.name = "{package}-client"
  spec.version = "0.1.0"
  spec.summary = "Ruby client for {prefix}"
  spec.authors = ["{org} contributors"]
  spec.license = "MIT"
  spec.files = Dir["lib/**/*.rb"]
  spec.required_ruby_version = ">= 3.1"
end
'''
        write_generated_text(
            directory / f"{package}-client.gemspec",
            gemspec,
            changed,
            previous_templates=(legacy_gemspec, legacy_standardizer_gemspec),
        )
        write_text(directory / f"lib/{s}_client.rb", f'''class {cap}Client
  attr_reader :base_url, :bearer_token
  def initialize(base_url:, bearer_token: nil)
    @base_url = base_url
    @bearer_token = bearer_token
  end
  def health = !@base_url.empty?
end
''', changed, missing_only=True)
    elif spec.name == "php":
        namespace = f"ZedPkg\\{cap}"
        write_json(directory / "composer.json", {
            "name": f"{kebab(org)}/{package}-client",
            "type": "library",
            "require": {"php": ">=8.2"},
            "autoload": {"psr-4": {namespace + "\\": "src/"}},
        }, changed, missing_only=True)
        write_text(directory / "src/Client.php", f'''<?php
declare(strict_types=1);
namespace {namespace};
final readonly class Client {{
  public function __construct(public string $baseUrl, public ?string $bearerToken = null) {{}}
  public function health(): bool {{ return $this->baseUrl !== ''; }}
}}
''', changed, missing_only=True)
    elif spec.name == "kotlin":
        kotlin_pkg = f"io.zedpkg.{s}"
        kotlin_path = kotlin_pkg.replace(".", "/")
        write_text(directory / "settings.gradle.kts", f'rootProject.name = "{package}-client-kotlin"\n', changed, missing_only=True)
        write_text(directory / "build.gradle.kts", '''plugins { kotlin("jvm") version "2.0.21" }
group = "io.zedpkg"
version = "0.1.0"
repositories { mavenCentral() }
kotlin { jvmToolchain(17) }
''', changed, missing_only=True)
        write_text(directory / f"src/main/kotlin/{kotlin_path}/{cap}Client.kt", f'''package {kotlin_pkg}
import java.net.URI
data class {cap}Client(val baseUrl: URI, val bearerToken: String? = null) {{
  suspend fun health(): Boolean = baseUrl.toString().isNotEmpty()
}}
''', changed, missing_only=True)
    elif spec.name == "swift":
        write_text(directory / "Package.swift", f'''// swift-tools-version: 5.9
import PackageDescription
let package = Package(
  name: "{cap}Client",
  products: [.library(name: "{cap}Client", targets: ["{cap}Client"])],
  targets: [.target(name: "{cap}Client")]
)
''', changed, missing_only=True)
        write_text(directory / f"Sources/{cap}Client/Client.swift", '''import Foundation
public struct Client: Sendable {
  public let baseURL: URL
  public let bearerToken: String?
  public init(baseURL: URL, bearerToken: String? = nil) { self.baseURL = baseURL; self.bearerToken = bearerToken }
  public func health() async -> Bool { !baseURL.absoluteString.isEmpty }
}
''', changed, missing_only=True)
    elif spec.runtime:
        if directory == root / "clients/typescript":
            return
        source = '''export interface ClientOptions { readonly baseUrl: string; readonly bearerToken?: string }
export class Client {
  readonly baseUrl: URL;
  readonly bearerToken?: string;
  constructor(options: ClientOptions) { this.baseUrl = new URL(options.baseUrl); this.bearerToken = options.bearerToken; }
  async health(): Promise<boolean> { return this.baseUrl.href.length > 0; }
}
export function createClient(options: ClientOptions): Client { return new Client(options); }
'''
        if spec.runtime == "deno":
            write_json(directory / "deno.json", {"name": f"@{kebab(org)}/{package}-client-deno", "version": "0.1.0", "exports": "./mod.ts"}, changed, missing_only=True)
            write_text(directory / "mod.ts", source, changed, missing_only=True)
        else:
            write_json(directory / "package.json", {"name": f"@{kebab(org)}/{package}-client-{spec.runtime}", "version": "0.1.0", "type": "module", "exports": "./src/index.ts"}, changed, missing_only=True)
            write_text(directory / "src/index.ts", source, changed, missing_only=True)


def ensure_matrix(root: Path, target_dirs: dict[str, Path], changed: list[str]) -> None:
    matrix: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "minimum_targets": MINIMUM_TARGETS,
        "standard_target_count": len(TARGETS),
        "api_surface": "clients/api-surface.json",
        "api_schema": "clients/client-api.schema.json",
        "targets": {
            spec.name: {
                "dir": target_dirs[spec.name].relative_to(root).as_posix(),
                "zed_target": spec.zed_target,
                "runtime": spec.runtime or spec.name,
            }
            for spec in TARGETS
        },
    }
    write_json(root / "clients/sdk-matrix.json", matrix, changed)


def ensure_contract(
    root: Path,
    schema_source: Path,
    org: str,
    repo: str,
    prefix: str,
    target_dirs: dict[str, Path],
    changed: list[str],
) -> tuple[dict[str, Any], str]:
    schema = json.loads(schema_source.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    write_json(root / "clients/client-api.schema.json", schema, changed)

    surface_path = root / "clients/api-surface.json"
    if surface_path.exists():
        surface = json.loads(surface_path.read_text(encoding="utf-8"))
        package = surface.setdefault("package", {})
        package["coordinate"] = f"{org}/{repo}"
        package.setdefault("namespace", camel(prefix))
        surface["schemaVersion"] = SCHEMA_VERSION
        surface["$schema"] = "./client-api.schema.json"
        merge_standard_symbols(surface, str(package["namespace"]))
    else:
        surface = baseline_surface(org, repo, prefix)

    validator = Draft202012Validator(schema)
    schema_errors = sorted(validator.iter_errors(surface), key=lambda item: list(item.absolute_path))
    if schema_errors:
        rendered = "; ".join(f"{'/'.join(map(str, item.absolute_path)) or '<root>'}: {item.message}" for item in schema_errors)
        raise ValueError(f"api surface does not satisfy client-api.schema.json: {rendered}")
    semantic = semantic_errors(surface)
    if semantic:
        raise ValueError("api surface semantic errors: " + "; ".join(semantic))

    write_json(surface_path, surface, changed)
    surface_digest = digest(surface)
    write_text(root / "clients/.api-surface.sha256", surface_digest, changed)

    contracts: list[dict[str, Any]] = []
    for spec in TARGETS:
        directory = target_dirs[spec.name]
        marker = marker_dir(root, spec, directory)
        contract = {
            "schemaVersion": SCHEMA_VERSION,
            "coordinate": f"{org}/{repo}",
            "target": spec.name,
            "zedTarget": spec.zed_target,
            "runtime": spec.runtime or spec.name,
            "apiSurface": "clients/api-surface.json",
            "apiSurfaceSha256": surface_digest,
            "schemaId": schema["$id"],
        }
        write_json(marker / ".zed-client-contract.json", contract, changed)
        write_text(marker / ".zed-api-surface.sha256", surface_digest, changed)
        contracts.append({**contract, "dir": directory.relative_to(root).as_posix()})

    write_json(
        root / "clients/contract-manifest.json",
        {
            "schemaVersion": SCHEMA_VERSION,
            "coordinate": f"{org}/{repo}",
            "apiSurfaceSha256": surface_digest,
            "targetCount": len(TARGETS),
            "targets": contracts,
        },
        changed,
    )
    return surface, surface_digest


def verify(root: Path, schema_source: Path) -> list[str]:
    errors: list[str] = []
    schema_path = root / "clients/client-api.schema.json"
    surface_path = root / "clients/api-surface.json"
    manifest_path = root / ".zpkg.toml"
    matrix_path = root / "clients/sdk-matrix.json"
    if not schema_path.is_file():
        errors.append("missing clients/client-api.schema.json")
        return errors
    if not surface_path.is_file():
        errors.append("missing clients/api-surface.json")
        return errors
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        canonical_schema = json.loads(schema_source.read_text(encoding="utf-8"))
        if digest(schema) != digest(canonical_schema):
            errors.append("client-api.schema.json differs from canonical schema")
        Draft202012Validator.check_schema(schema)
        surface = json.loads(surface_path.read_text(encoding="utf-8"))
        for item in Draft202012Validator(schema).iter_errors(surface):
            errors.append(f"api-surface schema error at {'/'.join(map(str, item.absolute_path)) or '<root>'}: {item.message}")
        errors.extend(semantic_errors(surface))
        surface_digest = digest(surface)
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(str(exc))
        return errors

    if not manifest_path.is_file():
        errors.append("missing .zpkg.toml")
        return errors
    try:
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        errors.append(f"invalid .zpkg.toml: {exc}")
        return errors
    targets = manifest.get("targets", {})
    repository_root = root.resolve()
    target_owners: dict[Path, str] = {}
    if isinstance(targets, dict):
        for target_name, target in targets.items():
            if not isinstance(target, dict) or not isinstance(target.get("dir"), str):
                continue
            target_root = (root / target["dir"]).resolve()
            if not target_root.is_relative_to(repository_root):
                errors.append(f"target {target_name} source directory escapes repository: {target['dir']!r}")
                continue
            previous = target_owners.get(target_root)
            if previous is not None:
                errors.append(
                    f"targets {previous} and {target_name} share source directory {target['dir']!r}"
                )
            else:
                target_owners[target_root] = str(target_name)
    for spec in TARGETS:
        for alias in spec.zed_aliases:
            if alias in targets:
                errors.append(f"legacy target alias [targets.{alias}] must migrate to [targets.{spec.zed_target}]")
    found = 0
    for spec in TARGETS:
        entry = targets.get(spec.zed_target)
        if not isinstance(entry, dict):
            errors.append(f"missing [targets.{spec.zed_target}]")
            continue
        raw_dir = entry.get("dir")
        if not isinstance(raw_dir, str):
            errors.append(f"target {spec.zed_target} points to missing directory: {raw_dir!r}")
            continue
        directory = (root / raw_dir).resolve()
        if not directory.is_relative_to(repository_root):
            errors.append(f"target {spec.zed_target} source directory escapes repository: {raw_dir!r}")
            continue
        if not directory.is_dir():
            errors.append(f"target {spec.zed_target} points to missing directory: {raw_dir!r}")
            continue
        found += 1
        marker = marker_dir(root, spec, directory)
        digest_path = marker / ".zed-api-surface.sha256"
        contract_path = marker / ".zed-client-contract.json"
        if not digest_path.is_file() or digest_path.read_text(encoding="utf-8").strip() != surface_digest:
            errors.append(f"{spec.name} API fingerprint is missing or stale")
        if not contract_path.is_file():
            errors.append(f"{spec.name} contract marker is missing")
        else:
            try:
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                if contract.get("apiSurfaceSha256") != surface_digest or contract.get("target") != spec.name:
                    errors.append(f"{spec.name} contract marker does not match the canonical surface")
            except json.JSONDecodeError as exc:
                errors.append(f"{spec.name} contract marker is invalid JSON: {exc}")
    if found < MINIMUM_TARGETS:
        errors.append(f"only {found} targets are valid; at least {MINIMUM_TARGETS} are required")
    if found != len(TARGETS):
        errors.append(f"standard fleet target count is {found}; expected {len(TARGETS)}")
    if not matrix_path.is_file():
        errors.append("missing clients/sdk-matrix.json")
    return sorted(set(errors))


def infer_identity(root: Path, explicit_org: str | None, explicit_repo: str | None, explicit_prefix: str | None) -> tuple[str, str, str]:
    manifest: dict[str, Any] = {}
    path = root / ".zpkg.toml"
    if path.exists():
        try:
            manifest = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            manifest = {}
    package = manifest.get("package", {}) if isinstance(manifest, dict) else {}
    org = explicit_org or (package.get("org") if isinstance(package, dict) else None)
    repo = explicit_repo or (package.get("name") if isinstance(package, dict) else None) or root.name
    if not org:
        raise ValueError("--org is required when .zpkg.toml does not declare package.org")
    suffix = "-clients"
    prefix = explicit_prefix or (repo[: -len(suffix)] if repo.endswith(suffix) else repo)
    return str(org), str(repo), str(prefix)


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    schema_source = args.schema.resolve()
    org, repo, prefix = infer_identity(root, args.org, args.repo, args.prefix)
    changed: list[str] = []

    manifest_targets: dict[str, Any] = {}
    manifest_path = root / ".zpkg.toml"
    if manifest_path.exists():
        try:
            parsed_manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
            raw_targets = parsed_manifest.get("targets", {})
            if isinstance(raw_targets, dict):
                manifest_targets = raw_targets
        except tomllib.TOMLDecodeError:
            manifest_targets = {}
    target_dirs = choose_target_dirs(root, manifest_targets)
    if args.write:
        for spec in TARGETS:
            directory = target_dirs[spec.name]
            directory.mkdir(parents=True, exist_ok=True)
            scaffold_target(root, spec, directory, org, repo, prefix, changed)
        ensure_manifest(root, org, repo, target_dirs, changed)
        ensure_matrix(root, target_dirs, changed)
        _, surface_digest = ensure_contract(root, schema_source, org, repo, prefix, target_dirs, changed)
    else:
        surface_path = root / "clients/api-surface.json"
        surface_digest = digest(json.loads(surface_path.read_text(encoding="utf-8"))) if surface_path.exists() else ""

    errors = verify(root, schema_source)
    result = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": f"{org}/{repo}",
        "prefix": prefix,
        "mode": "write" if args.write else "check",
        "minimumTargets": MINIMUM_TARGETS,
        "standardTargets": len(TARGETS),
        "apiSurfaceSha256": surface_digest,
        "changed": sorted(set(changed)),
        "errors": errors,
    }
    if args.output:
        write_json(args.output, result, [])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--org")
    parser.add_argument("--repo")
    parser.add_argument("--prefix")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:  # noqa: BLE001 - CLI must report repository-specific failures.
        print(json.dumps({"errors": [f"{type(exc).__name__}: {exc}"]}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
