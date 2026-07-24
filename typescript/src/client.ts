import type {
  ApiErrorBody,
  ClaimOrgResponse,
  PackageMetadata,
  PublishResponse,
  SearchResponse,
  VersionMetadata,
} from "./types.js";

export const DEFAULT_REGISTRY_URL = "https://registry.zpkg.tech";

/** Bounds every request (connect + read), in milliseconds. */
export const DEFAULT_TIMEOUT_MS = 30_000;

/**
 * Hard ceiling on artifact downloads, matching the server's MAX_ARTIFACT_BYTES
 * default (100 MiB); plus the slack added to a version's declared size.
 */
export const MAX_ARTIFACT_BYTES = 100 * 1024 * 1024;
const DOWNLOAD_SLACK = 1024 * 1024;

/** The declared size (when sane) plus slack, capped by the ceiling. */
function downloadLimit(size: number): number {
  if (Number.isFinite(size) && size > 0) {
    return Math.min(size + DOWNLOAD_SLACK, MAX_ARTIFACT_BYTES);
  }
  return MAX_ARTIFACT_BYTES;
}

/** Stream a response body, refusing once more than `limit` bytes arrive. */
async function readCapped(response: Response, limit: number): Promise<Uint8Array> {
  const tooLarge = () =>
    new ZedApiError(0, "artifact_too_large", `artifact exceeded ${limit} bytes; refusing`);
  const body = response.body;
  if (!body) {
    const buf = new Uint8Array(await response.arrayBuffer());
    if (buf.byteLength > limit) throw tooLarge();
    return buf;
  }
  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value) {
      total += value.byteLength;
      if (total > limit) {
        await reader.cancel();
        throw tooLarge();
      }
      chunks.push(value);
    }
  }
  const out = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return out;
}

export class ZedApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(`registry error ${status}: ${code}: ${message}`);
    this.name = "ZedApiError";
  }
}

export interface ClientOptions {
  registryUrl?: string;
  token?: string;
  fetchImpl?: typeof fetch;
}

export function packagePath(org: string, name: string): string {
  return `/v1/packages/${encodeURIComponent(org)}/${encodeURIComponent(name)}`;
}

export function versionPath(org: string, name: string, version: string): string {
  return `/v1/packages/${encodeURIComponent(org)}/${encodeURIComponent(name)}/versions/${encodeURIComponent(version)}`;
}

export function artifactPath(sha256: string): string {
  return `/v1/artifacts/${encodeURIComponent(sha256)}`;
}

export function filePath(org: string, name: string, version: string, path: string): string {
  const encodedPath = path.split("/").map(encodeURIComponent).join("/");
  return `/v1/files/${encodeURIComponent(org)}/${encodeURIComponent(name)}/${encodeURIComponent(version)}/${encodedPath}`;
}

export class ZedClient {
  private readonly base: string;
  private readonly token?: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: ClientOptions = {}) {
    this.base = (options.registryUrl ?? DEFAULT_REGISTRY_URL).replace(/\/+$/, "");
    this.token = options.token;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    if (this.token) headers.set("authorization", `Bearer ${this.token}`);
    const response = await this.fetchImpl(`${this.base}${path}`, { ...init, headers });
    if (!response.ok) {
      const text = await response.text();
      let body: ApiErrorBody = { code: "unknown", message: text };
      try {
        const parsed = JSON.parse(text) as Partial<ApiErrorBody> | null;
        body = {
          // JSON error bodies without a stable code still get a defined one.
          code: typeof parsed?.code === "string" ? parsed.code : `http_${response.status}`,
          message: typeof parsed?.message === "string" ? parsed.message : text,
        };
      } catch {
        // non-JSON error body; keep the raw text
      }
      throw new ZedApiError(response.status, body.code, body.message);
    }
    return (await response.json()) as T;
  }

  getPackage(org: string, name: string): Promise<PackageMetadata> {
    return this.request(packagePath(org, name));
  }

  getVersion(org: string, name: string, version: string): Promise<VersionMetadata> {
    return this.request(versionPath(org, name, version));
  }

  search(query: string): Promise<SearchResponse> {
    return this.request(`/v1/search?q=${encodeURIComponent(query)}`);
  }

  claimOrg(slug: string): Promise<ClaimOrgResponse> {
    return this.request("/v1/orgs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ slug }),
    });
  }

  /** Download an artifact and verify its sha256 (WebCrypto). */
  async downloadArtifact(version: VersionMetadata): Promise<Uint8Array> {
    const url = version.download_url.startsWith("http")
      ? version.download_url
      : `${this.base}${artifactPath(version.sha256)}`;
    const response = await this.fetchImpl(url);
    if (!response.ok) {
      throw new ZedApiError(response.status, "download_failed", await response.text());
    }
    const bytes = new Uint8Array(await response.arrayBuffer());
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const actual = [...new Uint8Array(digest)]
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    if (actual !== version.sha256) {
      throw new ZedApiError(0, "sha256_mismatch", `expected ${version.sha256}, got ${actual}`);
    }
    return bytes;
  }

  /** Publish: multipart meta (PublishMeta JSON) + artifact bytes. */
  async publish(
    meta: { manifest: { package: { org: string; name: string; version: string } } } & Record<
      string,
      unknown
    >,
    artifact: Blob,
  ): Promise<PublishResponse> {
    const pkg = meta.manifest.package;
    const form = new FormData();
    form.set("meta", JSON.stringify(meta));
    form.set("artifact", artifact, `${pkg.org}-${pkg.name}-${pkg.version}.tar.gz`);
    return this.request(versionPath(pkg.org, pkg.name, pkg.version), {
      method: "PUT",
      body: form,
    });
  }
}
