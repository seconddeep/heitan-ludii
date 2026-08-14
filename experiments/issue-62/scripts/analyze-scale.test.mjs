import test from 'node:test';
import assert from 'node:assert/strict';
import {allocationPattern,spatialMetrics,bootstrap,parseCsv,checkpointLeader} from './analyze-scale.mjs';

test('classifies all three placement allocations',()=>{assert.equal(allocationPattern(['LL','LL','LL']),'3');assert.equal(allocationPattern(['LL','LL','MM']),'2+1');assert.equal(allocationPattern(['LL','MM','HH']),'1+1+1');assert.throws(()=>allocationPattern(['LL','MM']));});
test('normalizes nine-region metrics',()=>{const uniform=spatialMetrics(['a','b','c','d','e','f','g','h','i']);assert.ok(Math.abs(uniform.normalized_entropy-1)<1e-12);assert.equal(uniform.region_coverage,1);const one=spatialMetrics(Array(12).fill('a'));assert.equal(one.normalized_entropy,0);assert.equal(one.largest_region_share,1);assert.equal(one.hhi,1);});
test('bootstrap is deterministic',()=>assert.deepEqual(bootstrap([0,1],100,56),bootstrap([0,1],100,56)));
test('parses quoted CSV',()=>assert.deepEqual(parseCsv('"a","b"\n"x","y"\n'),[{a:'x',b:'y'}]));
test('leader layers and ties are explicit',()=>{const row=(state,p1=0,p2=0)=>({point_type:'objective',state_at_turn_end:String(state),p1_at_turn_end:String(p1),p2_at_turn_end:String(p2)});assert.equal(checkpointLeader([row(3),row(2)],'secured'),1);assert.equal(checkpointLeader([row(1),row(2),row(0,2,1)],'secured'),0);assert.equal(checkpointLeader([row(1),row(2),row(0,2,1)],'secured_advantage'),0);assert.equal(checkpointLeader([row(1),row(2),row(0,2,1)],'full_lexicographic'),1);});
