import test from 'node:test';
import assert from 'node:assert/strict';
import { isAbsolute } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createZedMetricViews } from '../dist/claritas.js';

// Deliberately use caller-approved local artifacts, never a network or demo fallback.
const modulePath = name => {
  const path = process.env[name];
  if (!path || !isAbsolute(path)) throw new Error('Absolute pinned Claritas module paths are required');
  return pathToFileURL(path).href;
};
const core = await import(modulePath('CLARITAS_CORE_MODULE'));
const client = await import(modulePath('CLARITAS_CLIENT_MODULE'));
const local = client.createLocalVisualizationClient(core.createVisualizationSdk());
const views = createZedMetricViews(local);
const window = { start: 0, end: 30, bucketMs: 10, minEntities: 2 };
const sample = (id, value, at = 0) => ({ packageVersionId: id, ecosystem: 'npm', metric: 'install_duration_ms', unit: 'ms', at, value });

test('real composed SDK retains entity weighting, zero, gaps and suppression', () => {
  const rows = [sample('a@1', 0), sample('a@1', 0, 1), sample('b@1', 10), sample('a@1', 4, 10)];
  const [result] = views.cohorts(rows, 'install_duration_ms', window);
  assert.deepEqual(result.series.points.map(p => [p.value, p.entities, p.state]), [
    [5, 2, 'observed'], [null, null, 'suppressed'], [null, null, 'missing'],
  ]);
  assert.ok(result.svg.startsWith('<svg')); assert.ok(!/NaN|Infinity/.test(result.svg));
  assert.equal(views.individual(rows, 'install_duration_ms', 'a@1', window).series.points[0].value, 0);
});
test('the integrated upstream core contains the merged cancellation fix', () => {
  assert.equal(core.CONTRACT_VERSION, 'claritas-viz.pub-lib-core.v1');
  assert.equal(core.rollingMean([1e15, 0.01, 0.01], 2)[2], 0.01);
  assert.equal(core.rollingMean([1e15, 0.01, -1e15], 3)[2], 0.01 / 3);
});
test('real SDK receives only admitted row and window fields', () => {
  let observed;
  const guarded = createZedMetricViews({ ...local,
    cohortTrends(rows, window) { observed = { rows, window }; return local.cohortTrends(rows, window); },
  });
  guarded.cohorts([{ ...sample('a@1', 0), secret: 'not-forwarded' }], 'install_duration_ms', { ...window, token: 'not-forwarded' });
  assert.deepEqual(Object.keys(observed.rows[0]).sort(), ['at', 'cohortId', 'entityId', 'value']);
  assert.deepEqual(Object.keys(observed.window).sort(), ['bucketMs', 'end', 'minEntities', 'start']);
  assert.ok(Object.isFrozen(observed.window));
});
test('local render uses no implicit hosted transport', () => {
  const previous = globalThis.fetch;
  globalThis.fetch = () => { throw Error('network forbidden'); };
  try {
    const result = views.individual([sample('a@1', 0)], 'install_duration_ms', 'a@1', window);
    assert.ok(result.svg.startsWith('<svg'));
  } finally { globalThis.fetch = previous; }
});
