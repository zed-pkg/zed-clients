# Agent instructions

## Scope and hierarchy

- These instructions apply to the whole `zed-pkg/zed-clients` repository unless a deeper lowercase `agents.md` adds narrower rules.
- Before editing, resolve the current working directory and load every readable ancestor `agents.md` from the filesystem root to the working directory. Do not search siblings. Resolve symlinks, deduplicate resolved files, and report unreadable or cyclic instruction files.
- `.claude/CLAUDE.md`, `.gemini/GEMINI.md`, and `.openai/AGENTS.md` are pointers only. Never duplicate instructions in tool-specific files.

## Repository role

This repository is the multi-language Zed client and SDK release set. It maps one registry/API contract into language-idiomatic clients while preserving equivalent authentication, transport, error, versioning, and package-publication behavior.

## Working rules

- Treat the API/OpenAPI source and generator inputs as canonical. Do not hand-edit generated files without updating the generator or manifest that owns them.
- Preserve operation coverage and behavioral parity across supported language clients; document intentional language-specific differences.
- Keep public names, request/response schemas, error categories, retry/idempotency behavior, and authentication semantics compatible.
- Never log bearer tokens, refresh tokens, signed URLs, package credentials, or sensitive response bodies.
- Keep network timeouts, redirect policy, response-size limits, and error truncation bounded and explicit.
- Regenerate deterministically and fail CI on generator drift, uncommitted output, missing packages, or lockfile changes.
- Validate each language with its native formatter, compiler/type checker, tests, package metadata checks, and a shared contract fixture.
- Coordinate API/interface changes contract-first and update release notes/versioning for every affected client.
- Keep every SDK under `clients/<language>/` and preserve the single root `.zpkg.toml` / `.zpkg.lock` release set; do not add nested client locks.
- Treat `zed-pkg/zed-interfaces` as the Rust and WebAssembly contract source. Do not duplicate or weaken those types to make a local build pass.
- Refuse registry redirects, never forward registry bearer tokens to third-party artifact URLs, cap response bodies, and verify artifact SHA-256 before return.
- Do not claim operation parity that a client does not implement. Keep the README matrix and fleet parity issue accurate.
- Pin GitHub Actions by immutable commit SHA and keep workflow permissions read-only unless a write is essential and documented.
- Resolve conflicts by preserving the contract, security invariants, and release topology. Never accept an entire side merely because it is newer.

## Reproducible validation

Use the pinned development shell instead of mutable globally installed toolchains:

```sh
nix develop -c agent-check
```

Rust and WebAssembly validation requires `zed-interfaces` as a sibling checkout:

```text
workspace/
├── zed-clients/
└── zed-interfaces/
```

Focused stages such as `nix develop -c agent-check go` are suitable while iterating, but the default complete command is required before merge. Keep package-manager lock files and the root `flake.lock` committed when they belong to the repository's release model.

## Pinned development environment

- Enter the repository toolchain with `nix develop --no-update-lock-file`; do not replace the committed `flake.lock` during ordinary validation.
- Use `nix develop --no-update-lock-file -c agent-check <stage>` for focused work and `nix develop --no-update-lock-file -c agent-check` before review.
- Rust and browser-WASM packages require the exact compatible `zed-interfaces` sibling checkout documented in `README.md` and pinned by `.github/workflows/nix.yml`.
- Keep package-manager caches under `.cache/nix-agent/` or another explicit `NIX_AGENT_CACHE_ROOT`. Cache contents are disposable and must never affect release artifacts.
- Changes to client manifests, `.zpkg.toml`, `.zpkg.lock`, the Nix flake, the interface pin, or validation scripts require the Nix workflow and the existing native matrix to pass on the same reviewed head.
- The Swift stage must use the flake-locked Nixpkgs compiler and SwiftPM packages. Do not introduce an independently repacked upstream toolchain.
- Do not claim the Nix shell replaces the dedicated real-browser transport workflow; Chromium, Firefox, and WebKit execution remain separately certified.

## Pinned development environment

- Enter the repository toolchain with `nix develop --no-update-lock-file`; do not replace the committed `flake.lock` during ordinary validation.
- Use `nix develop -c agent-check <stage>` for focused work and `nix develop -c agent-check` before review.
- Rust and browser-WASM packages require the exact compatible `zed-interfaces` sibling checkout documented in `README.md` and pinned by `.github/workflows/nix.yml`.
- Keep package-manager caches under `.cache/nix-agent/` or another explicit `NIX_AGENT_CACHE_ROOT`. Cache contents are disposable and must never affect release artifacts.
- Changes to client manifests, `.zpkg.toml`, `.zpkg.lock`, the Nix flake, the interface pin, or validation scripts require the Nix workflow and the existing native matrix to pass on the same reviewed head.
- Do not claim the Nix shell replaces the dedicated real-browser transport workflow; Chromium, Firefox, and WebKit execution remain separately certified.

## Pinned development environment

- Enter the repository toolchain with `nix develop --no-update-lock-file`; do not replace the committed `flake.lock` during ordinary validation.
- Use `nix develop -c agent-check <stage>` for focused work and `nix develop -c agent-check` before review.
- Rust and browser-WASM packages require the exact compatible `zed-interfaces` sibling checkout documented in `README.md` and pinned by `.github/workflows/nix.yml`.
- Keep package-manager caches under `.cache/nix-agent/` or another explicit `NIX_AGENT_CACHE_ROOT`. Cache contents are disposable and must never affect release artifacts.
- Changes to client manifests, `.zpkg.toml`, `.zpkg.lock`, the Nix flake, the interface pin, or validation scripts require the Nix workflow and the existing native matrix to pass on the same reviewed head.
- Do not claim the Nix shell replaces the dedicated real-browser transport workflow; Chromium, Firefox, and WebKit execution remain separately certified.

## Pinned development environment

- Enter the repository toolchain with `nix develop --no-update-lock-file`; do not replace the committed `flake.lock` during ordinary validation.
- Use `nix develop -c agent-check <stage>` for focused work and `nix develop -c agent-check` before review.
- Rust and browser-WASM packages require the exact compatible `zed-interfaces` sibling checkout documented in `README.md` and pinned by `.github/workflows/nix.yml`.
- Keep package-manager caches under `.cache/nix-agent/` or another explicit `NIX_AGENT_CACHE_ROOT`. Cache contents are disposable and must never affect release artifacts.
- Changes to client manifests, `.zpkg.toml`, `.zpkg.lock`, the Nix flake, the interface pin, or validation scripts require the Nix workflow and the existing native matrix to pass on the same reviewed head.
- Do not claim the Nix shell replaces the dedicated real-browser transport workflow; Chromium, Firefox, and WebKit execution remain separately certified.

## Validation

The pinned `agents policy` workflow validates this hierarchy and the three tool pointers. Follow `README.md`, generator documentation, the root Nix entrypoint, and existing CI before requesting review.
