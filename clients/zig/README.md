# Zed Package Registry Zig client

This dependency-free Zig 0.15 baseline provides the security-sensitive client configuration shared by the registry SDKs:

- credential-free absolute HTTP(S) registry URL validation;
- explicit bearer-token access for request code and redacted generic diagnostics;
- canonical package, version, and SHA-256 artifact paths;
- percent-encoded untrusted path segments;
- allocator-owned outputs with native leak-checked tests.

The baseline deliberately leaves HTTP transport selection to the consumer. Transport adapters must preserve the validated URL, credential, redirect, response-bound, and path contracts before being treated as release-capable.

Run locally with Zig 0.15.2:

```sh
zig fmt --check src/client.zig build.zig
zig build test
```
