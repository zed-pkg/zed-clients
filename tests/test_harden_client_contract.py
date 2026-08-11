from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harden_client_contract.py"
SCHEMA = ROOT / "schemas/client-api.schema.json"


class ClientContractHardenerTests(unittest.TestCase):
    def make_repo(self) -> tempfile.TemporaryDirectory[str]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / ".zpkg.toml").write_text(
            """[package]
org = "acme-cloud"
name = "acme-clients"
version = "0.1.0"

[package.repository]
vcs = "git"
url = "https://github.com/acme-cloud/acme-clients"

[install]
dir = ".vendor/.zed"

[targets.repository]
dir = "."
""",
            encoding="utf-8",
        )
        return temporary

    def run_tool(self, root: Path, mode: str, *, expect: int = 0) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(root),
                "--schema",
                str(SCHEMA),
                mode,
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, expect, result.stderr or result.stdout)
        return json.loads(result.stdout if result.stdout else result.stderr)

    def test_write_check_and_idempotence(self) -> None:
        with self.make_repo() as path:
            root = Path(path)
            first = self.run_tool(root, "--write")
            checked = self.run_tool(root, "--check")
            second = self.run_tool(root, "--write")

            self.assertGreater(len(first["changed"]), 70)
            self.assertEqual(checked["errors"], [])
            self.assertEqual(second["changed"], [])
            self.assertEqual(first["standardTargets"], 20)

            manifest = tomllib.loads((root / ".zpkg.toml").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["targets"]) - 1, 20)
            contract = json.loads((root / "clients/contract-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(contract["targetCount"], 20)
            self.assertEqual(contract["coordinate"], "acme-cloud/acme-clients")
            self.assertIn("github.com/acme-cloud/acme-clients/clients/golang", (root / "clients/golang/go.mod").read_text())
            self.assertIn("b.addLibrary", (root / "clients/zig/build.zig").read_text())
            self.assertIn("b.createModule", (root / "clients/zig/build.zig").read_text())
            self.assertIn(
                'spec.authors = ["acme-cloud contributors"]',
                (root / "clients/ruby/acme-client.gemspec").read_text(),
            )

    def test_aliases_and_shared_typescript_are_preserved(self) -> None:
        with self.make_repo() as path:
            root = Path(path)
            (root / "clients/go").mkdir(parents=True)
            (root / "clients/go/go.mod").write_text("module example.test/existing\n\ngo 1.22\n", encoding="utf-8")
            (root / "clients/python").mkdir(parents=True)
            (root / "clients/python/pyproject.toml").write_text("[project]\nname = \"existing\"\nversion = \"1.0.0\"\n", encoding="utf-8")
            (root / "clients/typescript/src/runtimes/nodejs").mkdir(parents=True)
            (root / "clients/typescript/src/runtimes/deno").mkdir(parents=True)
            (root / "clients/typescript/src/runtimes/bun").mkdir(parents=True)
            (root / "clients/typescript/src/runtimes/edge").mkdir(parents=True)
            (root / "clients/typescript/package.json").write_text('{"name":"existing"}\n', encoding="utf-8")

            self.run_tool(root, "--write")
            manifest = tomllib.loads((root / ".zpkg.toml").read_text(encoding="utf-8"))
            self.assertEqual(manifest["targets"]["golang"]["dir"], "clients/go")
            self.assertEqual(manifest["targets"]["python3"]["dir"], "clients/python")
            self.assertEqual(manifest["targets"]["typescript-nodejs"]["dir"], "clients/typescript")
            self.assertEqual(manifest["targets"]["typescript-deno"]["dir"], "clients/typescript/deno")
            self.assertEqual(manifest["targets"]["typescript-bun"]["dir"], "clients/typescript/bun")
            self.assertEqual(manifest["targets"]["typescript-edge"]["dir"], "clients/typescript/edge")
            canonical_dirs = [manifest["targets"][target]["dir"] for target in (
                "c", "cpp", "zig", "rust-wasm", "gleamlang", "erlang", "elixir", "dart",
                "rust", "java", "golang", "python3", "ruby", "php", "kotlin", "swift",
                "typescript-nodejs", "typescript-deno", "typescript-bun", "typescript-edge",
            )]
            self.assertEqual(len(canonical_dirs), len(set(canonical_dirs)))
            self.assertEqual((root / "clients/go/go.mod").read_text(), "module example.test/existing\n\ngo 1.22\n")
            self.assertTrue((root / "clients/typescript/.zed-contracts/nodejs/.zed-client-contract.json").is_file())

    def test_manifest_aliases_are_migrated_without_duplicate_target_roots(self) -> None:
        with self.make_repo() as path:
            root = Path(path)
            for directory in ("clients/gleam", "clients/python", "clients/typescript"):
                (root / directory).mkdir(parents=True)
            with (root / ".zpkg.toml").open("a", encoding="utf-8") as manifest:
                manifest.write(
                    """
[targets.gleam]
dir = "clients/gleam"
adapter = "none"

[targets.python]
dir = "clients/python"
adapter = "none"

[targets.typescript-nodejs]
dir = "clients/typescript"
adapter = "node"

[targets.typescript-nodejs.native]
registry = "npm"

[targets.nodejs]
dir = "clients/typescript"
adapter = "node"
name = "existing-node-package"

[targets.nodejs.native]
package = "@acme-cloud/existing-node-package"

[targets.deno]
dir = "clients/typescript"
adapter = "none"
"""
                )

            self.run_tool(root, "--write")
            manifest = tomllib.loads((root / ".zpkg.toml").read_text(encoding="utf-8"))
            targets = manifest["targets"]
            for legacy in ("gleam", "python", "nodejs", "deno"):
                self.assertNotIn(legacy, targets)
            self.assertEqual(targets["gleamlang"]["dir"], "clients/gleam")
            self.assertEqual(targets["python3"]["dir"], "clients/python")
            self.assertEqual(targets["typescript-nodejs"]["dir"], "clients/typescript")
            self.assertEqual(targets["typescript-nodejs"]["name"], "existing-node-package")
            self.assertEqual(targets["typescript-nodejs"]["native"]["registry"], "npm")
            self.assertEqual(
                targets["typescript-nodejs"]["native"]["package"],
                "@acme-cloud/existing-node-package",
            )
            target_dirs = [value["dir"] for name, value in targets.items() if name != "repository"]
            self.assertEqual(len(target_dirs), len(set(target_dirs)))

    def test_manifest_target_cannot_escape_repository(self) -> None:
        with self.make_repo() as path, tempfile.TemporaryDirectory() as outside_path:
            root = Path(path)
            outside = Path(outside_path)
            sentinel = outside / "sentinel"
            sentinel.write_text("unchanged\n", encoding="utf-8")
            self.run_tool(root, "--write")
            manifest_path = root / ".zpkg.toml"
            manifest = manifest_path.read_text(encoding="utf-8").replace(
                'dir = "clients/python3"',
                f'dir = "{outside.as_posix()}"',
                1,
            )
            manifest_path.write_text(manifest, encoding="utf-8")

            failed = self.run_tool(root, "--check", expect=1)
            self.assertIn(
                f"target python3 source directory escapes repository: '{outside.as_posix()}'",
                failed["errors"],
            )

            self.run_tool(root, "--write")
            manifest = tomllib.loads((root / ".zpkg.toml").read_text(encoding="utf-8"))
            self.assertEqual(manifest["targets"]["python3"]["dir"], "clients/python3")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged\n")

    def test_fingerprint_drift_fails_closed(self) -> None:
        with self.make_repo() as path:
            root = Path(path)
            self.run_tool(root, "--write")
            marker = root / "clients/rust/.zed-api-surface.sha256"
            marker.write_text("0" * 64 + "\n", encoding="utf-8")
            failed = self.run_tool(root, "--check", expect=1)
            self.assertIn("rust API fingerprint is missing or stale", failed["errors"])

    def test_duplicate_target_source_roots_fail_closed(self) -> None:
        with self.make_repo() as path:
            root = Path(path)
            self.run_tool(root, "--write")
            manifest_path = root / ".zpkg.toml"
            manifest = manifest_path.read_text(encoding="utf-8")
            manifest = manifest.replace(
                'dir = "clients/typescript/deno"',
                'dir = "clients/typescript/nodejs"',
                1,
            )
            manifest_path.write_text(manifest, encoding="utf-8")
            failed = self.run_tool(root, "--check", expect=1)
            self.assertIn(
                "targets typescript-nodejs and typescript-deno share source directory 'clients/typescript/nodejs'",
                failed["errors"],
            )

    def test_known_generated_zig_template_is_migrated(self) -> None:
        with self.make_repo() as path:
            root = Path(path)
            zig = root / "clients/zig"
            zig.mkdir(parents=True)
            (zig / "build.zig").write_text(
                '''const std = @import("std");
pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});
    const lib = b.addStaticLibrary(.{ .name = "client", .root_source_file = b.path("src/root.zig"), .target = target, .optimize = optimize });
    b.installArtifact(lib);
}
''',
                encoding="utf-8",
            )
            self.run_tool(root, "--write")
            migrated = (zig / "build.zig").read_text(encoding="utf-8")
            self.assertIn("b.addLibrary", migrated)
            self.assertNotIn("b.addStaticLibrary", migrated)

    def test_schema_drift_and_unresolved_types_fail_closed(self) -> None:
        with self.make_repo() as path:
            root = Path(path)
            self.run_tool(root, "--write")
            surface_path = root / "clients/api-surface.json"
            surface = json.loads(surface_path.read_text(encoding="utf-8"))
            surface["symbols"][0]["definition"]["fields"][0]["type"] = {
                "kind": "named",
                "name": "MissingType",
            }
            surface_path.write_text(json.dumps(surface, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            failed = self.run_tool(root, "--check", expect=1)
            self.assertIn("unresolved named type: MissingType", failed["errors"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
