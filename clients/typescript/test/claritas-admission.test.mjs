import test from 'node:test';
import assert from 'node:assert/strict';
import { createZedMetricViews } from '../dist/claritas.js';
const sample = (id = 'pkg@1', value = 1) => ({ packageVersionId: id, ecosystem: 'npm', metric: 'install_duration_ms', unit: 'ms', at: 0, value });
const window = { start: 0, end: 20, bucketMs: 10, minEntities: 2 };
function port() {
  let calls = 0;
  return {
    get calls() { return calls; },
    cohortTrends: (rows, window) => { calls++; return [{ rows, window }]; },
    individualTrend: (rows, id, window) => { calls++; return { rows, id, window }; },
    trendSvg: () => '<svg/>',
  };
}
for (const [field, value] of [
  ['packageVersionId', ''], ['packageVersionId', 'x'.repeat(161)],
  ['packageVersionId', '\ud800'], ['packageVersionId', 'hidden\u202e'],
  ['packageVersionId', 'line\n'], ['packageVersionId', 1], ['ecosystem', null],
  ['ecosystem', ''], ['ecosystem', '\u2066hidden'], ['at', NaN], ['at', Infinity],
  ['at', '0'], ['at', 0.5], ['at', 1e15 + 1],
]) {
  test(`reject invalid ${field} (${typeof value}) before calling Claritas`, () => {
    const core = port(); const views = createZedMetricViews(core);
    assert.throws(() => views.cohorts([{ ...sample(), [field]: value }], 'install_duration_ms', window), { message: 'Invalid metric projection' });
    assert.equal(core.calls, 0);
  });
}
for (const patch of [
  { start: NaN }, { start: 0.5 }, { end: 0 }, { end: '20' }, { end: Infinity },
  { bucketMs: 0 }, { bucketMs: -1 }, { bucketMs: 0.5 },
  { end: 1001, bucketMs: 1 }, { minEntities: 0 }, { minEntities: 1.5 }, { minEntities: 10001 },
]) {
  test(`reject invalid window ${JSON.stringify(patch)} before calling Claritas`, () => {
    const core = port(); const views = createZedMetricViews(core);
    assert.throws(() => views.cohorts([], 'install_duration_ms', { ...window, ...patch }), { message: 'Invalid metric projection' });
    assert.equal(core.calls, 0);
  });
}
test('null, array, and malformed window objects fail closed', () => {
  const core = port(); const views = createZedMetricViews(core);
  for (const value of [null, undefined, [], {}]) {
    assert.throws(() => views.cohorts([], 'install_duration_ms', value), { message: 'Invalid metric projection' });
    assert.throws(() => views.individual([], 'install_duration_ms', 'pkg@1', value), { message: 'Invalid metric projection' });
  }
  assert.equal(core.calls, 0);
});
test('sparse rows and sparse row fields are rejected before SDK invocation', () => {
  const core = port(); const views = createZedMetricViews(core);
  assert.throws(() => views.cohorts(new Array(1), 'install_duration_ms', window), TypeError);
  assert.throws(() => views.cohorts([{}], 'install_duration_ms', window), TypeError);
  assert.equal(core.calls, 0);
});
test('only admitted window keys cross the SDK boundary, with no caller alias', () => {
  const input = { ...window, token: 'private', get extra() { throw Error('must not read'); } };
  const result = createZedMetricViews(port()).cohorts([sample()], 'install_duration_ms', input)[0].series;
  assert.deepEqual(result.window, window); assert.notStrictEqual(result.window, input);
  assert.ok(Object.isFrozen(result.window));
  assert.ok(!('token' in result.window)); assert.ok(!('extra' in result.window));
  const individual = createZedMetricViews(port()).individual([sample()], 'install_duration_ms', 'pkg@1', input).series;
  assert.deepEqual(individual.window, { start: 0, end: 20, bucketMs: 10 });
  assert.ok(Object.isFrozen(individual.window));
});
test('individual ID is validated even for an empty dataset', () => {
  const core = port(); const views = createZedMetricViews(core);
  for (const id of [null, '', 'bad\n', 'x'.repeat(161), '\ud800']) {
    assert.throws(() => views.individual([], 'install_duration_ms', id, window), { message: 'Invalid metric projection' });
  }
  assert.equal(core.calls, 0);
});
test('metric coercion and source accessors cannot leak their thrown values', () => {
  const core = port(); const views = createZedMetricViews(core);
  let coerced = false;
  const metric = { toString() { coerced = true; throw Error('private'); } };
  assert.throws(() => views.cohorts([], metric, window), { message: 'Invalid metric projection' });
  assert.equal(coerced, false);
  assert.throws(() => views.cohorts([{ ...sample(), get at() { throw Error('private'); } }], 'install_duration_ms', window), { message: 'Invalid metric projection' });
  assert.throws(() => views.cohorts([], 'install_duration_ms', { ...window, get start() { throw Error('private'); } }), { message: 'Invalid metric projection' });
  assert.equal(core.calls, 0);
});
test('valid boundary values, Unicode identities, nulls, and zero are preserved', () => {
  const core = port(); const views = createZedMetricViews(core);
  const input = Object.freeze([Object.freeze({ ...sample('pkg-😀@1', 0), at: -1e15 }), Object.freeze(sample('pkg@2', null))]);
  const result = views.cohorts(input, 'install_duration_ms', { start: -1e15, end: -1e15 + 1000, bucketMs: 1, minEntities: 10000 })[0].series;
  assert.equal(result.rows[0].entityId, 'pkg-😀@1');
  assert.deepEqual(result.rows.map(row => row.value), [0, null]);
  assert.equal(result.window.minEntities, 10000);
});
