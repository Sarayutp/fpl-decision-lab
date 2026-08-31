const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const zlib = require('node:zlib');
const path = require('node:path');

function setup() {
  const storage = new Map();
  const data = JSON.parse(zlib.gunzipSync(Buffer.from(fs.readFileSync(path.join(__dirname,'fixtures/owned-team-gw3.json.gz.b64'),'utf8'),'base64')));
  const now = new Date().toISOString();
  data.generated_at=now; data.data_quality.oldest_source_at=now; data.data_quality.is_stale=false; data.data_quality.age_hours=0;
  data.game.next_gameweek.deadline_time=new Date(Date.now()+86400000).toISOString();
  const context = vm.createContext({console, data, localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)}, URL});
  for(const file of ['runtime.js','decision-log.js','app.js']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../dashboard/assets',file),'utf8').replace(/\nboot\(\);\s*$/,''),context);
  const run = code=>vm.runInContext(code,context);
  run(`state.data=data; state.identityCheck={valid:true}; state.settings={expectedTeamId:990001};
    state.playerById=new Map(data.catalog.players.map(p=>[p.id,p]));state.projectionById=new Map(data.analysis.projections.map(p=>[p.player_id,p]));
    state.transferSettings={freeTransfers:1,bank:0,sellingPrices:{}};state.plannerSettings=defaultPlannerSettings();
    state.briefing='- Team ID: 990001\\n- เป้าหมาย: Gameweek 3\\n- สร้างเมื่อ: '+data.generated_at;`);
  return {run,storage};
}

test('current contract is accepted, future schema and mixed model versions are rejected',()=>{
  const {run}=setup(); assert.equal(run('snapshotCompatibility(data)'),null);
  run('data.schema_version=999');assert.match(run('snapshotCompatibility(data)'),/รุ่นข้อมูล/);
  run('data.schema_version=2;data.gameweek_decision.source.model_version="wrong"');assert.match(run('snapshotCompatibility(data)'),/คนละรุ่น/);
});
test('missing critical structures fail before rendering',()=>{
  const {run}=setup();run('delete data.catalog.players');assert.match(run('snapshotCompatibility(data)'),/ข้อมูลสำคัญ/);
});
test('freshness keeps pipeline stale flags and detects future timestamps',()=>{
  const {run}=setup();run('data.data_quality.is_stale=true');assert.equal(run('assessFreshness(data).stale'),true);
  run('data.data_quality.is_stale=false;data.data_quality.oldest_source_at=new Date(Date.now()+7200000).toISOString()');
  assert.equal(run('assessFreshness(data).stale'),true);
});
test('deadline and offline prevent new decisions even with matching identity',()=>{
  const {run}=setup();assert.equal(run('decisionActionsAllowed()'),true);
  run('data.gameweek_decision.status="unavailable"');assert.equal(run('decisionActionsAllowed()'),false);
  run('data.gameweek_decision.status="ready"');
  run('state.runtime.offline=true');assert.equal(run('decisionActionsAllowed()'),false);
  run('state.runtime.offline=false;data.game.next_gameweek.deadline_time=new Date(0).toISOString()');
  assert.equal(run('runtimeState(data).kind'),'deadline');assert.throws(()=>run('createDecisionRecord()'));
});
test('a missing briefing is partial, but a wrong-generation briefing blocks identity',()=>{
  const {run}=setup();assert.equal(run('validateIdentity().valid'),true);
  run('state.briefing=state.briefing.replace(data.generated_at,"2000-01-01T00:00:00Z")');assert.equal(run('validateIdentity().valid'),false);
  run('state.runtime.partial=true;state.briefing=""');assert.equal(run('validateIdentity().valid'),true);
  assert.equal(run('runtimeState(data,{partial:true}).kind'),'partial');
});
test('journal captures a frozen legal XV with C/VC, bench and provenance',()=>{
  const {run}=setup();run('const record=createDecisionRecord("Test note");persistDecisionLog([record]);');
  assert.equal(run('record.lineup.picks.filter(p=>p.starter).length'),11);
  assert.equal(run('record.lineup.bench.length'),4);
  assert.notEqual(run('record.lineup.captain.player_id'),run('record.lineup.vice_captain.player_id'));
  run('state.plannerSettings.selectedChip="triple_captain";savePlannerSettings();const tcRecord=createDecisionRecord();');
  assert.equal(run('tcRecord.expectedPoints'),run('Math.round((record.expectedPoints + record.lineup.triple_captain_gain)*100)/100'));
  const expected=run('record.expectedPoints');run('state.projectionById.clear()');assert.equal(run('loadDecisionLog().entries[0].expectedPoints'),expected);
  assert.equal(run('loadDecisionLog().entries[0].release'),'2.0.0-rc.1');
});
test('journal isolates accounts and seasons and rejects corrupt data without overwrite',()=>{
  const {run,storage}=setup();run('persistDecisionLog([createDecisionRecord()])');
  const key=run('decisionLogKey()');run('state.data.identity.season="2027-28"');assert.equal(run('loadDecisionLog().entries.length'),0);
  run('state.data.identity.season="2026-27";state.data.manager.team_id=990002');assert.equal(run('loadDecisionLog().entries.length'),0);
  run('state.data.manager.team_id=990001');storage.set(key,'not-json');assert.match(run('loadDecisionLog().error'),/อ่านประวัติไม่ได้/);assert.equal(storage.get(key),'not-json');
});
test('reported results compare only with an explicitly matching plan',()=>{
  const {run}=setup();run('const entry={expectedPoints:50,actual:{points:63,samePlan:false}}');assert.equal(run('decisionDifference(entry)'),null);
  run('entry.actual.samePlan=true');assert.equal(run('decisionDifference(entry)'),13);
});
test('storage quota failures cannot claim a successfully saved plan',()=>{
  const {run}=setup();run('localStorage.setItem=()=>{throw new Error("quota")};state.plannerSettings.selectedChip="save"');
  assert.equal(run('persistDecisionLog([])'),false);assert.throws(()=>run('savePlannerSettings()'));
  assert.equal(run('state.plannerSettings.savedAt'),null);
});
