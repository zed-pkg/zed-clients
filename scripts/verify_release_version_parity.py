#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = tomllib.loads((ROOT / ".zpkg.toml").read_text())["package"]["version"]

def require(label: str, actual: str) -> None:
    if actual != EXPECTED:
        raise SystemExit(f"{label}: version {actual!r} != root release {EXPECTED!r}")

require("rust", tomllib.loads((ROOT / "clients/rust/Cargo.toml").read_text())["package"]["version"])
require("rust-wasm", tomllib.loads((ROOT / "clients/wasm/Cargo.toml").read_text())["package"]["version"])
require("nodejs", json.loads((ROOT / "clients/typescript/package.json").read_text())["version"])
require("python", tomllib.loads((ROOT / "clients/python/pyproject.toml").read_text())["project"]["version"])

dart = re.search(r"^version:\s*([^\s]+)\s*$", (ROOT / "clients/dart/pubspec.yaml").read_text(), re.MULTILINE)
require("dart", dart.group(1) if dart else "")

require("gleam", tomllib.loads((ROOT / "clients/gleam/gleam.toml").read_text())["version"])

elixir = re.search(r'version:\s*"([^"]+)"', (ROOT / "clients/elixir/mix.exs").read_text())
require("elixir", elixir.group(1) if elixir else "")

for label, path in (
    ("java", ROOT / "clients/java/pom.xml"),
    ("kotlin", ROOT / "clients/kotlin/pom.xml"),
):
    root = ElementTree.fromstring(path.read_text())
    namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
    value = root.findtext("m:version", namespaces=namespace) or ""
    require(label, value)

ruby = re.search(r'spec\.version\s*=\s*"([^"]+)"', (ROOT / "clients/ruby/zed_pkg_client.gemspec").read_text())
require("ruby", ruby.group(1) if ruby else "")

cpp = re.search(r"project\([^)]*\bVERSION\s+([^\s)]+)", (ROOT / "clients/cpp/CMakeLists.txt").read_text())
require("cpp", cpp.group(1) if cpp else "")

erlang = re.search(r'\{vsn,\s*"([^"]+)"\}', (ROOT / "clients/erlang/src/zed_pkg_client.app.src").read_text())
require("erlang", erlang.group(1) if erlang else "")

node_lock = json.loads((ROOT / "clients/typescript/package-lock.json").read_text())
require("nodejs lock root", node_lock["version"])
require("nodejs lock package", node_lock["packages"][""]["version"])

for label, lock_path, package_name in (
    ("rust lock", ROOT / "clients/rust/Cargo.lock", "zed-client"),
    ("rust-wasm lock", ROOT / "clients/wasm/Cargo.lock", "zed-client-wasm"),
):
    lock = tomllib.loads(lock_path.read_text())
    matches = [pkg["version"] for pkg in lock["package"] if pkg["name"] == package_name]
    if matches != [EXPECTED]:
        raise SystemExit(f"{label}: expected one {package_name}@{EXPECTED}, got {matches!r}")

print(f"release version parity OK: {EXPECTED}")
