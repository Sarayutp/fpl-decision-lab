const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Pure application-logic tests: no browser, network or real localStorage is used.
function fixture() {
  const storage = new Map();
  const context = vm.createContext({console, URL, localStorage: {
    getItem: key => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: key => storage.delete(key)
  }});
  const source = fs.readFileSync(path.join(__dirname, '../dashboard/assets/app.js'), 'utf8').replace(/\nboot\(\);\s*$/, '');
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../dashboard/assets/runtime.js'), 'utf8'), context);
  vm.runInContext(source, context);
  vm.runInContext(`
    const positions = [1,1,2,2,2,2,2,3,3,3,3,3,4,4,4,2];
    const testPlayers = positions.map((position, index) => ({id:index+1, web_name:'P'+(index+1), position_id:position, team_id:index < 15 ? index % 5 + 1 : 6, price:index===15 ? 5.5 : 5}));
    state.playerById = new Map(testPlayers.map(player => [player.id, player]));
    state.projectionById = new Map(testPlayers.map(player => {
      const xp = player.id === 8 ? 8 : player.id === 16 ? 7 : 3;
      return [player.id, {player_id:player.id, xp_next:xp, captain_score:xp, captain_eligible:true, availability:1, expected_minutes:82, start_probability:.9, projection_confidence:'medium', gameweeks:[3,4,5,6,7].map(gw => ({gameweek:gw, expected_points:xp, ranking_score:xp, expected_minutes:82, start_probability:.9, fixture_count:1, opponents:['TST (H)'], interval:{lower:1, upper:xp+3}}))}];
    }));
    state.data = {generated_at:'test-snapshot-1', identity:{season:'2026-27'}, manager:{team_id:123, bank:1, squad_value:75}, game:{next_gameweek:{id:3}}, data_quality:{is_stale:false}, analysis:{recommendations:{}}};
    const ids = testPlayers.slice(0,15).map(player => player.id);
    const weeks = [3,4,5,6,7].map(gw => plannerWeekForSquad(ids, gw));
    const first = weeks[0];
    first.picks.forEach(item => {item.starter = !first.bench.some(bench => bench.player_id === item.player_id);});
    state.data.gameweek_decision = {starting_xi:{status:'ready', formation:first.formation, squad:first.picks, players:first.picks.filter(item => item.starter), xp_starting_xi_with_captain:first.base_xp_with_captain}, captaincy:{captain:first.captain}, bench:{players:first.bench, xp_total:first.bench_boost_gain}};
    state.transferSettings = {bank:1, freeTransfers:1, sellingPrices:{'3':5}};
    const chipState = Object.fromEntries(Object.keys(CHIP_LABELS).map(chip => [chip, {available:chip !== 'bench_boost', used_events:chip==='bench_boost'?[2]:[], period:1}]));
    const chips = Object.fromEntries(Object.keys(CHIP_LABELS).map(chip => {
      const gain = chip === 'triple_captain' ? 8 : chip === 'bench_boost' ? 12 : 0;
      return [chip, {chip, current_gain:gain, best_visible_gain:gain, best_visible_gameweek:3, available:chipState[chip].available, confidence_gate_passed:false, reasons:[{kind:'estimate',text:'original'}], weekly_gains:[3,4,5,6,7].map(gameweek => ({gameweek,gain}))}];
    }));
    const moves = [{gameweek:3, out_player_id:3, in_player_id:16, out_name:'P3', in_name:'P16', bank_after:.5}];
    const transferPath = {valid:true, moves, resulting_squad_ids:ids.map(id=>id===3?16:id), weekly:weeks.map(week=>({gameweek:week.gameweek,squad_ids:ids.map(id=>id===3?16:id)})), budget_checkpoints:weeks.map(week=>({gameweek:week.gameweek,legal:true}))};
    state.data.analysis.recommendations.chip_planner = {status:'ready', version:'chip-planner-1.0', horizon:{gameweeks:[3,4,5,6,7]}, chip_state:chipState, chips, weekly:weeks, transfer_paths:{main:transferPath,alternative:transferPath}};
    state.plannerSettings = defaultPlannerSettings();
  `, context);
  return code => vm.runInContext(code, context);
}

module.exports = {fixture};

test('expired pending overrides cannot block a new Gameweek', () => {
  const run = fixture();
  run("state.plannerSettings.targetGameweek=2; state.plannerSettings.chipOverrides={free_hit:'pending'};");
  assert.equal(run("effectivePlanner().chips.triple_captain.available"), true);
  assert.equal(run("effectivePlanner().chips.bench_boost.available"), false);
});

test('pending chip enforces one chip and cannot override public usage', () => {
  const run = fixture();
  run("state.plannerSettings.chipOverrides={free_hit:'pending',bench_boost:'available'};");
  assert.equal(run("effectivePlanner().chips.triple_captain.available"), false);
  assert.equal(run("effectivePlanner().chips.bench_boost.available"), false);
  assert.equal(run("effectivePlanner().chips.free_hit.available"), true);
});

test('saved plan persists transfers and expires on GW or assumption changes', () => {
  const run = fixture();
  run("state.plannerSettings.selectedChip='save'; state.plannerSettings.selectedPath='main'; savePlannerSettings(); state.plannerSettings=loadPlannerSettings();");
  assert.equal(run("state.plannerSettings.savedPlan.moves[0].in_player_id"), 16);
  assert.equal(run("plannerSaveStatus()"), 'current');
  run("state.data.generated_at='test-snapshot-2';");
  assert.equal(run("plannerSaveStatus()"), 'changed');
  run("state.data.game.next_gameweek.id=4;");
  assert.equal(run("plannerSaveStatus()"), 'expired');
});

test('actual selling price can invalidate an estimated transfer path', () => {
  const run = fixture();
  assert.equal(run("effectivePlanner().transfer_paths.main.valid"), true);
  run("state.transferSettings.bank=0; state.transferSettings.sellingPrices['3']=4.5;");
  assert.equal(run("effectivePlanner().transfer_paths.main.valid"), false);
  assert.equal(run("effectivePlanner().transfer_paths.main.certified_affordable"), false);
});

test('current captain risk changes gain, recommendation and reason text', () => {
  const run = fixture();
  assert.equal(run("effectivePlanner().chips.triple_captain.action"), 'use_now');
  run("state.riskDecision=clone(state.data.gameweek_decision); state.riskDecision.captaincy.captain={...state.riskDecision.captaincy.captain, name:'Changed captain', xp_next:2, expected_minutes:30};");
  assert.equal(run("effectivePlanner().chips.triple_captain.current_gain"), 2);
  assert.equal(run("effectivePlanner().chips.triple_captain.action"), 'save');
  assert.match(run("JSON.stringify(effectivePlanner().chips.triple_captain.reasons)"), /Changed captain/);
});

test('stale snapshot cannot recommend activating a chip', () => {
  const run = fixture();
  run("state.data.data_quality.is_stale=true;");
  assert.equal(run("effectivePlanner().recommendation.action"), 'save');
});
