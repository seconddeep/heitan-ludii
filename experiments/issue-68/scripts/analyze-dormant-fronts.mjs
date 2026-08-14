import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE=path.dirname(fileURLToPath(import.meta.url));
const ISSUE=path.resolve(HERE,'..');
const REPO=path.resolve(ISSUE,'..','..');
const DEFAULT_RESULTS=path.join(ISSUE,'results');

export function parseCsv(text){
  const rows=[];let row=[],field='',quoted=false;
  for(let i=0;i<text.length;i++){
    const c=text[i];
    if(quoted){if(c==='"'&&text[i+1]==='"'){field+='"';i++;}else if(c==='"')quoted=false;else field+=c;}
    else if(c==='"')quoted=true;else if(c===','){row.push(field);field='';}
    else if(c==='\n'){row.push(field);rows.push(row);row=[];field='';}else if(c!=='\r')field+=c;
  }
  if(field||row.length){row.push(field);rows.push(row);}
  const header=rows.shift()??[];
  return rows.filter(r=>r.some(Boolean)).map(r=>Object.fromEntries(header.map((h,i)=>[h,r[i]??''])));
}
function readCsv(file){return parseCsv(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,''));}
function csvValue(value){const s=value===null||value===undefined?'':String(value);return `"${s.replaceAll('"','""')}"`;}
function writeCsv(file,rows,headers=[]){const keys=rows.length?Object.keys(rows[0]):headers;if(!keys.length)throw new Error(`no schema for ${file}`);fs.writeFileSync(file,[keys.map(csvValue).join(','),...rows.map(r=>keys.map(k=>csvValue(r[k])).join(','))].join('\n')+'\n');}
function groupBy(rows,fn){const map=new Map();for(const row of rows){const key=fn(row);if(!map.has(key))map.set(key,[]);map.get(key).push(row);}return map;}
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null;
const median=a=>{if(!a.length)return null;const s=[...a].sort((a,b)=>a-b),m=Math.floor(s.length/2);return s.length%2?s[m]:(s[m-1]+s[m])/2;};
const fixed=x=>x===null||x===undefined||!Number.isFinite(x)?'':x.toFixed(6);
const gameKey=r=>`${r.board}|${r.experiment_id}|${+r.game_index}`;
const conditionKey=r=>`${r.board}|${r.search_level}`;
function sha256(file){return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');}
function rng(seed){let x=seed>>>0;return()=>{x+=0x6D2B79F5;let t=x;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return((t^t>>>14)>>>0)/4294967296;};}
function hash(text){let h=2166136261;for(const c of text){h^=c.codePointAt(0);h=Math.imul(h,16777619);}return h>>>0;}
export function bootstrap(values,samples,seed){if(!values.length)return[null,null];const random=rng(seed),means=[];for(let b=0;b<samples;b++){let sum=0;for(let i=0;i<values.length;i++)sum+=values[Math.floor(random()*values.length)];means.push(sum/values.length);}means.sort((a,b)=>a-b);return[means[Math.floor(.025*samples)],means[Math.min(samples-1,Math.floor(.975*samples))]];}

export function isActive(recentRows,current){
  const p1=recentRows.reduce((s,r)=>s+(+r.p1),0),p2=recentRows.reduce((s,r)=>s+(+r.p2),0);
  const recent=p1+p2>0,bothRecent=p1>0&&p2>0;
  return recent&&(bothRecent||current.unresolved);
}
export function dominantFocus(regionCounts){const max=Math.max(...Object.values(regionCounts));const top=Object.entries(regionCounts).filter(([,n])=>n===max&&n>0);return top.length===1?top[0][0]:null;}
function longestRun(values,predicate){let best=0,current=0;for(const value of values){if(predicate(value)){current++;best=Math.max(best,current);}else current=0;}return best;}

export function prepareTimeline(rows,window=4){
  const timeline=rows.map(r=>({
    turn:+r.turn,
    p1:+r.p1,
    p2:+r.p2,
    placements:+r.p1+(+r.p2),
    unresolved:Boolean(r.unresolved),
    local_lead:r.local_lead===undefined?0:+r.local_lead
  }));
  for(let i=0;i<timeline.length;i++)timeline[i].active=isActive(timeline.slice(Math.max(0,i-window+1),i+1),timeline[i]);
  return timeline;
}

export function extractDepartureCycles(timeline,threshold){
  const events=[];let state='idle',candidate=null,cycle=0;
  const close=(outcome,index,returnTurn=null)=>{
    const endTurn=timeline[index].turn;
    events.push({
      cycle_index:++cycle,
      departure_turn:candidate.departure_turn,
      qualification_turn:candidate.qualification_turn,
      endpoint_turn:endTurn,
      revisit_turn:returnTurn,
      outcome,
      duration:endTurn-candidate.departure_turn,
      revisit_lag:returnTurn===null?null:returnTurn-candidate.departure_turn,
      active_lapsed:candidate.active_lapsed
    });
    state='idle';candidate=null;
  };
  for(let i=0;i<timeline.length;i++){
    const row=timeline[i],previous=i?timeline[i-1]:null;
    if(row.placements>0){
      if(state==='qualified'){
        if(row.active)close(candidate.active_lapsed?'reactivation_revisit':'persistent_revisit',i,row.turn);
        else close('never_revisited_nonfront_return',i,null);
      }else if(state==='candidate'){state='idle';candidate=null;}
      continue;
    }
    if(state==='idle'&&previous&&previous.placements>0&&previous.active&&row.active){
      state='candidate';candidate={departure_turn:row.turn,qualification_turn:null,active_lapsed:false};
    }
    if(state==='candidate'){
      const streak=row.turn-candidate.departure_turn+1;
      if(!row.active){state='idle';candidate=null;continue;}
      if(streak>=threshold){state='qualified';candidate.qualification_turn=row.turn;}
    }else if(state==='qualified'){
      if(!row.active)candidate.active_lapsed=true;
      if(!row.active&&!row.unresolved)close('never_revisited_resolved',i,null);
    }
  }
  if(state==='qualified'){
    const last=timeline.at(-1);
    if(last.active||last.unresolved)close('right_censored',timeline.length-1,null);
    else close('never_revisited_resolved',timeline.length-1,null);
  }
  return events;
}

export function classifyFocusSwitches(turns,regions){
  const events=[];
  for(let i=1;i<turns.length;i++){
    const previous=turns[i-1],current=turns[i];
    if(previous.focus===null||current.focus===null||previous.focus===current.focus)continue;
    const prior=previous.focus,state=current.by_region[prior];
    let duration=0;
    if(state.active)for(let j=i;j<turns.length&&turns[j].by_region[prior].active;j++)duration++;
    let revisitTurn=null;
    for(let j=i+1;j<turns.length;j++){const r=turns[j].by_region[prior];if(r.placements>0){if(r.active)revisitTurn=turns[j].turn;break;}}
    events.push({switch_turn:current.turn,from_region:prior,to_region:current.focus,unresolved_carryover:state.active,carryover_duration:duration,later_revisited:revisitTurn!==null,revisit_turn:revisitTurn,revisit_lag:revisitTurn===null?null:revisitTurn-current.turn});
  }
  return events;
}

function validateAndLoad(config){
  const artifacts=[];
  for(const input of config.input_files){const file=path.join(REPO,input.path),actual=sha256(file);if(actual!==input.sha256)throw new Error(`input hash mismatch: ${input.path}`);artifacts.push({path:input.path,sha256:actual,bytes:fs.statSync(file).size});}
  const source=path.join(REPO,'experiments','issue-65','results');
  const manifest=readCsv(path.join(source,'trial-sources.csv'));
  const games=readCsv(path.join(source,'raw','games.csv'));
  const placements=readCsv(path.join(source,'raw','placements.csv'));
  const states=readCsv(path.join(source,'raw','regional-turn-states.csv'));
  const manifestKeys=new Set(),trialHashes=new Set(),seeds=new Set();
  for(const row of manifest){const key=gameKey(row);if(manifestKeys.has(key))throw new Error(`duplicate manifest game key ${key}`);manifestKeys.add(key);if(seeds.has(row.seed))throw new Error(`duplicate seed ${row.seed}`);seeds.add(row.seed);if(trialHashes.has(row.trial_sha256))throw new Error(`duplicate trial hash ${row.trial_sha256}`);trialHashes.add(row.trial_sha256);const trial=path.join(REPO,row.trial_file);if(sha256(trial)!==row.trial_sha256)throw new Error(`trial hash mismatch ${row.trial_file}`);}
  const gameMap=new Map();
  for(const game of games){const key=gameKey(game);if(gameMap.has(key))throw new Error(`duplicate game ${key}`);if(!manifestKeys.has(key))throw new Error(`game missing from manifest ${key}`);const expected=game.board==='3x3'?[54,18]:game.board==='4x4'?[72,24]:game.board==='6x6'?[144,48]:null;if(!expected||+game.moves!==expected[0]||+game.turns!==expected[1]||game.end_type!=='NaturalEnd')throw new Error(`invalid natural length ${key}`);gameMap.set(key,game);}
  if(gameMap.size!==manifestKeys.size)throw new Error('manifest and game totals differ');
  const placementKeys=new Set(),targetRegions=new Map(),placementsByTurn=groupBy(placements,r=>`${gameKey(r)}|${+r.turn_number}`);
  for(const row of placements){const key=gameKey(row),pk=`${key}|${+row.turn_number}|${+row.placement_number}`;if(!gameMap.has(key))throw new Error(`placement for unknown game ${key}`);if(placementKeys.has(pk))throw new Error(`duplicate placement key ${pk}`);placementKeys.add(pk);if(+row.mover!==1&&+row.mover!==2)throw new Error(`invalid placement mover ${pk}`);if(!config.regions.includes(row.region))throw new Error(`unmapped or unknown placement region ${pk}`);const target=`${row.board}|${row.target}`,prior=targetRegions.get(target);if(prior&&prior!==row.region)throw new Error(`inconsistent target region ${target}`);targetRegions.set(target,row.region);}
  const stateKeys=new Set(),statesByTurn=groupBy(states,r=>`${gameKey(r)}|${+r.turn_number}`),statesByGame=groupBy(states,gameKey);
  for(const row of states){const key=gameKey(row),sk=`${key}|${+row.turn_number}|${row.region}`;if(!gameMap.has(key))throw new Error(`state for unknown game ${key}`);if(stateKeys.has(sk))throw new Error(`duplicate regional state ${sk}`);stateKeys.add(sk);if(!config.regions.includes(row.region))throw new Error(`unknown state region ${sk}`);}
  for(const game of games)for(let turn=1;turn<=+game.turns;turn++){
    const key=`${gameKey(game)}|${turn}`,pp=placementsByTurn.get(key)??[],ss=statesByTurn.get(key)??[];
    if(pp.length!==3||new Set(pp.map(r=>+r.placement_number)).size!==3||pp.some(r=>+r.placement_number<1||+r.placement_number>3))throw new Error(`turn does not contain three unique placements ${key}`);
    if(ss.length!==config.regions.length||new Set(ss.map(r=>r.region)).size!==config.regions.length)throw new Error(`turn does not contain nine unique regional states ${key}`);
    const expected=new Map(config.regions.flatMap(region=>[[`${region}|1`,0],[`${region}|2`,0]]));for(const row of pp)expected.set(`${row.region}|${+row.mover}`,expected.get(`${row.region}|${+row.mover}`)+1);
    let total=0;for(const row of ss){const p1=+row.turn_p1_placements,p2=+row.turn_p2_placements;total+=p1+p2;if(p1!==expected.get(`${row.region}|1`)||p2!==expected.get(`${row.region}|2`))throw new Error(`placement/state regional mismatch ${key}/${row.region}`);}if(total!==3)throw new Error(`nine-region placement total is not three ${key}`);
  }
  const manifestByGame=new Map(manifest.map(r=>[gameKey(r),r]));
  return{artifacts,manifest,games,placements,states,statesByGame,manifestByGame,validation:{games:games.length,placements:placements.length,turns:games.reduce((s,g)=>s+(+g.turns),0),regional_turn_rows:states.length,unique_trial_hashes:trialHashes.size,unique_target_region_assignments:targetRegions.size,all_input_hashes_match:true,all_trial_hashes_match:true,all_games_natural_and_board_totals_match:true,all_placements_have_unique_region:true,all_turns_have_three_unique_placements:true,regional_placement_totals_match:true}};
}

function decorateGame(game,stateRows,searchLevel,config){
  const rowsByRegion=groupBy(stateRows,r=>r.region),byRegion={};
  for(const region of config.regions){const rows=(rowsByRegion.get(region)??[]).sort((a,b)=>+a.turn_number-+b.turn_number);if(rows.length!==+game.turns)throw new Error(`missing region timeline ${gameKey(game)}/${region}`);byRegion[region]=prepareTimeline(rows.map(r=>({turn:+r.turn_number,p1:+r.turn_p1_placements,p2:+r.turn_p2_placements,unresolved:+r.p1_unsecured_presence>0&&+r.p2_unsecured_presence>0,local_lead:+r.local_lead})),config.active_window_turns);}
  const turns=[];
  for(let i=0;i<+game.turns;i++){const regionState=Object.fromEntries(config.regions.map(r=>[r,byRegion[r][i]])),counts=Object.fromEntries(config.regions.map(r=>[r,regionState[r].placements]));turns.push({turn:i+1,by_region:regionState,focus:dominantFocus(counts),active_count:config.regions.filter(r=>regionState[r].active).length,backlog_count:config.regions.filter(r=>regionState[r].active&&regionState[r].placements===0).length});}
  return{board:game.board,experiment_id:game.experiment_id,search_level:searchLevel,game_index:+game.game_index,turns,byRegion};
}

function gameThresholdAnalysis(data,threshold,config){
  const cycles=[];
  for(const region of config.regions)for(const event of extractDepartureCycles(data.byRegion[region],threshold))cycles.push({...event,region});
  const dormantCounts=data.turns.map((turn,i)=>config.regions.filter(region=>{const timeline=data.byRegion[region];let streak=0;for(let j=i;j>=0&&timeline[j].placements===0;j--)streak++;return timeline[i].active&&streak>=threshold;}).length);
  const backlog=data.turns.map(r=>r.backlog_count),revisits=cycles.filter(r=>r.outcome.endsWith('_revisit')),never=cycles.filter(r=>r.outcome.startsWith('never_revisited')),censored=cycles.filter(r=>r.outcome==='right_censored'),observed=revisits.length+never.length;
  const remaining=e=>data.turns.length-e.departure_turn;
  const fixedEligible=cycles.filter(e=>remaining(e)>=config.fixed_followup_turns),early=cycles.filter(e=>e.departure_turn/data.turns.length<=config.early_departure_progress_max),quarter=Math.ceil(config.normalized_followup_fraction*data.turns.length);
  const revisitCounts=groupBy(revisits,r=>r.region);
  const metric={board:data.board,experiment_id:data.experiment_id,search_level:data.search_level,game_index:data.game_index,threshold,turns:data.turns.length,
    mean_dormant_active_fronts:fixed(avg(dormantCounts)),dormant_ge1_turn_rate:fixed(dormantCounts.filter(x=>x>=1).length/data.turns.length),dormant_ge2_turn_rate:fixed(dormantCounts.filter(x=>x>=2).length/data.turns.length),longest_dormant_run:longestRun(dormantCounts,x=>x>=1),longest_dormant_run_fraction:fixed(longestRun(dormantCounts,x=>x>=1)/data.turns.length),
    mean_backlog_size:fixed(avg(backlog)),max_backlog_size:Math.max(...backlog),backlog_ge1_turn_rate:fixed(backlog.filter(x=>x>=1).length/data.turns.length),backlog_ge2_turn_rate:fixed(backlog.filter(x=>x>=2).length/data.turns.length),longest_backlog_run:longestRun(backlog,x=>x>=1),longest_backlog_run_fraction:fixed(longestRun(backlog,x=>x>=1)/data.turns.length),
    qualifying_departures:cycles.length,persistent_revisits:cycles.filter(r=>r.outcome==='persistent_revisit').length,reactivation_revisits:cycles.filter(r=>r.outcome==='reactivation_revisit').length,never_revisited:never.length,right_censored:censored.length,revisit_rate_observed:observed?fixed(revisits.length/observed):'',never_revisited_rate_observed:observed?fixed(never.length/observed):'',right_censored_rate:cycles.length?fixed(censored.length/cycles.length):'',simple_end_revisit_rate:cycles.length?fixed(revisits.length/cycles.length):'',mean_revisit_lag:fixed(avg(revisits.map(r=>r.revisit_lag))),median_revisit_lag:fixed(median(revisits.map(r=>r.revisit_lag))),mean_normalized_revisit_lag:fixed(avg(revisits.map(r=>r.revisit_lag/data.turns.length))),distinct_revisited_regions:new Set(revisits.map(r=>r.region)).size,repeated_revisit_regions:[...revisitCounts.values()].filter(r=>r.length>=2).length,
    fixed_four_turn_eligible:fixedEligible.length,revisit_within_four_turns_rate:fixedEligible.length?fixed(fixedEligible.filter(e=>e.outcome.endsWith('_revisit')&&e.revisit_lag<=config.fixed_followup_turns).length/fixedEligible.length):'',early_departures:early.length,early_revisit_within_quarter_rate:early.length?fixed(early.filter(e=>e.outcome.endsWith('_revisit')&&e.revisit_lag<=quarter).length/early.length):''};
  const eventRows=cycles.map(e=>({board:data.board,experiment_id:data.experiment_id,search_level:data.search_level,game_index:data.game_index,region:e.region,threshold,cycle_index:e.cycle_index,departure_turn:e.departure_turn,departure_progress:fixed(e.departure_turn/data.turns.length),qualification_turn:e.qualification_turn,endpoint_turn:e.endpoint_turn,outcome:e.outcome,revisit_turn:e.revisit_turn??'',duration:e.duration,normalized_duration:fixed(e.duration/data.turns.length),revisit_lag:e.revisit_lag??'',normalized_revisit_lag:e.revisit_lag===null?'':fixed(e.revisit_lag/data.turns.length),active_lapsed:String(e.active_lapsed),right_censored:String(e.outcome==='right_censored')}));
  return{metric,eventRows,dormantCounts};
}

function analyzeGame(game,stateRows,searchLevel,config){
  const data=decorateGame(game,stateRows,searchLevel,config),metrics=[],events=[],thresholdCounts={};
  for(const threshold of [config.primary_dormancy_threshold,...config.sensitivity_dormancy_thresholds]){const result=gameThresholdAnalysis(data,threshold,config);metrics.push(result.metric);events.push(...result.eventRows);thresholdCounts[threshold]=result.dormantCounts;}
  const frontTurns=data.turns.map((turn,i)=>({board:data.board,experiment_id:data.experiment_id,search_level:data.search_level,game_index:data.game_index,turn_number:turn.turn,progress:fixed(turn.turn/data.turns.length),active_fronts:turn.active_count,backlog_size:turn.backlog_count,dominant_focus:turn.focus??'',...Object.fromEntries(Object.entries(thresholdCounts).map(([k,v])=>[`dormant_k${k}`,v[i]]))}));
  const focus=classifyFocusSwitches(data.turns,config.regions).map((e,index)=>({board:data.board,experiment_id:data.experiment_id,search_level:data.search_level,game_index:data.game_index,switch_index:index+1,...e,unresolved_carryover:String(e.unresolved_carryover),later_revisited:String(e.later_revisited),revisit_turn:e.revisit_turn??'',revisit_lag:e.revisit_lag??''}));
  const carried=focus.filter(r=>r.unresolved_carryover==='true');
  const focusMetric={board:data.board,experiment_id:data.experiment_id,search_level:data.search_level,game_index:data.game_index,focus_switches:focus.length,unresolved_carryover_switches:carried.length,unresolved_carryover_rate:focus.length?fixed(carried.length/focus.length):'',mean_carryover_duration:fixed(avg(carried.map(r=>r.carryover_duration))),carryover_later_revisited:carried.filter(r=>r.later_revisited==='true').length,carryover_later_revisit_rate:carried.length?fixed(carried.filter(r=>r.later_revisited==='true').length/carried.length):''};
  return{metrics,events,frontTurns,focus,focusMetric};
}

function numericValues(rows,metric){return rows.filter(r=>r[metric]!==''&&r[metric]!==null&&r[metric]!==undefined).map(r=>+r[metric]).filter(Number.isFinite);}
function summarize(rows,metrics,config,keyFn){const out=[];for(const group of groupBy(rows,keyFn).values())for(const metric of metrics){const values=numericValues(group,metric);if(!values.length)continue;const ci=bootstrap(values,config.bootstrap_samples,(config.bootstrap_seed+hash(`${keyFn(group[0])}|${metric}`))>>>0);out.push({board:group[0].board,search_level:group[0].search_level,...(group[0].threshold!==undefined?{threshold:group[0].threshold}:{}),metric,games:values.length,value:fixed(avg(values)),median:fixed(median(values)),ci_low:fixed(ci[0]),ci_high:fixed(ci[1]),primary:String(group[0].search_level===config.primary_search_level&&(group[0].threshold===undefined||+group[0].threshold===config.primary_dormancy_threshold))});}return out;}

function eventTimeTable(events){const out=[];for(const group of groupBy(events,r=>`${conditionKey(r)}|${r.threshold}`).values()){const max=Math.max(...group.map(r=>+r.duration));for(let lag=0;lag<=max;lag++){const atRisk=group.filter(r=>+r.duration>=lag),end=group.filter(r=>+r.duration===lag);out.push({board:group[0].board,search_level:group[0].search_level,threshold:+group[0].threshold,lag,normalized_lag:fixed(lag/(group[0].board==='3x3'?18:group[0].board==='4x4'?24:48)),at_risk:atRisk.length,persistent_revisits:end.filter(r=>r.outcome==='persistent_revisit').length,reactivation_revisits:end.filter(r=>r.outcome==='reactivation_revisit').length,never_revisited_resolved:end.filter(r=>r.outcome==='never_revisited_resolved').length,never_revisited_nonfront_return:end.filter(r=>r.outcome==='never_revisited_nonfront_return').length,right_censored:end.filter(r=>r.outcome==='right_censored').length});}}return out;}
function lagDistribution(events){const revisits=events.filter(r=>r.outcome.endsWith('_revisit')),out=[];for(const group of groupBy(revisits,r=>`${conditionKey(r)}|${r.threshold}|${r.revisit_lag}`).values()){const condition=revisits.filter(r=>r.board===group[0].board&&r.search_level===group[0].search_level&&r.threshold===group[0].threshold);out.push({board:group[0].board,search_level:group[0].search_level,threshold:+group[0].threshold,revisit_lag:+group[0].revisit_lag,count:group.length,fraction:fixed(group.length/condition.length)});}return out.sort((a,b)=>a.board.localeCompare(b.board)||a.search_level.localeCompare(b.search_level)||a.threshold-b.threshold||a.revisit_lag-b.revisit_lag);}

export function runAnalysis(results=DEFAULT_RESULTS){
  fs.mkdirSync(results,{recursive:true});
  const config=JSON.parse(fs.readFileSync(path.join(ISSUE,'config.json'),'utf8')),loaded=validateAndLoad(config),allMetrics=[],allEvents=[],allTurns=[],allFocus=[],focusMetrics=[];
  for(const game of loaded.games){const manifest=loaded.manifestByGame.get(gameKey(game));if(!manifest)throw new Error(`missing manifest ${gameKey(game)}`);const result=analyzeGame(game,loaded.statesByGame.get(gameKey(game))??[],manifest.search_level,config);allMetrics.push(...result.metrics);allEvents.push(...result.events);allTurns.push(...result.frontTurns);allFocus.push(...result.focus);focusMetrics.push(result.focusMetric);}
  writeCsv(path.join(results,'front-turns.csv'),allTurns);writeCsv(path.join(results,'departure-events.csv'),allEvents);writeCsv(path.join(results,'focus-switch-events.csv'),allFocus,['board','experiment_id','search_level','game_index','switch_index','switch_turn','from_region','to_region','unresolved_carryover','carryover_duration','later_revisited','revisit_turn','revisit_lag']);writeCsv(path.join(results,'game-front-metrics.csv'),allMetrics);writeCsv(path.join(results,'game-focus-metrics.csv'),focusMetrics);writeCsv(path.join(results,'revisit-time-table.csv'),eventTimeTable(allEvents));writeCsv(path.join(results,'revisit-lag-distribution.csv'),lagDistribution(allEvents),['board','search_level','threshold','revisit_lag','count','fraction']);
  const thresholdMetricNames=['mean_dormant_active_fronts','dormant_ge1_turn_rate','dormant_ge2_turn_rate','longest_dormant_run_fraction','mean_backlog_size','max_backlog_size','backlog_ge1_turn_rate','backlog_ge2_turn_rate','longest_backlog_run_fraction','qualifying_departures','persistent_revisits','reactivation_revisits','never_revisited','right_censored','revisit_rate_observed','never_revisited_rate_observed','right_censored_rate','simple_end_revisit_rate','mean_revisit_lag','median_revisit_lag','mean_normalized_revisit_lag','distinct_revisited_regions','repeated_revisit_regions','revisit_within_four_turns_rate','early_revisit_within_quarter_rate'];
  const focusMetricNames=['focus_switches','unresolved_carryover_switches','unresolved_carryover_rate','mean_carryover_duration','carryover_later_revisited','carryover_later_revisit_rate'];
  const boardSummary=summarize(allMetrics,thresholdMetricNames,config,r=>`${conditionKey(r)}|${r.threshold}`),focusSummary=summarize(focusMetrics,focusMetricNames,config,conditionKey);writeCsv(path.join(results,'board-summary.csv'),boardSummary);writeCsv(path.join(results,'focus-summary.csv'),focusSummary);
  const sensitivity=boardSummary.filter(r=>r.search_level!==config.primary_search_level||+r.threshold!==config.primary_dormancy_threshold);writeCsv(path.join(results,'sensitivity-summary.csv'),sensitivity);
  fs.copyFileSync(path.join(REPO,'experiments','issue-65','results','trial-sources.csv'),path.join(results,'trial-sources.csv'));
  fs.writeFileSync(path.join(results,'source-artifacts.json'),JSON.stringify({schema_version:1,source_issue:config.source_issue,artifacts:loaded.artifacts},null,2)+'\n');
  const analysis={schema_version:1,validation:loaded.validation,primary_games:loaded.manifest.filter(r=>r.search_level===config.primary_search_level).length,frozen_definitions:{regions:config.regions,active_window_turns:config.active_window_turns,primary_dormancy_threshold:config.primary_dormancy_threshold,sensitivity_dormancy_thresholds:config.sensitivity_dormancy_thresholds,persistent_boundary:'active at every turn through the turn immediately before return; return placement may refresh activity',reactivation_boundary:'at least one inactive turn while opposing unsecured presence persists; first return ends active',terminal_outcomes:['persistent_revisit','reactivation_revisit','never_revisited_resolved','never_revisited_nonfront_return','right_censored'],focus_denominator:'adjacent turns with a unique dominant region at both endpoints'},outputs:{departure_cycles:allEvents.length,focus_switches:allFocus.length,front_turn_rows:allTurns.length}};
  fs.writeFileSync(path.join(results,'analysis.json'),JSON.stringify(analysis,null,2)+'\n');return analysis;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(JSON.stringify(runAnalysis(process.argv[2]?path.resolve(process.argv[2]):DEFAULT_RESULTS)));
