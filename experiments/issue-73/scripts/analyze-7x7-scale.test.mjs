import test from 'node:test';
import assert from 'node:assert/strict';
import {bootstrapDifference,expectedRegionCounts,regionForSite} from './analyze-7x7-scale.mjs';
import {isActive as issue65IsActive} from '../../issue-65/scripts/analyze-regional-independence.mjs';
import {extractDepartureCycles,prepareTimeline} from '../../issue-68/scripts/analyze-dormant-fronts.mjs';
import {classifyFront,concentration,fixedOutcome} from '../../issue-70/scripts/analyze-front-selection.mjs';

test('7x7 mapping has frozen 3/2/3 Supply and 2/3/2 Objective bands',()=>{
  const supplyAxis=Array.from({length:8},(_,column)=>regionForSite('supply',0,column)[1]);
  const objectiveAxis=Array.from({length:7},(_,column)=>regionForSite('objective',0,column)[1]);
  assert.deepEqual(supplyAxis,['L','L','L','M','M','H','H','H']);
  assert.deepEqual(objectiveAxis,['L','L','M','M','M','H','H']);
  assert.deepEqual(expectedRegionCounts(),{LL:13,LM:12,LH:13,ML:12,MM:13,MH:12,HL:13,HM:12,HH:13});
  assert.equal(Object.values(expectedRegionCounts()).reduce((a,b)=>a+b,0),113);
});

test('primary bootstrap is explicitly 7x7 minus 6x6',()=>{
  const result=bootstrapDifference([4,4],[1,1],100,73);
  assert.equal(result.difference,3);
  assert.equal(result.low,3);
  assert.equal(result.high,3);
});

test('Issue 65 active rule remains unchanged for 7x7 rows',()=>{
  const recent=[{turn_p1_placements:1,turn_p2_placements:0},{turn_p1_placements:0,turn_p2_placements:1}];
  const status=issue65IsActive(recent,{p1_unsecured_presence:0,p2_unsecured_presence:0});
  assert.deepEqual(status,{active:true,both_invested:true});
});

test('Issue 68 departure-cycle behavior is reused unchanged',()=>{
  const timeline=prepareTimeline([
    {turn:1,p1:1,p2:1,unresolved:true},{turn:2,p1:0,p2:0,unresolved:true},
    {turn:3,p1:0,p2:0,unresolved:true},{turn:4,p1:1,p2:0,unresolved:true}
  ],4);
  const events=extractDepartureCycles(timeline,2);
  assert.equal(events.length,1);
  assert.equal(events[0].outcome,'persistent_revisit');
  assert.equal(events[0].revisit_lag,2);
});

test('Issue 70 concentration and classification definitions are unchanged',()=>{
  assert.deepEqual(concentration([2,1,0]),{entropy:-(2/3*Math.log(2/3)+1/3*Math.log(1/3))/Math.log(3),hhi:5/9,largest:2/3,top_two:1,regions:2});
  assert.equal(classifyFront({hasLaterObservation:true,allLaterOpportunityZero:true,resolvedOrFixed:false,remainingTurns:10,remainingFraction:.2,mode:'turns4'}),'mechanically_closed');
  const tied=[{state:0,p1:0,p2:0}];
  assert.equal(fixedOutcome(tied,[0],0,0),0);
});
