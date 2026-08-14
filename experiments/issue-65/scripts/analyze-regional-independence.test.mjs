import test from 'node:test';
import assert from 'node:assert/strict';
import {associationWithCircularNull,dominantFocus,focusMetrics,isActive,localLead,midranks,pearson,regionDistance,spearman} from './analyze-regional-independence.mjs';

test('local lead follows the frozen lexicographic order',()=>{
  const row={p1_secured_objective:'1',p2_secured_objective:'0',p1_advantage_objective:'0',p2_advantage_objective:'3',p1_objective_pieces:'0',p2_objective_pieces:'3'};
  assert.equal(localLead(row),1);
  assert.equal(localLead({...row,p1_secured_objective:'0',p2_secured_objective:'0'}),-1);
  assert.equal(localLead({...row,p1_secured_objective:'0',p2_secured_objective:'0',p1_advantage_objective:'3',p2_advantage_objective:'3',p1_objective_pieces:'2',p2_objective_pieces:'2'}),0);
});

test('activity requires recent investment and contest evidence',()=>{
  const current={turn_p1_placements:'1',turn_p2_placements:'0',p1_unsecured_presence:'2',p2_unsecured_presence:'1'};
  assert.deepEqual(isActive([current],current),{active:true,both_invested:false});
  const both={...current,turn_p2_placements:'1',p2_unsecured_presence:'0'};
  assert.deepEqual(isActive([both],both),{active:true,both_invested:true});
  const stale={...current,turn_p1_placements:'0',p1_unsecured_presence:'2'};
  assert.deepEqual(isActive([stale],stale),{active:false,both_invested:false});
});

test('dominant focus and no-dominant denominator are explicit',()=>{
  assert.equal(dominantFocus({LL:2,MM:1,HH:0}),'LL');
  assert.equal(dominantFocus({LL:1,MM:1,HH:1}),null);
  const m=focusMetrics(['LL',null,'MM','HH','HH']);
  assert.equal(m.eligible_pairs,2);
  assert.equal(m.switches,1);
  assert.equal(m.switch_rate,.5);
  assert.equal(m.no_dominant_rate,.2);
  assert.equal(m.mean_persistence,4/3);
});

test('regional Manhattan distance uses normalized grid coordinates',()=>{
  assert.equal(regionDistance('LL','HH'),4);
  assert.equal(regionDistance('LM','MH'),2);
});

test('rank correlations use midranks and reject constants',()=>{
  assert.deepEqual(midranks([-1,0,0,1]),[1,2.5,2.5,4]);
  assert.equal(spearman([-1,0,1],[-1,0,1]),1);
  assert.equal(pearson([0,0,0],[0,1,0]),null);
});

test('circular null enumerates every non-zero shift',()=>{
  const r=associationWithCircularNull([-1,0,1,0],[-1,0,1,0],'spearman');
  assert.equal(r.observed,1);
  assert.equal(r.null_shifts,3);
  assert.ok(r.dependence_excess>0);
  assert.equal(associationWithCircularNull([0,0,0],[0,1,0],'phi'),null);
});
