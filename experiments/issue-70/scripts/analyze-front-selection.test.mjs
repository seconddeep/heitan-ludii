import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyFront,concentration,fixedOutcome,optimisticMaxDifference,parseSnapshot,progressBand,tupleScore} from './analyze-front-selection.mjs';

test('end-of-turn progress bands preserve frozen boundaries',()=>{
  assert.equal(progressBand(6,24),1);
  assert.equal(progressBand(7,24),2);
  assert.equal(progressBand(18,24),3);
  assert.equal(progressBand(24,24),4);
});

test('concentration metrics use all nine regions',()=>{
  const uniform=concentration(Array(9).fill(1));
  assert.ok(Math.abs(uniform.entropy-1)<1e-12);
  assert.ok(Math.abs(uniform.hhi-1/9)<1e-12);
  const single=concentration([9,0,0,0,0,0,0,0,0]);
  assert.equal(single.entropy,0); assert.equal(single.hhi,1); assert.equal(single.top_two,1);
});

test('classification follows the preregistered exclusive priority',()=>{
  assert.equal(classifyFront({hasLaterObservation:true,allLaterOpportunityZero:true,resolvedOrFixed:true,remainingTurns:0,remainingFraction:0,mode:'turns4'}),'mechanically_closed');
  assert.equal(classifyFront({hasLaterObservation:false,allLaterOpportunityZero:false,resolvedOrFixed:true,remainingTurns:0,remainingFraction:0,mode:'turns4'}),'resolved_or_settled');
  assert.equal(classifyFront({hasLaterObservation:false,allLaterOpportunityZero:false,resolvedOrFixed:false,remainingTurns:3,remainingFraction:.5,mode:'turns4'}),'end_censored');
  assert.equal(classifyFront({hasLaterObservation:true,allLaterOpportunityZero:false,resolvedOrFixed:false,remainingTurns:4,remainingFraction:.2,mode:'turns4'}),'selectively_abandoned');
  assert.equal(classifyFront({hasLaterObservation:true,allLaterOpportunityZero:false,resolvedOrFixed:false,remainingTurns:9,remainingFraction:.09,mode:'0.1'}),'end_censored');
  assert.equal(classifyFront({hasLaterObservation:true,allLaterOpportunityZero:false,resolvedOrFixed:false,remainingTurns:9,remainingFraction:.1,mode:'0.1'}),'selectively_abandoned');
});

test('optimistic bound respects secured sites and per-player cap three',()=>{
  const secured=parseSnapshot('3:3:0');
  assert.equal(fixedOutcome(secured,[0],0,20),1);
  const empty=parseSnapshot('0:0:0');
  assert.equal(fixedOutcome(empty,[0],0,0),0);
  assert.equal(fixedOutcome(empty,[0],1,0),null);
  assert.equal(optimisticMaxDifference(empty,[0],1,99),tupleScore(parseSnapshot('3:3:0'),[0],1)-tupleScore(parseSnapshot('3:3:0'),[0],2));
});

test('remaining-piece snapshot boundary changes the upper bound',()=>{
  const state=parseSnapshot('2:1:2');
  assert.ok(optimisticMaxDifference(state,[0],1,0)<0);
  assert.ok(optimisticMaxDifference(state,[0],1,2)>0);
});
