import { createHash } from 'node:crypto';
import { isAbsolute } from 'node:path';

export const CONTRACT_IR_SCHEMA = 'ores.typespec-json-schema-validator.contract-ir/v1';
export const PARITY_REPORT_SCHEMA = 'ores.typespec-json-schema-validator.report/v1';
export const VALIDATOR_REVISION = 'd60d0d79d83e075077382623ec9e23a401ab601f';
const HEX = /^[a-f0-9]{64}$/u;
const LANES = ['typespec', 'authoredJsonSchema', 'generatedJsonSchema'];
const COVERAGE = ['directDeclarationInventory', 'typespecGeneratedJsonSchemaComparison', 'differentialInstanceValidation'];
const REQUIREMENTS = ['exactInputDigests', 'directDeclarationInventory', 'generatedSchemaComparison', 'differentialInstanceValidation', 'zeroUnexplainedFindings'];
const VALIDATOR_URL = new URL('../.deps/typespec-json-schema-validator/src/contract-ir.mjs', import.meta.url);
const obj = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

function need(condition, message) {
  if (!condition) throw new Error(`contract-ir admission rejected: ${message}`);
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (!obj(value)) return value;
  return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
}
export const canonicalStringify = (value) => JSON.stringify(canonicalize(value));
export const sha256Json = (value) => createHash('sha256').update(canonicalStringify(value)).digest('hex');

function digest(value, label) {
  need(typeof value === 'string' && HEX.test(value), `${label} must be a lowercase SHA-256 digest`);
  return value;
}

function identities(values, label, nonempty = false) {
  need(Array.isArray(values) && (!nonempty || values.length > 0), `${label} must be ${nonempty ? 'a nonempty' : 'an'} array`);
  need(values.every((value) => typeof value === 'string' && value.trim() === value && value.length > 0), `${label} contains an invalid identity`);
  need(new Set(values).size === values.length, `${label} contains duplicate identities`);
  return new Set(values);
}

export function verifyContractIrEnvelope({
  contractIr, parityReport, requiredDeclarations, forbiddenDeclarations = [], requireComplete = true,
}) {
  need(obj(contractIr), 'contractIr must be an object');
  need(obj(parityReport), 'parityReport must be an object');
  need(typeof requireComplete === 'boolean', 'requireComplete must be a boolean');
  const required = identities(requiredDeclarations, 'requiredDeclarations', true);
  const forbidden = identities(forbiddenDeclarations, 'forbiddenDeclarations');
  need(contractIr.schema === CONTRACT_IR_SCHEMA, 'unexpected Contract IR schema');
  need(contractIr.status === 'passed' && contractIr.admissible === true, 'Contract IR must be passed and admissible');
  need(contractIr.role === 'downstream-derived-parity-artifact' && contractIr.editableAuthority === false, 'Contract IR must be a downstream non-editable artifact');
  need(contractIr.authorities?.typespec === 'independently-authored', 'TypeSpec must remain independently authored');
  need(contractIr.authorities?.jsonSchema === 'independently-authored', 'JSON Schema must remain independently authored');
  need(contractIr.authorities?.generatedJsonSchema === 'comparison-evidence-only', 'generated JSON Schema must remain comparison evidence only');
  need(contractIr.authorities?.precedence === 'none', 'peer authorities must have no precedence');
  need(parityReport.schema === PARITY_REPORT_SCHEMA, 'unexpected parity report schema');
  need(parityReport.status === 'passed' && parityReport.zeroUnexplainedFindings === true, 'parity report must have passed with zero unexplained findings');
  need(Array.isArray(parityReport.findings) && parityReport.findings.length === 0, 'parity report findings must be empty');
  digest(parityReport.runId, 'parityReport.runId');
  for (const field of COVERAGE) {
    need(parityReport.coverage?.[field] === true && contractIr.coverage?.[field] === true, `${field} evidence is missing or disabled`);
  }
  need(parityReport.differential?.disabled !== true, 'differential evidence is disabled');
  for (const field of REQUIREMENTS) need(contractIr.admission?.requirements?.[field] === true, `admission requirement ${field} is missing`);
  const receipt = contractIr.admission?.receipt;
  need(obj(receipt), 'Contract IR receipt is missing');
  need(receipt.schema === parityReport.schema && receipt.runId === parityReport.runId, 'receipt identity does not match parity report');
  need(receipt.status === 'passed' && receipt.zeroUnexplainedFindings === true, 'receipt must bind a passed report with zero unexplained findings');
  need(receipt.digest === sha256Json(parityReport), 'receipt digest does not match the supplied parity report');
  const { irId, ...body } = contractIr;
  need(digest(irId, 'contractIr.irId') === sha256Json(body), 'Contract IR self digest does not match its body');
  for (const lane of LANES) {
    need(digest(parityReport.inputs?.[lane]?.digest, `parityReport.inputs.${lane}.digest`) ===
      digest(contractIr.provenance?.[lane]?.digest, `contractIr.provenance.${lane}.digest`), `${lane} input binding is invalid`);
  }
  need(Array.isArray(contractIr.declarations), 'Contract IR declarations are missing');
  need(contractIr.declarations.every(obj), 'Contract IR declaration must be an object');
  const admitted = identities(contractIr.declarations.map((item) => item.id), 'declaration ids', true);
  need(Array.isArray(parityReport.declarationMap) && parityReport.declarationMap.every(obj), 'receipt declarationMap is missing');
  const mapped = identities(parityReport.declarationMap.map((item) => item.typespec), 'mapped TypeSpec identities', true);
  identities(parityReport.declarationMap.map((item) => item.generated), 'mapped generated identities', true);
  identities(parityReport.declarationMap.map((item) => item.authored), 'mapped authored identities', true);
  need(admitted.size === mapped.size && [...admitted].every((id) => mapped.has(id)), 'declarations do not match the receipt inventory');
  for (const id of required) need(admitted.has(id), `required declaration is absent: ${id}`);
  for (const id of forbidden) need(!admitted.has(id), `forbidden declaration is exported: ${id}`);
  need(Array.isArray(contractIr.excludedDeclarations) && Array.isArray(contractIr.outOfScopeDeclarations), 'scope inventories are missing');
  const scope = contractIr.admission?.scope;
  need(scope?.admittedDeclarations === admitted.size &&
    scope.excludedDeclarations === contractIr.excludedDeclarations.length &&
    scope.outOfScopeDeclarations === contractIr.outOfScopeDeclarations.length, 'scope counts disagree with inventories');
  const complete = contractIr.excludedDeclarations.length === 0 && contractIr.outOfScopeDeclarations.length === 0;
  need(scope.complete === complete, 'scope completeness disagrees with inventories');
  need(!requireComplete || complete, 'consumer requires a complete Contract IR scope');
  for (const declaration of contractIr.declarations) {
    need(Object.hasOwn(declaration, 'assertionSchema'), `declaration ${declaration.id} has no assertion schema`);
    need(digest(declaration.assertionDigest, 'assertionDigest') === sha256Json(declaration.assertionSchema), `declaration ${declaration.id} assertion digest is invalid`);
    for (const [lane, role] of [['typespecGeneratedJsonSchema', 'comparison-evidence-only'], ['authoredJsonSchema', 'independently-authored-authority']]) {
      const evidence = declaration.lanes?.[lane];
      need(evidence?.role === role, `declaration ${declaration.id} ${lane} role is invalid`);
      need(Object.hasOwn(evidence, 'normalizedSchema'), `declaration ${declaration.id} ${lane} schema is missing`);
      need(digest(evidence.schemaDigest, `${lane}.schemaDigest`) === sha256Json(evidence.normalizedSchema), `declaration ${declaration.id} ${lane} digest is invalid`);
    }
  }
  return Object.freeze({ envelopeVerified: true, irId, runId: parityReport.runId });
}

export async function verifyContractIrAdmission(options) {
  need(obj(options), 'options must be an object');
  need(obj(options.inputPaths), 'explicit inputPaths are required');
  const inputPaths = {};
  for (const name of ['typespec', 'generatedSchema', 'authoredSchema']) {
    const path = options.inputPaths[name];
    need(typeof path === 'string' && isAbsolute(path), `inputPaths.${name} must be an explicit absolute path`);
    inputPaths[name] = path;
  }
  const evidence = JSON.parse(canonicalStringify({
    contractIr: options.contractIr, parityReport: options.parityReport,
    requiredDeclarations: options.requiredDeclarations,
    forbiddenDeclarations: options.forbiddenDeclarations ?? [],
    requireComplete: options.requireComplete ?? true,
  }));
  const envelope = verifyContractIrEnvelope(evidence);
  const { verifyContractIr } = await import(VALIDATOR_URL.href);
  const verification = await verifyContractIr({ contractIr: evidence.contractIr, report: evidence.parityReport, ...inputPaths });
  need(verification.schema === 'ores.typespec-json-schema-validator.contract-ir-verification/v1' &&
    verification.status === 'passed' && verification.admissible === true &&
    verification.suppliedIrId === envelope.irId && verification.computedIrId === envelope.irId &&
    verification.expectedIrId === envelope.irId && verification.receiptRunId === envelope.runId,
  `current-checkout verification failed: ${verification.error ?? 'evidence mismatch'}`);
  return Object.freeze({ admitted: true, irId: envelope.irId, runId: envelope.runId, validatorRevision: VALIDATOR_REVISION });
}
