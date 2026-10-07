//! Cancellable async transport for zed-pkg registry reads.
//!
//! This is the replacement transport for latency-sensitive resolution paths.
//! Hyper request futures are ordinary Rust futures: dropping the future stops
//! polling the request and lets Hyper cancel the in-flight HTTP operation.
//! Keep blocking compatibility in `zed-client` only while callers migrate.

use std::time::Duration;

use bytes::{BufMut, Bytes, BytesMut};
use http_body_util::{BodyExt, Empty};
use hyper::body::Incoming;
use hyper::header::{ACCEPT, USER_AGENT};
use hyper::{Request, Response, StatusCode, Uri};
use hyper_rustls::{HttpsConnector, HttpsConnectorBuilder};
use hyper_util::client::legacy::Client as HyperClient;
use hyper_util::client::legacy::connect::HttpConnector;
use hyper_util::rt::TokioExecutor;
use percent_encoding::{AsciiSet, NON_ALPHANUMERIC, percent_decode_str, utf8_percent_encode};
use serde::de::DeserializeOwned;
use url::Url;
use zed_interfaces::registry::{self, ApiError, PackageMetadata, SearchResponse, VersionMetadata};

pub use zed_lib::{ResolveError, resolve_version};

const SEGMENT: &AsciiSet = &NON_ALPHANUMERIC
    .remove(b'-')
    .remove(b'.')
    .remove(b'_')
    .remove(b'~');
const DEFAULT_TIMEOUT: Duration = Duration::from_secs(30);
pub const DEFAULT_MAX_RESPONSE_BYTES: u64 = 16 * 1024 * 1024;
pub const MAX_ERROR_BODY_BYTES: u64 = 16 * 1024;
const MAX_SEGMENT_BYTES: usize = 256;

type Connector = HttpsConnector<HttpConnector>;
type ClientInner = HyperClient<Connector, Empty<Bytes>>;

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("registry error {status}: {code}")]
    Api {
        status: u16,
        code: String,
        message: String,
    },
    #[error("invalid registry base URL")]
    InvalidBaseUrl,
    #[error("invalid client input: {0}")]
    InvalidInput(String),
    #[error("{what} exceeded {limit} bytes")]
    ResponseTooLarge { what: String, limit: u64 },
    #[error("registry request timed out")]
    Timeout,
    #[error("http transport error: {0}")]
    Transport(String),
    #[error("version resolution failed: {0}")]
    Resolution(#[from] ResolveError),
    #[error("{0}")]
    Other(String),
}

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Clone)]
pub struct AsyncClient {
    base: String,
    max_response_bytes: u64,
    timeout: Duration,
    http: ClientInner,
}

impl std::fmt::Debug for AsyncClient {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("AsyncClient")
            .field("base", &self.base)
            .field("max_response_bytes", &self.max_response_bytes)
            .field("timeout", &self.timeout)
            .finish_non_exhaustive()
    }
}

impl AsyncClient {
    pub fn new(base_url: impl Into<String>) -> Result<Self> {
        let raw = base_url.into();
        let trimmed = raw.trim();
        let mut parsed = Url::parse(trimmed).map_err(|_| Error::InvalidBaseUrl)?;
        if !matches!(parsed.scheme(), "http" | "https")
            || parsed.host_str().is_none()
            || !parsed.username().is_empty()
            || parsed.password().is_some()
            || parsed.query().is_some()
            || parsed.fragment().is_some()
        {
            return Err(Error::InvalidBaseUrl);
        }
        validate_path_segments(parsed.path(), "registry path")
            .map_err(|_| Error::InvalidBaseUrl)?;
        let path = parsed.path().trim_end_matches('/').to_string();
        parsed.set_path(&path);
        let base = parsed.as_str().trim_end_matches('/').to_string();

        let https = HttpsConnectorBuilder::new()
            .with_webpki_roots()
            .https_or_http()
            .enable_http1()
            .enable_http2()
            .build();
        let http = HyperClient::builder(TokioExecutor::new()).build(https);

        Ok(Self {
            base,
            max_response_bytes: DEFAULT_MAX_RESPONSE_BYTES,
            timeout: DEFAULT_TIMEOUT,
            http,
        })
    }

    #[must_use]
    pub fn with_max_response_bytes(mut self, limit: u64) -> Self {
        self.max_response_bytes = limit.max(1);
        self
    }

    #[must_use]
    pub fn with_timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }

    pub async fn get_package(&self, org: &str, name: &str) -> Result<PackageMetadata> {
        let path = registry::package_path(
            &checked_segment(org, "org")?,
            &checked_segment(name, "name")?,
        );
        self.get_json(&path, "package metadata").await
    }

    pub async fn get_version(
        &self,
        org: &str,
        name: &str,
        version: &str,
    ) -> Result<VersionMetadata> {
        let path = registry::version_path(
            &checked_segment(org, "org")?,
            &checked_segment(name, "name")?,
            &checked_segment(version, "version")?,
        );
        self.get_json(&path, "version metadata").await
    }

    pub async fn get_resolved_version(
        &self,
        org: &str,
        name: &str,
        requirement: &str,
    ) -> Result<VersionMetadata> {
        let package = self.get_package(org, name).await?;
        let selected = resolve_version(&package, requirement)?.to_string();
        self.get_version(org, name, &selected).await
    }

    pub async fn search(&self, query: &str) -> Result<SearchResponse> {
        let mut url =
            Url::parse(&self.url(&registry::search_path())).map_err(|_| Error::InvalidBaseUrl)?;
        url.query_pairs_mut().append_pair("q", query);
        self.get_json_url(url, "search response").await
    }

    async fn get_json<T: DeserializeOwned>(&self, path: &str, what: &str) -> Result<T> {
        let url = Url::parse(&self.url(path)).map_err(|_| Error::InvalidBaseUrl)?;
        self.get_json_url(url, what).await
    }

    async fn get_json_url<T: DeserializeOwned>(&self, url: Url, what: &str) -> Result<T> {
        let uri: Uri = url
            .as_str()
            .parse()
            .map_err(|error| Error::Transport(format!("invalid request URI: {error}")))?;
        let request = Request::get(uri)
            .header(
                USER_AGENT,
                concat!("zed-client-async-rust/", env!("CARGO_PKG_VERSION")),
            )
            .header(ACCEPT, "application/json")
            .body(Empty::<Bytes>::new())
            .map_err(|error| Error::Transport(format!("building request: {error}")))?;

        let response = tokio::time::timeout(self.timeout, self.http.request(request))
            .await
            .map_err(|_| Error::Timeout)?
            .map_err(|error| Error::Transport(error.to_string()))?;
        self.decode_json(response, what).await
    }

    async fn decode_json<T: DeserializeOwned>(
        &self,
        response: Response<Incoming>,
        what: &str,
    ) -> Result<T> {
        let status = response.status();
        let limit = if status.is_success() {
            self.max_response_bytes
        } else {
            self.max_response_bytes.min(MAX_ERROR_BODY_BYTES)
        };
        let body = read_capped(response.into_body(), limit, what).await?;
        if !status.is_success() {
            return Err(api_error(status, &body));
        }
        serde_json::from_slice(&body)
            .map_err(|error| Error::Other(format!("invalid registry response: {error}")))
    }

    fn url(&self, path: &str) -> String {
        format!("{}{path}", self.base)
    }
}

async fn read_capped(mut body: Incoming, limit: u64, what: &str) -> Result<Vec<u8>> {
    let capacity = usize::try_from(limit.min(64 * 1024)).unwrap_or(64 * 1024);
    let mut output = BytesMut::with_capacity(capacity);
    while let Some(frame) = body.frame().await {
        let frame = frame.map_err(|error| Error::Transport(error.to_string()))?;
        let Ok(data) = frame.into_data() else {
            continue;
        };
        if output.len() as u64 + data.len() as u64 > limit {
            return Err(Error::ResponseTooLarge {
                what: what.to_string(),
                limit,
            });
        }
        output.put(data);
    }
    Ok(output.to_vec())
}

fn api_error(status: StatusCode, body: &[u8]) -> Error {
    let status = status.as_u16();
    match serde_json::from_slice::<ApiError>(body) {
        Ok(error) => Error::Api {
            status,
            code: if error.code.trim().is_empty() {
                format!("http_{status}")
            } else {
                error.code.trim().to_string()
            },
            message: error.message,
        },
        Err(_) => Error::Api {
            status,
            code: format!("http_{status}"),
            message: String::from_utf8_lossy(body).into_owned(),
        },
    }
}

fn checked_segment(segment: &str, name: &str) -> Result<String> {
    validate_segment(segment, name)?;
    Ok(match segment {
        "." => "%2E".to_string(),
        ".." => "%2E%2E".to_string(),
        _ => utf8_percent_encode(segment, SEGMENT).to_string(),
    })
}

fn validate_segment<'a>(segment: &'a str, name: &str) -> Result<&'a str> {
    if segment.trim().is_empty() {
        return Err(Error::InvalidInput(format!("{name} must not be blank")));
    }
    if matches!(segment, "." | "..") {
        return Err(Error::InvalidInput(format!(
            "{name} must not be a dot segment"
        )));
    }
    if segment.len() > MAX_SEGMENT_BYTES {
        return Err(Error::InvalidInput(format!(
            "{name} exceeds {MAX_SEGMENT_BYTES} UTF-8 bytes"
        )));
    }
    if segment.chars().any(char::is_control) {
        return Err(Error::InvalidInput(format!(
            "{name} must not contain control characters"
        )));
    }
    Ok(segment)
}

fn validate_path_segments(path: &str, name: &str) -> Result<()> {
    for (index, segment) in path
        .split('/')
        .filter(|segment| !segment.is_empty())
        .enumerate()
    {
        let decoded = percent_decode_str(segment).decode_utf8().map_err(|_| {
            Error::InvalidInput(format!("{name} contains invalid percent encoding"))
        })?;
        validate_segment(&decoded, &format!("{name} segment {}", index + 1))?;
        if decoded.contains('/') || decoded.contains('\\') {
            return Err(Error::InvalidInput(format!(
                "{name} segments must not contain encoded separators"
            )));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base_url_validation_preserves_gateway_path() {
        let client = AsyncClient::new(" https://registry.zpkg.tech/gateway/// ").unwrap();
        assert_eq!(
            client.url(&registry::package_path("acme", "kit")),
            "https://registry.zpkg.tech/gateway/v1/packages/acme/kit"
        );
    }

    #[test]
    fn invalid_base_urls_are_rejected() {
        for invalid in [
            "ftp://registry.zpkg.tech",
            "https://user@example.com",
            "https://registry.zpkg.tech/?query=1",
            "https://registry.zpkg.tech/#fragment",
        ] {
            assert!(AsyncClient::new(invalid).is_err(), "accepted {invalid}");
        }
    }
}
