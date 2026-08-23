# Canonical polyglot client contract

Every `*-clients` repository is hardened from the same machine-readable contract.
The canonical files live in `zed-pkg/zed-clients`:

- `schemas/client-api.schema.json` defines package metadata plus public and private
  classes, constructors, methods, functions, interfaces, types, fields, parameters,
  return values, errors, async/static semantics, and recursive type references.
- `scripts/harden_client_contract.py` preserves existing implementations and mature
  publish matrices, creates missing runtime baselines for incomplete fleets, and
  verifies parity.
- `clients/api-surface.json` is the repository-specific API declaration generated
  or maintained by each client repository. Its `package.interfaces` entries must
  exactly match the repository's versioned `*-interfaces` dependencies and declare
  JSON Schema Draft 2020-12.

The canonical hardener is checked in as ordinary reviewable Python source and is
covered by its unit suite.

## Behavior, authorization, and lifecycle metadata

Every class, interface, function, type, field, constructor, and method has a
stable `documentationId`, an explicit stability state, and nullable deprecation
metadata. Every callable also declares `behavior` as `sync`, `async`, or
`streaming` plus structured authorization mode, schemes, and scopes. The
hardener fills deterministic defaults for existing declarations before Draft
2020-12 validation; semantic validation rejects duplicate documentation IDs,
async/behavior contradictions, and deprecated declarations without migration
metadata.

## Standard target matrix

The fleet baseline contains 20 targets under `clients/`, with a hard minimum of 15:
C, C++, Zig, WebAssembly, Gleam, Erlang, Elixir, Dart, Rust, Java, Go, Python,
Ruby, PHP, Kotlin, Swift, TypeScript/Node.js, TypeScript/Deno, TypeScript/Bun, and
TypeScript/edge runtimes.

Existing aliases such as `clients/go`, `clients/python`, `clients/gleam`, and a
shared `clients/typescript` package are preserved. New repositories use the
canonical directory names emitted by the hardener. The normalized fleet view is
stored in `clients/client-contract-matrix.json`; it never overwrites a repository's
native `clients/sdk-matrix.json`, adapters, registry metadata, or runtime slicing.

## Parity proof

The canonical API surface is serialized deterministically and SHA-256 hashed.
Every runtime receives:

- `.zed-client-contract.json`, identifying the package coordinate, target,
  runtime, schema ID, and expected API-surface digest;
- `.zed-api-surface.sha256`, containing that digest.

For shared TypeScript packages, markers are stored below
`clients/typescript/.zed-contracts/<runtime>/`. The central contract manifest also
records a deterministic digest and file count over each target's implementation
source and export/package metadata. Any SDK or export-map change therefore fails
until the reviewed contract manifest is regenerated. A stale or missing marker
also fails closed, as do unresolved named types, duplicate symbols, missing
visibility classes, malformed schemas, unsafe target paths, and uncovered client
directories.

## Commands

```sh
python -m pip install tomlkit jsonschema
python scripts/harden_client_contract.py \
  --root . \
  --schema schemas/client-api.schema.json \
  --write

python scripts/harden_client_contract.py \
  --root . \
  --schema schemas/client-api.schema.json \
  --check
```

The nightly fleet controller checks out this repository at `main`, so all client
repositories are assessed against the current canonical schema and generator.
It also checks out and builds `zed-pkg/zed-cli` from `main`, validates package
metadata with the CLI, records the Zed API-server tip, and exercises discoverable
consumers in each paired `*-test` organization.
