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
            for target in ("typescript-nodejs", "typescript-deno", "typescript-bun", "typescript-edge"):
                self.assertEqual(manifest["targets"][target]["dir"], "clients/typescript")
            self.assertEqual((root / "clients/go/go.mod").read_text(), "module example.test/existing\n\ngo 1.22\n")
            self.assertTrue((root / "clients/typescript/.zed-contracts/nodejs/.zed-client-contract.json").is_file())

    def test_fingerprint_drift_fails_closed(self) -> None:
        with self.make_repo() as path:
            root = Path(path)
            self.run_tool(root, "--write")
            marker = root / "clients/rust/.zed-api-surface.sha256"
            marker.write_text("0" * 64 + "\n", encoding="utf-8")
            failed = self.run_tool(root, "--check", expect=1)
            self.assertIn("rust API fingerprint is missing or stale", failed["errors"])

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
