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
| [clients/python/](clients/python/) | `zed-pkg-client` | Python 3 stdlib only (urllib) | `python3 -m unittest` |
| [clients/go/](clients/go/) | `github.com/zed-pkg/zed-clients/clients/go` | stdlib only (net/http) | `go test ./...` |
| [clients/dart/](clients/dart/) | `zed_pkg_client` | http, crypto | `dart analyze && dart test` |
| [clients/gleam/](clients/gleam/) | `zed_pkg_client` | gleam_http, gleam_httpc, gleam_json, gleam_crypto | `gleam test` |
| [clients/erlang/](clients/erlang/) | `zed_pkg_client` | stdlib only (httpc + json + crypto) | `rebar3 eunit` |
| [clients/elixir/](clients/elixir/) | `zed_pkg_client` | OTP httpc + Jason | `mix test` |
| [clients/java/](clients/java/) | `tech.zpkg:zed-client` | Java 17 HTTP + Jackson | `mvn verify` |
| [clients/kotlin/](clients/kotlin/) | `tech.zpkg:zed-client-kotlin` | Kotlin/JVM + Java 17 HTTP | `mvn verify` |
| [clients/ruby/](clients/ruby/) | `zed_pkg_client` | Ruby stdlib | `ruby -Ilib test/client_test.rb` |
| [clients/php/](clients/php/) | `zed-pkg/client` | PHP 8.2 + ext-curl | `php tests/client_test.php` |
| [clients/swift/](clients/swift/) | `ZedClient` | Foundation only | `swift test --parallel` |

The shared baseline is package/version lookup, text search, SHA-256-verified
artifact download, organization claim, version yank/restore, and multipart
publication using JSON `meta` plus raw `artifact` bytes. All fourteen clients
implement that core lifecycle. Method names remain idiomatic to each language;
for example, some clients additionally expose `restore` or `setYanked`
conveniences over the same yank endpoint.
artifact download, organization claim, multipart publication using JSON `meta`
plus raw `artifact` bytes, and version yank/restore. All ten clients
implement that core lifecycle. Language-idiomatic APIs may expose the state
transition as `yank`, `restore`, and/or `setYanked`, but they preserve the same
registry contract and authenticated mutation boundary.

TypeScript uses one npm-compatible package with explicit entry points for
Node.js, Deno, Bun, and edge runtimes. See
[`clients/README.md`](clients/README.md) for the canonical naming map, including
`python` = Python 3, `go` = Golang, and `gleam` = Gleamlang.
publication using JSON `meta` plus raw `artifact` bytes. All ten clients
implement that core lifecycle. Method names remain idiomatic to each language;
for example, some clients additionally expose `restore` or `setYanked`
conveniences over the same yank endpoint.

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

The root Nix flake pins the contributor toolchain and exposes one
The root Nix flake pins the multi-runtime contributor toolchain and exposes one
non-interactive entrypoint for agents and humans:

```bash
nix develop --no-update-lock-file -c agent-check
```

Rust and browser-WASM checks consume `zed-interfaces` through the existing
sibling path dependency. For local validation, check out the exact compatible
contract beside this repository:

```text
../zed-interfaces @ 5f15f1f2686199924b3e32e7ef8e6a85434bca3e
../zed-interfaces @ 6e893ad0f28ccfbb7722f007d75e88548f1bcfdf
../zed-clients
```

Focused stages are available when iterating:

```bash
nix develop --no-update-lock-file -c agent-check contract
nix develop --no-update-lock-file -c agent-check typescript
nix develop --no-update-lock-file -c agent-check rust
nix develop --no-update-lock-file -c agent-check elixir
nix develop --no-update-lock-file -c agent-check php
nix develop --no-update-lock-file -c agent-check swift
```

The complete check validates the locked flake, workflow syntax, shell scripts,
the single root `.zpkg.toml` / `.zpkg.lock` release set, and all fourteen native
SDK packages. Mutable package-manager caches are isolated under
`.cache/nix-agent/`; they are never release inputs. The Swift stage uses the
flake-locked Nixpkgs compiler and SwiftPM packages rather than a hand-repacked
upstream binary.

The dedicated GitHub Actions workflow uses read-only permissions, immutable
action SHAs, the committed flake lock, and the same `agent-check` command.
Real-browser Chromium, Firefox, and WebKit transport certification remains a
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
## Reproducible agent environment

The repository has a pinned Nix development shell for the complete SDK matrix.
Place `zed-interfaces` beside this repository so the Rust and WebAssembly path
dependencies resolve, then run:

```sh
nix develop -c agent-check
```

The default command validates the root Zed release set, checks Nix and workflow
formatting, and runs the TypeScript, Python, Go, Rust, WebAssembly, Dart, Gleam,
Erlang, Java, and Swift suites. Focused stages such as `agent-check go` and
`agent-check contract` are available while iterating. Toolchains and caches are
provided or isolated by the shell; the committed `flake.lock` prevents an
implicit Nixpkgs update during CI.

## License

MIT
