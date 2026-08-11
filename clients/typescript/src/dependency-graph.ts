import {
  encodePathSegment as encodeRegistryPathSegment,
  normalizeRegistryUrl,
} from "./client.js";

export const DEPENDENCY_GRAPH_DIGEST_HEADER = "x-zpkg-graph-digest";
export const DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER =
  "x-zpkg-graph-authoritative";
export const DEPENDENCY_GRAPH_DEFAULT_MAX_BYTES = 32 * 1024 * 1024;
export const DEPENDENCY_GRAPH_MAX_BYTES = 1024 * 1024 * 1024;
export const DEPENDENCY_GRAPH_DEFAULT_TIMEOUT_MS = 30_000;
export const DEPENDENCY_GRAPH_MAX_TIMEOUT_MS = 10 * 60_000;

export const DEPENDENCY_GRAPH_FORMATS = [
  "json",
  "yaml",
  "toml",
  "dot",
  "mermaid",
  "json5",
  "xml",
  "csv",
  "msgpack",
  "protobuf",
] as const;

export type DependencyGraphFormat = (typeof DEPENDENCY_GRAPH_FORMATS)[number];
export type DependencyGraphRouteKind = "canonical" | "extended";

export interface DependencyGraphExportDescriptor {
  readonly format: DependencyGraphFormat;
  readonly routeKind: DependencyGraphRouteKind;
  readonly extension: string;
  readonly mediaType: string;
  readonly authoritative: boolean;
  readonly binary: boolean;
}

const DESCRIPTORS: Readonly<
  Record<DependencyGraphFormat, DependencyGraphExportDescriptor>
> = Object.freeze({
  json: descriptor(
    "json",
    "canonical",
    "json",
    "application/vnd.zpkg.dependency-graph.v1+json",
    true,
    false,
  ),
  yaml: descriptor(
    "yaml",
    "canonical",
    "yaml",
    "application/vnd.zpkg.dependency-graph.v1+yaml",
    true,
    false,
  ),
  toml: descriptor(
    "toml",
    "canonical",
    "toml",
    "application/vnd.zpkg.dependency-graph.v1+toml",
    true,
    false,
  ),
  dot: descriptor(
    "dot",
    "canonical",
    "dot",
    "text/vnd.graphviz; charset=utf-8",
    false,
    false,
  ),
  mermaid: descriptor(
    "mermaid",
    "canonical",
    "mmd",
    "text/vnd.mermaid; charset=utf-8",
    false,
    false,
  ),
  json5: descriptor(
    "json5",
    "extended",
    "json5",
    "application/vnd.zpkg.dependency-graph.v1+json5",
    true,
    false,
  ),
  xml: descriptor(
    "xml",
    "extended",
    "xml",
    "application/vnd.zpkg.dependency-graph.v1+xml",
    true,
    false,
  ),
  csv: descriptor(
    "csv",
    "extended",
    "csv",
    "text/csv; charset=utf-8",
    false,
    false,
  ),
  msgpack: descriptor(
    "msgpack",
    "extended",
    "msgpack",
    "application/vnd.zpkg.dependency-graph.v1+msgpack",
    true,
    true,
  ),
  protobuf: descriptor(
    "protobuf",
    "extended",
    "pb",
    "application/vnd.zpkg.dependency-graph.v1+protobuf",
    true,
    true,
  ),
});

const FORMAT_ALIASES: Readonly<Record<string, DependencyGraphFormat>> =
  Object.freeze({
    json: "json",
    yaml: "yaml",
    yml: "yaml",
    toml: "toml",
    dot: "dot",
    graphviz: "dot",
    mermaid: "mermaid",
    mmd: "mermaid",
    json5: "json5",
    xml: "xml",
    csv: "csv",
    msgpack: "msgpack",
    messagepack: "msgpack",
    mpk: "msgpack",
    protobuf: "protobuf",
    proto: "protobuf",
    pb: "protobuf",
  });

function descriptor(
  format: DependencyGraphFormat,
  routeKind: DependencyGraphRouteKind,
  extension: string,
  mediaType: string,
  authoritative: boolean,
  binary: boolean,
): DependencyGraphExportDescriptor {
  return Object.freeze({
    format,
    routeKind,
    extension,
    mediaType,
    authoritative,
    binary,
  });
}

export function normalizeDependencyGraphFormat(
  value: string,
): DependencyGraphFormat {
  const normalized = FORMAT_ALIASES[value.trim().toLowerCase()];
  if (normalized === undefined) {
    throw new TypeError(
      `unsupported dependency graph format ${JSON.stringify(value)}`,
    );
  }
  return normalized;
}

export function dependencyGraphExportDescriptor(
  value: string,
): DependencyGraphExportDescriptor {
  return DESCRIPTORS[normalizeDependencyGraphFormat(value)];
}

export interface DependencyGraphCoordinate {
  readonly org: string;
  readonly name: string;
  readonly version: string;
}

export function dependencyGraphExportPath(
  coordinate: DependencyGraphCoordinate,
  format: string,
): string {
  const descriptor = dependencyGraphExportDescriptor(format);
  const segments = [
    "v1",
    "packages",
    coordinate.org,
    coordinate.name,
    "versions",
    coordinate.version,
    "dependency-graph",
  ];
  if (descriptor.routeKind === "extended") {
    segments.push("export", descriptor.format);
  }
  const path = `/${segments.map(encodePathSegment).join("/")}`;
  if (descriptor.routeKind === "canonical") {
    const query = new URLSearchParams({
      view: "declared",
      format: descriptor.format,
    });
    return `${path}?${query.toString()}`;
  }
  return path;
}

export function dependencyGraphDownloadUrl(
  baseUrl: string | URL,
  coordinate: DependencyGraphCoordinate,
  format: string,
  allowInsecureTransport = false,
): URL {
  const base = new URL(
    normalizeRegistryUrl(baseUrl.toString(), allowInsecureTransport),
  );
  const route = dependencyGraphExportPath(coordinate, format);
  const [routePath, routeQuery] = route.split("?", 2);
  const prefix = base.pathname.replace(/\/+$/, "");
  base.pathname = `${prefix}${routePath}`;
  base.search = routeQuery === undefined ? "" : `?${routeQuery}`;
  return base;
}

function encodePathSegment(value: string): string {
  return encodeRegistryPathSegment(value, "dependency graph path segment");
}

export interface DependencyGraphDownloadOptions
  extends DependencyGraphCoordinate {
  readonly baseUrl: string | URL;
  readonly format: string;
  readonly token?: string;
  readonly allowInsecureTransport?: boolean;
  readonly ifNoneMatch?: string;
  readonly signal?: AbortSignal;
  readonly fetch?: typeof globalThis.fetch;
  readonly maxBytes?: number;
  readonly timeoutMs?: number;
}

export interface DependencyGraphDownload {
  readonly status: 200 | 304;
  readonly notModified: boolean;
  readonly body: Uint8Array;
  readonly format: DependencyGraphFormat;
  readonly mediaType: string | null;
  readonly etag: string;
  readonly graphDigest: string;
  readonly authoritative: boolean;
  readonly filename: string;
  readonly url: URL;
}

export class DependencyGraphHttpError extends Error {
  readonly status: number;
  readonly url: URL;

  constructor(status: number, url: URL) {
    super(`dependency graph request failed with HTTP ${status}`);
    this.name = "DependencyGraphHttpError";
    this.status = status;
    this.url = new URL(url);
  }
}

export async function downloadDependencyGraph(
  options: DependencyGraphDownloadOptions,
): Promise<DependencyGraphDownload> {
  const descriptor = dependencyGraphExportDescriptor(options.format);
  const url = dependencyGraphDownloadUrl(
    options.baseUrl,
    options,
    descriptor.format,
    options.allowInsecureTransport,
  );
  const fetchImplementation = options.fetch ?? globalThis.fetch;
  if (typeof fetchImplementation !== "function") {
    throw new TypeError("no Fetch implementation is available");
  }
  const maxBytes = normalizeMaxBytes(options.maxBytes);
  const timeoutMs = normalizeTimeoutMs(options.timeoutMs);
  const headers = new Headers({ Accept: descriptor.mediaType });
  if (options.token !== undefined && options.token !== "") {
    headers.set("Authorization", `Bearer ${options.token}`);
  }
  if (options.ifNoneMatch !== undefined && options.ifNoneMatch !== "") {
    headers.set("If-None-Match", options.ifNoneMatch);
  }

  const timedSignal = createTimedSignal(options.signal, timeoutMs);
  try {
    const response = await fetchImplementation(url, {
      method: "GET",
      headers,
      redirect: "error",
      signal: timedSignal.signal,
    });
    if (response.redirected) {
      throw new TypeError("dependency graph responses may not follow redirects");
    }
    if (response.status !== 200 && response.status !== 304) {
      throw new DependencyGraphHttpError(response.status, url);
    }

    const mediaType = response.headers.get("content-type");
    const etag = requireStrongEtag(response.headers.get("etag"));
    const graphDigest = requireGraphDigest(
      response.headers.get(DEPENDENCY_GRAPH_DIGEST_HEADER),
    );
    const authoritative = requireAuthoritativeHeader(
      response.headers.get(DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER),
      descriptor.authoritative,
    );
    const metadata = {
      format: descriptor.format,
      mediaType,
      etag,
      graphDigest,
      authoritative,
      filename: dependencyGraphFilename(options, descriptor),
      url: new URL(url),
    } as const;

    if (response.status === 304) {
      if (options.ifNoneMatch === undefined || options.ifNoneMatch === "") {
        throw new TypeError(
          "registry returned 304 without an If-None-Match request",
        );
      }
      if (!ifNoneMatchMatches(options.ifNoneMatch, etag)) {
        throw new TypeError(
          "registry returned 304 with an ETag that does not match If-None-Match",
        );
      }
      return {
        status: 304,
        notModified: true,
        body: new Uint8Array(),
        ...metadata,
      };
    }

    requireExpectedMediaType(mediaType, descriptor.mediaType);
    return {
      status: 200,
      notModified: false,
      body: await readBoundedBody(response, maxBytes),
      ...metadata,
    };
  } finally {
    timedSignal.dispose();
  }
}

/** RFC 9110 uses weak comparison for If-None-Match on GET. The response still
 * has to identify one of the validators the caller supplied; an unrelated 304
 * must not be treated as proof that cached graph bytes are current. */
function ifNoneMatchMatches(condition: string, etag: string): boolean {
  const opaque = (value: string): string =>
    value.trim().replace(/^W\//i, "");
  return condition
    .split(",")
    .map((candidate) => candidate.trim())
    .some((candidate) => candidate === "*" || opaque(candidate) === opaque(etag));
}

function normalizeMaxBytes(value: number | undefined): number {
  const maxBytes = value ?? DEPENDENCY_GRAPH_DEFAULT_MAX_BYTES;
  if (
    !Number.isSafeInteger(maxBytes) ||
    maxBytes <= 0 ||
    maxBytes > DEPENDENCY_GRAPH_MAX_BYTES
  ) {
    throw new RangeError(
      `maxBytes must be an integer between 1 and ${DEPENDENCY_GRAPH_MAX_BYTES}`,
    );
  }
  return maxBytes;
}

function normalizeTimeoutMs(value: number | undefined): number {
  const timeoutMs = value ?? DEPENDENCY_GRAPH_DEFAULT_TIMEOUT_MS;
  if (
    !Number.isSafeInteger(timeoutMs) ||
    timeoutMs <= 0 ||
    timeoutMs > DEPENDENCY_GRAPH_MAX_TIMEOUT_MS
  ) {
    throw new RangeError(
      `timeoutMs must be an integer between 1 and ${DEPENDENCY_GRAPH_MAX_TIMEOUT_MS}`,
    );
  }
  return timeoutMs;
}

function createTimedSignal(
  callerSignal: AbortSignal | undefined,
  timeoutMs: number,
): { readonly signal: AbortSignal; dispose(): void } {
  const controller = new AbortController();
  const forwardAbort = (): void => controller.abort(callerSignal?.reason);
  if (callerSignal?.aborted) {
    forwardAbort();
  } else {
    callerSignal?.addEventListener("abort", forwardAbort, { once: true });
  }
  const timer = globalThis.setTimeout(() => {
    controller.abort(
      new DOMException(
        `dependency graph request exceeded the ${timeoutMs}ms client timeout`,
        "TimeoutError",
      ),
    );
  }, timeoutMs);
  return {
    signal: controller.signal,
    dispose(): void {
      globalThis.clearTimeout(timer);
      callerSignal?.removeEventListener("abort", forwardAbort);
    },
  };
}

function requireStrongEtag(value: string | null): string {
  if (value === null || value.startsWith("W/") || !/^"[^"\r\n]+"$/.test(value)) {
    throw new TypeError("dependency graph response is missing a valid strong ETag");
  }
  return value;
}

function requireGraphDigest(value: string | null): string {
  if (value === null || !/^sha256:[0-9a-f]{64}$/.test(value)) {
    throw new TypeError(
      `dependency graph response is missing a valid ${DEPENDENCY_GRAPH_DIGEST_HEADER} header`,
    );
  }
  return value;
}

function requireExpectedMediaType(
  actual: string | null,
  expected: string,
): void {
  const bareType = (value: string): string =>
    value.split(";", 1)[0]?.trim().toLowerCase() ?? "";
  if (actual === null || bareType(actual) !== bareType(expected)) {
    throw new TypeError(
      "dependency graph response Content-Type does not match the requested format",
    );
  }
}

function requireAuthoritativeHeader(
  value: string | null,
  expected: boolean,
): boolean {
  if (value === null) {
    throw new TypeError(
      `missing ${DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER} response header`,
    );
  }
  const normalized = value.toLowerCase();
  const actual = normalized === "true" ? true : normalized === "false" ? false : null;
  if (actual === null) {
    throw new TypeError(
      `invalid ${DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER} response header`,
    );
  }
  if (actual !== expected) {
    throw new TypeError(
      `${DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER} does not match the requested format`,
    );
  }
  return actual;
}

function dependencyGraphFilename(
  coordinate: DependencyGraphCoordinate,
  descriptor: DependencyGraphExportDescriptor,
): string {
  const stem = [coordinate.org, coordinate.name, coordinate.version]
    .map((part) => part.replace(/[^A-Za-z0-9.+-]/g, "_"))
    .join("_");
  return `${stem}.dependency-graph.${descriptor.extension}`;
}

async function readBoundedBody(
  response: Response,
  maxBytes: number,
): Promise<Uint8Array> {
  const declaredLength = response.headers.get("content-length");
  if (declaredLength !== null) {
    if (!/^[0-9]+$/.test(declaredLength)) {
      throw new TypeError("dependency graph response has an invalid Content-Length");
    }
    if (BigInt(declaredLength) > BigInt(maxBytes)) {
      throw new RangeError(
        `dependency graph body exceeds the ${maxBytes}-byte client limit`,
      );
    }
  }

  if (response.body === null) {
    const body = new Uint8Array(await response.arrayBuffer());
    if (body.byteLength > maxBytes) {
      throw new RangeError(
        `dependency graph body exceeds the ${maxBytes}-byte client limit`,
      );
    }
    return body;
  }

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value === undefined || value.byteLength === 0) continue;
      total += value.byteLength;
      if (total > maxBytes) {
        await reader.cancel("dependency graph client size limit exceeded");
        throw new RangeError(
          `dependency graph body exceeds the ${maxBytes}-byte client limit`,
        );
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}
