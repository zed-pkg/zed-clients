# Dependency graph downloads

The TypeScript SDK exposes one runtime-neutral download helper for every
`zpkg/dependency-graph/v1` representation:

```ts
import { downloadDependencyGraph } from "@zed-pkg/client";

const graph = await downloadDependencyGraph({
  baseUrl: "https://api.zpkg.net",
  org: "acme",
  name: "widget",
  version: "2.0.0-beta.1",
  format: "msgpack",
  token: process.env.ZED_PKG_TOKEN,
});

console.log(
  graph.graphDigest,
  graph.etag,
  graph.authoritative,
  graph.contentLength,
);
await Bun.write(graph.filename, graph.body);
```

Supported canonical names are `json`, `yaml`, `toml`, `dot`, `mermaid`,
`json5`, `xml`, `csv`, `msgpack`, and `protobuf`. Common aliases such as `yml`,
`graphviz`, `mmd`, `messagepack`, `mpk`, `proto`, and `pb` normalize to those
stable names before URL construction.

JSON, YAML, TOML, JSON5, XML, MessagePack, and Protocol Buffers are lossless
interchange representations. CSV, DOT, and Mermaid are convenience projections
and return `authoritative: false`.

## Transport behavior

- Registry base URLs must use HTTP or HTTPS and may not embed credentials,
  queries, or fragments. Cleartext HTTP is limited to loopback/private/in-cluster
  hosts unless `allowInsecureTransport` is explicitly enabled.
- Coordinates are encoded as individual URL path segments. Empty, control, and
  dot-segment values are rejected.
- Bearer credentials are supplied only in the `Authorization` header.
- Redirect following is disabled so a registry cannot redirect credentials to a
  different origin.
- Bodies are streamed under a 32 MiB default limit. `maxBytes` can lower or
  explicitly raise that caller-side bound up to 1 GiB.
- Requests and response streams have a 30-second default deadline. `timeoutMs`
  can select a positive deadline up to 10 minutes, and a caller `AbortSignal`
  remains authoritative.
- Successful responses must carry the requested graph media type, a strong
  syntactically valid byte ETag, a canonical SHA-256 semantic graph digest,
  the contract authority classification, and an exact safe `Content-Length`.
  The SDK rejects a body whose bytes do not match that declared length.
- `If-None-Match` is supported. A `304` result has an empty body while retaining
  ETag and semantic graph-digest metadata.
- Non-success response bodies are not exposed by `DependencyGraphHttpError`,
  preserving private-package indistinguishability.

The client-generated filename is deterministic and uses the representation's
canonical extension. The server's `Content-Disposition` header remains the
network authority when an application chooses to honor it.
