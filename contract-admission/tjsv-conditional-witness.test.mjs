import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { resolve } from 'node:path';
import { promisify } from 'node:util';
import test from 'node:test';
import { VALIDATOR_REVISION } from './contract-ir-admission.mjs';

const exec = promisify(execFile);
const root = resolve(import.meta.dirname, '..');
const validator = resolve(root, '.deps/typespec-json-schema-validator');

test('pinned TJSV keeps conditional allOf witnesses constructible and probeable', async () => {
  const revision = (await exec('git', ['-C', validator, 'rev-parse', 'HEAD'])).stdout.trim();
  assert.equal(revision, VALIDATOR_REVISION, 'conditional-witness test must run against the admitted validator revision');

  const [{ SchemaResolver, validateInstance }, { buildProbes, synthesizeInstance }] = await Promise.all([
    import('../.deps/typespec-json-schema-validator/src/instance-validator.mjs'),
    import('../.deps/typespec-json-schema-validator/src/witness.mjs'),
  ]);

  const schema = {
    allOf: [
      {
        if: { properties: { opcode: { const: 'report' } }, required: ['opcode'] },
        then: { properties: { effects: { contains: { const: 'emit' } } } },
      },
      {
        type: 'object',
        properties: {
          opcode: { type: 'string', enum: ['report', 'other'] },
          effects: {
            type: 'array',
            items: { type: 'string', enum: ['emit', 'other'] },
            minItems: 1,
          },
        },
        required: ['opcode', 'effects'],
      },
    ],
  };

  const resolver = new SchemaResolver();
  const record = resolver.addDocument(schema, 'zed-conditional-consumer.json');
  const synthesized = synthesizeInstance({ schema, base: record.base, resolver });

  assert.ok(synthesized.instance && typeof synthesized.instance === 'object' && !Array.isArray(synthesized.instance));
  assert.deepEqual(synthesized.instance.effects, ['emit']);
  const validated = validateInstance({ schema, instance: synthesized.instance, resolver, base: record.base });
  assert.equal(validated.valid, true, JSON.stringify(validated.errors));

  const probes = buildProbes({
    schema,
    base: record.base,
    resolver,
    lane: 'authored',
    declaration: 'Zed.Admission.ConditionalFunctionBody',
    maxProbes: 64,
  });
  assert.ok(probes.length > 0, 'differential probe corpus must not be empty');
  assert.ok(
    probes.some((probe) => probe.origin === 'domain-member' && probe.pointer === '/effects/0'),
    'nested enum domain-member probe must survive conditional allOf synthesis',
  );
});

test('sibling object shape remains the final overlay beside non-constructive conditionals', async () => {
  const { SchemaResolver, validateInstance } = await import('../.deps/typespec-json-schema-validator/src/instance-validator.mjs');
  const { buildProbes, synthesizeInstance } = await import('../.deps/typespec-json-schema-validator/src/witness.mjs');
  const schema = {
    type: 'object',
    properties: {
      opcode: { type: 'string', const: 'other' },
      effects: { type: 'array', items: { type: 'string', enum: ['emit', 'other'] }, minItems: 1 },
    },
    required: ['opcode', 'effects'],
    allOf: [
      {
        if: { properties: { opcode: { const: 'report' } }, required: ['opcode'] },
        then: { properties: { effects: { contains: { const: 'emit' } } } },
      },
    ],
  };
  const resolver = new SchemaResolver();
  const record = resolver.addDocument(schema, 'zed-conditional-sibling.json');
  const synthesized = synthesizeInstance({ schema, base: record.base, resolver });
  assert.equal(synthesized.instance.opcode, 'other');
  assert.deepEqual(synthesized.instance.effects, ['emit']);
  assert.equal(validateInstance({ schema, instance: synthesized.instance, resolver, base: record.base }).valid, true);
  assert.doesNotThrow(() => buildProbes({ schema, base: record.base, resolver, lane: 'authored', declaration: 'Zed.Admission.SiblingConditional', maxProbes: 64 }));
});
