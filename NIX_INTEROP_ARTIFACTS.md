# Nix interoperability SDK artifacts

The repository publishes commit-addressed GitHub Actions artifacts for the
strict Nix interoperability readers implemented in TypeScript and Go.

## Contents

Each successful `Nix interoperability artifacts` workflow run uploads one
artifact named:

```text
zed-nix-interop-<full-git-commit>
```

It contains:

```text
zed-nix-interop-typescript.tar.gz
zed-nix-interop-go.tar.gz
provenance.json
SHA256SUMS
```

The TypeScript archive contains compiled ESM declarations/code, package
metadata and lock, the source contract readers, and the Nix interoperability
verification guide. It supports:

- `zed.nix-export-plan/v1`;
- `zed.nix-adapter/v1`.

The Go archive contains the standard-library client module, strict Nix adapter
reader/canonicalizer, and its golden/negative tests. It supports:

- `zed.nix-adapter/v1`.

## Build and test gate

Artifacts are assembled only after:

```text
npm ci
npm run build
npm test
go vet ./...
go test ./...
```

Both language archives use sorted entries, zero ownership, numeric owners, and a
fixed Unix epoch timestamp. Their SHA-256 values, plus the provenance-document
SHA-256, are recorded in `SHA256SUMS` and verified before upload.

`provenance.json` identifies the exact repository, full commit, workflow run,
run attempt, event, language, and supported contracts. It contains no token,
credential, workstation path, registry secret, signing key, or mutable branch as
an artifact identity.

## Publication boundary

These are **commit artifacts**, not package-registry releases. The workflow uses
read-only repository permission and does not:

- publish to npm or a Go proxy;
- create a GitHub release or tag;
- write GitHub Packages;
- request an OIDC token;
- push a branch or commit;
- sign with an unreviewed identity; or
- inherit repository or organization secrets.

The artifacts are retained for 14 days. They provide review, integration,
reproduction, and downstream-codegen inputs for a specific commit.

Stable npm, Go module, Zed package, release, or binary-cache publication requires
an independently reviewed immutable tag and release workflow. A successful pull
request artifact never promotes itself to a stable release.

## Verification

After downloading the workflow artifact:

```bash
sha256sum --check SHA256SUMS
```

Consumers should also verify that `provenance.json.commit` equals the reviewed
commit and that the workflow run belongs to `zed-pkg/zed-clients`.

The SDK helpers perform structural and byte-level adapter verification. Claims
about Nix realization, live store paths, NAR replay, cache signatures, or
registry publication still require the pinned CLI and explicit Nix/store or
registry verification.
