import test from 'node:test';
import assert from 'node:assert/strict';
import { allocationPattern, spatialMetrics, bootstrap, parseCsv } from './analyze-scale.mjs';

test('classifies all three turn allocation patterns',()=>{assert.equal(allocationPattern(['LL','LL','LL']),'3');assert.equal(allocationPattern(['LL','LL','MM']),'2+1');assert.equal(allocationPattern(['LL','MM','HH']),'1+1+1');assert.throws(()=>allocationPattern(['LL','MM']));});
test('normalizes spatial metrics',()=>{const uniform=spatialMetrics(['a','b','c','d','e','f','g','h','i']);assert.ok(Math.abs(uniform.normalized_entropy-1)<1e-12);assert.equal(uniform.region_coverage,1);const one=spatialMetrics(Array(9).fill('a'));assert.equal(one.normalized_entropy,0);assert.equal(one.largest_region_share,1);});
test('game bootstrap is deterministic',()=>assert.deepEqual(bootstrap([0,1],100,56),bootstrap([0,1],100,56)));
test('parses quoted CSV',()=>assert.deepEqual(parseCsv('"a","b"\n"x","y"\n'),[{a:'x',b:'y'}]));
