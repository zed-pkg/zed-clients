# Claritas consumer admission (DEN-2308)

`createZedMetricViews` calls the real caller-selected Claritas library/SDK.
The adapter now validates bounded package-version and ecosystem identifiers,
safe-integer timestamps, paired metric/unit/value constraints, and bounded time
windows before invoking that SDK. Sparse arrays fail closed. Window snapshots
contain only start/end/bucketMs and, for cohorts, minEntities. Arbitrary source
or window metadata never travels through this projection. Individual windows
do not carry a cohort threshold. Input accessors that throw are replaced with a
bounded generic admission error; upstream SDK errors still propagate unchanged.

Compatibility: canonical identities, metric units, zero/null semantics, window
values and SVG algorithms are unchanged. Window reference identity is intentionally
not preserved: the SDK receives a frozen whitelist snapshot rather than caller-owned
configuration. Bidirectional text controls are rejected to prevent misleading
package labels. No wire models, resolver edges, cycle witnesses, dependency locks,
publication versions or generated runtime clients are changed.

## Executed September 8, 2026

Strict TypeScript 5.8.3 compilation and 42 Node 22.16.0 tests passed: 32 new
admission cases, the six existing adapter tests, and four real cross-repository
integration cases. Before the fix, 31 of the 32 new admission cases failed.
The real calls use these source candidates, reconstructed with verified source
blobs and built locally:

- claritas-viz/claritas-pub-lib-core: 71f0655842d4f1dcc889ac8f0705be9afa19cf23
- claritas-viz/claritas-clients: b246fac56e741dfdeb9be644e5fca048eb55b02e

The core includes merged PR #5 numerical hardening plus both portable and cohort
APIs. The integration checks actual entity-balanced means, zero/missing/suppressed
states, whitelisted arguments, local SVG rendering with fetch forbidden, and the
large-sample cancellation regressions. It does not substitute test doubles for
the core calculations.

After approved builds, set CLARITAS_CORE_MODULE and CLARITAS_CLIENT_MODULE to
absolute local built entry-point paths and run:

    node --test test/claritas*.test.mjs integration/claritas-boundary.integration.mjs

Missing/non-absolute paths fail; no package is implicitly fetched. These environment
paths select trusted local executable artifacts, not a cryptographic admission
mechanism. Approved source/package provenance and the resolver-owned frozen Zed
lock remain release gates; source pins are not evidence of registry publication.
The original two-case integration file remains intact and was not included in
this 42-test count.

## Still required

Full pinned Nix/native/package CI and review; upstream release/admission; Rust/Dart
consumer parity; collector and production UI wiring. Host tenant membership,
consent, individual/aggregate/export permissions and anti-differencing rules remain
mandatory. This projection is not authorization, anonymization, or completed
dependency-graph rendering; existing graph PRs and resolver authority are preserved.
