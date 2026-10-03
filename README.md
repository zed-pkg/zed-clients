# zed-clients

Official client SDKs for the [Zed package registry](https://zpkg.tech), with one
release set and one root `.zpkg.toml` / `.zpkg.lock`. The SDKs follow the shared
contract from [zed-interfaces](https://github.com/zed-pkg/zed-interfaces); Rust
and WebAssembly consume its Rust types directly, while the other packages keep
language-idiomatic public APIs over the same wire behavior.

## SDK matrix

| SDK | Native package | Verification |
| --- | --- | --- |
| [clients/c/](clients/c/) | CMake package | `cmake -S . -B build && cmake --build build` |
| [clients/cpp/](clients/cpp/) | CMake package | `cmake -S . -B build && cmake --build build && ctest --test-dir build` |
| [clients/zig/](clients/zig/) | Zig package | `zig build test` |
| [clients/rust/](clients/rust/) | `zed-client` | `cargo test` |
| [clients/wasm/](clients/wasm/) | `@zed-pkg/client-wasm` | `wasm-pack build --target web && cargo test` |
| [clients/typescript/](clients/typescript/) | `@zed-pkg/client` | `npm run build && npm test` |
| [clients/python/](clients/python/) | `zed-pkg-client` | `python3 -m unittest` |
| [clients/go/](clients/go/) | `github.com/zed-pkg/zed-clients/clients/go` | `go test ./...` |
| [clients/dart/](clients/dart/) | `zed_pkg_client` | `dart analyze && dart test` |
| [clients/gleam/](clients/gleam/) | `zed_pkg_client` | `gleam format --check && gleam test` |
| [clients/erlang/](clients/erlang/) | `zed_pkg_client` | `rebar3 eunit` |
| [clients/elixir/](clients/elixir/) | `zed_pkg_client` | `mix test` |
| [clients/java/](clients/java/) | `tech.zpkg:zed-client` | `mvn verify` |
| [clients/kotlin/](clients/kotlin/) | `tech.zpkg:zed-client-kotlin` | `mvn verify` |
| [clients/ruby/](clients/ruby/) | `zed_pkg_client` | `ruby -Ilib test/client_test.rb` |
| [clients/php/](clients/php/) | `zed-pkg/client` | `php tests/client_test.php` |
| [clients/swift/](clients/swift/) | `ZedClient` | `swift test --parallel` |

The Zed manifest publishes those 17 canonical language slices plus a
language-agnostic whole-repository artifact. TypeScript remains one published
Node.js-language package with explicit Node.js, Deno, Bun, and edge runtime
entry points; those four runtimes are certified independently in
[`clients/sdk-matrix.json`](clients/sdk-matrix.json) without pretending they are
four different languages. The full hardening matrix therefore contains 20
runtime contracts while the package manifest remains compatible with Zed's
language and ecosystem guards.

The mature clients implement package/version lookup, search, authenticated
publication and lifecycle mutations, and size-capped SHA-256-verified artifact
downloads. The newer dependency-free C, C++, and Zig baselines intentionally
claim only their currently implemented surface. Capability claims are checked
against code, and the canonical lifecycle/auth/stability metadata lives in
[`clients/api-surface.json`](clients/api-surface.json).

Every client transports bearer credentials but does not parse them. Registry
redirects are refused. Artifact downloads do not carry the registry bearer
because a download URL may point to a third-party object store. Downloaded
response bodies are bounded and artifact bytes are digest-verified before use.

## Reproducible development

Place the exact `zed-interfaces` revision pinned by the workflows beside this
checkout:

```text
workspace/
├── zed-clients/
└── zed-interfaces/
```

Then run the complete locked toolchain check:

```sh
nix develop --no-update-lock-file -c agent-check
```

Focused stages are available while iterating, for example:

```sh
nix develop --no-update-lock-file -c agent-check contract
nix develop --no-update-lock-file -c agent-check typescript
nix develop --no-update-lock-file -c agent-check rust
nix develop --no-update-lock-file -c agent-check gleam
nix develop --no-update-lock-file -c agent-check swift
```

The default check validates the root release set, the canonical API schema and
fingerprints, Nix and workflow formatting, and every native SDK stage. The
real-browser Chromium, Firefox, and WebKit transport contract remains a
separate exact-head workflow because browser binaries and retained evidence are
not part of the everyday development shell.

## License

MIT
