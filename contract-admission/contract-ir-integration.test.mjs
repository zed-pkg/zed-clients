import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { cp, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { promisify } from 'node:util';
import test from 'node:test';
import { canonicalStringify, sha256Json, VALIDATOR_REVISION, verifyContractIrAdmission } from './contract-ir-admission.mjs';

const exec = promisify(execFile);
const root = resolve(import.meta.dirname, '..');
const validator = resolve(root, '.deps/typespec-json-schema-validator');
const cli = resolve(validator, 'bin/typespec-json-schema-validator.mjs');
const readJson = async (path) => JSON.parse(await readFile(path, 'utf8'));

// Absence of the pinned compiler is a failure, never a skipped/green suite.
test('compiler-backed Contract IR consumer against the pinned validator', async (t) => {
  const revision = (await exec('git', ['-C', validator, 'rev-parse', 'HEAD'])).stdout.trim();
  assert.equal(revision, VALIDATOR_REVISION, 'unexpected validator checkout');
  const { canonicalStringify: upstreamCanonical } = await import('../.deps/typespec-json-schema-validator/src/canonical.mjs');
  const workspace = await mkdtemp(join(validator, '.zed-admission-test-'));
  t.after(() => rm(workspace, { recursive: true, force: true }));
  const sources = join(workspace, 'sources');
  await cp(resolve(import.meta.dirname, 'fixtures/package-ref'), sources, { recursive: true });
  const inputPaths = {
    typespec: join(sources, 'main.tsp'), authoredSchema: join(sources, 'authored.schema.json'),
    generatedSchema: join(workspace, 'witness'),
  };
  const reportPath = join(workspace, 'report.json');
  const irPath = join(workspace, 'contract-ir.json');
  const args = ['check', `--typespec=${inputPaths.typespec}`, `--schema=${inputPaths.authoredSchema}`,
    `--output-dir=${inputPaths.generatedSchema}`, `--report=${reportPath}`, `--contract-ir=${irPath}`, '--quiet'];
  await exec(process.execPath, [cli, ...args], { cwd: validator, timeout: 120000, maxBuffer: 4 * 1024 * 1024 });
  const evidence = { contractIr: await readJson(irPath), parityReport: await readJson(reportPath),
    inputPaths, requiredDeclarations: ['Zed.Admission.PackageRef'] };

  await t.test('admits an independently authored Zed fixture after real compilation', async () => {
    const admitted = await verifyContractIrAdmission(evidence);
    assert.equal(admitted.admitted, true);
    assert.equal(admitted.irId, evidence.contractIr.irId);
    assert.ok(Object.isFrozen(admitted));
  });
  await t.test('canonicalization agrees with upstream on literal arrays and own keys', () => {
    const value = JSON.parse('{"__proto__":{"enum":[2,1,1]},"default":{"required":["z","a"]}}');
    assert.equal(canonicalStringify(value), upstreamCanonical(value));
    assert.equal(canonicalStringify(evidence.contractIr), upstreamCanonical(evidence.contractIr));
  });
  await t.test('captures inputs before an asynchronous caller can mutate them', async () => {
    const mutable = structuredClone(evidence);
    const pending = verifyContractIrAdmission(mutable);
    mutable.inputPaths.typespec = '/not-the-admitted-source';
    mutable.contractIr.status = 'failed';
    assert.equal((await pending).admitted, true);
  });
  for (const key of ['typespec', 'authoredSchema', 'generatedSchema']) {
    await t.test(`rejects stale ${key} checkout despite unchanged copied receipt hashes`, async () => {
      let path = inputPaths[key];
      if (key === 'generatedSchema') {
        const jsonFiles = (await readdir(path, { recursive: true })).filter((name) => name.endsWith('.json'));
        assert.ok(jsonFiles.length > 0, 'compiler produced no schema witness');
        path = join(path, jsonFiles[0]);
      }
      const original = await readFile(path, 'utf8');
      try {
        await writeFile(path, `${original}\n${key === 'typespec' ? '// changed checkout' : ' '}`);
        await assert.rejects(verifyContractIrAdmission(evidence), /current-checkout verification failed/);
      } finally { await writeFile(path, original); }
    });
  }
  await t.test('rejects a changed assertion even when all supplied IR digests are rehashed', async () => {
    const changed = structuredClone(evidence);
    changed.contractIr.declarations[0].assertionSchema = { type: 'null' };
    changed.contractIr.declarations[0].assertionDigest = sha256Json({ type: 'null' });
    const { irId, ...body } = changed.contractIr;
    changed.contractIr.irId = sha256Json(body);
    await assert.rejects(verifyContractIrAdmission(changed), /current-checkout verification failed/);
  });
  await t.test('missing checked-out inputs cannot fall back to paths in the report', async () => {
    await assert.rejects(verifyContractIrAdmission({ ...evidence,
      inputPaths: { ...inputPaths, typespec: join(workspace, 'absent.tsp') } }), /current-checkout verification failed/);
  });
  await t.test('stopped compiler run tombstones the formerly passing IR', async () => {
    const original = await readFile(inputPaths.authoredSchema, 'utf8');
    const changed = JSON.parse(original);
    changed.$defs.PackageRef.properties.name.type = 'integer';
    await writeFile(inputPaths.authoredSchema, JSON.stringify(changed));
    await assert.rejects(exec(process.execPath, [cli, ...args], { cwd: validator, timeout: 120000 }),
      (error) => error.code === 2);
    const stopped = { ...evidence, contractIr: await readJson(irPath), parityReport: await readJson(reportPath) };
    assert.equal(stopped.contractIr.admissible, false);
    await assert.rejects(verifyContractIrAdmission(stopped), /passed and admissible/);
  });
});
