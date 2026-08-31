const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const zlib = require('node:zlib');
const path = require('node:path');

function setup() {
  const storage=new Map(), nodes=new Map(), draws=[];
  const data=JSON.parse(zlib.gunzipSync(Buffer.from(fs.readFileSync(path.join(__dirname,'fixtures/owned-team-gw3.json.gz.b64'),'utf8'),'base64')));
  data.generated_at=new Date().toISOString();data.data_quality.oldest_source_at=data.generated_at;
  data.data_quality.is_stale=false;data.game.next_gameweek.deadline_time=new Date(Date.now()+86400000).toISOString();
  const node=id=>{
    if(!nodes.has(id)) nodes.set(id,{value:id==='#share-card-slot'?'A':'',textContent:'',disabled:false,hidden:false,
      removeAttribute(name){delete this[name];},addEventListener(kind,fn){this[kind]=fn;}});
    return nodes.get(id);
  };
  const ctx={measureText:text=>({width:Array.from(text).length*13}),fillRect(){},fillText(text,x,y){draws.push({text,x,y});}};
  const canvas={getContext:()=>ctx,toDataURL:()=> 'data:image/png;base64,QA'};
  const document={querySelector:node,createElement:tag=>{assert.equal(tag,'canvas');return canvas;},fonts:{ready:Promise.resolve()}};
  const context=vm.createContext({console,data,document,URL,localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)}});
  for(const file of ['runtime.js','decision-log.js','scenario-compare.js','decision-card.js','app.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname,'../dashboard/assets',file),'utf8').replace(/\nboot\(\);\s*$/,''),context);
  }
  const run=code=>vm.runInContext(code,context);
  run(`state.data=data;state.identityCheck={valid:true};state.playerById=new Map(data.catalog.players.map(p=>[p.id,p]));
    state.projectionById=new Map(data.analysis.projections.map(p=>[p.player_id,p]));
    state.transferSettings={freeTransfers:1,bank:0,sellingPrices:{}};
    state.plannerSettings=defaultPlannerSettings();state.plannerSettings.selectedChip='save';
    captureComparison('A','PRIVATE_LABEL');`);
  return {run,storage,node,draws,canvas};
}

test('card uses an explicit public-data allowlist, not labels, raw risk notes or saved names',()=>{
  const {run}=setup();run(`const saved=loadComparisons();saved.slots.A.risks=['PRIVATE_RISK_URL'];
    saved.slots.A.lineup.picks[0].name='PRIVATE_SAVED_NAME';saved.slots.A.lineup.captain.name='PRIVATE_CAPTAIN';
    saved.slots.A.futureMoves=[{gameweek:4,out_player_id:1,in_player_id:2,out_name:'PRIVATE_FUTURE',in_name:'PRIVATE_IN'}];
    saved.slots.A.note='PRIVATE_NOTE';persistComparisons(saved.slots);`);
  const text=run('decisionCardText(createDecisionCard("A"))');
  for(const secret of ['PRIVATE_','990001','QA United','QA Manager','bankAfter','sellingPrices','contextKey','teamId']) assert.equal(text.includes(secret),false,secret);
  assert.deepEqual(JSON.parse(run('JSON.stringify(Object.keys(createDecisionCard("A")))')),
    ['version','slot','gameweek','title','subtitle','score','blocks']);
  assert.match(text,/Snapshot .*Z/);assert.match(text,/ไม่รับประกัน/);assert.match(text,/ไม่รวมมูลค่าชิป/);
});

test('captain, bench order and all fifteen public names match the frozen lineup',()=>{
  const {run}=setup();run('const record=loadComparisons().slots.A;const card=createDecisionCard("A");');
  const text=run('decisionCardText(card)');
  for(const name of JSON.parse(run('JSON.stringify(record.lineup.picks.map(p=>state.playerById.get(p.player_id).web_name))'))) assert.ok(text.includes(name));
  assert.ok(text.includes(run('record.lineup.captain.name')+' (C)'));
  assert.ok(text.includes(run('record.lineup.vice_captain.name')+' (VC)'));
  const bench=run('card.blocks.find(b=>b.label==="สำรอง").text');
  const names=JSON.parse(run('JSON.stringify(record.lineup.bench.filter(p=>p.position_id!==1).map(p=>p.name))'));
  names.forEach((name,i)=>assert.ok(bench.includes(`${i+1}. ${name}`)));
});

test('all chip types preserve stored net scores and never recommend a winner',()=>{
  for(const chip of ['save','triple_captain','bench_boost','free_hit','wildcard']) {
    const {run}=setup();run(`state.plannerSettings.selectedChip='${chip}';
      if('${chip}'!=='save') state.data.analysis.recommendations.chip_planner.chip_state['${chip}'].available=true;
      if(['free_hit','wildcard'].includes('${chip}')) state.data.analysis.recommendations.chip_planner.chips['${chip}'].scenario={squad_ids:currentDecision().starting_xi.squad.map(p=>p.player_id)};
      const record=captureComparison('B');const card=createDecisionCard('B');`);
    assert.equal(run('card.score'),run('record.metrics.netPoints.toFixed(2)+" xPts สุทธิ"'));
    assert.ok(run('decisionCardText(card)').includes('ไม่ใช่คำแนะนำ'));
  }
});

test('card creation leaves Planner, Journal and saved comparisons untouched',()=>{
  const {run,storage}=setup();const before=JSON.stringify([...storage]);
  run('const settings=JSON.stringify(state.plannerSettings);createDecisionCard("A");decisionCardText(createDecisionCard("A"));');
  assert.equal(run('JSON.stringify(state.plannerSettings)'),run('settings'));
  assert.equal(JSON.stringify([...storage]),before);assert.equal(run('loadDecisionLog().entries.length'),0);
});

test('stale, offline, expired, changed and wrong identity are never shareable',()=>{
  for(const change of ['state.runtime.offline=true','data.data_quality.is_stale=true',
    'data.game.next_gameweek.deadline_time=new Date(0).toISOString()','state.identityCheck.valid=false',
    'state.transferSettings.bank=1','data.analysis.model.version="xp-v2.new"','state.activeRiskAdjustments=[{player_id:1,expected_minutes:30}]',
    'data.generated_at=new Date(Date.now()+1000).toISOString()']) {
    const {run}=setup();run(change);assert.throws(()=>run('createDecisionCard("A")'),/ข้อมูลปัจจุบัน/);
  }
});

test('empty, malformed, cross-team, cross-season and cross-GW plans fail closed',()=>{
  for(const change of ['persistComparisons({A:null,B:null})','data.manager.team_id=990002','data.identity.season="2027-28"',
    'data.game.next_gameweek.id=4','localStorage.setItem(comparisonStorageKey(),"broken")']) {
    const {run}=setup();run(change);assert.throws(()=>run('createDecisionCard("A")'));
  }
  const {run}=setup();assert.throws(()=>run('createDecisionCard("C")'));
  run('state.playerById.clear()');assert.throws(()=>run('createDecisionCard("A")'),/รายชื่อ/);
});

test('preview must be reviewed again after same-context replacement, deletion or slot switch',()=>{
  for(const change of ['state.plannerSettings.selectedChip="triple_captain";captureComparison("A")',
    'persistComparisons({A:null,B:null})','document.querySelector("#share-card-slot").value="B"']) {
    const {run,node}=setup();run(`decisionCardPreview={slot:'A',recordKey:JSON.stringify(shareableComparison('A')),image:'data:image/png;base64,QA',text:'OLD'};syncDecisionCard();`);
    assert.equal(node('#share-card-copy').disabled,false);
    run(change);assert.throws(()=>run('checkedDecisionCard()'));run('syncDecisionCard()');
    assert.equal(node('#share-card-preview').hidden,true);assert.equal(node('#share-card-copy').disabled,true);
    assert.equal(node('#share-card-text').textContent,'');assert.equal(run('decisionCardPreview'),null);
  }
});

test('export guard checks the actual clock even before periodic UI refresh',()=>{
  const {run}=setup();run(`decisionCardPreview={slot:'A',recordKey:JSON.stringify(shareableComparison('A'))};
    data.game.next_gameweek.deadline_time=new Date(0).toISOString();`);
  assert.throws(()=>run('checkedDecisionCard()'),/deadline/);
});

test('wrapping retains Thai graphemes, long names and multiline content within bounds',()=>{
  const {run}=setup();
  const lines=JSON.parse(run(`JSON.stringify(cardWrappedLines('กัปตันตัวจริง\\nABCDEFGHIJKLMNOPQRSTUVWXYZ',s=>[...new Intl.Segmenter('th',{granularity:'grapheme'}).segment(s)].length,8))`));
  for(const line of lines) assert.ok([...new Intl.Segmenter('th',{granularity:'grapheme'}).segment(line)].length<=8);
  assert.equal(lines.join(''),'กัปตันตัวจริงABCDEFGHIJKLMNOPQRSTUVWXYZ');
});

test('PNG renderer draws only allowlisted text, uses dynamic height and no network resources',()=>{
  const {run,draws,canvas}=setup();run('const card=createDecisionCard("A");decisionCardImage(card)');
  assert.equal(canvas.width,800);assert.ok(canvas.height>800 && canvas.height<4000);
  for(const draw of draws) {assert.ok(draw.y+44<canvas.height);assert.ok(draw.x>=0);assert.ok(!draw.text.includes('PRIVATE_'));}
  assert.ok(draws.some(d=>d.text.includes('Snapshot')));
  const code=fs.readFileSync(path.join(__dirname,'../dashboard/assets/decision-card.js'),'utf8');
  assert.doesNotMatch(code,/fetch\(|XMLHttpRequest|sendBeacon|navigator\.share|localStorage\.setItem/);
});

test('canvas failure retains the downloadable text and disables only PNG',async()=>{
  const {run,node,canvas}=setup();canvas.getContext=()=>null;
  run('toast=()=>{};bindDecisionCardEvents()');await node('#share-card-create').click();
  assert.equal(node('#share-card-png').disabled,true);assert.equal(node('#share-card-txt').disabled,false);
  assert.match(node('#share-card-text').textContent,/GW3/);assert.equal(node('#share-card-image').hidden,true);
});
