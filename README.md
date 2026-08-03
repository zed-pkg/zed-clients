# zed-clients

Official client SDKs for the [zed-pkg](https://zpkg.tech) registry API, one
folder per language under `clients/`. All of them speak the contract defined
in [zed-interfaces](https://github.com/zed-pkg/zed-interfaces) (the Rust and
WebAssembly SDKs reuse its types directly; the others mirror the generated
JSON Schemas in `zed-interfaces/schemas/`).

| SDK | Package | Deps | Verify |
| --- | --- | --- | --- |
| [clients/rust/](clients/rust/) | `zed-client` | reqwest (rustls) | `cargo test` |
| [clients/wasm/](clients/wasm/) | `@zed-pkg/client-wasm` | wasm-bindgen + global fetch | `wasm-pack build --target web && cargo test` |
| [clients/typescript/](clients/typescript/) | `@zed-pkg/client` | zero runtime deps (global fetch) | `npm run build && npm test` |
| [clients/python/](clients/python/) | `zed-pkg-client` | stdlib only (urllib) | `python3 -m unittest` |
| [clients/go/](clients/go/) | `github.com/zed-pkg/zed-clients/clients/go` | stdlib only (net/http) | `go test ./...` |
| [clients/dart/](clients/dart/) | `zed_pkg_client` | http, crypto | `dart analyze && dart test` |
| [clients/gleam/](clients/gleam/) | `zed_pkg_client` | gleam_http, gleam_httpc, gleam_json, gleam_crypto | `gleam test` |
| [clients/erlang/](clients/erlang/) | `zed_pkg_client` | stdlib only (httpc + json + crypto) | `rebar3 eunit` |
| [clients/java/](clients/java/) | `tech.zpkg:zed-client` | Java 17 HTTP + Jackson | `mvn verify` |
| [clients/swift/](clients/swift/) | `ZedClient` | Foundation only | `swift test --parallel` |

The shared baseline is package/version lookup, text search, SHA-256-verified
artifact download, organization claim, and multipart publication using JSON
`meta` plus raw `artifact` bytes. The current server contract also includes
version yank/restore; Java and Swift implement it as `yank`, `restore`, and
`setYanked`, matching the newer WASM/Dart/Gleam/Erlang clients. Completion of
that operation in the older TypeScript/Python/Go/Rust clients remains tracked
by the fleet-level parity issue rather than being hidden by an overbroad claim.

Every client transports bearer credentials but does not parse them. Registry
redirects are refused. Artifact downloads do not carry the registry bearer
because `download_url` may be a third-party presigned URL, and downloaded bytes
are size-capped and digest-verified before use.

Core endpoints:

```
GET  /v1/packages/{org}/{name}
GET  /v1/packages/{org}/{name}/versions/{version}
PUT  /v1/packages/{org}/{name}/versions/{version}        multipart, bearer
POST /v1/packages/{org}/{name}/versions/{version}/yank   JSON, bearer
GET  /v1/artifacts/{sha256}
GET  /v1/search?q=
POST /v1/orgs                                             JSON, bearer
GET  /v1/files/{org}/{name}/{version}/{path}
```

Package listing, semantic search, embedding administration, and organization
audit are newer router surfaces tracked separately so this core SDK matrix does
not claim support it has not yet implemented.

## Reproducible development environment

The root Nix flake pins the multi-runtime contributor toolchain and exposes one
non-interactive entrypoint for agents and humans:

```bash
nix develop --no-update-lock-file -c agent-check
```

Rust and browser-WASM checks consume `zed-interfaces` through the existing
sibling path dependency. For local validation, check out the exact compatible
contract beside this repository:

```text
../zed-interfaces @ 6e893ad0f28ccfbb7722f007d75e88548f1bcfdf
../zed-clients
```

Focused stages are available when iterating:

```bash
nix develop -c agent-check contract
nix develop -c agent-check typescript
nix develop -c agent-check rust
nix develop -c agent-check wasm
nix develop -c agent-check dart
nix develop -c agent-check swift
```

The complete check validates the locked flake, workflow syntax, shell scripts,
the single root `.zpkg.toml` / `.zpkg.lock` release set, and all ten native SDK
packages. Mutable package-manager caches are isolated under
`.cache/nix-agent/`; they are never release inputs. The dedicated GitHub
Actions workflow uses read-only permissions, immutable action SHAs, the
committed flake lock, and the same `agent-check` command.

The real-browser Chromium, Firefox, and WebKit transport contract remains a
separate exact-head workflow because browser binaries and retained evidence are
not part of the everyday development shell.

## License

MIT
