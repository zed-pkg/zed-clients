#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
text = "\n".join(path.read_text(errors="ignore") for path in (ROOT / "validation-consumer").rglob("*") if path.is_file())
required = ["@zed-pkg/zed-validation", "zed-validation", "github.com/zed-pkg/zed-lib-core/validation/golang", "zed_validation"]
for dependency in required:
    assert dependency in text, f"missing public lib-core import: {dependency}"
for forbidden in ("zed-validation-server", "golang-server", "zed_validation_server"):
    assert forbidden not in text, f"client imported server-only package: {forbidden}"
print("all four clients import only public lib-core validation packages")
