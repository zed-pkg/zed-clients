#!/bin/sh
set -eu

target="${ZED_PKG_TEST_TARGET:?ZED_PKG_TEST_TARGET is required}"

test -f "$target/clients/go/go.mod"
test -f "$target/clients/rust/Cargo.toml"
test -f "$target/clients/dart/pubspec.yaml"
test -f "$target/clients/typescript/package.json"
