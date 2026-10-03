# Zed local Claritas metric views (DEN-2308)

Import `createZedMetricViews` from `@zed-pkg/client/claritas`. Supply the composed
Claritas library and SDK: `createLocalVisualizationClient(createVisualizationSdk())`.
The adapter calls upstream `cohortTrends`, `individualTrend` and `trendSvg`.
It does not copy chart logic, collect telemetry, add API routes or require a
Claritas server. The existing resolver remains authoritative for exact package
versions, dependency edges and cycle witnesses; network-renderer work is preserved.

Inputs are local projections, not a new wire protocol: packageVersionId,
ecosystem, metric, unit, at and value. One metric/unit per call is required.
Supported measurement labels are install_duration_ms (ms), cache_hit_ratio
(ratio) and download_bytes (bytes). These define adapter inputs, not claims of
existing collector coverage. Only entityId/cohortId/at/value reach Claritas;
source metadata is discarded. Invalid data and SDK errors propagate; there is
no synthetic fallback. Averages are entity-balanced means, not summed downloads,
pooled ratios/percentiles or duration-weighted measurements.

Pin public-core source `b0082e5ee2598c54a013f217cff8bac7e0ce5765` (PR #3) and
Claritas clients `3eec600c294b56b3b121c6b41802d6802a67b733` (PR #8), then build
and resolve their packages through the approved Zed/artifact path. These are
reviewable source candidates, not evidence of registry publication. No mutable
CDN or implicit registry dependency is introduced here.

After the native build, `node --test test/claritas.test.mjs` runs six focused
unit tests. With CLARITAS_CORE_MODULE and CLARITAS_CLIENT_MODULE set to absolute
built entry-point paths, `node --test integration/claritas.integration.mjs`
runs two real cross-repository tests. Missing artifacts fail, never skip or fetch.

Remaining: full pinned Nix/native/package CI, upstream review, approved artifact
resolution, real data-source/UI wiring, Rust/Dart parity and deployment evidence.
The host retains tenant membership, individual/aggregate/export permissions and
anti-differencing policy. Do not interpret frontend suppression as authorization
or infer real-world groups from projection clustering. This adapter is not a
completed production dashboard or a new graph authority.
