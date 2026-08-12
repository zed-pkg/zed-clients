from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harden_client_contract.py"
SCHEMA = ROOT / "schemas/client-api.schema.json"


class TargetNameMigrationTests(unittest.TestCase):
    def test_stale_names_are_removed_and_valid_names_survive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "clients/typescript").mkdir(parents=True)
            (root / ".zpkg.toml").write_text(
                """[package]
org = "acme-cloud"
name = "acme-clients"
version = "0.1.0"

[targets.repository]
dir = "."
name = "acme-clients-repository"

[targets.nodejs]
dir = "clients/typescript"
name = "@acme-cloud/client"
adapter = "node"

[targets.golang]
dir = "clients/golang"
name = "existing-node-package"
adapter = "go"
""",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(root),
                    "--schema",
                    str(SCHEMA),
                    "--write",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

            targets = tomllib.loads(
                (root / ".zpkg.toml").read_text(encoding="utf-8")
            )["targets"]
            self.assertNotIn("name", targets["repository"])
            self.assertNotIn("name", targets["typescript-nodejs"])
            self.assertEqual(
                targets["golang"]["name"],
                "existing-node-package",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
