# Contract IR admission for Zed build tooling

Tracks ORESoftware/typespec-json-schema-validator#20 and DEN-3828; related SDK
rollout: DEN-3600. TypeSpec and authored JSON Schema remain independent peers.
The generated witness and Contract IR are downstream evidence, not authorities.

`verifyContractIrAdmission` is **asynchronous**. Await it before generating or
promoting a downstream artifact. It reuses the upstream `verifyContractIr`
implementation rather than replacing its inventory/resource-graph semantics.
Supply absolute paths from trusted build configuration, not from the receipt:

```js
const evidence = await verifyContractIrAdmission({
  contractIr,
  parityReport,
  inputPaths: { typespec, generatedSchema, authoredSchema },
  requiredDeclarations: ['Zed.Admission.PackageRef'],
  forbiddenDeclarations: ['Zed.Validation.RegistryPackageRow'],
  requireComplete: true,
});
// Only now generate; bind evidence.irId and evidence.runId into the output.
```

Names are exact qualified TypeSpec identities. The example is a test fixture,
not a claim that Zed's complete registry/API contract has passed this gate.
Complete scope is required by default. A reviewed partial-scope consumer must
explicitly opt out and still name every required declaration. For browser/edge
bundles, enumerate all forbidden server identities in trusted build policy.

Provision `.deps/typespec-json-schema-validator` at immutable commit
`22d66b53d2cb5b99f78bbd16c2f235e3defde0f3`, then install its locked dependencies
with `npm ci --ignore-scripts`. The workflow and integration suite assert this
pin. This is repository/build-time tooling, not a new runtime SDK dependency.
Missing checkout/compiler/input files are errors; tests never skip them.

`verifyContractIrEnvelope` is a pure preflight and intentionally returns only
`envelopeVerified`, never `admitted`. It does not read files or prove that a
compiler ran. Hashes prove binding, not publisher authenticity: retain trusted
CI provenance and isolate generation from concurrent input mutation. An
admission result is valid only for the checked revision, not an indefinite
capability. Production operation/projection manifests, signed provenance,
15-language compilation and sibling-test certification remain separate gates.

The canonical hash preserves array order/multiplicity and own `__proto__` keys;
it is not schema normalization. Tests independently check known bytes and
compare with the pinned upstream implementation.

```sh
node --test contract-admission/contract-ir-admission.test.mjs
node --test contract-admission/contract-ir-integration.test.mjs
```

The integration suite compiles independently authored fixtures, consumes real
receipt/IR output, changes each checked input lane, tests rehashed tampering,
and verifies stopped-run tombstones. It creates only disposable fixture copies;
production authored schemas and generated SDK files are not modified. These
focused checks do not replace the repository's Nix/native/browser merge gates.
