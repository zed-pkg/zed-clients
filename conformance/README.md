# Conformance

`zed-clients` is a consumer, not a second contract authority. `contracts/` therefore contains immutable bindings to the exact upstream revisions consumed by the SDK. The checker fails if those bindings drift from the Rust client's immutable dependency revisions.

`conformance/` owns shared client-side behavioral cases/evidence. Coverage starts `scaffold-only`; bootstrap metadata is not behavioral coverage. The generic boundary checker still binds deterministic contract/corpus/spec digests and fails closed on symlinks, path escape, overlap, stale evidence, or unsafe authority policy.

`node conformance/check.mjs` is the lifecycle entrypoint used by Zed install/build/test/pack/publish and Git hook admission.
