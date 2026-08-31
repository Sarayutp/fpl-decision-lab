const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const zlib = require('node:zlib');

function setup() {
  const storage = new Map();
  const data = JSON.parse(zlib.gunzipSync(Buffer.from(fs.readFileSync(path.join(__dirname,'fixtures/owned-team-gw3.json.gz.b64'),'utf8'),'base64')));
  const now = new Date().toISOString();
  data.generated_at=now; data.data_quality.oldest_source_at=now; data.data_quality.is_stale=false; data.data_quality.age_hours=0;
  data.game.next_gameweek.deadline_time=new Date(Date.now()+86400000).toISOString();
  const context = vm.createContext({console, data, URL, localStorage:{getItem:k=>storage.has(k)?storage.get(k):null,setItem:(k,v)=>storage.set(k,v)}});
  for (const file of ['runtime.js','decision-log.js','scenario-compare.js','app.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname,'../dashboard/assets',file),'utf8').replace(/\nboot\(\);\s*$/,''),context);
  }
  const run = code=>vm.runInContext(code,context);
  run(`state.data=data; state.identityCheck={valid:true}; state.playerById=new Map(data.catalog.players.map(p=>[p.id,p]));
    state.projectionById=new Map(data.analysis.projections.map(p=>[p.player_id,p]));
    state.transferSettings={freeTransfers:1,bank:0,sellingPrices:{}};
    state.plannerSettings=defaultPlannerSettings();state.plannerSettings.selectedChip='save';`);
  const addPath = () => run(`
    const owned=currentDecision().starting_xi.squad.map(p=>p.player_id);
    const outs=owned.filter(id=>state.playerById.get(id).position_id===2).slice(0,2);
    outs.forEach((id,i)=>{
      const incoming={...state.playerById.get(id),id:99001+i,team_id:9991+i,web_name:'Incoming '+i};
      state.playerById.set(incoming.id,incoming);
      const forecast=clone(projection(id));forecast.player_id=incoming.id;
      forecast.gameweeks.forEach(row=>{row.expected_points+=2;row.ranking_score+=2;});
      state.projectionById.set(incoming.id,forecast);
      state.transferSettings.sellingPrices[id]=incoming.price;
    });
    const after=owned.map(id=>outs.includes(id)?99001+outs.indexOf(id):id);
    const gameweeks=state.data.analysis.recommendations.chip_planner.horizon.gameweeks;
    state.data.analysis.recommendations.chip_planner.transfer_paths.main={valid:true,
      moves:outs.map((id,i)=>({gameweek:3,out_player_id:id,in_player_id:99001+i,out_name:state.playerById.get(id).web_name,in_name:'Incoming '+i})),
      weekly:gameweeks.map(gameweek=>({gameweek,squad_ids:after})),resulting_squad_ids:after,
      budget_checkpoints:gameweeks.map(gameweek=>({gameweek,legal:true,bank:0}))};
    state.plannerSettings.selectedPath='main';
  `);
  return {run,storage,addPath};
}

test('A/B captures a legal frozen team without mutating the saved Planner or journal',()=>{
  const {run,storage}=setup(); run('savePlannerSettings();const before=JSON.stringify(state.plannerSettings);captureComparison("A","Safe plan");');
  assert.equal(run('JSON.stringify(state.plannerSettings)===before'),true);
  assert.equal(run('loadComparisons().slots.A.lineup.picks.filter(p=>p.starter).length'),11);
  assert.equal(run('loadComparisons().slots.A.lineup.bench.length'),4);
  assert.equal(run('loadDecisionLog().entries.length'),0);
  const captured=storage.get(run('comparisonStorageKey()'));
  run('state.projectionById.clear()');
  assert.equal(storage.get(run('comparisonStorageKey()')),captured);
});

test('TC and BB add the captain or four bench scores exactly once',()=>{
  const {run}=setup();run('const base=captureComparison("A");state.plannerSettings.selectedChip="triple_captain";const tc=captureComparison("B");');
  assert.equal(run('tc.metrics.netPoints'),run('comparisonRound(base.lineup.base_xp_with_captain+base.lineup.triple_captain_gain)'));
  assert.equal(run('comparisonDifference(loadComparisons().slots)'),run('comparisonRound(tc.metrics.netPoints-base.metrics.netPoints)'));
  run('state.data.analysis.recommendations.chip_planner.chip_state.bench_boost.available=true;state.plannerSettings.selectedChip="bench_boost";const bb=createComparisonRecord();');
  assert.equal(run('bb.metrics.netPoints'),run('comparisonRound(base.lineup.base_xp_with_captain+base.lineup.bench_boost_gain)'));
});

test('regular transfers require FT, subtract current hit and certify only confirmed prices',()=>{
  const {run,addPath}=setup(); addPath();
  run('const record=createComparisonRecord()');
  assert.equal(run('record.moves.length'),2);assert.equal(run('record.metrics.hitCost'),4);
  assert.equal(run('record.metrics.netPoints'),run('comparisonRound(record.lineup.base_xp_with_captain-4)'));
  assert.equal(run('record.pricesConfirmed'),true);
  run('state.transferSettings.sellingPrices={}');assert.equal(run('createComparisonRecord().pricesConfirmed'),false);
  run('state.transferSettings.freeTransfers=null');assert.throws(()=>run('createComparisonRecord()'),/Free Transfer/);
});

test('future moves are shown separately and cannot affect this-GW points or hit',()=>{
  const {run,addPath}=setup(); addPath();
  run(`const path=state.data.analysis.recommendations.chip_planner.transfer_paths.main;
    path.moves.forEach(move=>move.gameweek=4);path.weekly[0].squad_ids=owned;
    const record=createComparisonRecord();`);
  assert.equal(run('record.moves.length'),0);assert.equal(run('record.futureMoves.length'),2);
  assert.equal(run('record.metrics.hitCost'),0);
  assert.equal(run('record.metrics.netPoints'),run('comparisonRound(plannerWeekForSquad(owned,3).base_xp_with_captain)'));
});

test('Free Hit and Wildcard use a replacement XV without TC/BB uplift or ordinary hits',()=>{
  for(const chip of ['free_hit','wildcard']) {
    const {run,addPath}=setup();addPath();
    run(`state.plannerSettings.selectedPath='roll';state.plannerSettings.selectedChip='${chip}';
      state.data.analysis.recommendations.chip_planner.chips['${chip}'].scenario={squad_ids:after};
      const record=createComparisonRecord();`);
    assert.equal(run('record.moves.length'),2);assert.equal(run('record.metrics.hitCost'),0);
    assert.equal(run('record.metrics.chipGain'),0);
    assert.equal(run('record.metrics.netPoints'),run('comparisonRound(plannerWeekForSquad(after,3).base_xp_with_captain)'));
    run("state.plannerSettings.selectedPath='main'");assert.throws(()=>run('createComparisonRecord()'),/แยก/);
  }
});

test('unavailable chips, changed GW, illegal teams and incomplete forecasts cannot be captured',()=>{
  const {run}=setup();run('state.plannerSettings.selectedChip="bench_boost"');assert.throws(()=>run('createComparisonRecord()'),/ชิปนี้ใช้ไม่ได้/);
  run('state.plannerSettings.selectedChip="save";state.plannerSettings.targetGameweek=2');assert.throws(()=>run('createComparisonRecord()'),/Gameweek/);
  run('state.plannerSettings.targetGameweek=3;state.projectionById.clear()');assert.throws(()=>run('createComparisonRecord()'),/ไม่ครบ/);
  const other=setup();other.run('state.data.gameweek_decision.starting_xi.squad[0].player_id=state.data.gameweek_decision.starting_xi.squad[1].player_id');
  assert.throws(()=>other.run('createComparisonRecord()'),/ซ้ำ/);
});

test('cash shortfalls and a mismatching transfer path fail closed',()=>{
  const {run,addPath}=setup();addPath();
  run('state.transferSettings.sellingPrices[outs[0]]=0');assert.throws(()=>run('createComparisonRecord()'),/งบ/);
  run('state.transferSettings.sellingPrices[outs[0]]=state.playerById.get(outs[0]).price;state.data.analysis.recommendations.chip_planner.transfer_paths.main.weekly[0].squad_ids=owned');
  assert.throws(()=>run('createComparisonRecord()'),/ไม่ตรง/);
});

test('changing snapshot, model, selling prices or risk invalidates deltas without rewriting records',()=>{
  for(const change of ['state.data.generated_at=new Date(Date.now()+1000).toISOString()',
    'state.data.analysis.model.version="xp-v2.1"','state.transferSettings.bank=1',
    'state.activeRiskAdjustments=[{player_id:1,expected_minutes:30}]']) {
    const {run,storage}=setup();run('captureComparison("A");captureComparison("B")');
    assert.equal(run('comparisonDifference(loadComparisons().slots)'),0);
    const raw=storage.get(run('comparisonStorageKey()'));run(change);
    assert.equal(run('comparisonStatus(loadComparisons().slots.A)'),'changed');
    assert.equal(run('comparisonDifference(loadComparisons().slots)'),null);
    assert.equal(storage.get(run('comparisonStorageKey()')),raw);
  }
});

test('different input key ordering and an unsaved draft do not invalidate equivalent contexts',()=>{
  const {run}=setup();run('state.transferSettings.sellingPrices={"4":5,"2":4};captureComparison("A");captureComparison("B");state.transferSettings={sellingPrices:{"2":4,"4":5},bank:0,freeTransfers:1};state.plannerSettings=defaultPlannerSettings();');
  assert.equal(run('comparisonDifference(loadComparisons().slots)'),0);
});

test('storage isolates accounts, seasons and GWs; corrupt content is never overwritten',()=>{
  const {run,storage}=setup();run('captureComparison("A")');const key=run('comparisonStorageKey()');
  for(const change of ['state.data.manager.team_id=990002','state.data.identity.season="2027-28"','state.data.game.next_gameweek.id=4']) {
    run(change);assert.equal(run('loadComparisons().slots.A'),null);
    run('state.data.manager.team_id=990001;state.data.identity.season="2026-27";state.data.game.next_gameweek.id=3');
  }
  for(const corrupt of ['bad-json','null','{"schemaVersion":99}']) {
    storage.set(key,corrupt);assert.ok(run('loadComparisons().error'));
    assert.throws(()=>run('captureComparison("B")'));assert.equal(storage.get(key),corrupt);
  }
});

test('invalid nested records, altered scores and wrong-team envelopes cannot be trusted',()=>{
  for(const change of ['payload.slots.A.metrics.netPoints+=4','payload.slots.A.moves=[null]',
    'payload.slots.A.lineup.bench[0]=payload.slots.A.lineup.captain','payload.teamId=123']) {
    const {run,storage}=setup();run('captureComparison("A");const payload=JSON.parse(localStorage.getItem(comparisonStorageKey()));'+change);
    const raw=run('JSON.stringify(payload)');storage.set(run('comparisonStorageKey()'),raw);
    assert.ok(run('loadComparisons().error'));assert.throws(()=>run('captureComparison("B")'));
  }
});

test('offline, stale, deadline and identity mismatch keep history read-only and suppress deltas',()=>{
  for(const change of ['state.runtime.offline=true','state.data.data_quality.is_stale=true',
    'state.data.game.next_gameweek.deadline_time=new Date(0).toISOString()','state.identityCheck.valid=false']) {
    const {run,storage}=setup();run('captureComparison("A");captureComparison("B")');
    const raw=storage.get(run('comparisonStorageKey()'));run(change);
    assert.equal(run('comparisonDifference(loadComparisons().slots)'),null);
    assert.throws(()=>run('captureComparison("A")'));assert.equal(storage.get(run('comparisonStorageKey()')),raw);
  }
});

test('quota failure cannot replace a previously stored slot or claim success',()=>{
  const {run,storage}=setup();run('captureComparison("A","Original")');const key=run('comparisonStorageKey()');const raw=storage.get(key);
  run('localStorage.setItem=()=>{throw new Error("quota")}');assert.throws(()=>run('captureComparison("A","Replacement")'),/ไม่สำเร็จ/);
  assert.equal(storage.get(key),raw);assert.throws(()=>run('captureComparison("C")'),/ช่องแผน/);
});
