import test from 'node:test';
import assert from 'node:assert/strict';
import {bootstrap,classifyFocusSwitches,dominantFocus,extractDepartureCycles,isActive,prepareTimeline} from './analyze-dormant-fronts.mjs';

const row=(turn,placements,active,unresolved=true)=>({turn,placements,p1:placements,p2:0,active,unresolved,local_lead:0});

test('active front preserves the frozen four-turn contest rule',()=>{
  const current={p1:0,p2:0,unresolved:true};
  assert.equal(isActive([{p1:1,p2:0},current],current),true);
  assert.equal(isActive([{p1:1,p2:0}],{...current,unresolved:false}),false);
  assert.equal(isActive([{p1:1,p2:1}],{...current,unresolved:false}),true);
  assert.equal(isActive([{p1:0,p2:0}],current),false);
});

test('timeline reconstructs activity from placements and unresolved presence',()=>{
  const timeline=prepareTimeline([
    {turn:1,p1:1,p2:1,unresolved:false},
    {turn:2,p1:0,p2:0,unresolved:false},
    {turn:3,p1:0,p2:0,unresolved:false},
    {turn:4,p1:0,p2:0,unresolved:false},
    {turn:5,p1:0,p2:0,unresolved:true}
  ],4);
  assert.deepEqual(timeline.map(r=>r.active),[true,true,true,true,false]);
});

test('return placement that refreshes activity is persistent when no prior lapse occurred',()=>{
  const timeline=prepareTimeline([
    {turn:1,p1:1,p2:0,unresolved:false},
    {turn:2,p1:0,p2:1,unresolved:false},
    {turn:3,p1:0,p2:0,unresolved:false},
    {turn:4,p1:0,p2:0,unresolved:false},
    {turn:5,p1:1,p2:0,unresolved:false}
  ],4);
  assert.equal(timeline[3].active,true);
  const withoutReturn=timeline.slice(1,5).map((r,i)=>({...r,p1:i===3?0:r.p1,p2:i===3?0:r.p2}));
  assert.equal(isActive(withoutReturn,withoutReturn[3]),false);
  const events=extractDepartureCycles(timeline,2);
  assert.equal(events.length,1);
  assert.equal(events[0].outcome,'persistent_revisit');
  assert.equal(events[0].revisit_lag,2);
  assert.equal(events[0].active_lapsed,false);
});

test('an inactive unresolved gap followed by an active return is reactivation',()=>{
  const events=extractDepartureCycles([
    row(1,1,true),row(2,0,true),row(3,0,true),row(4,0,false,true),row(5,1,true,true)
  ],2);
  assert.equal(events[0].outcome,'reactivation_revisit');
  assert.equal(events[0].active_lapsed,true);
});

test('resolved, non-front return, and right-censored endpoints remain distinct',()=>{
  const resolved=extractDepartureCycles([row(1,1,true),row(2,0,true),row(3,0,true),row(4,0,false,false)],2);
  const nonfront=extractDepartureCycles([row(1,1,true),row(2,0,true),row(3,0,true),row(4,1,false,true)],2);
  const censored=extractDepartureCycles([row(1,1,true),row(2,0,true),row(3,0,true),row(4,0,false,true)],2);
  assert.equal(resolved[0].outcome,'never_revisited_resolved');
  assert.equal(nonfront[0].outcome,'never_revisited_nonfront_return');
  assert.equal(censored[0].outcome,'right_censored');
});

test('a candidate that loses activity before the threshold is not a departure',()=>{
  assert.deepEqual(extractDepartureCycles([row(1,1,true),row(2,0,true),row(3,0,false,false)],2),[]);
});

test('revisited regions can start mechanically separate later cycles',()=>{
  const events=extractDepartureCycles([
    row(1,1,true),row(2,0,true),row(3,1,true),
    row(4,0,true),row(5,1,true)
  ],1);
  assert.equal(events.length,2);
  assert.deepEqual(events.map(e=>e.outcome),['persistent_revisit','persistent_revisit']);
  assert.deepEqual(events.map(e=>e.cycle_index),[1,2]);
});

test('dominant focus excludes 1+1+1 ties',()=>{
  assert.equal(dominantFocus({LL:2,MM:1,HH:0}),'LL');
  assert.equal(dominantFocus({LL:1,MM:1,HH:1}),null);
});

test('no-focus turns break switch adjacency and carryover starts at the switch endpoint',()=>{
  const state=(active,placements=0)=>({active,placements});
  const turns=[
    {turn:1,focus:'LL',by_region:{LL:state(true),MM:state(false),HH:state(false)}},
    {turn:2,focus:null,by_region:{LL:state(true),MM:state(false),HH:state(false)}},
    {turn:3,focus:'MM',by_region:{LL:state(true),MM:state(true),HH:state(false)}},
    {turn:4,focus:'HH',by_region:{LL:state(false),MM:state(true),HH:state(true)}},
    {turn:5,focus:'HH',by_region:{LL:state(false),MM:state(true,1),HH:state(true)}}
  ];
  const events=classifyFocusSwitches(turns,['LL','MM','HH']);
  assert.equal(events.length,1);
  assert.equal(events[0].from_region,'MM');
  assert.equal(events[0].unresolved_carryover,true);
  assert.equal(events[0].carryover_duration,2);
  assert.equal(events[0].revisit_turn,5);
});

test('bootstrap is deterministic for the frozen seed',()=>{
  assert.deepEqual(bootstrap([1,2,3,4],100,680068),bootstrap([1,2,3,4],100,680068));
});
