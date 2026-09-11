import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { canonicalStringify, sha256Json, verifyContractIrEnvelope, verifyContractIrAdmission } from './contract-ir-admission.mjs';

const h = (char) => char.repeat(64);
function reseal(value) {
  value.contractIr.admission.receipt.digest = sha256Json(value.parityReport);
  const { irId, ...body } = value.contractIr;
  value.contractIr.irId = sha256Json(body);
  return value;
}
function fixture() {
  const coverage = { directDeclarationInventory: true, typespecGeneratedJsonSchemaComparison: true, differentialInstanceValidation: true };
  const inputs = Object.fromEntries(['typespec', 'authoredJsonSchema', 'generatedJsonSchema'].map((key, i) => [key, { digest: h('abc'[i]), files: [] }]));
  const parityReport = {
    schema: 'ores.typespec-json-schema-validator.report/v1', runId: h('d'), status: 'passed', zeroUnexplainedFindings: true,
    findings: [], inputs, coverage, declarationMap: [{ typespec: 'Zed.PackageRef', generated: 'PackageRef', authored: 'PackageRef' }],
  };
  const assertionSchema = { type: 'object', properties: { name: { type: 'string' } }, required: ['name'] };
  const lane = (role) => ({ role, normalizedSchema: assertionSchema, schemaDigest: sha256Json(assertionSchema) });
  return reseal({
    requiredDeclarations: ['Zed.PackageRef'],
    contractIr: {
      schema: 'ores.typespec-json-schema-validator.contract-ir/v1', status: 'passed', admissible: true,
      role: 'downstream-derived-parity-artifact', editableAuthority: false,
      authorities: { typespec: 'independently-authored', jsonSchema: 'independently-authored', generatedJsonSchema: 'comparison-evidence-only', precedence: 'none' },
      admission: {
        receipt: { schema: parityReport.schema, runId: parityReport.runId, status: 'passed', zeroUnexplainedFindings: true },
        requirements: { exactInputDigests: true, directDeclarationInventory: true, generatedSchemaComparison: true, differentialInstanceValidation: true, zeroUnexplainedFindings: true },
        scope: { admittedDeclarations: 1, excludedDeclarations: 0, outOfScopeDeclarations: 0, complete: true },
      },
      provenance: structuredClone(inputs), coverage: structuredClone(coverage), excludedDeclarations: [], outOfScopeDeclarations: [],
      declarations: [{ id: 'Zed.PackageRef', assertionSchema, assertionDigest: sha256Json(assertionSchema), lanes: {
        typespecGeneratedJsonSchema: lane('comparison-evidence-only'), authoredJsonSchema: lane('independently-authored-authority'),
      } }],
    }, parityReport,
  });
}

test('preflight verifies binding, not current-checkout admission', () => {
  const result = verifyContractIrEnvelope(fixture());
  assert.equal(result.envelopeVerified, true);
  assert.equal(Object.hasOwn(result, 'admitted'), false);
  assert.ok(Object.isFrozen(result));
});

test('canonical object keys match an independent known byte string', () => {
  const bytes = '{"a":{"c":3,"d":4},"b":2}';
  assert.equal(canonicalStringify({ b: 2, a: { d: 4, c: 3 } }), bytes);
  assert.equal(sha256Json({ b: 2, a: { d: 4, c: 3 } }), createHash('sha256').update(bytes).digest('hex'));
});
for (const key of ['enum', 'required', 'type', 'allOf', 'anyOf', 'oneOf', 'prefixItems', 'examples']) {
  test(`canonical digest retains literal array order under ${key}`, () => {
    assert.notEqual(sha256Json({ default: { [key]: [1, 2] } }), sha256Json({ default: { [key]: [2, 1] } }));
  });
  test(`canonical digest retains array multiplicity under ${key}`, () => {
    assert.notEqual(sha256Json({ [key]: [1] }), sha256Json({ [key]: [1, 1] }));
  });
}
test('own prototype-looking properties remain digest-bound', () => {
  const value = JSON.parse('{"__proto__":{"polluted":true},"constructor":1,"prototype":2}');
  assert.equal(canonicalStringify(value), '{"__proto__":{"polluted":true},"constructor":1,"prototype":2}');
  assert.notEqual(sha256Json(value), sha256Json({ constructor: 1, prototype: 2 }));
  assert.equal({}.polluted, undefined);
});

const rejects = [
  ['tombstone', (v) => { v.contractIr.admissible = false; }, /passed and admissible/],
  ['unknown IR version', (v) => { v.contractIr.schema += '.unknown'; }, /unexpected Contract IR schema/],
  ['authority promotion', (v) => { v.contractIr.authorities.precedence = 'typespec'; }, /no precedence/],
  ['generated witness promoted to authority', (v) => { v.contractIr.authorities.generatedJsonSchema = 'authority'; }, /comparison evidence only/],
  ['editable IR', (v) => { v.contractIr.editableAuthority = true; }, /non-editable/],
  ['stopped receipt', (v) => { v.parityReport.status = 'stopped_for_evaluation'; }, /passed with zero/],
  ['unexplained findings', (v) => { v.parityReport.findings.push({ rule: 'drift' }); }, /findings must be empty/],
  ['missing direct inventory', (v) => { delete v.parityReport.coverage.directDeclarationInventory; }, /directDeclarationInventory/],
  ['missing generated comparison', (v) => { v.contractIr.coverage.typespecGeneratedJsonSchemaComparison = false; }, /typespecGeneratedJsonSchemaComparison/],
  ['disabled differential coverage', (v) => { v.parityReport.coverage.differentialInstanceValidation = false; }, /differentialInstanceValidation/],
  ['explicitly disabled differential block', (v) => { v.parityReport.differential = { disabled: true }; }, /differential evidence is disabled/],
  ['missing exact-input requirement', (v) => { delete v.contractIr.admission.requirements.exactInputDigests; }, /exactInputDigests/],
  ['receipt run mismatch', (v) => { v.contractIr.admission.receipt.runId = h('e'); }, /receipt identity/],
  ['input binding mismatch', (v) => { v.contractIr.provenance.typespec.digest = h('e'); }, /input binding/],
  ['invalid input hash', (v) => { v.parityReport.inputs.typespec.digest = 'not-a-digest'; }, /lowercase SHA-256/],
  ['missing expected contract', (v) => { v.requiredDeclarations = ['Zed.Missing']; }, /required declaration is absent/],
  ['empty consumer inventory', (v) => { v.requiredDeclarations = []; }, /nonempty/],
  ['duplicate required identities', (v) => { v.requiredDeclarations.push('Zed.PackageRef'); }, /duplicate identities/],
  ['forbidden client export', (v) => { v.forbiddenDeclarations = ['Zed.PackageRef']; }, /forbidden declaration/],
  ['duplicate admitted identities', (v) => { v.contractIr.declarations.push(v.contractIr.declarations[0]); }, /duplicate identities/],
  ['duplicate authored mapping', (v) => { v.parityReport.declarationMap.push({ typespec: 'Zed.Other', generated: 'Other', authored: 'PackageRef' }); }, /mapped authored identities contains duplicate/],
  ['unmapped declaration', (v) => { v.parityReport.declarationMap[0].typespec = 'Zed.Other'; }, /receipt inventory/],
  ['incorrect admitted count', (v) => { v.contractIr.admission.scope.admittedDeclarations = 2; }, /scope counts/],
  ['false completeness claim', (v) => { v.contractIr.excludedDeclarations.push({ id: 'Zed.Other' }); v.contractIr.admission.scope.excludedDeclarations = 1; }, /completeness disagrees/],
  ['incomplete scope by default', (v) => { v.contractIr.excludedDeclarations.push({ id: 'Zed.Other' }); Object.assign(v.contractIr.admission.scope, { excludedDeclarations: 1, complete: false }); }, /requires a complete/],
  ['nonboolean completeness policy', (v) => { v.requireComplete = 'false'; }, /must be a boolean/],
  ['missing assertion', (v) => { delete v.contractIr.declarations[0].assertionSchema; }, /no assertion schema/],
  ['tampered assertion digest', (v) => { v.contractIr.declarations[0].assertionDigest = h('e'); }, /assertion digest/],
  ['tampered normalized lane', (v) => { v.contractIr.declarations[0].lanes.authoredJsonSchema.schemaDigest = h('e'); }, /authoredJsonSchema digest/],
];
for (const [name, change, pattern] of rejects) {
  test(`rejects ${name} even after envelope rehash`, () => {
    const value = fixture(); change(value); reseal(value);
    assert.throws(() => verifyContractIrEnvelope(value), pattern);
  });
}
test('rejects changed receipt without rehash', () => {
  const value = fixture(); value.parityReport.extra = 'changed';
  assert.throws(() => verifyContractIrEnvelope(value), /receipt digest/);
});
test('rejects changed IR without rehash', () => {
  const value = fixture(); value.contractIr.extra = 'changed';
  assert.throws(() => verifyContractIrEnvelope(value), /self digest/);
});
test('explicit partial scope still requires named declarations', () => {
  const value = fixture(); value.requireComplete = false;
  value.contractIr.excludedDeclarations.push({ id: 'Zed.Other' });
  Object.assign(value.contractIr.admission.scope, { excludedDeclarations: 1, complete: false });
  assert.equal(verifyContractIrEnvelope(reseal(value)).envelopeVerified, true);
});
test('no implicit report-controlled input paths', async () => {
  await assert.rejects(verifyContractIrAdmission(fixture()), /explicit inputPaths/);
});
for (const name of ['typespec', 'generatedSchema', 'authoredSchema']) {
  test(`requires explicit absolute ${name} path before loading a verifier`, async () => {
    const inputPaths = { typespec: '/checkout/main.tsp', authoredSchema: '/checkout/authored.json', generatedSchema: '/checkout/generated' };
    inputPaths[name] = '../receipt-controlled';
    await assert.rejects(verifyContractIrAdmission({ ...fixture(), inputPaths }), /explicit absolute path/);
  });
}
