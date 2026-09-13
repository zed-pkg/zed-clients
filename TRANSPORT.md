# Rust HTTP transport policy

`reqwest::blocking` is deprecated in zed-pkg Rust clients.

The transport authority for new registry reads is `clients/rust-async` (`zed-client-async`), built on Hyper, hyper-util, Hyper-Rustls, and Tokio. Request futures are cancellable by dropping/aborting them; consumers that race local work against remote resolution should couple those futures to an explicit cancellation token.

## Compatibility boundary

`clients/rust` remains temporarily supported as the legacy synchronous SDK. Its existing blocking transport is grandfathered only so current consumers can migrate without a flag day. Do not add new `reqwest::blocking` call sites there or anywhere else.

Migration order:

1. package/version/search registry reads -> `zed-client-async`
2. artifact and binary artifact GET streams -> async Hyper streaming
3. source-host fallback reads -> async transport
4. multipart publication/uploads -> async streaming bodies
5. remove the blocking reqwest dependency and legacy compatibility client

New resolver or speculative network code must use the async client. A synchronous command boundary may use a Tokio runtime to drive async work, but the network operation itself must remain a cancellable future rather than a blocking socket call.
