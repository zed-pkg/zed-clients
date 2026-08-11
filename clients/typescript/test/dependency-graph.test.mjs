import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER,
  DEPENDENCY_GRAPH_DIGEST_HEADER,
  DEPENDENCY_GRAPH_FORMATS,
  DependencyGraphHttpError,
  dependencyGraphDownloadUrl,
  dependencyGraphExportDescriptor,
  dependencyGraphExportPath,
  downloadDependencyGraph,
  normalizeDependencyGraphFormat,
} from "../dist/dependency-graph.js";

const coordinate = {
  org: "acme tools",
  name: "http/client",
  version: "2.0.0-beta.1+build.7",
};
const graphDigest = `sha256:${"a".repeat(64)}`;

test("descriptors match the pinned shared format fixture", async (context) => {
  const fixturePath = process.env.ZED_INTERFACES_FORMAT_FIXTURE;
  if (fixturePath === undefined) {
    context.skip("set ZED_INTERFACES_FORMAT_FIXTURE in cross-repository CI");
    return;
  }

  const fixture = JSON.parse(await readFile(fixturePath, "utf8"));
  assert.equal(fixture.schema, "zpkg/dependency-graph-formats/v1");
  assert.deepEqual(
    fixture.formats.map(({ name }) => name),
    DEPENDENCY_GRAPH_FORMATS,
  );
  for (const format of fixture.formats) {
    const descriptor = dependencyGraphExportDescriptor(format.name);
    assert.deepEqual(
      {
        format: descriptor.format,
        route_kind:
          descriptor.routeKind === "canonical"
            ? "canonical_query"
            : "export_path",
        extension: descriptor.extension,
        media_type: descriptor.mediaType,
        authoritative: descriptor.authoritative,
        binary: descriptor.binary,
      },
      {
        format: format.name,
        route_kind: format.route_kind,
        extension: format.extension,
        media_type: format.media_type,
        authoritative: format.authoritative,
        binary: format.binary,
      },
    );
    for (const alias of [format.name, ...format.aliases]) {
      assert.equal(normalizeDependencyGraphFormat(alias), format.name);
    }
  }
});

test("format aliases normalize to stable route names", () => {
  assert.equal(normalizeDependencyGraphFormat("YML"), "yaml");
  assert.equal(normalizeDependencyGraphFormat("graphviz"), "dot");
  assert.equal(normalizeDependencyGraphFormat("mmd"), "mermaid");
  assert.equal(normalizeDependencyGraphFormat("messagepack"), "msgpack");
  assert.equal(normalizeDependencyGraphFormat("mpk"), "msgpack");
  assert.equal(normalizeDependencyGraphFormat("proto"), "protobuf");
  assert.equal(normalizeDependencyGraphFormat("PB"), "protobuf");
  assert.throws(
    () => normalizeDependencyGraphFormat("pickle"),
    /unsupported dependency graph format/,
  );
});

test("descriptors distinguish lossless interchange from projections", () => {
  assert.equal(dependencyGraphExportDescriptor("json").authoritative, true);
  assert.equal(dependencyGraphExportDescriptor("xml").authoritative, true);
  assert.equal(dependencyGraphExportDescriptor("csv").authoritative, false);
  assert.equal(dependencyGraphExportDescriptor("dot").authoritative, false);
  assert.equal(dependencyGraphExportDescriptor("msgpack").binary, true);
  assert.equal(dependencyGraphExportDescriptor("protobuf").extension, "pb");
});

test("canonical paths carry declared view and safely encode coordinates", () => {
  const path = dependencyGraphExportPath(coordinate, "yaml");
  assert.equal(
    path,
    "/v1/packages/acme%20tools/http%2Fclient/versions/2.0.0-beta.1%2Bbuild.7/dependency-graph?view=declared&format=yaml",
  );
});

test("extended paths use the additive export route and preserve base prefixes", () => {
  const url = dependencyGraphDownloadUrl(
    "https://registry.example/internal/",
    coordinate,
    "proto",
  );
  assert.equal(url.origin, "https://registry.example");
  assert.equal(
    url.pathname,
    "/internal/v1/packages/acme%20tools/http%2Fclient/versions/2.0.0-beta.1%2Bbuild.7/dependency-graph/export/protobuf",
  );
  assert.equal(url.search, "");
});

test("base URL and path validation reject credential and traversal hazards", () => {
  assert.throws(
    () =>
      dependencyGraphDownloadUrl(
        "https://user:secret@registry.example",
        coordinate,
        "json",
      ),
    /credential-free absolute HTTP\(S\) URL/,
  );
  assert.throws(
    () =>
      dependencyGraphExportPath(
        { org: "..", name: "pkg", version: "1.0.0" },
        "json",
      ),
    /dot segment/,
  );
  assert.throws(
    () =>
      dependencyGraphDownloadUrl(
        "file:///tmp/registry",
        coordinate,
        "json",
      ),
    /absolute HTTP\(S\) URL/,
  );
  assert.throws(
    () =>
      dependencyGraphDownloadUrl(
        "http://registry.example",
        coordinate,
        "json",
      ),
    /refusing cleartext http/,
  );
  assert.equal(
    dependencyGraphDownloadUrl(
      "http://registry.example",
      coordinate,
      "json",
      true,
    ).protocol,
    "http:",
  );
});

test("download sends bounded, redirect-safe, authenticated requests", async () => {
  let requestUrl;
  let requestInit;
  const fetch = async (url, init) => {
    requestUrl = new URL(url);
    requestInit = init;
    return new Response(new TextEncoder().encode('{"schema":"zpkg/dependency-graph/v1"}'), {
      status: 200,
      headers: {
        "content-type": "application/vnd.zpkg.dependency-graph.v1+json5",
        etag: '"bytes-sha256"',
        [DEPENDENCY_GRAPH_DIGEST_HEADER]: graphDigest,
        [DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER]: "true",
      },
    });
  };

  const result = await downloadDependencyGraph({
    baseUrl: "https://registry.example",
    ...coordinate,
    format: "json5",
    token: "private-token",
    ifNoneMatch: '"old-etag"',
    fetch,
    maxBytes: 1024,
  });

  assert.equal(requestUrl.pathname.endsWith("/export/json5"), true);
  assert.equal(requestInit.method, "GET");
  assert.equal(requestInit.redirect, "error");
  assert.equal(requestInit.headers.get("authorization"), "Bearer private-token");
  assert.equal(requestInit.headers.get("if-none-match"), '"old-etag"');
  assert.equal(
    requestInit.headers.get("accept"),
    "application/vnd.zpkg.dependency-graph.v1+json5",
  );
  assert.equal(result.status, 200);
  assert.equal(result.notModified, false);
  assert.equal(result.graphDigest, graphDigest);
  assert.equal(result.etag, '"bytes-sha256"');
  assert.equal(result.authoritative, true);
  assert.equal(result.filename, "acme_tools_http_client_2.0.0-beta.1+build.7.dependency-graph.json5");
  assert.match(new TextDecoder().decode(result.body), /dependency-graph/);
});

test("304 responses return validators without consuming a body", async () => {
  const result = await downloadDependencyGraph({
    baseUrl: "https://registry.example",
    org: "acme",
    name: "pkg",
    version: "1.0.0",
    format: "csv",
    ifNoneMatch: '"same"',
    fetch: async () =>
      new Response(null, {
        status: 304,
        headers: {
          etag: '"same"',
          [DEPENDENCY_GRAPH_DIGEST_HEADER]: graphDigest,
          [DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER]: "false",
        },
      }),
  });

  assert.equal(result.status, 304);
  assert.equal(result.notModified, true);
  assert.equal(result.body.byteLength, 0);
  assert.equal(result.authoritative, false);
});

test("unsolicited 304 responses are rejected", async () => {
  await assert.rejects(
    downloadDependencyGraph({
      baseUrl: "https://registry.example",
      org: "acme",
      name: "pkg",
      version: "1.0.0",
      format: "json",
      fetch: async () =>
        new Response(null, {
          status: 304,
          headers: {
            etag: '"same"',
            [DEPENDENCY_GRAPH_DIGEST_HEADER]: graphDigest,
            [DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER]: "true",
          },
        }),
    }),
    /304 without an If-None-Match request/,
  );
});

test("304 validators must weakly match the caller's condition", async () => {
  const fetch = async () =>
    new Response(null, {
      status: 304,
      headers: {
        etag: '"current"',
        [DEPENDENCY_GRAPH_DIGEST_HEADER]: graphDigest,
        [DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER]: "true",
      },
    });
  const common = {
    baseUrl: "https://registry.example",
    org: "acme",
    name: "pkg",
    version: "1.0.0",
    format: "json",
    fetch,
  };

  await assert.rejects(
    downloadDependencyGraph({ ...common, ifNoneMatch: '"other"' }),
    /does not match If-None-Match/,
  );
  const weak = await downloadDependencyGraph({
    ...common,
    ifNoneMatch: 'W/"current"',
  });
  assert.equal(weak.status, 304);
  assert.equal(weak.etag, '"current"');
});

test("streaming and declared body sizes are capped", async () => {
  await assert.rejects(
    downloadDependencyGraph({
      baseUrl: "https://registry.example",
      org: "acme",
      name: "pkg",
      version: "1.0.0",
      format: "msgpack",
      maxBytes: 3,
      fetch: async () =>
        new Response(new Uint8Array([1, 2, 3, 4]), {
          status: 200,
          headers: {
            "content-length": "4",
            "content-type": "application/vnd.zpkg.dependency-graph.v1+msgpack",
            etag: '"bytes"',
            [DEPENDENCY_GRAPH_DIGEST_HEADER]: graphDigest,
            [DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER]: "true",
          },
        }),
    }),
    /exceeds the 3-byte client limit/,
  );
});

test("successful responses require contract media type and validators", async () => {
  await assert.rejects(
    downloadDependencyGraph({
      baseUrl: "https://registry.example",
      org: "acme",
      name: "pkg",
      version: "1.0.0",
      format: "json",
      fetch: async () =>
        new Response("<html>login</html>", {
          status: 200,
          headers: {
            "content-type": "text/html",
            etag: '"bytes"',
            [DEPENDENCY_GRAPH_DIGEST_HEADER]: graphDigest,
            [DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER]: "true",
          },
        }),
    }),
    /Content-Type does not match/,
  );
  await assert.rejects(
    downloadDependencyGraph({
      baseUrl: "https://registry.example",
      org: "acme",
      name: "pkg",
      version: "1.0.0",
      format: "json",
      fetch: async () =>
        new Response("{}", {
          status: 200,
          headers: {
            "content-type": "application/vnd.zpkg.dependency-graph.v1+json",
          },
        }),
    }),
    /valid strong ETag/,
  );
});

test("authority metadata is required and must match the shared descriptor", async () => {
  const response = (authoritative) =>
    new Response("{}", {
      status: 200,
      headers: {
        "content-type": "application/vnd.zpkg.dependency-graph.v1+json",
        etag: '"bytes"',
        [DEPENDENCY_GRAPH_DIGEST_HEADER]: graphDigest,
        ...(authoritative === undefined
          ? {}
          : { [DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER]: authoritative }),
      },
    });
  const common = {
    baseUrl: "https://registry.example",
    org: "acme",
    name: "pkg",
    version: "1.0.0",
    format: "json",
  };

  await assert.rejects(
    downloadDependencyGraph({ ...common, fetch: async () => response() }),
    /missing x-zpkg-graph-authoritative/,
  );
  await assert.rejects(
    downloadDependencyGraph({ ...common, fetch: async () => response("false") }),
    /does not match the requested format/,
  );
});

test("size and timeout overrides remain bounded", async () => {
  await assert.rejects(
    downloadDependencyGraph({
      baseUrl: "https://registry.example",
      org: "acme",
      name: "pkg",
      version: "1.0.0",
      format: "json",
      maxBytes: 1024 * 1024 * 1024 + 1,
      fetch: async () => {
        throw new Error("fetch must not run");
      },
    }),
    /maxBytes must be an integer/,
  );

  await assert.rejects(
    downloadDependencyGraph({
      baseUrl: "https://registry.example",
      org: "acme",
      name: "pkg",
      version: "1.0.0",
      format: "json",
      timeoutMs: 5,
      fetch: async (_url, init) =>
        await new Promise((_resolve, reject) => {
          init.signal.addEventListener(
            "abort",
            () => reject(init.signal.reason),
            { once: true },
          );
        }),
    }),
    /client timeout/,
  );
});

test("non-success responses expose status but never consume an error body", async () => {
  await assert.rejects(
    downloadDependencyGraph({
      baseUrl: "https://registry.example",
      org: "private",
      name: "pkg",
      version: "1.0.0",
      format: "json",
      fetch: async () => new Response("secret details", { status: 404 }),
    }),
    (error) => {
      assert.equal(error instanceof DependencyGraphHttpError, true);
      assert.equal(error.status, 404);
      assert.equal(error.message.includes("secret details"), false);
      return true;
    },
  );
});
