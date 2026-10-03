# Zed Package Registry C++ client

This dependency-free C++20 baseline provides the security-sensitive client configuration shared by the registry SDKs:

- credential-free absolute HTTP(S) registry URL validation;
- explicit bearer-token access for request code and redacted generic diagnostics;
- canonical package, version, and SHA-256 artifact paths;
- percent-encoded untrusted path segments;
- CMake/CTest coverage with warnings treated as errors.

The baseline does not choose an HTTP or JSON implementation for consumers. A transport adapter can be layered on top without changing the validated URL, credential, or path contracts.

Run locally:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```
