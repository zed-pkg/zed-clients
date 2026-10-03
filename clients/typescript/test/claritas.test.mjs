import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createZedMetricViews} from '../dist/claritas.js';
const sample = (id, value) => ({ packageVersionId: id, ecosystem: 'group', metric: 'install_duration_ms', unit: 'ms', at: 0, value });
const window = {start: 0, end: 20, bucketMs: 10, minEntities: 2};
function port() { return {cohortTrends: (rows, window) => [{rows, window}], individualTrend: (rows,id,window) => ({rows,id,window}), trendSvg: () => '<svg/>'}; }
test('adapter exports immutable local entry points', () => assert.ok(Object.isFrozen(createZedMetricViews(port()))));
test('projection preserves exact identity and excludes private metadata', () => {
  const rows=[{...sample('same@1',0),secret:'never-forward',rawBody:'private'},sample('same@2',null)];
  const before=JSON.stringify(rows); const result=createZedMetricViews(port()).cohorts(rows,'install_duration_ms',window);
  assert.deepEqual(result[0].series.rows,[{entityId:'same@1',cohortId:'group',at:0,value:0},{entityId:'same@2',cohortId:'group',at:0,value:null}]);
  assert.equal(JSON.stringify(rows),before);
});
test('individual projection uses the selected identifier and a whitelisted window snapshot', () => {
  const result=createZedMetricViews(port()).individual([sample('a',1)],'install_duration_ms','a',window);
  assert.equal(result.series.id,'a');
  assert.deepEqual(result.series.window,{start:0,end:20,bucketMs:10});
  assert.notEqual(result.series.window,window);
});
test('mixed metrics, units and invalid values fail with generic errors', () => {
  for(const patch of [{unit:'wrong'},{metric:'wrong'},{value:NaN},{value:Infinity},{value:'1'}])
    assert.throws(()=>createZedMetricViews(port()).cohorts([{...sample('a',1),...patch}],'install_duration_ms',window),{message:'Invalid metric projection'});
});
test('incomplete SDK and unbounded inputs rejected', () => {
  assert.throws(()=>createZedMetricViews({}),TypeError);
  assert.throws(()=>createZedMetricViews(port()).cohorts(Array(50001).fill(sample('a',1)),'install_duration_ms',window),TypeError);
  assert.throws(()=>createZedMetricViews(port()).cohorts([],'constructor',window),TypeError);
});
test('SDK failures propagate instead of substituting demo data', () => {
  const error=new Error('upstream failure'); const sdk={...port(),cohortTrends:()=>{throw error}};
  assert.throws(()=>createZedMetricViews(sdk).cohorts([],'install_duration_ms',window),error);
});
