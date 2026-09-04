from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate-client-matrix.py"
SPEC = importlib.util.spec_from_file_location("validate_client_matrix", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def manifest() -> dict:
    return {"dependencies": {"zed-pkg/zed-interfaces": "^0.1.0"}}


def locked_package() -> dict:
    return {
        "org": "zed-pkg",
        "name": "zed-interfaces",
        "version": "0.1.0",
        "sha256": "a" * 64,
        "size": 6031,
        "format": "tar.gz",
        "vcs_tag": "v0.1.0",
        "vcs_commit": "0123456789abcdef0123456789abcdef01234567",
        "source": "https://registry.zpkg.net",
    }


class LockProvenanceTests(unittest.TestCase):
    def test_dependency_bearing_placeholder_is_rejected(self) -> None:
        with self.assertRaisesRegex(AssertionError, "missing canonical entries"):
            MODULE.validate_lock_provenance(manifest(), {"version": 1})

    def test_complete_immutable_entry_is_accepted(self) -> None:
        MODULE.validate_lock_provenance(
            manifest(), {"version": 1, "package": [locked_package()]}
        )

    def test_artifact_identity_is_fail_closed(self) -> None:
        for field, value, expected in (
            ("sha256", "ABC", "lowercase SHA-256"),
            ("size", 0, "positive artifact size"),
            ("format", "directory", "tar.gz or zip"),
            ("vcs_commit", "main", "immutable VCS commit"),
            ("source", "", "resolver source"),
        ):
            with self.subTest(field=field):
                package = locked_package()
                package[field] = value
                with self.assertRaisesRegex(AssertionError, expected):
                    MODULE.validate_lock_provenance(
                        manifest(), {"version": 1, "package": [package]}
                    )

    def test_duplicate_coordinates_are_rejected(self) -> None:
        package = locked_package()
        with self.assertRaisesRegex(AssertionError, "duplicate locked package"):
            MODULE.validate_lock_provenance(
                manifest(), {"version": 1, "package": [package, package.copy()]}
            )


if __name__ == "__main__":
    unittest.main()
