#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-published-target-boundaries.py"
SPEC = importlib.util.spec_from_file_location("target_boundaries", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PublishedTargetBoundaryTests(unittest.TestCase):
    def write_target(self, root: Path, cargo_text: str) -> None:
        target = root / "clients" / "rust"
        target.mkdir(parents=True)
        (target / "Cargo.toml").write_text(cargo_text, encoding="utf-8")

    def test_accepts_git_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_target(
                root,
                """[package]
name = "client"
version = "0.1.0"

[dependencies]
zed-interfaces = { git = "https://github.com/zed-pkg/zed-interfaces.git", rev = "0123456789abcdef0123456789abcdef01234567" }
""",
            )
            module.check_cargo_target(root, "rust", "clients/rust")

    def test_accepts_path_inside_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_target(
                root,
                """[package]
name = "client"
version = "0.1.0"

[dependencies]
helper = { path = "helper" }
""",
            )
            helper = root / "clients" / "rust" / "helper"
            helper.mkdir()
            module.check_cargo_target(root, "rust", "clients/rust")

    def test_rejects_path_that_escapes_staged_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_target(
                root,
                """[package]
name = "client"
version = "0.1.0"

[dependencies]
zed-interfaces = { path = "../../../zed-interfaces" }
""",
            )
            with self.assertRaisesRegex(ValueError, "escapes staged target artifact"):
                module.check_cargo_target(root, "rust", "clients/rust")

    def test_rejects_target_specific_escaping_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_target(
                root,
                """[package]
name = "client"
version = "0.1.0"

[target.'cfg(unix)'.dependencies]
helper = { path = "../../outside" }
""",
            )
            with self.assertRaisesRegex(ValueError, "escapes staged target artifact"):
                module.check_cargo_target(root, "rust", "clients/rust")


if __name__ == "__main__":
    unittest.main()
