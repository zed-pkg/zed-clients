export const DEPENDENCY_GRAPH_DIGEST_HEADER = "x-zpkg-graph-digest";
export const DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER =
  "x-zpkg-graph-authoritative";
export const DEPENDENCY_GRAPH_DEFAULT_MAX_BYTES = 32 * 1024 * 1024;

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
): URL {
  const base = normalizeBaseUrl(baseUrl);
  const route = dependencyGraphExportPath(coordinate, format);
  const [routePath, routeQuery] = route.split("?", 2);
  const prefix = base.pathname.replace(/\/+$/, "");
  base.pathname = `${prefix}${routePath}`;
  base.search = routeQuery === undefined ? "" : `?${routeQuery}`;
  return base;
}

function normalizeBaseUrl(value: string | URL): URL {
  const base = new URL(value.toString());
  if (base.protocol !== "https:" && base.protocol !== "http:") {
    throw new TypeError("dependency graph downloads require an HTTP(S) URL");
  }
  if (base.username !== "" || base.password !== "") {
    throw new TypeError(
      "registry URLs may not embed credentials; pass the bearer token separately",
    );
  }
  if (base.search !== "" || base.hash !== "") {
    throw new TypeError("registry base URLs may not include a query or fragment");
  }
  return base;
}

function encodePathSegment(value: string): string {
  if (value.length === 0) {
    throw new TypeError("dependency graph path segments may not be empty");
  }
  if (value === "." || value === "..") {
    throw new TypeError("dependency graph path segments may not be dot segments");
  }
  for (const character of value) {
    const code = character.codePointAt(0) ?? 0;
    if (code === 0 || code < 0x20 || code === 0x7f) {
      throw new TypeError("dependency graph path segments may not contain controls");
    }
  }
  return encodeURIComponent(value);
}

export interface DependencyGraphDownloadOptions
  extends DependencyGraphCoordinate {
  readonly baseUrl: string | URL;
  readonly format: string;
  readonly token?: string;
  readonly ifNoneMatch?: string;
  readonly signal?: AbortSignal;
  readonly fetch?: typeof globalThis.fetch;
  readonly maxBytes?: number;
}

export interface DependencyGraphDownload {
  readonly status: 200 | 304;
  readonly notModified: boolean;
  readonly body: Uint8Array;
  readonly format: DependencyGraphFormat;
  readonly mediaType: string | null;
  readonly etag: string | null;
  readonly graphDigest: string | null;
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
  const url = dependencyGraphDownloadUrl(options.baseUrl, options, descriptor.format);
  const fetchImplementation = options.fetch ?? globalThis.fetch;
  if (typeof fetchImplementation !== "function") {
    throw new TypeError("no Fetch implementation is available");
  }
  const maxBytes = normalizeMaxBytes(options.maxBytes);
  const headers = new Headers({ Accept: descriptor.mediaType });
  if (options.token !== undefined && options.token !== "") {
    headers.set("Authorization", `Bearer ${options.token}`);
  }
  if (options.ifNoneMatch !== undefined && options.ifNoneMatch !== "") {
    headers.set("If-None-Match", options.ifNoneMatch);
  }

  const response = await fetchImplementation(url, {
    method: "GET",
    headers,
    redirect: "error",
    signal: options.signal,
  });
  if (response.status !== 200 && response.status !== 304) {
    throw new DependencyGraphHttpError(response.status, url);
  }

  const authoritative = parseAuthoritativeHeader(
    response.headers.get(DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER),
    descriptor.authoritative,
  );
  const metadata = {
    format: descriptor.format,
    mediaType: response.headers.get("content-type"),
    etag: response.headers.get("etag"),
    graphDigest: response.headers.get(DEPENDENCY_GRAPH_DIGEST_HEADER),
    authoritative,
    filename: dependencyGraphFilename(options, descriptor),
    url: new URL(url),
  } as const;

  if (response.status === 304) {
    return {
      status: 304,
      notModified: true,
      body: new Uint8Array(),
      ...metadata,
    };
  }

  return {
    status: 200,
    notModified: false,
    body: await readBoundedBody(response, maxBytes),
    ...metadata,
  };
}

function normalizeMaxBytes(value: number | undefined): number {
  const maxBytes = value ?? DEPENDENCY_GRAPH_DEFAULT_MAX_BYTES;
  if (!Number.isSafeInteger(maxBytes) || maxBytes <= 0) {
    throw new RangeError("maxBytes must be a positive safe integer");
  }
  return maxBytes;
}

function parseAuthoritativeHeader(
  value: string | null,
  fallback: boolean,
): boolean {
  if (value === null) return fallback;
  if (value.toLowerCase() === "true") return true;
  if (value.toLowerCase() === "false") return false;
  throw new TypeError(
    `invalid ${DEPENDENCY_GRAPH_AUTHORITATIVE_HEADER} response header`,
  );
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
    const parsed = Number(declaredLength);
    if (Number.isFinite(parsed) && parsed > maxBytes) {
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
