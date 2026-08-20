import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {addContrast,bootstrapDifference,budgetOf,expectedRegionCounts,regionForSite,turnsOf} from './analyze-7x7-scale.mjs';
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

test('all three contrasts preserve their preregistered direction',()=>{
  const config={bootstrap_samples:100,bootstrap_seed:77};
  const cases=[
    [{id:'84-minus-72',minuend:84,subtrahend:72},[4,4],[1,1]],
    [{id:'96-minus-72',minuend:96,subtrahend:72},[7,7],[1,1]],
    [{id:'96-minus-84',minuend:96,subtrahend:84},[7,7],[4,4]]
  ];
  for(const [contrast,minuend,subtrahend] of cases){
    const rows=[];addContrast(rows,config,contrast,'test','direction','value',minuend.map(value=>({value})),subtrahend.map(value=>({value})));
    assert.equal(rows[0].contrast_id,contrast.id);
    assert.equal(rows[0].minuend_budget,contrast.minuend);
    assert.equal(rows[0].subtrahend_budget,contrast.subtrahend);
    assert.equal(+rows[0].difference_minuend_minus_subtrahend,minuend[0]-subtrahend[0]);
    assert.equal(+rows[0].ci_low,minuend[0]-subtrahend[0]);
    assert.equal(+rows[0].ci_high,minuend[0]-subtrahend[0]);
  }
});

test('budget-derived game lengths are 48, 56, and 64 turns',()=>{
  assert.equal(budgetOf({board:'7x7-p84'}),84);
  assert.deepEqual([72,84,96].map(piece_budget=>turnsOf({piece_budget})),[48,56,64]);
});

test('all piece budgets use byte-identical 7x7 topology and regions',()=>{
  const source=fs.readFileSync(new URL('../../../games/Heitan.lud',import.meta.url),'utf8');
  const block=name=>{const start=source.indexOf(`(item "${name}"`);let depth=0;for(let i=start;i<source.length;i++){if(source[i]==='(')depth++;else if(source[i]===')'&&--depth===0)return source.slice(start,i+1);}throw new Error(`missing ${name}`);};
  const normalize=text=>text.replaceAll('\r','').replace(/item "7x7(?:-84|-96)?"/,'item "7x7"').replace(/\n        <(?:72|84|96)>\n        <(?:144|168|192)>\n        <(?:73|85|97)>\n        <(?:3650|4250|4850)>\n        "[^"]+"\n    \)$/,'\n        <CONFIG>\n    )');
  assert.equal(normalize(block('7x7-84')),normalize(block('7x7')));
  assert.equal(normalize(block('7x7-96')),normalize(block('7x7')));
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
