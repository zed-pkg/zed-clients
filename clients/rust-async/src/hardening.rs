use std::collections::HashSet;
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};
use std::time::{Duration, Instant};

use hyper::header::{ETAG, HeaderMap, RETRY_AFTER};
use url::Url;

/// One monotonic budget shared by every probe in one recovery operation.
#[derive(Debug, Clone)]
pub struct RecoveryBudget {
    deadline: Instant,
}

impl RecoveryBudget {
    #[must_use]
    pub fn new(total: Duration) -> Self {
        Self {
            deadline: Instant::now() + total,
        }
    }

    #[must_use]
    pub fn remaining(&self) -> Duration {
        self.deadline
            .checked_duration_since(Instant::now())
            .unwrap_or(Duration::ZERO)
    }

    #[must_use]
    pub fn child_timeout(&self, cap: Duration) -> Duration {
        self.remaining().min(cap)
    }

    #[must_use]
    pub fn exhausted(&self) -> bool {
        self.remaining().is_zero()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum TransportSourceKind {
    Registry,
    GithubApi,
    GithubRelease,
    Ghcr,
    GithubCodeload,
    ExplicitMirror,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum AuthMode {
    Anonymous,
    Token,
}

/// Per-resolution only: callers create/drop this with one solve/fetch operation.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct NegativeProbeKey {
    pub package: String,
    pub immutable_ref: String,
    pub source: TransportSourceKind,
    pub auth: AuthMode,
}

#[derive(Debug, Default)]
pub struct NegativeProbeCache {
    failed: HashSet<NegativeProbeKey>,
    hits: u64,
    misses: u64,
}

impl NegativeProbeCache {
    pub fn contains(&mut self, key: &NegativeProbeKey) -> bool {
        if self.failed.contains(key) {
            self.hits += 1;
            true
        } else {
            self.misses += 1;
            false
        }
    }

    pub fn insert(&mut self, key: NegativeProbeKey) {
        self.failed.insert(key);
    }

    #[must_use]
    pub fn counters(&self) -> (u64, u64) {
        (self.hits, self.misses)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RateLimitInfo {
    pub limited: bool,
    pub retry_after: Option<Duration>,
    pub remaining: Option<u64>,
    pub reset_unix_seconds: Option<u64>,
    pub resource: Option<String>,
}

impl RateLimitInfo {
    #[must_use]
    pub fn from_headers(status: u16, headers: &HeaderMap) -> Self {
        let retry_after = header_u64(headers, RETRY_AFTER.as_str()).map(Duration::from_secs);
        let remaining = header_u64(headers, "x-ratelimit-remaining");
        let reset_unix_seconds = header_u64(headers, "x-ratelimit-reset");
        let resource = safe_header_text(headers, "x-ratelimit-resource", 64);
        let limited = status == 429
            || (status == 403 && remaining == Some(0))
            || retry_after.is_some();
        Self {
            limited,
            retry_after,
            remaining,
            reset_unix_seconds,
            resource,
        }
    }
}

fn header_u64(headers: &HeaderMap, name: &str) -> Option<u64> {
    headers
        .get(name)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.trim().parse().ok())
}

fn safe_header_text(headers: &HeaderMap, name: &str, max: usize) -> Option<String> {
    let value = headers.get(name)?.to_str().ok()?.trim();
    if value.is_empty()
        || value.len() > max
        || value.chars().any(|ch| ch.is_control())
    {
        return None;
    }
    Some(value.to_string())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DestinationClass {
    Public,
    Loopback,
    Private,
    LinkLocal,
    CarrierGradeNat,
    Unspecified,
    Multicast,
}

#[must_use]
pub fn classify_ip(ip: IpAddr) -> DestinationClass {
    match ip {
        IpAddr::V4(ip) => classify_v4(ip),
        IpAddr::V6(ip) => classify_v6(ip),
    }
}

fn classify_v4(ip: Ipv4Addr) -> DestinationClass {
    if ip.is_loopback() {
        DestinationClass::Loopback
    } else if ip.is_unspecified() {
        DestinationClass::Unspecified
    } else if ip.is_multicast() {
        DestinationClass::Multicast
    } else if ip.is_link_local() {
        DestinationClass::LinkLocal
    } else if ip.is_private() {
        DestinationClass::Private
    } else if is_cgnat(ip) {
        DestinationClass::CarrierGradeNat
    } else {
        DestinationClass::Public
    }
}

fn classify_v6(ip: Ipv6Addr) -> DestinationClass {
    let first = ip.segments()[0];
    if ip.is_loopback() {
        DestinationClass::Loopback
    } else if ip.is_unspecified() {
        DestinationClass::Unspecified
    } else if ip.is_multicast() {
        DestinationClass::Multicast
    } else if first & 0xffc0 == 0xfe80 {
        DestinationClass::LinkLocal
    } else if first & 0xfe00 == 0xfc00 {
        DestinationClass::Private
    } else {
        DestinationClass::Public
    }
}

fn is_cgnat(ip: Ipv4Addr) -> bool {
    let octets = ip.octets();
    octets[0] == 100 && (64..=127).contains(&octets[1])
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RedirectDecision {
    SameOrigin,
    CrossOrigin,
}

pub fn validate_redirect(
    from: &Url,
    to: &Url,
    allowed_hosts: &[&str],
) -> Result<RedirectDecision, &'static str> {
    if !matches!(to.scheme(), "http" | "https") || to.host_str().is_none() {
        return Err("unsupported redirect destination");
    }
    if !to.username().is_empty() || to.password().is_some() {
        return Err("redirect destination contains userinfo");
    }
    if from.scheme() == "https" && to.scheme() != "https" {
        return Err("https redirect downgrade refused");
    }
    let host = to.host_str().ok_or("redirect destination has no host")?;
    if !allowed_hosts
        .iter()
        .any(|candidate| host.eq_ignore_ascii_case(candidate))
    {
        return Err("redirect destination host is not allowlisted");
    }
    if same_origin(from, to) {
        Ok(RedirectDecision::SameOrigin)
    } else {
        Ok(RedirectDecision::CrossOrigin)
    }
}

#[must_use]
pub fn same_origin(left: &Url, right: &Url) -> bool {
    left.scheme().eq_ignore_ascii_case(right.scheme())
        && left.host_str().map(str::to_ascii_lowercase)
            == right.host_str().map(str::to_ascii_lowercase)
        && left.port_or_known_default() == right.port_or_known_default()
}

#[must_use]
pub fn forward_sensitive_headers(from: &Url, to: &Url) -> bool {
    same_origin(from, to)
}

#[must_use]
pub fn strong_etag(headers: &HeaderMap) -> Option<String> {
    let value = headers.get(ETAG)?.to_str().ok()?.trim();
    if value.len() < 2
        || value.len() > 256
        || value.starts_with("W/")
        || !value.starts_with('"')
        || !value.ends_with('"')
        || value.chars().any(|ch| ch.is_control())
    {
        return None;
    }
    Some(value.to_string())
}

/// Validate `Content-Range: bytes start-end/total` for a resume request.
#[must_use]
pub fn valid_content_range(
    value: &str,
    expected_start: u64,
    expected_total: Option<u64>,
) -> bool {
    let Some(rest) = value.strip_prefix("bytes ") else {
        return false;
    };
    let Some((range, total)) = rest.split_once('/') else {
        return false;
    };
    let Some((start, end)) = range.split_once('-') else {
        return false;
    };
    let (Ok(start), Ok(end)) = (start.parse::<u64>(), end.parse::<u64>()) else {
        return false;
    };
    if start != expected_start || end < start {
        return false;
    }
    match (total, expected_total) {
        ("*", None) => true,
        ("*", Some(_)) => false,
        (value, expected) => value
            .parse::<u64>()
            .ok()
            .is_some_and(|actual| expected.is_none_or(|wanted| actual == wanted) && end < actual),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use hyper::header::HeaderValue;

    #[test]
    fn child_timeouts_never_exceed_recovery_budget() {
        let budget = RecoveryBudget::new(Duration::from_millis(50));
        assert!(budget.child_timeout(Duration::from_secs(10)) <= Duration::from_millis(50));
    }

    #[test]
    fn negative_cache_is_scoped_and_counted() {
        let key = NegativeProbeKey {
            package: "acme/widget".into(),
            immutable_ref: "v1.2.3".into(),
            source: TransportSourceKind::GithubRelease,
            auth: AuthMode::Anonymous,
        };
        let mut cache = NegativeProbeCache::default();
        assert!(!cache.contains(&key));
        cache.insert(key.clone());
        assert!(cache.contains(&key));
        assert_eq!(cache.counters(), (1, 1));
    }

    #[test]
    fn parses_bounded_rate_limit_metadata() {
        let mut headers = HeaderMap::new();
        headers.insert("x-ratelimit-remaining", HeaderValue::from_static("0"));
        headers.insert("x-ratelimit-reset", HeaderValue::from_static("1770000000"));
        headers.insert("x-ratelimit-resource", HeaderValue::from_static("core"));
        headers.insert(RETRY_AFTER, HeaderValue::from_static("7"));
        let info = RateLimitInfo::from_headers(403, &headers);
        assert!(info.limited);
        assert_eq!(info.retry_after, Some(Duration::from_secs(7)));
        assert_eq!(info.resource.as_deref(), Some("core"));
    }

    #[test]
    fn classifies_non_public_destinations() {
        assert_eq!(classify_ip("127.0.0.1".parse().unwrap()), DestinationClass::Loopback);
        assert_eq!(classify_ip("10.1.2.3".parse().unwrap()), DestinationClass::Private);
        assert_eq!(classify_ip("169.254.1.2".parse().unwrap()), DestinationClass::LinkLocal);
        assert_eq!(classify_ip("100.64.1.2".parse().unwrap()), DestinationClass::CarrierGradeNat);
        assert_eq!(classify_ip("::1".parse().unwrap()), DestinationClass::Loopback);
        assert_eq!(classify_ip("fd00::1".parse().unwrap()), DestinationClass::Private);
        assert_eq!(classify_ip("2606:4700:4700::1111".parse().unwrap()), DestinationClass::Public);
    }

    #[test]
    fn redirects_refuse_downgrade_and_cross_origin_credentials() {
        let from = Url::parse("https://api.github.com/repos/acme/widget").unwrap();
        let allowed = Url::parse("https://codeload.github.com/acme/widget/tar.gz/v1").unwrap();
        assert_eq!(
            validate_redirect(&from, &allowed, &["api.github.com", "codeload.github.com"]),
            Ok(RedirectDecision::CrossOrigin)
        );
        assert!(!forward_sensitive_headers(&from, &allowed));

        let downgrade = Url::parse("http://codeload.github.com/acme/widget").unwrap();
        assert!(validate_redirect(&from, &downgrade, &["codeload.github.com"]).is_err());
    }

    #[test]
    fn resume_requires_strong_etag_and_exact_content_range() {
        let mut headers = HeaderMap::new();
        headers.insert(ETAG, HeaderValue::from_static("\"immutable-object\""));
        assert_eq!(strong_etag(&headers).as_deref(), Some("\"immutable-object\""));
        headers.insert(ETAG, HeaderValue::from_static("W/\"weak\""));
        assert!(strong_etag(&headers).is_none());

        assert!(valid_content_range("bytes 100-199/500", 100, Some(500)));
        assert!(!valid_content_range("bytes 0-99/500", 100, Some(500)));
        assert!(!valid_content_range("bytes 100-599/500", 100, Some(500)));
    }
}
