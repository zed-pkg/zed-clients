#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import textwrap
import tomllib
from pathlib import Path

import tomlkit


def clean(value: str) -> str:
    return textwrap.dedent(value).lstrip().rstrip() + "\n"


def snake(value: str) -> str:
    out = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return ("z_" + out) if out[:1].isdigit() else (out or "zed")


def camel(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", value)
    out = "".join(part[:1].upper() + part[1:] for part in parts) or "Zed"
    return ("Z" + out) if out[:1].isdigit() else out


def npm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-") or "zed-pkg"


def write_missing(path: str, content: str, changed: list[str]) -> None:
    target = Path(path)
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(clean(content), encoding="utf-8")
    changed.append(path)


def write_replace(path: str, content: str, changed: list[str]) -> None:
    target = Path(path)
    rendered = clean(content)
    old = target.read_text(encoding="utf-8") if target.exists() else None
    if old == rendered:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    changed.append(path)


def ensure_manifest(org: str, prefix: str, repo: str, kind: str, mobile: bool, changed: list[str]) -> None:
    path = Path(".zpkg.toml")
    data = tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else {}

    package = data.setdefault("package", {})
    if not isinstance(package, dict):
        raise TypeError(".zpkg.toml [package] must be a TOML table")
    package["org"] = org
    package["name"] = repo
    package.setdefault("version", "0.1.0")
    package.setdefault("description", f"{kind.capitalize()} Zed package for {prefix}.")
    package.setdefault("license", "MIT")
    repository = package.get("repository")
    if isinstance(repository, dict):
        repository["vcs"] = "git"
        repository["url"] = f"https://github.com/{org}/{repo}"
    elif repository is None:
        package["repository"] = {"vcs": "git", "url": f"https://github.com/{org}/{repo}"}

    deps = data.setdefault("dependencies", {})
    if not isinstance(deps, dict):
        raise TypeError(".zpkg.toml [dependencies] must be a TOML table")
    required: list[str] = []
    if kind == "lib":
        required = [f"{prefix}-interfaces"]
    elif kind == "clients":
        required = [f"{prefix}-interfaces", f"{prefix}-lib"]
    elif kind == "cli":
        required = [f"{prefix}-interfaces", f"{prefix}-lib", f"{prefix}-clients"]
    for name in required:
        deps[f"{org}/{name}"] = deps.get(f"{org}/{name}", "^0.1.0")

    if kind == "clients":
        targets = data.setdefault("targets", {})
        if not isinstance(targets, dict):
            raise TypeError(".zpkg.toml [targets] must be a TOML table")
        target_data = {
            "repository": {"dir": "."},
            "gleamlang": {"dir": "clients/gleamlang", "adapter": "none"},
            "erlang": {"dir": "clients/erlang", "adapter": "none"},
            "elixir": {"dir": "clients/elixir", "adapter": "none"},
            "dart": {"dir": "clients/dart", "adapter": "dart"},
            "rust": {"dir": "clients/rust", "adapter": "rust"},
            "java": {"dir": "clients/java", "adapter": "java"},
            "golang": {"dir": "clients/golang", "adapter": "go"},
            "python3": {"dir": "clients/python3", "adapter": "none"},
            "ruby": {"dir": "clients/ruby", "adapter": "none"},
            "php": {"dir": "clients/php", "adapter": "none"},
            "typescript-nodejs": {"dir": "clients/typescript/nodejs", "adapter": "node"},
            "typescript-deno": {"dir": "clients/typescript/deno", "adapter": "none"},
            "typescript-bun": {"dir": "clients/typescript/bun", "adapter": "node"},
            "typescript-edge": {"dir": "clients/typescript/edge", "adapter": "none"},
        }
        if mobile:
            target_data.update({
                "kotlin": {"dir": "clients/kotlin", "adapter": "none"},
                "swift": {"dir": "clients/swift", "adapter": "none"},
            })
        for name, value in target_data.items():
            current = targets.get(name)
            if isinstance(current, dict):
                current.update(value)
            else:
                targets[name] = value

    rendered = tomlkit.dumps(data)
    tomllib.loads(rendered)
    write_replace(str(path), rendered, changed)


def scaffold_clients(org: str, prefix: str, mobile: bool, changed: list[str]) -> None:
    s = snake(prefix)
    cap = camel(prefix)
    pkg = f"{s}_client"
    repo = f"{prefix}-clients"
    java_pkg = f"io.zedpkg.{s}"
    java_path = java_pkg.replace(".", "/")
    scope = npm_name(org)

    write_replace("clients/sdk-matrix.toml", f"""
        schema_version = 1
        interfaces_package = "{prefix}-interfaces"
        shared_library_package = "{prefix}-lib"

        [targets]
        gleamlang = true
        erlang = true
        elixir = true
        dart = true
        rust = true
        java = true
        golang = true
        python3 = true
        ruby = true
        php = true
        typescript_nodejs = true
        typescript_deno = true
        typescript_bun = true
        typescript_edge = true
        kotlin = {str(mobile).lower()}
        swift = {str(mobile).lower()}
    """, changed)

    write_missing("clients/README.md", f"""
        # {prefix} client SDKs

        These runtime-specific SDK baselines depend on the `{prefix}-interfaces`
        and `{prefix}-lib` Zed packages. Existing product bindings are preserved;
        missing targets receive a transport-neutral client configuration baseline.
    """, changed)

    write_missing("clients/gleamlang/gleam.toml", f"""
        name = "{pkg}"
        version = "0.1.0"
        target = "erlang"
        [dependencies]
        gleam_stdlib = ">= 0.44.0 and < 2.0.0"
    """, changed)
    write_missing(f"clients/gleamlang/src/{pkg}.gleam", """
        import gleam/option.{type Option}
        pub type Client { Client(base_url: String, bearer_token: Option(String)) }
        pub fn new(base_url: String, bearer_token: Option(String)) -> Client {
          Client(base_url: base_url, bearer_token: bearer_token)
        }
    """, changed)

    write_missing("clients/erlang/rebar.config", "{erl_opts, [debug_info, warnings_as_errors]}.\n", changed)
    write_missing(f"clients/erlang/src/{pkg}.erl", f"""
        -module({pkg}).
        -export([new/2, base_url/1]).
        new(BaseUrl, BearerToken) -> #{{base_url => BaseUrl, bearer_token => BearerToken}}.
        base_url(Client) -> maps:get(base_url, Client).
    """, changed)

    write_missing("clients/elixir/mix.exs", f"""
        defmodule {cap}Client.MixProject do
          use Mix.Project
          def project, do: [app: :{pkg}, version: "0.1.0", elixir: "~> 1.15"]
          def application, do: [extra_applications: [:logger, :inets, :ssl]]
        end
    """, changed)
    write_missing(f"clients/elixir/lib/{pkg}.ex", f"""
        defmodule {cap}Client do
          @enforce_keys [:base_url]
          defstruct [:base_url, :bearer_token]
          def new(base_url, bearer_token \\ nil), do: %__MODULE__{{base_url: base_url, bearer_token: bearer_token}}
        end
    """, changed)

    write_missing("clients/dart/pubspec.yaml", f"""
        name: {pkg}
        version: 0.1.0
        environment:
          sdk: ">=3.3.0 <4.0.0"
    """, changed)
    write_missing(f"clients/dart/lib/{pkg}.dart", f"""
        final class {cap}Client {{
          const {cap}Client({{required this.baseUrl, this.bearerToken}});
          final Uri baseUrl;
          final String? bearerToken;
        }}
    """, changed)

    write_missing("clients/rust/Cargo.toml", f"""
        [package]
        name = "{prefix}-client"
        version = "0.1.0"
        edition = "2021"
        [dependencies]
        url = "2"
    """, changed)
    write_missing("clients/rust/src/lib.rs", """
        use url::Url;
        #[derive(Clone, Debug)]
        pub struct Client { pub base_url: Url, pub bearer_token: Option<String> }
        impl Client {
            pub fn new(base_url: Url, bearer_token: Option<String>) -> Self { Self { base_url, bearer_token } }
        }
    """, changed)

    write_missing("clients/java/settings.gradle.kts", f'rootProject.name = "{prefix}-client"\n', changed)
    write_missing("clients/java/build.gradle.kts", """
        plugins { `java-library` }
        group = "io.zedpkg"
        version = "0.1.0"
        java { toolchain { languageVersion.set(JavaLanguageVersion.of(17)) } }
    """, changed)
    write_missing(f"clients/java/src/main/java/{java_path}/{cap}Client.java", f"""
        package {java_pkg};
        import java.net.URI;
        public record {cap}Client(URI baseUri, String bearerToken) {{}}
    """, changed)

    write_missing("clients/golang/go.mod", f"module github.com/{org}/{repo}/clients/golang\n\ngo 1.22\n", changed)
    write_missing("clients/golang/client.go", f"""
        package {s}client
        import "net/url"
        type Client struct {{ BaseURL *url.URL; BearerToken string }}
        func New(baseURL, bearerToken string) (*Client, error) {{
            parsed, err := url.Parse(baseURL); if err != nil {{ return nil, err }}
            return &Client{{BaseURL: parsed, BearerToken: bearerToken}}, nil
        }}
    """, changed)

    write_missing("clients/python3/pyproject.toml", f"""
        [build-system]
        requires = ["hatchling>=1.24"]
        build-backend = "hatchling.build"
        [project]
        name = "{prefix}-client"
        version = "0.1.0"
        requires-python = ">=3.10"
    """, changed)
    write_missing(f"clients/python3/src/{pkg}/__init__.py", "from .client import Client\n\n__all__ = [\"Client\"]\n", changed)
    write_missing(f"clients/python3/src/{pkg}/client.py", """
        from dataclasses import dataclass
        @dataclass(frozen=True, slots=True)
        class Client:
            base_url: str
            bearer_token: str | None = None
    """, changed)

    write_missing(f"clients/ruby/{prefix}-client.gemspec", f"""
        Gem::Specification.new do |spec|
          spec.name = "{prefix}-client"
          spec.version = "0.1.0"
          spec.summary = "Ruby client SDK for {prefix}"
          spec.files = Dir["lib/**/*.rb"]
          spec.required_ruby_version = ">= 3.1"
        end
    """, changed)
    write_missing(f"clients/ruby/lib/{pkg}.rb", f"""
        class {cap}Client
          attr_reader :base_url, :bearer_token
          def initialize(base_url:, bearer_token: nil)
            @base_url = base_url
            @bearer_token = bearer_token
          end
        end
    """, changed)

    php_ns = f"ZedPkg\\{cap}"
    write_missing("clients/php/composer.json", json.dumps({
        "name": f"{scope}/{prefix}-client",
        "type": "library",
        "require": {"php": ">=8.2"},
        "autoload": {"psr-4": {php_ns + "\\\\": "src/"}},
    }, indent=2), changed)
    write_missing("clients/php/src/Client.php", f"""
        <?php
        declare(strict_types=1);
        namespace {php_ns};
        final readonly class Client {{
            public function __construct(public string $baseUrl, public ?string $bearerToken = null) {{}}
        }}
    """, changed)

    ts = """
        export interface ClientOptions { baseUrl: string; bearerToken?: string }
        export class Client {
          readonly baseUrl: URL;
          readonly bearerToken?: string;
          constructor(options: ClientOptions) {
            this.baseUrl = new URL(options.baseUrl);
            this.bearerToken = options.bearerToken;
          }
        }
    """
    for runtime in ("nodejs", "bun", "edge"):
        write_missing(f"clients/typescript/{runtime}/package.json", json.dumps({
            "name": f"@{scope}/{prefix}-client-{runtime}",
            "version": "0.1.0", "type": "module", "exports": "./src/index.ts",
        }, indent=2), changed)
        write_missing(f"clients/typescript/{runtime}/src/index.ts", ts, changed)
    write_missing("clients/typescript/deno/deno.json", json.dumps({
        "name": f"@{scope}/{prefix}-client-deno", "version": "0.1.0", "exports": "./mod.ts",
    }, indent=2), changed)
    write_missing("clients/typescript/deno/mod.ts", ts, changed)

    if mobile:
        write_missing("clients/kotlin/settings.gradle.kts", f'rootProject.name = "{prefix}-client-kotlin"\n', changed)
        write_missing("clients/kotlin/build.gradle.kts", """
            plugins { kotlin("jvm") version "2.0.21" }
            group = "io.zedpkg"
            version = "0.1.0"
            repositories { mavenCentral() }
            kotlin { jvmToolchain(17) }
        """, changed)
        write_missing(f"clients/kotlin/src/main/kotlin/{java_path}/{cap}Client.kt", f"""
            package {java_pkg}
            import java.net.URI
            data class {cap}Client(val baseUri: URI, val bearerToken: String? = null)
        """, changed)
        write_missing("clients/swift/Package.swift", f"""
            // swift-tools-version: 5.9
            import PackageDescription
            let package = Package(
              name: "{cap}Client",
              platforms: [.iOS(.v15), .macOS(.v12)],
              products: [.library(name: "{cap}Client", targets: ["{cap}Client"])],
              targets: [.target(name: "{cap}Client")]
            )
        """, changed)
        write_missing(f"clients/swift/Sources/{cap}Client/Client.swift", """
            import Foundation
            public struct Client: Sendable {
              public let baseURL: URL
              public let bearerToken: String?
              public init(baseURL: URL, bearerToken: String? = nil) {
                self.baseURL = baseURL; self.bearerToken = bearerToken
              }
            }
        """, changed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org")
    parser.add_argument("--prefix")
    parser.add_argument("--kind", choices=("clients", "cli", "lib", "interfaces"), required=True)
    parser.add_argument("--mobile", choices=("true", "false", "auto"), default="auto")
    args = parser.parse_args()

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    env_org, _, env_repo = repository.partition("/")
    repo = env_repo or Path.cwd().name
    org = args.org or env_org
    if not org:
        raise SystemExit("--org or GITHUB_REPOSITORY is required")
    suffix = "-" + args.kind
    prefix = args.prefix or (repo[:-len(suffix)] if repo.endswith(suffix) else repo)
    mobile = args.mobile == "true" or (args.mobile == "auto" and (Path("clients/swift").exists() or Path("clients/kotlin").exists()))

    changed: list[str] = []
    ensure_manifest(org, prefix, repo, args.kind, mobile, changed)
    if args.kind == "clients":
        scaffold_clients(org, prefix, mobile, changed)

    print(json.dumps({"org": org, "repo": repo, "prefix": prefix, "kind": args.kind, "mobile": mobile, "changed": changed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
