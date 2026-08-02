# zed-clients agent instructions

## Scope and contract

- Keep every SDK under `clients/<language>/` and preserve the single root `.zpkg.toml` / `.zpkg.lock` release set.
- Treat `zed-pkg/zed-interfaces` as the Rust and WebAssembly contract source. Do not duplicate or weaken those types to make a local build pass.
- Preserve the security contract across languages: refuse registry redirects, do not forward registry bearer tokens to third-party artifact URLs, cap response bodies, and verify artifact SHA-256 before return.
- Do not claim operation parity that a client does not implement. Update the README matrix and fleet parity ticket honestly.

## Required checks

Use the pinned shell rather than relying on mutable globally installed toolchains:

```sh
nix develop -c agent-check
```

Rust and WebAssembly checks require `zed-interfaces` as a sibling checkout:

```text
workspace/
├── zed-clients/
└── zed-interfaces/
```

Run a focused stage while iterating, for example `nix develop -c agent-check go`, but run the default complete command before requesting merge.

## Change discipline

- Keep package-manager lock files and the root Nix `flake.lock` committed when they are part of the existing release model.
- Do not add nested `.zpkg.lock` files below `clients/`.
- Pin GitHub Actions by immutable commit SHA and keep workflow permissions read-only unless a write is essential and documented.
- Resolve merge conflicts by preserving the current contract, security invariants, and release topology. Never accept an entire side merely because it is newer.
