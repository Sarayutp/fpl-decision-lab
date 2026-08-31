"use strict";

const LEGACY_STORAGE_KEY = "fpl-decision-lab:squad:v1";
const SETTINGS_KEY = "fpl-decision-lab:settings:v2";
const STORAGE_PREFIX = "fpl-decision-lab:squad:v2";
const TRANSFER_STORAGE_PREFIX = "fpl-decision-lab:transfers:v3";
const RISK_STORAGE_PREFIX = "fpl-decision-lab:risk:v4";
const PLANNER_STORAGE_PREFIX = "fpl-decision-lab:planner:v5";
const POSITION_LIMITS = { 1: 2, 2: 5, 3: 5, 4: 3 };
const POSITION_NAMES = { 1: "GKP", 2: "DEF", 3: "MID", 4: "FWD" };
const FORMATIONS = [[3,4,3], [3,5,2], [4,3,3], [4,4,2], [4,5,1], [5,2,3], [5,3,2], [5,4,1]];
const RISK_SOURCE_WEIGHT = { official_club: 4, official_competition: 3, user_override: 2, predicted_lineup: 1 };

const state = {
  data: null,
  briefing: "",
  playerById: new Map(),
  baseProjectionById: new Map(),
  projectionById: new Map(),
  teamById: new Map(),
  localSquad: [],
  transferSettings: null,
  transferScenarios: null,
  riskEntries: [],
  riskDecision: null,
  activeRiskAdjustments: [],
  plannerSettings: null,
  settings: null,
  identityCheck: null,
  tableLimit: 40,
  deadlineTimer: null,
  runtime: {offline: false, partial: false},
  loadedAt: null
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const esc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");
const formatNumber = (value) => value == null ? "—" : new Intl.NumberFormat("th-TH").format(value);
const formatDecimal = (value, digits = 1) => Number(value ?? 0).toFixed(digits);

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => element.classList.remove("show"), 2600);
}

function squadStorageKey() {
  const season = state.data.identity?.season || state.data.game.season || "unknown";
  return `${STORAGE_PREFIX}:${season}:${state.data.manager.team_id}`;
}

function loadSettings() {
  try {
    const payload = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
    const expectedTeamId = Number(payload.expectedTeamId);
    return {
      expectedTeamId: Number.isInteger(expectedTeamId) && expectedTeamId > 0
        ? expectedTeamId
        : state.data.manager.team_id
    };
  } catch {
    return { expectedTeamId: state.data.manager.team_id };
  }
}

function saveSettings(expectedTeamId) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify({
    schemaVersion: 2,
    expectedTeamId,
    updatedAt: new Date().toISOString()
  }));
}

function briefingTeamId() {
  const match = state.briefing.match(/^\s*-\s*Team ID:\s*(\d+)\s*$/m);
  return match ? Number(match[1]) : null;
}

function briefingGameweekName() {
  const match = state.briefing.match(/^\s*-\s*เป้าหมาย:\s*(.+?)\s*$/m);
  return match ? match[1] : null;
}

function validateIdentity() {
  const identity = state.data.identity || {};
  const requestedTeamId = Number(identity.requested_team_id);
  const snapshotTeamId = Number(identity.snapshot_team_id);
  const managerTeamId = Number(state.data.manager?.team_id);
  const expectedTeamId = Number(state.settings?.expectedTeamId);
  const briefingId = briefingTeamId();
  const briefingUnavailable = state.runtime.partial;
  const briefingTime = state.briefing.match(/^\s*-\s*สร้างเมื่อ:\s*(.+)\s*$/m)?.[1]?.trim();
  const briefingMatches = briefingUnavailable || (briefingId === managerTeamId
    && Date.parse(briefingTime) === Date.parse(state.data.generated_at));
  const snapshotGameweek = state.data.game.next_gameweek;
  const expectedGameweekName = snapshotGameweek?.name || "ไม่ทราบ Gameweek";
  const gameweekMatches = Number(identity.target_gameweek_id) === Number(snapshotGameweek?.id)
    && (briefingUnavailable || briefingGameweekName() === expectedGameweekName);
  const serverValid = identity.verified === true
    && requestedTeamId === snapshotTeamId
    && snapshotTeamId === managerTeamId
    && Number(state.data.gameweek_decision?.team_id) === managerTeamId
    && Number(state.data.gameweek_decision?.target_gameweek?.id) === Number(snapshotGameweek?.id)
    && briefingMatches
    && gameweekMatches;
  const expectedMatches = expectedTeamId === managerTeamId;
  return {
    valid: serverValid && expectedMatches,
    serverValid,
    expectedMatches,
    briefingMatches,
    briefingId,
    gameweekMatches,
    expectedTeamId,
    managerTeamId
  };
}

function recommendationsAllowed() {
  return state.identityCheck?.valid === true;
}

function decisionActionsAllowed() {
  if (!recommendationsAllowed() || state.runtime?.offline || !state.data?.game.next_gameweek) return false;
  if (state.data.gameweek_decision?.status === "unavailable" || state.data.gameweek_decision?.starting_xi?.status !== "ready") return false;
  const freshness = assessFreshness(state.data);
  return !freshness.stale && !freshness.deadlinePassed;
}

function renderRuntimeStatus() {
  const status = runtimeState(state.data, {...state.runtime, valid: recommendationsAllowed()});
  $("#runtime-state").textContent = status.message;
  $("#runtime-state").dataset.kind = status.kind;
  const canCopy = recommendationsAllowed() && !state.runtime.partial;
  $("#copy-briefing").disabled = !canCopy;
  $("#download-briefing").hidden = !canCopy;
  $("#save-planner").disabled = !decisionActionsAllowed();
  renderDecisionLog();
  renderComparison();
  return status;
}

function loadStoredSquad() {
  try {
    const currentKey = squadStorageKey();
    let payload = JSON.parse(localStorage.getItem(currentKey) || "null");
    if (!payload) {
      const legacy = JSON.parse(localStorage.getItem(LEGACY_STORAGE_KEY) || "null");
      if (legacy && Number(legacy.teamId) === state.data.manager.team_id) {
        payload = {
          schemaVersion: 2,
          teamId: state.data.manager.team_id,
          season: state.data.identity?.season || state.data.game.season || "unknown",
          playerIds: legacy.playerIds,
          updatedAt: legacy.updatedAt,
          migratedFrom: LEGACY_STORAGE_KEY
        };
        localStorage.setItem(currentKey, JSON.stringify(payload));
      }
    }
    if (!payload || Number(payload.teamId) !== state.data.manager.team_id) return [];
    return Array.isArray(payload.playerIds)
      ? payload.playerIds.map(Number).filter((id) => Number.isInteger(id))
      : [];
  } catch {
    return [];
  }
}

function saveSquad() {
  localStorage.setItem(squadStorageKey(), JSON.stringify({
    schemaVersion: 2,
    teamId: state.data.manager.team_id,
    season: state.data.identity?.season || state.data.game.season || "unknown",
    playerIds: state.localSquad,
    updatedAt: new Date().toISOString()
  }));
}

function transferStorageKey() {
  const season = state.data.identity?.season || state.data.game.season || "unknown";
  return `${TRANSFER_STORAGE_PREFIX}:${season}:${state.data.manager.team_id}`;
}

function loadTransferSettings() {
  const advisor = state.data.analysis?.recommendations?.transfer_advisor || {};
  const defaults = {
    freeTransfers: null,
    bank: Number(advisor.inputs?.bank ?? state.data.manager?.bank ?? 0),
    sellingPrices: {}
  };
  try {
    const payload = JSON.parse(localStorage.getItem(transferStorageKey()) || "null");
    if (!payload || Number(payload.teamId) !== state.data.manager.team_id) return defaults;
    const freeTransfers = Number(payload.freeTransfers);
    const bank = Number(payload.bank);
    const sellingPrices = Object.fromEntries(Object.entries(payload.sellingPrices || {})
      .map(([playerId, value]) => [String(Number(playerId)), Number(value)])
      .filter(([playerId, value]) => Number(playerId) > 0 && Number.isFinite(value) && value >= 3));
    return {
      freeTransfers: Number.isInteger(freeTransfers) && freeTransfers >= 1 && freeTransfers <= 5 ? freeTransfers : null,
      bank: Number.isFinite(bank) && bank >= 0 ? bank : defaults.bank,
      sellingPrices
    };
  } catch {
    return defaults;
  }
}

function saveTransferSettings() {
  localStorage.setItem(transferStorageKey(), JSON.stringify({
    schemaVersion: 3,
    teamId: state.data.manager.team_id,
    season: state.data.identity?.season || state.data.game.season || "unknown",
    freeTransfers: state.transferSettings.freeTransfers,
    bank: state.transferSettings.bank,
    sellingPrices: state.transferSettings.sellingPrices,
    updatedAt: new Date().toISOString()
  }));
}

function riskStorageKey() {
  const season = state.data.identity?.season || state.data.game.season || "unknown";
  return `${RISK_STORAGE_PREFIX}:${season}:${state.data.manager.team_id}`;
}

function loadRiskEntries() {
  try {
    const payload = JSON.parse(localStorage.getItem(riskStorageKey()) || "null");
    if (!payload || Number(payload.teamId) !== state.data.manager.team_id) return [];
    return Array.isArray(payload.entries) ? payload.entries : [];
  } catch {
    return [];
  }
}

function saveRiskEntries() {
  localStorage.setItem(riskStorageKey(), JSON.stringify({
    schemaVersion: 4,
    teamId: state.data.manager.team_id,
    season: state.data.identity?.season || state.data.game.season || "unknown",
    targetGameweek: state.data.game.next_gameweek?.id,
    entries: state.riskEntries,
    updatedAt: new Date().toISOString()
  }));
}

function plannerStorageKey() {
  const season = state.data.identity?.season || state.data.game.season || "unknown";
  return `${PLANNER_STORAGE_PREFIX}:${season}:${state.data.manager.team_id}`;
}

function defaultPlannerSettings() {
  return {
    targetGameweek: Number(state.data.game.next_gameweek?.id),
    selectedChip: null,
    selectedPath: "roll",
    chipOverrides: {},
    savedAt: null,
    savedPlan: null
  };
}

function loadPlannerSettings() {
  try {
    const payload = JSON.parse(localStorage.getItem(plannerStorageKey()) || "null");
    if (!payload || Number(payload.teamId) !== state.data.manager.team_id) return defaultPlannerSettings();
    return {
      targetGameweek: Number(payload.targetGameweek),
      selectedChip: ["save", "bench_boost", "triple_captain", "free_hit", "wildcard"].includes(payload.selectedChip) ? payload.selectedChip : null,
      selectedPath: ["main", "alternative", "roll"].includes(payload.selectedPath) ? payload.selectedPath : "roll",
      chipOverrides: Object.fromEntries(Object.entries(payload.chipOverrides || {})
        .filter(([chip, value]) => ["bench_boost", "triple_captain", "free_hit", "wildcard"].includes(chip) && ["available", "used", "pending"].includes(value))),
      savedAt: Number.isFinite(Date.parse(payload.savedAt)) ? payload.savedAt : null,
      savedPlan: payload.savedPlan || null
    };
  } catch {
    return defaultPlannerSettings();
  }
}

function plannerAssumptionKey() {
  return JSON.stringify({
    source: state.data.generated_at,
    risk: state.activeRiskAdjustments,
    transfers: state.transferSettings,
    overrides: currentPlannerOverrides()
  });
}

function currentPlannerOverrides() {
  return Number(state.plannerSettings?.targetGameweek) === Number(state.data.game.next_gameweek?.id)
    ? state.plannerSettings.chipOverrides || {} : {};
}

function plannerSaveStatus(planner = effectivePlanner()) {
  const settings = state.plannerSettings || {};
  if (!settings.savedAt) return "unsaved";
  if (Number(settings.targetGameweek) !== Number(state.data.game.next_gameweek?.id)) return "expired";
  if (settings.selectedChip !== "save" && !planner.chips?.[settings.selectedChip]?.available) return "invalid";
  if (!settings.savedPlan || settings.savedPlan.assumptionKey !== plannerAssumptionKey()) return "changed";
  return "current";
}

function beginPlannerDraft() {
  if (Number(state.plannerSettings.targetGameweek) !== Number(state.data.game.next_gameweek?.id)) {
    state.plannerSettings = defaultPlannerSettings();
  }
  state.plannerSettings.savedAt = null;
  state.plannerSettings.savedPlan = null;
}

function savePlannerSettings() {
  const targetGameweek = Number(state.data.game.next_gameweek?.id);
  const planner = effectivePlanner();
  state.plannerSettings.targetGameweek = targetGameweek;
  const path = planner.transfer_paths?.[state.plannerSettings.selectedPath];
  const chip = state.plannerSettings.selectedChip;
  state.plannerSettings.savedPlan = {
    assumptionKey: plannerAssumptionKey(),
    sourceGeneratedAt: state.data.generated_at,
    chip, path: state.plannerSettings.selectedPath,
    moves: clone(path?.moves || []),
    resultingSquadIds: clone(path?.resulting_squad_ids || currentDecision().starting_xi?.squad?.map(item => item.player_id) || []),
    replacementSquadIds: clone(planner.chips?.[chip]?.scenario?.squad_ids || []),
    priceCertified: path?.certified_affordable || false
  };
  state.plannerSettings.savedAt = new Date().toISOString();
  const persisted = writeLocal(plannerStorageKey(), {
    schemaVersion: 5,
    teamId: state.data.manager.team_id,
    season: state.data.identity?.season || state.data.game.season || "unknown",
    ...state.plannerSettings
  });
  if (!persisted) {
    state.plannerSettings.savedAt = null;
    state.plannerSettings.savedPlan = null;
    throw new Error("บันทึกแผนไม่ได้: Browser ปิด storage หรือพื้นที่เต็ม");
  }
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function riskEntryStatus(entry, now = new Date()) {
  const targetGameweek = Number(state.data.game.next_gameweek?.id);
  const published = new Date(entry.publishedAt);
  const ageHours = (now.getTime() - published.getTime()) / 3600000;
  if (!Number.isFinite(published.getTime())) return { active: false, label: "เวลาไม่ถูกต้อง", kind: "invalid", ageHours: null };
  if (published > now) return { active: false, label: "ยังไม่ถึงเวลาเผยแพร่", kind: "invalid", ageHours };
  if (Number(entry.targetGameweek) !== targetGameweek || Number(entry.expiresGameweek) < targetGameweek) {
    return { active: false, label: "หมดอายุข้าม GW", kind: "expired", ageHours };
  }
  if (ageHours > Number(state.data.analysis.risk_layer?.stale_after_hours || 24)) {
    return { active: false, label: `เก่า ${formatDecimal(ageHours, 1)} ชม.`, kind: "stale", ageHours };
  }
  return { active: true, label: `ใหม่ ${formatDecimal(Math.max(0, ageHours), 1)} ชม.`, kind: "fresh", ageHours };
}

function adjustedProjection(base, entry) {
  const item = clone(base);
  const beforeMinutes = Number(base.expected_minutes || 0);
  const beforeStart = Number(base.start_probability || 0);
  let minutes = entry.expectedMinutes == null ? beforeMinutes : Number(entry.expectedMinutes);
  let startProbability = entry.startProbability == null ? beforeStart : Number(entry.startProbability);
  if (entry.sourceTier === "predicted_lineup") {
    minutes = Math.max(beforeMinutes - 15, Math.min(beforeMinutes + 15, minutes));
    startProbability = Math.max(beforeStart - 0.15, Math.min(beforeStart + 0.15, startProbability));
  }
  minutes = Math.max(0, Math.min(90, minutes));
  startProbability = Math.max(0, Math.min(1, startProbability));
  const pointRate = beforeMinutes > 0
    ? Number(base.expected_points_next || base.xp_next || 0) / beforeMinutes
    : Number(base.model_inputs?.projected_points_per_90 || 0) / 90;
  const beforeXp = Number(base.expected_points_next || base.xp_next || 0);
  const nextXp = Math.max(0, pointRate * minutes);
  const scale = beforeXp > 0 ? nextXp / beforeXp : 0;
  const delta = nextXp - beforeXp;
  item.expected_minutes = Math.round(minutes * 100) / 100;
  item.start_probability = Math.round(startProbability * 1000) / 1000;
  item.expected_minutes_range = { lower: Math.max(0, minutes - 12), upper: Math.min(90, minutes + 12) };
  item.expected_points_next = item.xp_next = Math.round(nextXp * 100) / 100;
  item.expected_points_horizon = item.xp_horizon = Math.max(0, Math.round((Number(base.expected_points_horizon || base.xp_horizon || 0) + delta) * 100) / 100);
  item.ranking_score_next = Math.round(Number(base.ranking_score_next || 0) * scale * 100) / 100;
  item.ranking_score_horizon = Math.max(0, Math.round((Number(base.ranking_score_horizon || 0) + delta) * 100) / 100);
  item.captain_score = Math.round(Number(base.captain_score || 0) * scale * (startProbability / Math.max(beforeStart, 0.01)) * 100) / 100;
  item.captain_eligible = minutes >= 60 && startProbability >= 0.65;
  item.expected_points_range = {
    lower: Math.max(0, Math.round(Number(base.expected_points_range?.lower || 0) * scale * 100) / 100),
    upper: Math.max(0, Math.round(Number(base.expected_points_range?.upper || 0) * scale * 100) / 100)
  };
  if (item.gameweeks?.length) {
    item.gameweeks[0].expected_points = item.gameweeks[0].xp = item.expected_points_next;
    item.gameweeks[0].ranking_score = item.ranking_score_next;
    item.gameweeks[0].expected_minutes = item.expected_minutes;
    item.gameweeks[0].start_probability = item.start_probability;
    item.gameweeks[0].interval = clone(item.expected_points_range);
  }
  item.projection_confidence = "low";
  item.risk = minutes < 45 || startProbability < 0.5 ? "high" : minutes < 65 || startProbability < 0.7 ? "medium" : base.risk;
  item.data_quality_flags = [...new Set([...(base.data_quality_flags || []), "browser_risk_override", `risk_${entry.category}`])];
  item.risk_context = {
    source: "browser",
    player_id: Number(entry.playerId),
    evidence_id: entry.id,
    claim_type: ["predicted_lineup", "user_override"].includes(entry.sourceTier) ? "inference" : "fact",
    category: entry.category,
    summary: entry.summary,
    source_url: entry.sourceUrl,
    published_at: entry.publishedAt,
    expires_gameweek: entry.expiresGameweek,
    before: { expected_minutes: beforeMinutes, start_probability: beforeStart, xp_next: beforeXp },
    after: { expected_minutes: item.expected_minutes, start_probability: item.start_probability, xp_next: item.expected_points_next }
  };
  return item;
}

function applyLocalRiskLayer() {
  state.projectionById = new Map([...state.baseProjectionById].map(([id, item]) => [id, clone(item)]));
  const candidates = state.riskEntries
    .map((entry) => ({ entry, status: riskEntryStatus(entry) }))
    .filter(({ entry, status }) => status.active && (entry.expectedMinutes != null || entry.startProbability != null))
    .sort((a, b) => (RISK_SOURCE_WEIGHT[b.entry.sourceTier] || 0) - (RISK_SOURCE_WEIGHT[a.entry.sourceTier] || 0)
      || new Date(b.entry.publishedAt) - new Date(a.entry.publishedAt));
  const selected = new Map();
  candidates.forEach(({ entry }) => { if (!selected.has(Number(entry.playerId))) selected.set(Number(entry.playerId), entry); });
  state.activeRiskAdjustments = [];
  selected.forEach((entry, playerId) => {
    const base = state.baseProjectionById.get(playerId);
    if (!base) return;
    const adjusted = adjustedProjection(base, entry);
    state.projectionById.set(playerId, adjusted);
    state.activeRiskAdjustments.push(adjusted.risk_context);
  });
  state.riskDecision = buildRiskDecision();
}

function currentDecision() {
  return state.riskDecision || state.data.gameweek_decision;
}

const CHIP_LABELS = {
  bench_boost: "Bench Boost",
  triple_captain: "Triple Captain",
  free_hit: "Free Hit",
  wildcard: "Wildcard"
};

function plannerWeekForSquad(ids, gameweek) {
  const picks = ids.map((id) => {
    const player = state.playerById.get(Number(id));
    const item = projection(id);
    const row = item.gameweeks?.find(value => Number(value.gameweek) === Number(gameweek)) || {};
    const xp = Number(row.expected_points ?? row.xp ?? 0);
    const minutes = Number(row.expected_minutes ?? item.expected_minutes ?? 0);
    const start = Number(row.start_probability ?? item.start_probability ?? 0);
    return {
      player_id: Number(id), name: player?.web_name, position_id: player?.position_id,
      team_id: player?.team_id, xp_next: xp, expected_minutes: minutes, start_probability: start,
      expected_points_range: row.interval || {}, fixture_count: Number(row.fixture_count || 0),
      opponents: row.opponents || [], projection_confidence: item.projection_confidence,
      rank: Number(row.ranking_score ?? xp),
      captain_score: Number(gameweek) === Number(state.data.game.next_gameweek?.id) ? Number(item.captain_score || 0) : xp * (.7 + .3 * start) + .06 * Number(row.interval?.upper || 0),
      captain_eligible: minutes >= 60 && start >= .65 && Number(item.availability ?? 1) >= .75
    };
  });
  let best = null;
  for (const [defenders, midfielders, forwards] of FORMATIONS) {
    const required = {1: 1, 2: defenders, 3: midfielders, 4: forwards};
    const starters = Object.entries(required).flatMap(([position, count]) => picks.filter(item => item.position_id === Number(position)).sort((a, b) => b.rank - a.rank).slice(0, count));
    if (starters.length !== 11) continue;
    const score = starters.reduce((sum, item) => sum + item.rank, 0);
    if (!best || score > best.score) best = {score, starters, formation: `${defenders}-${midfielders}-${forwards}`};
  }
  if (!best) return null;
  const eligible = best.starters.filter(item => item.captain_eligible);
  const captainOrder = [...(eligible.length >= 2 ? eligible : best.starters)].sort((a, b) => b.captain_score - a.captain_score);
  const captain = captainOrder[0];
  const viceCaptain = captainOrder.find(item => item.team_id !== captain.team_id) || captainOrder[1];
  const starters = new Set(best.starters.map(item => item.player_id));
  picks.forEach(item => { item.starter = starters.has(item.player_id); });
  const bench = picks.filter(item => !item.starter).sort((a, b) => (a.position_id === 1) - (b.position_id === 1) || b.rank - a.rank);
  return {
    gameweek, formation: best.formation, captain, vice_captain: viceCaptain, bench, picks,
    base_xp_with_captain: best.starters.reduce((sum, item) => sum + item.xp_next, 0) + captain.xp_next,
    bench_boost_gain: bench.reduce((sum, item) => sum + item.xp_next, 0),
    triple_captain_gain: captain.xp_next
  };
}

function assessPlannerPath(path, ownedWeeks) {
  const revised = clone(path);
  let bank = Math.round(Number(state.transferSettings?.bank ?? state.data.manager.bank ?? 0) * 10);
  let ft = state.transferSettings?.freeTransfers ?? 1;
  let certified = Number.isInteger(state.transferSettings?.freeTransfers);
  let hit = 0;
  const initialIds = new Set((currentDecision().starting_xi?.squad || []).map(item => item.player_id));
  revised.budget_checkpoints = (path.weekly || []).map((week) => {
    const moves = (path.moves || []).filter(move => Number(move.gameweek) === Number(week.gameweek));
    moves.forEach(move => {
      const out = state.playerById.get(Number(move.out_player_id));
      const incoming = state.playerById.get(Number(move.in_player_id));
      const confirmedSell = initialIds.has(Number(move.out_player_id)) ? state.transferSettings?.sellingPrices?.[String(move.out_player_id)] : null;
      if (confirmedSell == null) certified = false;
      bank += Math.round(Number(confirmedSell ?? out?.price ?? 0) * 10) - Math.round(Number(incoming?.price || 0) * 10);
      const revisedMove = revised.moves.find(item => item.gameweek === move.gameweek && item.in_player_id === move.in_player_id);
      revisedMove.bank_after = bank / 10;
    });
    const weekHit = Math.max(0, moves.length - ft) * 4;
    hit += weekHit;
    const before = ft;
    ft = Math.min(5, Math.max(0, ft - moves.length) + 1);
    const original = path.budget_checkpoints?.find(item => Number(item.gameweek) === Number(week.gameweek));
    return {...original, gameweek: week.gameweek, bank: bank / 10, legal: original?.legal === true && bank >= 0, hit_cost: weekHit, free_transfers_before: before, free_transfers_next: ft};
  });
  const weeks = (path.weekly || []).map(week => plannerWeekForSquad(week.squad_ids, week.gameweek)).filter(Boolean);
  revised.current_week = weeks[0] || null;
  revised.estimated_horizon_gain = Math.round((weeks.reduce((sum, week) => sum + week.base_xp_with_captain, 0) - ownedWeeks.reduce((sum, week) => sum + Number(week.base_xp_with_captain || 0), 0) - hit) * 100) / 100;
  revised.hit_cost = hit;
  revised.valid = revised.budget_checkpoints.every(item => item.legal);
  revised.certified_affordable = certified && revised.valid;
  revised.assumptions_changed = state.activeRiskAdjustments.length > 0;
  return revised;
}

function effectivePlanner() {
  const planner = clone(state.data.analysis?.recommendations?.chip_planner || {});
  if (planner.status !== "ready") return planner;
  const targetGameweek = Number(state.data.game.next_gameweek?.id);
  const current = currentDecision();
  const currentWeek = planner.weekly?.find((item) => Number(item.gameweek) === targetGameweek);
  if (currentWeek && current.starting_xi?.status === "ready") {
    const captain = {...(current.captaincy?.captain || {})};
    const captainRow = projection(captain.player_id).gameweeks?.[0] || {};
    captain.fixture_count = captainRow.fixture_count || 0;
    captain.opponents = captainRow.opponents || [];
    const bench = current.bench?.players || [];
    currentWeek.formation = current.starting_xi.formation;
    currentWeek.captain = captain;
    currentWeek.bench = bench;
    currentWeek.picks = current.starting_xi.squad || [];
    currentWeek.base_xp_with_captain = Number(current.starting_xi.xp_starting_xi_with_captain || 0);
    currentWeek.bench_boost_gain = Math.round(bench.reduce((sum, item) => sum + Number(item.xp_next || 0), 0) * 100) / 100;
    currentWeek.triple_captain_gain = Math.round(Number(captain.xp_next || 0) * 100) / 100;
    currentWeek.all_15_likely_available = [...(current.starting_xi.players || []), ...bench]
      .every((item) => Number(item.start_probability || 0) >= .65);
  }
  const overrides = currentPlannerOverrides();
  const pendingChip = Object.entries(overrides)
    .find(([, value]) => value === "pending")?.[0] || null;
  ["bench_boost", "triple_captain", "free_hit", "wildcard"].forEach((chip) => {
    const evaluation = planner.chips?.[chip];
    if (!evaluation || !currentWeek) return;
    if (chip === "bench_boost") evaluation.current_gain = currentWeek.bench_boost_gain;
    if (chip === "triple_captain") evaluation.current_gain = currentWeek.triple_captain_gain;
    if (["free_hit", "wildcard"].includes(chip) && state.activeRiskAdjustments.length && evaluation.scenario?.squad_ids) {
      const scenarioWeeks = (chip === "free_hit" ? [currentWeek] : planner.weekly).map(week => {
        const rebuilt = plannerWeekForSquad(evaluation.scenario.squad_ids, week.gameweek);
        return Number(rebuilt?.base_xp_with_captain || 0) - Number(week.base_xp_with_captain || 0);
      });
      evaluation.current_gain = Math.round(scenarioWeeks.reduce((sum, value) => sum + value, 0) * 100) / 100;
      evaluation.scenario_status = "review_required";
    }
    const weekly = evaluation.weekly_gains || [];
    const targetRow = weekly.find((item) => Number(item.gameweek) === targetGameweek);
    if (targetRow) targetRow.gain = evaluation.current_gain;
    if (weekly.length) {
      const best = [...weekly].sort((a, b) => Number(b.gain) - Number(a.gain))[0];
      evaluation.best_visible_gameweek = best.gameweek;
      evaluation.best_visible_gain = Number(best.gain);
      evaluation.opportunity_cost = Math.max(0, Math.round((Number(best.gain) - Number(evaluation.current_gain)) * 100) / 100);
    }
  });
  const useNow = [];
  Object.entries(planner.chips || {}).forEach(([chip, evaluation]) => {
    const officialAvailable = planner.chip_state?.[chip]?.available === true;
    const override = overrides[chip] || "available";
    evaluation.available = officialAvailable && override !== "used" && (!pendingChip || pendingChip === chip);
    evaluation.local_status = !officialAvailable ? "official_used_or_blocked" : override;
    if (!evaluation.available) {
      evaluation.action = "unavailable";
      if (officialAvailable) evaluation.reasons = [{kind: "rule", text: override === "used" ? "คุณระบุว่าใช้ชิปนี้แล้วใน Browser" : `มี ${CHIP_LABELS[pendingChip]} รอใช้ใน Gameweek นี้`}];
      return;
    }
    evaluation.reasons = [
      {kind: "estimate", text: `${chip === "wildcard" ? "กำไรช่วงที่เหลือ" : "กำไร GW นี้"} ${formatDecimal(evaluation.current_gain, 2)}; ดีสุดที่เห็น GW${evaluation.best_visible_gameweek} ${formatDecimal(evaluation.best_visible_gain, 2)}`},
      {kind: "opportunity_cost", text: `ค่าเสียโอกาสเฉพาะชิปชุดนี้ ${formatDecimal(evaluation.opportunity_cost, 2)} แต้ม; ไม่ครอบคลุม GW นอกช่วงโมเดล`},
      ...(evaluation.reasons || []).filter(reason => reason.kind === "risk" || reason.kind === "limitation")
    ];
    if (chip === "triple_captain") {
      const captain = currentWeek?.captain || {};
      evaluation.reasons = evaluation.reasons.filter(reason => reason.kind !== "risk");
      evaluation.reasons.push({kind: "risk", text: `${captain.name || "—"}: ${formatDecimal(captain.expected_minutes, 0)} นาที, ตัวจริง ${formatDecimal(Number(captain.start_probability || 0) * 100, 0)}%, ${captain.fixture_count || 0} นัด, เพดานช่วง ${formatDecimal(captain.expected_points_range?.upper, 2)} — ต้องเช็กข่าวก่อน deadline`});
    }
    const closeToBest = Number(evaluation.current_gain) >= Number(evaluation.best_visible_gain) - .75;
    let use = false;
    if (chip === "triple_captain") {
      const captain = currentWeek?.captain || {};
      use = Number(evaluation.current_gain) >= 7 && closeToBest
        && Number(captain.expected_minutes || 0) / Math.max(1, Number(captain.fixture_count || 0)) >= 75
        && Number(captain.start_probability || 0) >= .85;
    } else if (chip === "bench_boost") {
      use = Number(evaluation.current_gain) >= 16 && closeToBest
        && currentWeek?.all_15_have_fixture === true
        && currentWeek?.all_15_likely_available === true;
    } else if (chip === "free_hit") {
      use = Number(evaluation.current_gain) >= 8 && closeToBest && evaluation.confidence_gate_passed !== false;
    } else if (chip === "wildcard") {
      use = Number(evaluation.current_gain) >= 18 && closeToBest && evaluation.confidence_gate_passed !== false;
    }
    const deadline = Date.parse(state.data.game.next_gameweek?.deadline_time);
    const passedDeadline = Number.isFinite(deadline) && deadline <= Date.now();
    if (state.data.data_quality?.is_stale || state.runtime?.offline || passedDeadline || evaluation.scenario_status === "review_required") use = false;
    if (state.runtime?.offline || passedDeadline) evaluation.reasons.push({kind: "limitation", text: "ออฟไลน์หรือผ่าน deadline แล้ว ต้องโหลดข้อมูลใหม่ก่อนตัดสินใจใช้ชิป"});
    if (state.data.data_quality?.is_stale) evaluation.reasons.push({kind: "limitation", text: "ข้อมูลเกิน 24 ชั่วโมง ต้อง refresh ก่อนแนะนำใช้ชิป"});
    if (evaluation.scenario_status === "review_required") evaluation.reasons.push({kind: "limitation", text: "ข่าวใน Browser เปลี่ยนแล้ว ตัวเลขนี้ประเมินทีมจำลองเดิมใหม่ ต้อง refresh เพื่อค้นหาทีมใหม่"});
    evaluation.action = use ? "use_now" : "save";
    if (use) useNow.push(evaluation);
  });
  if (useNow.length > 1) {
    useNow.sort((a, b) => (Number(b.current_gain) - Number(b.opportunity_cost)) - (Number(a.current_gain) - Number(a.opportunity_cost)));
    useNow.slice(1).forEach((item) => { item.action = "save"; });
  }
  const chosen = Object.values(planner.chips || {}).find((item) => item.action === "use_now");
  planner.recommendation = chosen ? {
    action: "use_now",
    chip: chosen.chip,
    label: `ใช้ ${CHIP_LABELS[chosen.chip]}`,
    headline: `ใช้ใน GW${targetGameweek} หากข่าวยังผ่านก่อน deadline`,
    confidence: "low",
    gain: chosen.current_gain,
    opportunity_cost: chosen.opportunity_cost,
    reasons: chosen.reasons || []
  } : {
    action: "save", chip: null, label: "เก็บชิป", headline: "ยังไม่ใช้ชิปใน Gameweek นี้",
    confidence: "low", gain: 0, opportunity_cost: 0,
    reasons: [{ kind: "estimate", text: "ยังไม่มีชิปที่ผ่านทั้งเกณฑ์ผลตอบแทน ความพร้อม และค่าเสียโอกาส" }]
  };
  ["main", "alternative"].forEach(key => {
    if (planner.transfer_paths?.[key]?.weekly) planner.transfer_paths[key] = assessPlannerPath(planner.transfer_paths[key], planner.weekly);
  });
  return planner;
}

function plannerChipDecision() {
  const planner = effectivePlanner();
  const currentGameweek = Number(state.data.game.next_gameweek?.id);
  const settings = state.plannerSettings || {};
  const savedForCurrent = plannerSaveStatus(planner) === "current";
  if (savedForCurrent && settings.selectedChip === "save") {
    return {
      status: "ready", action: "save", chip: null, label: "เก็บชิป", headline: "แผนที่บันทึก: ยังไม่ใช้ชิป",
      confidence: "user_input", bench_boost_xp: currentDecision().bench?.xp_total || 0,
      estimated_gain: 0, opportunity_cost: 0,
      reasons: [{ kind: "fact", text: "คุณบันทึกแผนเก็บชิปไว้ใน Browser สำหรับ Gameweek นี้" }]
    };
  }
  if (savedForCurrent && settings.selectedChip && planner.chips?.[settings.selectedChip]?.available) {
    const evaluation = planner.chips[settings.selectedChip];
    const path = planner.transfer_paths?.[settings.selectedPath];
    const pathGain = settings.selectedChip === "triple_captain" ? path?.current_week?.triple_captain_gain : settings.selectedChip === "bench_boost" ? path?.current_week?.bench_boost_gain : null;
    return {
      status: "ready", action: "use_now", chip: settings.selectedChip,
      label: `ใช้ ${CHIP_LABELS[settings.selectedChip]}`, headline: `แผนที่บันทึก: ใช้ใน GW${currentGameweek}`,
      confidence: "user_input", bench_boost_xp: currentDecision().bench?.xp_total || 0,
      estimated_gain: pathGain ?? evaluation.current_gain, opportunity_cost: evaluation.opportunity_cost,
      reasons: [{ kind: "fact", text: `คุณบันทึกตัวเลือกนี้ไว้ใน Browser${path ? " พร้อมแผนย้ายตัว (กำไรชิปคำนวณหลัง move แรก; ค่าเสียโอกาสยังอิงทีมเดิม)" : ""}` }, ...(evaluation.reasons || [])]
    };
  }
  const recommendation = planner.recommendation || {};
  return {
    status: planner.status === "ready" ? "ready" : "unavailable",
    action: recommendation.action || "save", chip: recommendation.chip || null,
    label: recommendation.label || "เก็บชิป", headline: recommendation.headline || "ยังประเมินไม่ได้",
    confidence: recommendation.confidence || "unavailable",
    bench_boost_xp: currentDecision().bench?.xp_total || 0,
    estimated_gain: recommendation.gain || 0, opportunity_cost: recommendation.opportunity_cost || 0,
    reasons: recommendation.reasons || []
  };
}

function totalAdjustedPlayerCount() {
  return new Set([
    ...(state.data.analysis.risk_layer?.adjustments || []).map((item) => Number(item.player_id)),
    ...state.activeRiskAdjustments.map((item) => Number(item.player_id))
  ]).size;
}

function projection(playerId) {
  return state.projectionById.get(Number(playerId)) || {
    xp_next: 0,
    xp_horizon: 0,
    expected_points_next: 0,
    expected_points_horizon: 0,
    ranking_score_next: 0,
    ranking_score_horizon: 0,
    captain_score: 0,
    captain_eligible: false,
    expected_minutes: 0,
    start_probability: 0,
    projection_confidence: "unavailable",
    expected_points_range: { lower: 0, upper: 0 },
    value_score: 0,
    risk: "unavailable",
    gameweeks: []
  };
}

function teamName(teamId) {
  return state.teamById.get(Number(teamId))?.short_name || "—";
}

function nextOpponent(playerId) {
  const gameweek = projection(playerId).gameweeks?.[0];
  return gameweek?.opponents?.length ? gameweek.opponents.join(" + ") : "Blank";
}

function ownedTransferPlayers() {
  const squad = currentDecision()?.starting_xi?.squad || [];
  return squad.map((item) => state.playerById.get(Number(item.player_id))).filter(Boolean);
}

function transferConfidence(values) {
  const rank = { unavailable: 0, low: 1, medium: 2, high: 3 };
  if (!values.length) return "unavailable";
  return values.reduce((lowest, value) => (rank[value] || 0) < (rank[lowest] || 0) ? value : lowest, values[0]);
}

function transferPlanKey(moves) {
  return moves.map((move) => `${move.out_player_id}:${move.in_player_id}`).sort().join("|");
}

function evaluateTransferMoves(moves) {
  const rawFreeTransfers = state.transferSettings?.freeTransfers;
  const freeTransfers = rawFreeTransfers == null ? Number.NaN : Number(rawFreeTransfers);
  const bank = Number(state.transferSettings?.bank || 0);
  const sellingPrices = state.transferSettings?.sellingPrices || {};
  const owned = ownedTransferPlayers();
  const teamCounts = {};
  owned.forEach((player) => { teamCounts[player.team_id] = (teamCounts[player.team_id] || 0) + 1; });
  moves.forEach((move) => {
    teamCounts[move.out_team_id] = (teamCounts[move.out_team_id] || 0) - 1;
    teamCounts[move.in_team_id] = (teamCounts[move.in_team_id] || 0) + 1;
  });
  const clubLegal = Math.max(0, ...Object.values(teamCounts)) <= 3;
  const missingSellingPrices = moves
    .map((move) => Number(move.out_player_id))
    .filter((playerId) => !Number.isFinite(Number(sellingPrices[String(playerId)])));
  const saleTotal = moves.reduce((sum, move) => {
    const exact = Number(sellingPrices[String(move.out_player_id)]);
    return sum + (Number.isFinite(exact) ? exact : Number(move.out_current_price));
  }, 0);
  const buyTotal = moves.reduce((sum, move) => sum + Number(move.in_price), 0);
  const bankAfter = bank + saleTotal - buyTotal;
  const hitCost = Number.isInteger(freeTransfers)
    ? Math.max(0, moves.length - freeTransfers) * 4
    : 0;
  const gross = { 1: 0, 3: 0, 5: 0 };
  const downside = { 1: 0, 3: 0, 5: 0 };
  moves.forEach((move) => {
    [1, 3, 5].forEach((horizon) => {
      gross[horizon] += Number(move.gains?.[String(horizon)] || 0);
      downside[horizon] += Number(move.downside_gains?.[String(horizon)] || 0);
    });
  });
  const net = Object.fromEntries([1, 3, 5].map((horizon) => [horizon, gross[horizon] - hitCost]));
  const downsideNet = Object.fromEntries([1, 3, 5].map((horizon) => [horizon, downside[horizon] - hitCost]));
  const confidence = transferConfidence(moves.map((move) => move.incoming_confidence || "unavailable"));
  const minMinutes = Math.min(...moves.map((move) => Number(move.incoming_expected_minutes || 0)), Infinity);
  const minStart = Math.min(...moves.map((move) => Number(move.incoming_start_probability || 0)), Infinity);
  const rollNextFt = Number.isInteger(freeTransfers) ? Math.min(5, freeTransfers + 1) : null;
  const nextFt = Number.isInteger(freeTransfers)
    ? Math.min(5, Math.max(0, freeTransfers - moves.length) + 1)
    : null;
  const valid = clubLegal && bankAfter >= -0.0001;
  const certified = valid && missingSellingPrices.length === 0;
  let recommendation = "Needs input";
  if (!valid) recommendation = "Unavailable";
  else if (moves.length === 0) recommendation = Number.isInteger(freeTransfers) ? "Roll" : "Needs input";
  else if (certified && hitCost > 0) {
    const robust = downsideNet[5] > 0 && minMinutes >= 65 && minStart >= 0.70 && ["high", "medium"].includes(confidence);
    recommendation = robust ? "Do" : net[5] > 0 ? "Consider" : "Roll";
  } else if (certified) {
    const robust = net[3] >= 2 && downsideNet[3] >= 0 && minMinutes >= 60 && ["high", "medium"].includes(confidence);
    recommendation = robust ? "Do" : net[5] > 0 ? "Consider" : "Roll";
  }
  return {
    moves,
    valid,
    certified,
    missingSellingPrices,
    bankAfter,
    hitCost,
    gross,
    net,
    downsideNet,
    confidence,
    minMinutes: Number.isFinite(minMinutes) ? minMinutes : null,
    minStart: Number.isFinite(minStart) ? minStart : null,
    nextFt,
    ftOpportunityCost: rollNextFt == null || nextFt == null ? null : rollNextFt - nextFt,
    recommendation
  };
}

function transferBeamScore(moves) {
  const bank = Number(state.transferSettings?.bank || 0);
  const sellingPrices = state.transferSettings?.sellingPrices || {};
  const spend = moves.reduce((sum, move) => {
    const exact = Number(sellingPrices[String(move.out_player_id)]);
    const sale = Number.isFinite(exact) ? exact : Number(move.out_current_price);
    return sum + Number(move.in_price) - sale;
  }, 0);
  const raw = moves.reduce((sum, move) => sum + Number(move.score || 0), 0);
  return raw - Math.max(0, spend - bank) * 1.5;
}

function horizonValue(item, horizon, field = "expected_points") {
  return (item.gameweeks || []).slice(0, horizon).reduce((sum, gameweek) => {
    if (field === "lower") return sum + Number(gameweek.interval?.lower || 0);
    return sum + Number(gameweek[field] ?? gameweek.expected_points ?? 0);
  }, 0);
}

function refreshTransferMove(move) {
  const outgoing = projection(move.out_player_id);
  const incoming = projection(move.in_player_id);
  const gains = {};
  const downsideGains = {};
  [1, 3, 5].forEach((horizon) => {
    gains[String(horizon)] = Math.round((horizonValue(incoming, horizon) - horizonValue(outgoing, horizon)) * 100) / 100;
    downsideGains[String(horizon)] = Math.round((horizonValue(incoming, horizon, "lower") - horizonValue(outgoing, horizon, "lower")) * 100) / 100;
  });
  return {
    ...move,
    gains,
    downside_gains: downsideGains,
    score: gains["5"] + 0.35 * gains["3"] + 0.15 * gains["1"],
    incoming_expected_minutes: incoming.expected_minutes,
    incoming_start_probability: incoming.start_probability,
    incoming_confidence: incoming.projection_confidence,
    incoming_risk: incoming.risk
  };
}

function bestTransferPlans(transferCount, limit = 2) {
  const pool = (state.data.analysis?.recommendations?.transfer_advisor?.candidate_moves || []).map(refreshTransferMove);
  if (!transferCount || !pool.length) return [];
  let beam = [{ moves: [], key: "", score: 0 }];
  const beamWidth = transferCount >= 4 ? 650 : 1000;
  for (let depth = 0; depth < transferCount; depth += 1) {
    const expanded = new Map();
    for (const item of beam) {
      const outgoing = new Set(item.moves.map((move) => Number(move.out_player_id)));
      const incoming = new Set(item.moves.map((move) => Number(move.in_player_id)));
      for (const move of pool) {
        if (outgoing.has(Number(move.out_player_id)) || incoming.has(Number(move.in_player_id))) continue;
        const moves = [...item.moves, move];
        const key = transferPlanKey(moves);
        const candidate = { moves, key, score: transferBeamScore(moves) };
        const existing = expanded.get(key);
        if (!existing || candidate.score > existing.score) expanded.set(key, candidate);
      }
    }
    beam = [...expanded.values()].sort((a, b) => b.score - a.score).slice(0, beamWidth);
    if (!beam.length) break;
  }
  return beam
    .filter((item) => item.moves.length === transferCount)
    .map((item) => evaluateTransferMoves(item.moves))
    .filter((plan) => plan.valid)
    .sort((a, b) => (b.net[5] + 0.35 * b.net[3] + 0.15 * b.net[1]) - (a.net[5] + 0.35 * a.net[3] + 0.15 * a.net[1]))
    .slice(0, limit);
}

function computeTransferScenarios() {
  const rawFreeTransfers = state.transferSettings?.freeTransfers;
  const freeTransfers = rawFreeTransfers == null ? Number.NaN : Number(rawFreeTransfers);
  if (!Number.isInteger(freeTransfers) || freeTransfers < 1 || freeTransfers > 5) {
    return {
      ready: false,
      scenarios: [
        { key: "roll", label: "ROLL", unavailableReason: "กรอก Free Transfer ก่อน" },
        { key: "one", label: "1 FT", unavailableReason: "กรอก Free Transfer ก่อน" },
        { key: "two", label: "2 FT", unavailableReason: "กรอก Free Transfer ก่อน" },
        { key: "hit", label: "-4", unavailableReason: "กรอก Free Transfer ก่อน" }
      ],
      recommended: null
    };
  }
  const roll = evaluateTransferMoves([]);
  const onePlans = bestTransferPlans(1);
  const twoPlans = freeTransfers >= 2 ? bestTransferPlans(2) : [];
  const hitPlans = bestTransferPlans(Math.min(6, freeTransfers + 1));
  const scenarios = [
    { key: "roll", label: "ROLL", plan: roll, alternative: null },
    { key: "one", label: "1 FT", plan: onePlans[0], alternative: onePlans[1], unavailableReason: onePlans.length ? null : "ไม่พบ 1 FT ที่อยู่ในงบ" },
    {
      key: "two", label: "2 FT", plan: twoPlans[0], alternative: twoPlans[1],
      unavailableReason: freeTransfers < 2 ? "คุณมี FT ไม่ถึง 2 ครั้ง — ดู scenario -4" : twoPlans.length ? null : "ไม่พบ 2 FT ที่อยู่ในงบ"
    },
    {
      key: "hit", label: "-4", plan: hitPlans[0], alternative: hitPlans[1],
      unavailableReason: hitPlans.length ? null : `ไม่พบแผน ${freeTransfers + 1} transfers ที่ผ่านงบ`
    }
  ];
  const actionable = scenarios
    .map((scenario) => scenario.plan)
    .filter((plan) => plan?.certified && (plan.hitCost === 0 || plan.recommendation === "Do"));
  const recommendationRank = { Do: 3, Consider: 2, Roll: 1 };
  const recommended = actionable.sort((a, b) => {
    const rankDifference = (recommendationRank[b.recommendation] || 0) - (recommendationRank[a.recommendation] || 0);
    return rankDifference || b.net[5] - a.net[5];
  })[0] || roll;
  return { ready: true, scenarios, recommended };
}

function transferVerdictLabel(value) {
  return ({ Do: "ทำ", Consider: "พิจารณา", Roll: "เก็บ FT", "Needs input": "ต้องยืนยันราคา", Unavailable: "ทำไม่ได้" })[value] || value;
}

function signedPoints(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? "+" : ""}${formatDecimal(number, 2)}`;
}

function transferMovesMarkup(plan) {
  if (!plan?.moves?.length) return '<div class="transfer-moves"><span>ไม่เปลี่ยนผู้เล่น</span></div>';
  return `<div class="transfer-moves">${plan.moves.map((move) => `
    <div class="transfer-move"><strong>${esc(move.out_name)}</strong><span>→</span><strong>${esc(move.in_name)}</strong></div>
  `).join("")}</div>`;
}

function transferScenarioCard(scenario) {
  if (!scenario.plan) {
    return `<article class="transfer-scenario-card unavailable">
      <div class="transfer-scenario-top"><span>${esc(scenario.label)}</span><em class="transfer-verdict">รอข้อมูล</em></div>
      <h3>${esc(scenario.unavailableReason || "ยังคำนวณไม่ได้")}</h3>
      <div class="transfer-moves"><span>ยังไม่มี scenario</span></div>
    </article>`;
  }
  const plan = scenario.plan;
  const tone = plan.recommendation.toLowerCase().replace(" ", "-");
  const alternative = scenario.alternative?.moves?.length
    ? scenario.alternative.moves.map((move) => `${move.out_name}→${move.in_name}`).join(" • ")
    : "ไม่มีทางเลือกที่ดีกว่าใน shortlist";
  return `<article class="transfer-scenario-card ${esc(tone)}">
    <div class="transfer-scenario-top"><span>${esc(scenario.label)}</span><em class="transfer-verdict">${esc(transferVerdictLabel(plan.recommendation))}</em></div>
    <h3>${plan.moves.length ? `${plan.moves.length} transfer${plan.moves.length > 1 ? "s" : ""}` : "เก็บ Free Transfer"}</h3>
    ${transferMovesMarkup(plan)}
    <div class="transfer-gain-grid">
      <div><span>สุทธิ 1 GW</span><strong>${signedPoints(plan.net[1])}</strong></div>
      <div><span>สุทธิ 3 GW</span><strong>${signedPoints(plan.net[3])}</strong></div>
      <div><span>สุทธิ 5 GW</span><strong>${signedPoints(plan.net[5])}</strong></div>
    </div>
    <div class="transfer-scenario-meta">
      <span>Hit ${plan.hitCost ? `-${plan.hitCost}` : "0"} • เงินเหลือ ${formatDecimal(plan.bankAfter)}m • FT รอบถัดไป ${plan.nextFt ?? "—"}</span>
      <span>Downside 5 GW ${signedPoints(plan.downsideNet[5])} • นาทีต่ำสุด ${plan.minMinutes == null ? "—" : formatDecimal(plan.minMinutes, 0)}</span>
      <span>${plan.certified ? "✓ งบยืนยันจากราคาขายที่กรอก" : `! ยังขาดราคาขาย ${plan.missingSellingPrices.length} คนในแผนนี้`}</span>
    </div>
    <p class="transfer-alternative"><strong>ทางเลือก:</strong> ${esc(alternative)}</p>
  </article>`;
}

function renderSellingPrices() {
  const owned = ownedTransferPlayers().sort((a, b) => a.position_id - b.position_id || a.web_name.localeCompare(b.web_name));
  const sellingPrices = state.transferSettings?.sellingPrices || {};
  const completed = owned.filter((player) => Number.isFinite(Number(sellingPrices[String(player.id)]))).length;
  $("#selling-price-progress").textContent = `${completed}/${owned.length}`;
  $("#selling-price-grid").innerHTML = owned.map((player) => {
    const value = sellingPrices[String(player.id)];
    return `<div class="selling-price-row"><label><span><strong>${esc(player.web_name)}</strong><small>${esc(POSITION_NAMES[player.position_id])} • ปัจจุบัน ${formatDecimal(player.price)}m</small></span><input type="number" min="3" max="20" step="0.1" inputmode="decimal" data-selling-price-id="${player.id}" value="${value == null ? "" : esc(value)}" placeholder="${formatDecimal(player.price)}" aria-label="ราคาขายจริง ${esc(player.web_name)}"></label></div>`;
  }).join("");
}

function renderTransferAdvisor() {
  if (!recommendationsAllowed()) {
    $("#transfer-advisor-status").textContent = "Team ID ไม่ตรง";
    $("#transfer-advisor-status").classList.add("invalid");
    $("#transfer-scenario-grid").innerHTML = '<div class="blocked-state">แก้ Team ID ให้ตรงก่อนใช้ Transfer Advisor</div>';
    return;
  }
  $("#transfer-free-transfers").value = state.transferSettings.freeTransfers || "";
  $("#transfer-bank").value = formatDecimal(state.transferSettings.bank, 1);
  renderSellingPrices();
  state.transferScenarios = computeTransferScenarios();
  const status = $("#transfer-advisor-status");
  status.classList.toggle("invalid", !state.transferScenarios.ready);
  status.textContent = state.transferScenarios.ready ? "✓ คำนวณ scenarios แล้ว" : "กรอก FT ก่อน";
  $("#transfer-scenario-grid").innerHTML = state.transferScenarios.scenarios.map(transferScenarioCard).join("");
}

function updateTransferAdvice() {
  saveTransferSettings();
  renderTransferAdvisor();
  renderPlanner();
  renderDecisionCenter();
  renderBriefing();
}

function updateCountdown(deadlineIso) {
  if (state.deadlineTimer) clearInterval(state.deadlineTimer);
  const target = deadlineIso ? new Date(deadlineIso) : null;
  const draw = () => {
    if (!target || Number.isNaN(target.getTime())) {
      $("#countdown").textContent = "จบฤดูกาล";
      return;
    }
    const milliseconds = target.getTime() - Date.now();
    if (milliseconds <= 0) {
      $("#countdown").textContent = "ปิดรับทีมแล้ว";
      return;
    }
    const seconds = Math.floor(milliseconds / 1000);
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = seconds % 60;
    $("#countdown").textContent = `${days} วัน ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
  };
  draw();
  state.deadlineTimer = setInterval(draw, 1000);
}

function renderIdentity() {
  const identity = state.data.identity;
  const quality = state.data.data_quality;
  const next = state.data.game.next_gameweek;
  const check = state.identityCheck;
  const managerName = identity.manager_name || "ไม่เปิดเผยชื่อผู้จัดการ";
  const teamNameLabel = identity.team_name || `FPL Team ${identity.snapshot_team_id}`;

  $("#identity-team-name").textContent = teamNameLabel;
  $("#identity-manager-name").textContent = managerName;
  $("#identity-team-id").textContent = `Team ID ${identity.snapshot_team_id}`;
  $("#identity-season").textContent = `ฤดูกาล ${identity.season}`;
  $("#identity-gameweek").textContent = next?.name || "จบฤดูกาล";
  $("#identity-squad-source").textContent = state.data.team.source_status === "published"
    ? `ทีมที่ประกาศล่าสุด GW${state.data.team.published_gameweek}`
    : "รอทีมสาธารณะ — ใช้ Squad Lab";
  $("#identity-source-time").textContent = quality.oldest_source_at
    ? `ต้นทางเก่าสุด ${new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short" }).format(new Date(quality.oldest_source_at))}`
    : "ไม่ทราบเวลาต้นทาง";
  $("#team-id-input").value = String(check.expectedTeamId);

  const status = $("#identity-status");
  const alert = $("#identity-alert");
  status.classList.toggle("invalid", !check.valid);
  if (check.valid) {
    status.textContent = "✓ ยืนยันทีมแล้ว";
    alert.hidden = true;
  } else {
    status.textContent = "หยุดคำแนะนำ";
    alert.hidden = false;
    alert.innerHTML = check.serverValid
      ? `<strong>Team ID ไม่ตรงกัน</strong><span>คุณตั้งใจดูทีม ${esc(check.expectedTeamId)} แต่ snapshot นี้เป็นทีม ${esc(check.managerTeamId)} ระบบจึงหยุดคำแนะนำทั้งหมด</span>`
      : !check.briefingMatches
        ? `<strong>Snapshot กับ Briefing ไม่ตรงกัน</strong><span>Briefing เป็นทีม ${esc(check.briefingId ?? "ไม่ทราบ")} แต่ snapshot เป็นทีม ${esc(check.managerTeamId)} กรุณา build ใหม่</span>`
        : !check.gameweekMatches
          ? "<strong>Gameweek ไม่ตรงกัน</strong><span>Snapshot, identity และ briefing ต้องเป็น Gameweek เดียวกัน กรุณา refresh และ build ใหม่</span>"
        : "<strong>Snapshot ไม่ผ่านการยืนยัน</strong><span>Team ID ภายในไฟล์ไม่ตรงกัน กรุณารัน data refresh ใหม่</span>";
  }

  const staleAlert = $("#freshness-alert");
  staleAlert.hidden = !quality.is_stale;
  if (quality.is_stale) {
    staleAlert.innerHTML = `<strong>ข้อมูลเกิน ${esc(quality.stale_after_hours)} ชั่วโมง</strong><span>ข้อมูลต้นทางมีอายุ ${formatDecimal(quality.age_hours, 1)} ชั่วโมง โปรด refresh และตรวจสอบก่อนใช้คำแนะนำ</span>`;
  }
}

function confidenceLabel(value) {
  return ({ high: "สูง", medium: "ปานกลาง", low: "ต่ำ", unavailable: "ยังประเมินไม่ได้", user_input: "ผู้ใช้เลือกเอง" })[value] || value || "—";
}

function reasonDetails(reasons = []) {
  if (!reasons.length) return "";
  const labels = { fact: "ข้อเท็จจริง", estimate: "ค่าประมาณ", limitation: "ข้อจำกัด", rule: "กติกา", opportunity_cost: "ค่าเสียโอกาส", risk: "ความเสี่ยง" };
  return `<details class="decision-reasons"><summary>ดูเหตุผล</summary>${reasons.map((reason) => `
    <p><span class="reason-kind ${esc(reason.kind)}">${esc(labels[reason.kind] || reason.kind)}</span>${esc(reason.text)}</p>
  `).join("")}</details>`;
}

function decisionCard({ number, title, label, headline, detail, confidence, reasons, tone = "default" }) {
  return `<article class="decision-card ${esc(tone)}">
    <div class="decision-card-top"><span>${esc(number)}</span><strong>${esc(title)}</strong><em>${esc(label)}</em></div>
    <h2>${esc(headline)}</h2>
    <p>${esc(detail)}</p>
    <small>ความมั่นใจ: ${esc(confidenceLabel(confidence))}</small>
    ${reasonDetails(reasons)}
  </article>`;
}

function renderDecisionCenter() {
  const decision = currentDecision();
  const next = decision.target_gameweek;
  const identityValid = recommendationsAllowed();
  const status = $("#decision-status");
  $("#decision-title").textContent = next?.name ? `แผน ${next.name} ของคุณ` : "ยังไม่มี Gameweek ถัดไป";
  $("#decision-summary").textContent = identityValid
    ? decision.summary?.detail || "ใช้ทีมจริงของคุณเป็นฐาน"
    : "Team ID ไม่ตรงกัน ระบบหยุดคำแนะนำทั้งหมด";
  $("#decision-source").textContent = decision.source?.squad === "published"
    ? `ทีมที่ประกาศหลัง GW${decision.source.published_gameweek}`
    : "ยังไม่มีทีมสาธารณะ";
  $("#decision-deadline").textContent = next?.deadline_time
    ? `Deadline ${new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short" }).format(new Date(next.deadline_time))}`
    : "ไม่มี deadline";

  const available = identityValid && decision.status !== "unavailable";
  status.classList.toggle("invalid", !available || decision.status === "review_required");
  const timeReview = state.data.data_quality.is_stale || state.runtime.offline || Date.parse(next?.deadline_time) <= Date.now();
  status.classList.toggle("invalid", !available || timeReview || decision.status === "review_required");
  status.textContent = !identityValid
    ? "หยุดคำแนะนำ"
    : timeReview ? "อ่านเพื่ออ้างอิง — โหลดใหม่ก่อนใช้"
      : decision.status === "ready" ? "✓ แผนพร้อมตรวจข่าว"
      : decision.status === "review_required" ? "ต้อง refresh ก่อน" : "ยังแนะนำไม่ได้";

  if (!available) {
    const reason = !identityValid
      ? "แก้ Team ID ให้ตรงกับ snapshot ก่อน"
      : decision.summary?.detail || "ข้อมูลทีมยังไม่ครบ";
    $("#decision-grid").innerHTML = [
      ["01", "TRANSFER"], ["02", "STARTING XI"], ["03", "CAPTAIN / VICE"], ["04", "BENCH"], ["05", "CHIP"]
    ].map(([number, title]) => decisionCard({
      number, title, label: "ยังไม่พร้อม", headline: "ยังแนะนำไม่ได้", detail: reason,
      confidence: "unavailable", reasons: [], tone: "blocked"
    })).join("");
    $("#decision-alternatives").innerHTML = "";
    return;
  }

  const transfer = decision.transfer;
  const localTransfer = state.transferScenarios?.ready ? state.transferScenarios.recommended : null;
  const lineup = decision.starting_xi;
  const captaincy = decision.captaincy;
  const bench = decision.bench;
  const chip = plannerChipDecision();
  const captain = captaincy.captain;
  const vice = captaincy.vice_captain;
  const outfieldBench = bench.outfield_order || [];
  const benchText = outfieldBench.map((player, index) => `${index + 1}. ${player.name}`).join(" • ");
  const goalkeeperText = bench.goalkeeper ? ` • GK ${bench.goalkeeper.name}` : "";
  const localTransferHeadline = localTransfer?.moves?.length
    ? localTransfer.moves.map((move) => `${move.out_name} → ${move.in_name}`).join(" • ")
    : localTransfer ? "เก็บ Free Transfer" : transfer.headline;
  const localTransferLabel = localTransfer ? transferVerdictLabel(localTransfer.recommendation) : transfer.label;
  const transferDetail = localTransfer
    ? localTransfer.moves.length
      ? `สุทธิ ${signedPoints(localTransfer.net[1])} / ${signedPoints(localTransfer.net[3])} / ${signedPoints(localTransfer.net[5])} xPts ใน 1/3/5 GW • Hit ${localTransfer.hitCost ? `-${localTransfer.hitCost}` : "0"}`
      : "ยังไม่มีแผนที่ผ่านงบและเกณฑ์ความเสี่ยงดีกว่าการเก็บ FT"
    : "กรอก Free Transfer และราคาขายจริงใน Transfer Advisor ก่อนยืนยันแผน";
  const transferReasons = localTransfer ? [
    { kind: "estimate", text: `Downside case 5 GW ${signedPoints(localTransfer.downsideNet[5])} และคาดนาทีต่ำสุด ${localTransfer.minMinutes == null ? "—" : formatDecimal(localTransfer.minMinutes, 0)}` },
    { kind: localTransfer.certified ? "fact" : "limitation", text: localTransfer.certified ? `งบผ่านจากราคาขายที่กรอก เหลือ ${formatDecimal(localTransfer.bankAfter)}m` : "ราคาขายของผู้เล่นขาออกยังไม่ครบ จึงไม่รับรองงบ" }
  ] : transfer.reasons;

  $("#decision-grid").innerHTML = [
    decisionCard({
      number: "01", title: "TRANSFER", label: localTransferLabel, headline: localTransferHeadline,
      detail: transferDetail, confidence: localTransfer?.confidence || transfer.confidence, reasons: transferReasons,
      tone: !localTransfer?.moves?.length ? "safe" : localTransfer.recommendation === "Do" ? "primary" : "consider"
    }),
    decisionCard({
      number: "02", title: "STARTING XI", label: lineup.formation, headline: `จัดระบบ ${lineup.formation}`,
      detail: `xPts XI รวมกัปตัน ${formatDecimal(lineup.xp_starting_xi_with_captain, 2)} จากผู้เล่นที่มีอยู่จริง`,
      confidence: lineup.confidence, reasons: lineup.reasons, tone: "primary"
    }),
    decisionCard({
      number: "03", title: "CAPTAIN / VICE", label: "C / VC", headline: `${captain?.name || "—"} (C)`,
      detail: `${captain?.opponent || "—"} • ${formatDecimal(captain?.expected_minutes, 0)} นาที • ช่วง ${formatDecimal(captain?.expected_points_range?.lower, 1)}–${formatDecimal(captain?.expected_points_range?.upper, 1)} • รอง ${vice?.name || "—"}`,
      confidence: captaincy.confidence, reasons: captaincy.reasons, tone: "captain"
    }),
    decisionCard({
      number: "04", title: "BENCH ORDER", label: `${formatDecimal(bench.xp_total, 2)} xPts`,
      headline: benchText || "ยังแนะนำไม่ได้", detail: `${benchText || "ไม่มีข้อมูล"}${goalkeeperText}`,
      confidence: bench.confidence, reasons: bench.reasons
    }),
    decisionCard({
      number: "05", title: "CHIP", label: chip.label, headline: chip.headline,
      detail: `กำไรคาดการณ์ ${formatDecimal(chip.estimated_gain, 2)} • ค่าเสียโอกาสในช่วงที่เห็น ${formatDecimal(chip.opportunity_cost, 2)} • BB bench ${formatDecimal(chip.bench_boost_xp, 2)}`,
      confidence: chip.confidence, reasons: chip.reasons, tone: "chip"
    })
  ].join("");

  $("#decision-alternatives").innerHTML = decision.alternatives?.length
    ? `<strong>ทางเลือกสำรอง</strong>${decision.alternatives.map((item) => `
      <article><span>${esc(item.label)}</span><p>${esc(item.detail)}</p></article>
    `).join("")}`
    : "";
}

function renderOverview() {
  const { data } = state;
  const next = data.game.next_gameweek;
  const lineup = currentDecision().starting_xi;
  const ageHours = Number(data.data_quality.age_hours || 0);
  const freshness = $("#freshness-badge");
  freshness.textContent = ageHours < 1 ? "ข้อมูลใหม่ไม่ถึง 1 ชม." : `ข้อมูลอายุ ${Math.floor(ageHours)} ชม.`;
  freshness.classList.toggle("stale", data.data_quality.is_stale);

  $("#deadline-title").textContent = next?.name || "Season complete";
  $("#deadline-local").textContent = next
    ? new Intl.DateTimeFormat("th-TH", { dateStyle: "full", timeStyle: "short" }).format(new Date(next.deadline_time))
    : "ไม่มี deadline ถัดไป";
  updateCountdown(next?.deadline_time);
  $("#next-action").textContent = !recommendationsAllowed()
    ? "แก้ Team ID ให้ตรงกันก่อนใช้คำแนะนำ"
    : data.team.picks
      ? "ตรวจข่าว แล้วตัดสินใจ transfer ก่อนล็อกทีม"
      : "สร้างทีมเริ่มต้น 15 คน แล้วตรวจข่าวก่อนยืนยันใน FPL";

  $("#overall-rank").textContent = formatNumber(data.manager.overall_rank);
  $("#overall-points").textContent = data.manager.overall_points == null
    ? "ฤดูกาลยังไม่เริ่ม"
    : `${formatNumber(data.manager.overall_points)} คะแนน`;
  $("#recommended-xp").textContent = !recommendationsAllowed() || lineup.status === "unavailable" ? "—" : formatDecimal(lineup.xp_starting_xi_with_captain, 2);
  $("#recommended-formation").textContent = !recommendationsAllowed()
    ? "หยุดคำแนะนำ — Team ID ไม่ตรง"
    : lineup.formation ? `Formation ${lineup.formation}` : "ยังไม่มีทีมแนะนำ";
  $("#recommended-cost").textContent = !recommendationsAllowed() || data.manager.squad_value == null ? "—" : `${formatDecimal(data.manager.squad_value)}m`;
  $("#recommended-bank").textContent = !recommendationsAllowed()
    ? "ตรวจ Team ID ก่อน"
    : data.manager.bank == null ? "ไม่ทราบเงินในธนาคาร" : `ธนาคาร ${formatDecimal(data.manager.bank)}m`;
  $("#model-horizon").textContent = `${data.analysis.model.horizon} GW`;
  $("#model-version").textContent = data.analysis.model.version;
}

function renderCaptains() {
  if (!recommendationsAllowed()) {
    $("#captain-list").classList.remove("skeleton-lines");
    $("#captain-list").innerHTML = '<div class="blocked-state">คำแนะนำกัปตันถูกหยุดจนกว่า Team ID จะตรงกัน</div>';
    return;
  }
  const starters = [...(currentDecision().starting_xi.players || [])];
  const eligible = starters.filter((item) => item.expected_minutes >= 60 && item.start_probability >= 0.65);
  const candidates = (eligible.length >= 3 ? eligible : starters)
    .sort((a, b) => Number(b.captain_score ?? b.xp_next) - Number(a.captain_score ?? a.xp_next))
    .slice(0, 5);
  $("#captain-list").classList.remove("skeleton-lines");
  $("#captain-list").innerHTML = candidates.map((item, index) => `
    <div class="captain-row">
      <span class="captain-rank">${index + 1}</span>
      <div><strong>${esc(item.name)}</strong><small>${esc(teamName(item.team_id))} • ${esc(item.opponent)} • ${formatDecimal(item.expected_minutes, 0)} นาที • ${esc(confidenceLabel(item.projection_confidence))}</small></div>
      <span class="xp-number">${formatDecimal(item.xp_next, 2)}<small>xPts</small></span>
    </div>
  `).join("");
}

function renderModel() {
  const model = state.data.analysis.model;
  const labels = [
    ["Expected points", "คะแนน FPL ที่คาด โดย shrink ผลงานใหม่เข้าหา price/role prior"],
    ["Expected minutes", "ประเมินนาทีและโอกาสตัวจริงจากราคา บทบาท นาที และ starts"],
    ["Ranking score", "ใช้ expected points ร่วมกับ confidence เพื่อจัดอันดับ ไม่ใช่แต้มอีกชุด"],
    ["ช่วงความไม่แน่นอน", "แสดงช่วงคะแนน, confidence และธงคุณภาพข้อมูลต่อผู้เล่น"]
  ];
  $("#model-explainer").classList.remove("skeleton-lines");
  $("#model-explainer").innerHTML = labels.map(([title, text]) => `
    <div class="model-step"><span></span><div><strong>${title}</strong><small>${text}</small></div></div>
  `).join("") + `<p class="model-note">${esc(model.limitations.at(-1))}</p>`;
}

function renderWarnings() {
  const warnings = [
    ...state.data.diagnostics.warnings,
    ...(currentDecision().warnings || [])
  ];
  if (!recommendationsAllowed()) {
    warnings.unshift("Team ID ไม่ตรงกัน ระบบหยุดคำแนะนำเพื่อป้องกันการใช้ข้อมูลผิดทีม");
  }
  warnings.push("เช็ก press conference และ predicted lineup อีกครั้งใกล้ deadline");
  const container = $("#warning-list");
  container.classList.remove("skeleton-lines");
  container.innerHTML = warnings.length
    ? warnings.map((warning) => `<div class="warning-item">${esc(warning)}</div>`).join("")
    : '<div class="warning-item ok">ไม่พบคำเตือนจาก pipeline</div>';
}

function playerCard(pick) {
  const club = teamName(pick.team_id);
  const armband = pick.captain
    ? '<span class="armband">C</span>'
    : pick.vice_captain ? '<span class="armband vc">VC</span>' : "";
  return `<div class="player-card" data-position="${esc(pick.position)}" title="${esc(pick.name)} • ${formatDecimal(pick.price)}m">
    ${armband}<div class="shirt"><span>${esc(club)}</span></div>
    <div class="player-label"><strong>${esc(pick.name)}</strong><small>${formatDecimal(pick.xp_next, 2)} xPts • ${formatDecimal(pick.expected_minutes, 0)} นาที</small></div>
  </div>`;
}

function renderPitch(picks, pitchSelector, benchSelector) {
  const starters = picks.filter((pick) => pick.starter);
  const rows = [4, 3, 2, 1].map((positionId) => starters.filter((pick) => pick.position_id === positionId));
  $(pitchSelector).innerHTML = rows.map((row) => `<div class="pitch-row">${row.map(playerCard).join("")}</div>`).join("");
  const bench = picks.filter((pick) => !pick.starter).sort((a, b) => a.bench_order - b.bench_order);
  $(benchSelector).innerHTML = bench.map(playerCard).join("");
}

function renderRecommended() {
  const lineup = currentDecision().starting_xi;
  const validity = $("#squad-validity");
  if (!recommendationsAllowed()) {
    validity.textContent = "หยุดคำแนะนำ — Team ID ไม่ตรง";
    validity.classList.add("invalid");
    $("#recommended-pitch").innerHTML = '<div class="blocked-state">กรุณาตั้ง Team ID ให้ตรงกับ snapshot ก่อนดูทีมแนะนำ</div>';
    $("#recommended-bench").innerHTML = "";
    return;
  }
  if (lineup.status === "unavailable" || !lineup.squad?.length) {
    validity.textContent = "ยังจัด XI ไม่ได้";
    validity.classList.add("invalid");
    $("#recommended-pitch").innerHTML = '<div class="empty-state">ยังไม่มีทีมจริง 15 คนที่ใช้จัด XI ได้</div>';
    return;
  }
  validity.textContent = `✓ 11 คนจากทีมจริง • ${lineup.formation}`;
  validity.classList.remove("invalid");
  renderPitch(lineup.squad, "#recommended-pitch", "#recommended-bench");
}

function validateLocalSquad(ids) {
  const players = ids.map((id) => state.playerById.get(id)).filter(Boolean);
  const budget = Math.max(100, Number(state.data.manager?.squad_value) || 100);
  const positionCounts = {};
  const teamCounts = {};
  let cost = 0;
  for (const player of players) {
    positionCounts[player.position_id] = (positionCounts[player.position_id] || 0) + 1;
    teamCounts[player.team_id] = (teamCounts[player.team_id] || 0) + 1;
    cost += Number(player.price);
  }
  const violations = [];
  if (ids.length !== new Set(ids).size) violations.push("มีผู้เล่นซ้ำ");
  if (players.length !== 15) violations.push(`ต้องมี 15 คน (ตอนนี้ ${players.length})`);
  for (const [positionId, required] of Object.entries(POSITION_LIMITS)) {
    const actual = positionCounts[positionId] || 0;
    if (actual !== required) violations.push(`${POSITION_NAMES[positionId]} ${actual}/${required}`);
  }
  if (cost > budget + 0.0001) violations.push(`เกินงบ ${(cost - budget).toFixed(1)}m`);
  if (Math.max(0, ...Object.values(teamCounts)) > 3) violations.push("เกิน 3 คนจากสโมสรเดียว");
  return { valid: violations.length === 0, violations, cost, bank: budget - cost, budget, positionCounts, teamCounts };
}

function computeLineup(ids) {
  const validation = validateLocalSquad(ids);
  if (!validation.valid) return null;
  const selected = ids.map((id) => state.playerById.get(id));
  let best = null;
  for (const [defenders, midfielders, forwards] of FORMATIONS) {
    const required = { 1: 1, 2: defenders, 3: midfielders, 4: forwards };
    const starters = [];
    for (const [positionId, count] of Object.entries(required)) {
      const pool = selected
        .filter((player) => player.position_id === Number(positionId))
        .sort((a, b) => projection(b.id).ranking_score_next - projection(a.id).ranking_score_next);
      starters.push(...pool.slice(0, count));
    }
    const score = starters.reduce((sum, player) => sum + projection(player.id).ranking_score_next, 0);
    if (!best || score > best.score) best = { starters, score, formation: `${defenders}-${midfielders}-${forwards}` };
  }
  const captainEligible = best.starters.filter((player) => projection(player.id).captain_eligible);
  const captainPool = captainEligible.length >= 2 ? captainEligible : best.starters;
  const captainOrder = [...captainPool].sort((a, b) => projection(b.id).captain_score - projection(a.id).captain_score);
  const captain = captainOrder[0];
  const vice = captainOrder.find((player) => player.team_id !== captain.team_id) || captainOrder[1];
  const starterIds = new Set(best.starters.map((player) => player.id));
  const bench = selected
    .filter((player) => !starterIds.has(player.id))
    .sort((a, b) => (a.position_id === 1) - (b.position_id === 1) || projection(b.id).ranking_score_next - projection(a.id).ranking_score_next);
  const expectedPoints = best.starters.reduce((sum, player) => sum + projection(player.id).xp_next, 0);
  return {
    ...best,
    captainId: captain.id,
    viceId: vice.id,
    xpWithCaptain: expectedPoints + projection(captain.id).xp_next,
    bench
  };
}

function buildRiskDecision() {
  if (!state.activeRiskAdjustments.length) return null;
  const base = clone(state.data.gameweek_decision);
  const baseSquad = base.starting_xi?.squad || [];
  const ids = baseSquad.map((pick) => Number(pick.player_id));
  const lineup = computeLineup(ids);
  if (!lineup) return null;
  const basePickById = new Map(baseSquad.map((pick) => [Number(pick.player_id), pick]));
  const starterIds = new Set(lineup.starters.map((player) => player.id));
  const benchOrderById = new Map();
  let outfieldOrder = 1;
  lineup.bench.forEach((player) => {
    benchOrderById.set(player.id, player.position_id === 1 ? 4 : outfieldOrder++);
  });
  const picks = ids.map((playerId) => {
    const player = state.playerById.get(playerId);
    const item = projection(playerId);
    const starter = starterIds.has(playerId);
    return {
      ...(basePickById.get(playerId) || {}),
      ...clone(item),
      player_id: playerId,
      name: player?.web_name || basePickById.get(playerId)?.name || "—",
      team_id: player?.team_id,
      position_id: player?.position_id,
      position: POSITION_NAMES[player?.position_id],
      price: player?.price,
      starter,
      captain: playerId === lineup.captainId,
      vice_captain: playerId === lineup.viceId,
      bench_order: starter ? null : benchOrderById.get(playerId),
      opponent: nextOpponent(playerId)
    };
  });
  const starters = picks.filter((pick) => pick.starter);
  const bench = picks.filter((pick) => !pick.starter).sort((a, b) => a.bench_order - b.bench_order);
  const captain = picks.find((pick) => pick.captain);
  const vice = picks.find((pick) => pick.vice_captain);
  const confidence = transferConfidence(starters.map((pick) => pick.projection_confidence));
  const benchXp = bench.reduce((sum, pick) => sum + Number(pick.xp_next || 0), 0);
  base.starting_xi = {
    ...base.starting_xi,
    status: "ready",
    formation: lineup.formation,
    squad: picks,
    players: starters,
    xp_starting_xi_with_captain: Math.round(lineup.xpWithCaptain * 100) / 100,
    confidence,
    reasons: [
      { kind: "estimate", text: `คำนวณ XI ใหม่หลังใช้หลักฐานใน Browser ${state.activeRiskAdjustments.length} คน` },
      { kind: "limitation", text: "หลักฐานใน Browser ไม่ได้แก้ snapshot ต้นทางและหมดอายุเมื่อเปลี่ยน Gameweek" }
    ]
  };
  base.captaincy = {
    ...base.captaincy,
    status: "ready",
    headline: `${captain?.name || "—"} (C)`,
    confidence,
    captain,
    vice_captain: vice,
    alternative: { captain: vice, vice_captain: captain, label: "ทางเลือกสำรอง" },
    reasons: [
      { kind: "estimate", text: `จัดอันดับกัปตันใหม่จาก xPts, นาที และโอกาสตัวจริงหลัง Risk Check` },
      { kind: "limitation", text: "predicted lineup เป็นข้อสันนิษฐานและถูกจำกัดผลกระทบ" }
    ]
  };
  base.bench = {
    ...base.bench,
    status: "ready",
    players: bench,
    outfield_order: bench.filter((pick) => pick.position_id !== 1),
    goalkeeper: bench.find((pick) => pick.position_id === 1) || null,
    xp_total: Math.round(benchXp * 100) / 100,
    confidence,
    reasons: [{ kind: "estimate", text: "เรียงสำรองใหม่ตามคะแนนจัดอันดับหลัง Risk Check โดย GK อยู่ลำดับ 4" }]
  };
  base.chip = { ...base.chip, bench_boost_xp: Math.round(benchXp * 100) / 100 };
  base.summary = { ...base.summary, detail: `แผนนี้รวมหลักฐานใน Browser ${state.activeRiskAdjustments.length} คนแล้ว` };
  base.warnings = [...new Set([...(base.warnings || []), "มี Risk override ใน Browser โปรดเปิดแหล่งข่าวและยืนยันอีกครั้งก่อน deadline"] )];
  return base;
}

function plannerActionLabel(action) {
  return ({ use_now: "ใช้ตอนนี้", save: "เก็บไว้", unavailable: "ใช้ไม่ได้" })[action] || action || "—";
}

function renderPlanner() {
  renderComparison();
  const planner = effectivePlanner();
  const currentGameweek = Number(state.data.game.next_gameweek?.id);
  const allowed = recommendationsAllowed() && planner.status === "ready";
  const status = $("#planner-status");
  status.classList.toggle("invalid", !allowed);
  status.textContent = !recommendationsAllowed() ? "Team ID ไม่ตรง" : planner.status === "ready" ? "✓ ตรวจประวัติชิปแล้ว" : "ยังวางแผนไม่ได้";
  const gameweeks = planner.horizon?.gameweeks || [];
  $("#planner-horizon").textContent = gameweeks.length ? `ช่วง GW${gameweeks[0]}–GW${gameweeks.at(-1)}` : "ไม่มีช่วงโมเดล";
  $("#planner-visibility-warning").textContent = planner.horizon?.visibility_warning || "";
  if (!allowed) {
    $("#planner-saved-status").className = "planner-saved-status stale";
    $("#planner-saved-status").textContent = "Planner ถูกหยุดจนกว่า Team ID และ snapshot จะผ่านการยืนยัน";
    $("#planner-weekly").innerHTML = "";
    $("#planner-chip-grid").innerHTML = "";
    $("#planner-path-grid").innerHTML = "";
    return;
  }

  const savedForCurrent = Number(state.plannerSettings?.targetGameweek) === currentGameweek;
  const saved = Boolean(state.plannerSettings?.savedAt);
  const selectedChip = state.plannerSettings?.selectedChip;
  const selectedPath = state.plannerSettings?.selectedPath || "roll";
  const pathLabel = {main: "แผนหลัก", alternative: "แผนสำรอง", roll: "Roll / ไม่ย้ายตัว"}[selectedPath];
  const saveStatus = plannerSaveStatus(planner);
  const savedStatus = $("#planner-saved-status");
  savedStatus.className = `planner-saved-status ${saveStatus === "current" ? "saved" : saved ? "stale" : ""}`;
  const selectionLabel = `${selectedChip === "save" ? "เก็บชิป" : CHIP_LABELS[selectedChip] || "ยังไม่เลือกชิป"} • ${pathLabel}`;
  const saveMessage = saveStatus === "current" ? `✓ บันทึกแผน GW${currentGameweek}: ${selectionLabel}`
    : saveStatus === "expired" ? `แผนเดิม GW${state.plannerSettings.targetGameweek} หมดอายุแล้ว — เลือกใหม่สำหรับ GW${currentGameweek}`
      : saveStatus === "changed" ? `ข้อมูลหรือสมมติฐานเปลี่ยน — ตรวจและบันทึกใหม่: ${selectionLabel}`
        : saveStatus === "invalid" ? "ชิปในแผนเดิมใช้ไม่ได้แล้ว — เลือกใหม่ก่อนบันทึก"
          : `ฉบับร่าง GW${currentGameweek}: ${selectionLabel} — ยังไม่ได้บันทึก`;
  savedStatus.innerHTML = `${esc(saveMessage)} <button class="button button-ghost" type="button" data-planner-select="save">เลือกเก็บชิป</button>`;

  $("#planner-weekly").innerHTML = (planner.weekly || []).map((week) => {
    const captain = week.captain || {};
    return `<article class="planner-week-card ${Number(week.gameweek) === currentGameweek ? "current" : ""}">
      <span>GW${esc(week.gameweek)}</span>
      <strong>${esc(captain.name || "ยังไม่มีกัปตัน")}</strong>
      <small>${esc(week.formation || "—")} • XI+C ${formatDecimal(week.base_xp_with_captain, 2)}</small>
      <small>TC +${formatDecimal(week.triple_captain_gain, 2)} • BB +${formatDecimal(week.bench_boost_gain, 2)}</small>
      <small>${esc((captain.opponents || []).join(" + "))} • ${captain.fixture_count || 0} นัด</small>
      <details class="planner-detail"><summary>ดู XI และสำรอง</summary><p>XI: ${esc((week.picks || []).filter(item => item.starter).map(item => item.name).join(", "))}</p><p>สำรอง: ${esc((week.bench || []).map(item => `${item.name} ${formatDecimal(item.xp_next, 1)}`).join(" • "))}</p></details>
    </article>`;
  }).join("");

  $("#planner-chip-grid").innerHTML = Object.entries(planner.chips || {}).map(([chip, evaluation]) => {
    const stateItem = planner.chip_state?.[chip] || {};
    const officialLocked = stateItem.available !== true;
    const localStatus = officialLocked ? "used" : currentPlannerOverrides()[chip] || "available";
    const selected = savedForCurrent && selectedChip === chip;
    const reason = evaluation.reasons?.[0]?.text || "ยังไม่มีรายละเอียด";
    const used = (stateItem.used_events || []).map((item) => `GW${item}`).join(", ");
    return `<article class="planner-chip-card ${esc(evaluation.action?.replace("_", "-"))} ${selected ? "selected" : ""} ${!evaluation.available ? "unavailable" : ""}">
      <div class="planner-chip-top"><span>${esc(CHIP_LABELS[chip] || chip)}</span><em class="planner-chip-status">${esc(plannerActionLabel(evaluation.action))}</em></div>
      <h3>${esc(evaluation.action === "unavailable" ? officialLocked && used ? `ใช้แล้ว ${used}` : "ติดเงื่อนไข/สถานะบัญชี" : evaluation.action === "use_now" ? `พิจารณา GW${currentGameweek}` : `ดีสุด GW${evaluation.best_visible_gameweek || "—"}`)}</h3>
      <p>${esc(reason)}</p>
      <div class="planner-gains">
        <div><span>${chip === "wildcard" ? "ช่วงที่เหลือ" : "GW นี้"}</span><strong>${signedPoints(evaluation.current_gain)}</strong></div>
        <div><span>ดีที่สุด</span><strong>+${formatDecimal(evaluation.best_visible_gain, 2)}</strong></div>
        <div><span>เสียโอกาส</span><strong>${formatDecimal(evaluation.opportunity_cost, 2)}</strong></div>
      </div>
      ${reasonDetails(evaluation.reasons)}
      ${evaluation.scenario ? `<details class="planner-detail"><summary>ดูทีม ${esc(CHIP_LABELS[chip])} 15 คน</summary><p>${evaluation.scenario.permanent ? "เปลี่ยนทีมถาวร" : "ใช้หนึ่ง GW แล้วคืนทีมเดิม"} • ${formatDecimal(evaluation.scenario.cost)} / ${formatDecimal(evaluation.scenario.budget)}m • ยังไม่ยืนยันราคาขาย</p><p>${esc(evaluation.scenario.picks.map(item => `${item.name}${item.captain ? " (C)" : !item.starter ? " (สำรอง)" : ""}`).join(", "))}</p></details>` : ""}
      <label>สถานะในบัญชี
        <select data-planner-chip-state="${esc(chip)}" ${officialLocked ? "disabled" : ""}>
          <option value="available" ${localStatus === "available" ? "selected" : ""}>ยังมีชิป</option>
          <option value="pending" ${localStatus === "pending" ? "selected" : ""}>กดรอใช้ก่อน deadline</option>
          <option value="used" ${localStatus === "used" ? "selected" : ""}>ใช้แล้ว</option>
        </select>
      </label>
      <button class="button button-ghost" type="button" data-planner-select="${esc(chip)}" aria-pressed="${selected}" ${!evaluation.available ? "disabled" : ""}>${selected ? "✓ เลือกชิปนี้แล้ว" : "เลือกแผนนี้"}</button>
    </article>`;
  }).join("");

  $("#planner-path-grid").innerHTML = [
    ["main", "แผนหลัก"], ["alternative", "แผนสำรอง"]
  ].map(([key, label]) => {
    const path = planner.transfer_paths?.[key] || {};
    const moves = path.moves || [];
    return `<article class="planner-path-card ${selectedPath === key && savedForCurrent ? "selected" : ""}"><h3>${esc(label)}</h3>
      <div class="planner-path-moves">${moves.length ? moves.map((move) => `
        <div class="planner-path-move"><span>GW${esc(move.gameweek)}</span><div><strong>${esc(move.out_name)} → ${esc(move.in_name)}</strong><small>${esc(move.position)} • ประมาณ +${formatDecimal(move.estimated_horizon_gain, 2)} ช่วงโมเดล</small></div><em>bank ${formatDecimal(move.bank_after)}m</em></div>
      `).join("") : '<div class="empty-state">Roll — ยังไม่มี move ที่ผ่านเกณฑ์</div>'}</div>
      <p class="planner-path-meta">XI+C เทียบ Roll ${signedPoints(path.estimated_horizon_gain)} • ${path.valid ? "✓ ผ่านกฎ/งบตามสมมติฐาน" : "✕ งบไม่ผ่าน"} • ${path.certified_affordable ? "ยืนยันราคาขายแล้ว" : "ยังไม่ยืนยัน FT/ราคาขายครบ"} • Hit ${path.hit_cost || 0}</p>
      <details class="planner-detail"><summary>ตรวจงบทุก Gameweek</summary>${(path.budget_checkpoints || []).map(item => `<p>GW${item.gameweek}: bank ${formatDecimal(item.bank)}m • FT ${item.free_transfers_before} → ${item.free_transfers_next} • ${item.legal ? "ผ่าน" : "ไม่ผ่าน"}</p>`).join("")}</details>
      <button class="button button-ghost" type="button" data-planner-path="${key}" aria-pressed="${selectedPath === key}" ${!path.valid ? "disabled" : ""}>${selectedPath === key ? "✓ เลือกเส้นทางนี้แล้ว" : `เลือก${esc(label)}`}</button>
    </article>`;
  }).join("");
}

function renderLabSquad() {
  const validation = validateLocalSquad(state.localSquad);
  const lineup = computeLineup(state.localSquad);
  $("#lab-player-count").textContent = `${state.localSquad.length}/15`;
  $("#lab-cost").textContent = `${formatDecimal(validation.cost)}m`;
  $("#lab-bank").textContent = `${formatDecimal(validation.bank)}m`;
  $("#lab-xp").textContent = lineup ? formatDecimal(lineup.xpWithCaptain, 2) : "—";
  $("#lab-formation").textContent = lineup
    ? `Formation ${lineup.formation}`
    : state.localSquad.length === 15 ? "ทีมยังไม่ผ่านเงื่อนไข" : "ยังไม่ครบ 15 คน";
  const validityElement = $("#lab-validity");
  validityElement.className = `lab-validity ${validation.valid ? "valid" : state.localSquad.length ? "invalid" : ""}`;
  validityElement.textContent = validation.valid ? "✓ ทีมนี้ผ่านงบ ตำแหน่ง และโควตาสโมสร" : validation.violations.join(" • ") || "เริ่มเลือกผู้เล่นด้านล่าง";

  const container = $("#lab-squad-list");
  if (!state.localSquad.length) {
    container.className = "lab-squad-list empty-state";
    container.textContent = "เลือก “ใช้ทีมจริงในแผน” หรือเพิ่มผู้เล่นจากตาราง";
  } else {
    container.className = "lab-squad-list";
    const starterIds = new Set(lineup?.starters.map((player) => player.id) || []);
    container.innerHTML = [...state.localSquad]
      .map((id) => state.playerById.get(id))
      .filter(Boolean)
      .sort((a, b) => a.position_id - b.position_id || projection(b.id).ranking_score_next - projection(a.id).ranking_score_next)
      .map((player) => {
        const tags = [];
        if (lineup?.captainId === player.id) tags.push("C");
        if (lineup?.viceId === player.id) tags.push("VC");
        if (lineup && !starterIds.has(player.id)) tags.push("BENCH");
        return `<div class="lab-player"><div><strong>${esc(player.web_name)} ${tags.length ? `(${tags.join("/")})` : ""}</strong><small>${esc(POSITION_NAMES[player.position_id])} • ${esc(teamName(player.team_id))} • ${formatDecimal(player.price)}m • ${formatDecimal(projection(player.id).xp_next, 2)} xPts • ${formatDecimal(projection(player.id).expected_minutes, 0)} นาที</small></div><button class="remove-player" type="button" data-remove-id="${player.id}" aria-label="นำ ${esc(player.web_name)} ออกจากทีม">×</button></div>`;
      }).join("");
  }
  renderSwaps(validation);
}

function calculateSwaps(validation) {
  if (!state.localSquad.length) return [];
  const selectedIds = new Set(state.localSquad);
  const suggestions = [];
  const bank = Math.max(0, validation.bank);
  for (const outgoingId of state.localSquad) {
    const outgoing = state.playerById.get(outgoingId);
    const outgoingProjection = projection(outgoingId);
    for (const incoming of state.data.catalog.players) {
      const incomingProjection = projection(incoming.id);
      if (selectedIds.has(incoming.id) || incoming.position_id !== outgoing.position_id) continue;
      if (!incoming.can_select || incomingProjection.availability < 0.5) continue;
      if (incoming.price > outgoing.price + bank + 0.0001) continue;
      const countAfterRemoval = (validation.teamCounts[incoming.team_id] || 0) - (incoming.team_id === outgoing.team_id ? 1 : 0);
      if (countAfterRemoval >= 3) continue;
      const nextGain = incomingProjection.xp_next - outgoingProjection.xp_next;
      const horizonGain = incomingProjection.xp_horizon - outgoingProjection.xp_horizon;
      const score = nextGain + 0.35 * horizonGain;
      if (score > 0.05) suggestions.push({ outgoing, incoming, nextGain, horizonGain, score });
    }
  }
  return suggestions.sort((a, b) => b.score - a.score).slice(0, 6);
}

function renderSwaps(validation) {
  if (!recommendationsAllowed()) {
    const container = $("#swap-list");
    container.className = "swap-list blocked-state";
    container.textContent = "หยุดคำแนะนำ swap จนกว่า Team ID จะตรงกัน";
    return;
  }
  const suggestions = calculateSwaps(validation);
  const container = $("#swap-list");
  if (!suggestions.length) {
    container.className = "swap-list empty-state";
    container.textContent = state.localSquad.length ? "ไม่พบ swap ที่เพิ่ม expected points ภายใต้งบปัจจุบัน" : "จะคำนวณเมื่อมีผู้เล่นในทีม";
    return;
  }
  container.className = "swap-list";
  container.innerHTML = suggestions.map((item) => `
    <div class="swap-card">
      <div><strong>${esc(item.outgoing.web_name)}</strong><small>ออก • ${formatDecimal(item.outgoing.price)}m</small></div>
      <span class="swap-arrow">→</span>
      <div><strong>${esc(item.incoming.web_name)}</strong><small>เข้า • ${formatDecimal(item.incoming.price)}m</small></div>
      <button class="add-player" type="button" data-swap-out="${item.outgoing.id}" data-swap-in="${item.incoming.id}" aria-label="เปลี่ยน ${esc(item.outgoing.web_name)} เป็น ${esc(item.incoming.web_name)}">+${formatDecimal(item.nextGain, 2)}</button>
    </div>
  `).join("");
}

function addPlayer(playerId) {
  if (!recommendationsAllowed()) return toast("แก้ Team ID ให้ตรงกันก่อนใช้ Squad Lab");
  const id = Number(playerId);
  if (state.localSquad.includes(id)) return;
  const player = state.playerById.get(id);
  const validation = validateLocalSquad(state.localSquad);
  if (!player || state.localSquad.length >= 15) return toast("ทีมมีผู้เล่นครบ 15 คนแล้ว");
  if ((validation.positionCounts[player.position_id] || 0) >= POSITION_LIMITS[player.position_id]) return toast(`${POSITION_NAMES[player.position_id]} ครบโควตาแล้ว`);
  if ((validation.teamCounts[player.team_id] || 0) >= 3) return toast(`มีผู้เล่นจาก ${teamName(player.team_id)} ครบ 3 คนแล้ว`);
  if (validation.cost + player.price > validation.budget + 0.0001) return toast("งบไม่พอสำหรับผู้เล่นคนนี้");
  state.localSquad.push(id);
  saveSquad();
  renderLabSquad();
  renderPlayerTable();
}

function removePlayer(playerId) {
  if (!recommendationsAllowed()) return toast("แก้ Team ID ให้ตรงกันก่อนใช้ Squad Lab");
  state.localSquad = state.localSquad.filter((id) => id !== Number(playerId));
  saveSquad();
  renderLabSquad();
  renderPlayerTable();
}

function populateFilters() {
  $("#team-filter").innerHTML = '<option value="all">ทุกสโมสร</option>' + state.data.catalog.teams
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((team) => `<option value="${team.id}">${esc(team.name)}</option>`).join("");
}

function filteredPlayers() {
  const query = $("#player-search").value.trim().toLocaleLowerCase("th");
  const position = $("#position-filter").value;
  const team = $("#team-filter").value;
  const sort = $("#sort-filter").value;
  const rows = state.data.catalog.players.filter((player) => {
    const fullName = `${player.first_name} ${player.second_name} ${player.web_name}`.toLocaleLowerCase("th");
    return player.can_select
      && (!query || fullName.includes(query))
      && (position === "all" || player.position_id === Number(position))
      && (team === "all" || player.team_id === Number(team));
  });
  rows.sort((a, b) => {
    if (sort === "price_asc") return a.price - b.price || projection(b.id).ranking_score_next - projection(a.id).ranking_score_next;
    if (sort === "selected") return Number(b.selected_by_percent) - Number(a.selected_by_percent);
    return Number(projection(b.id)[sort]) - Number(projection(a.id)[sort]);
  });
  return rows;
}

function renderPlayerTable() {
  const rows = filteredPlayers();
  $("#player-result-count").textContent = `${formatNumber(rows.length)} คน`;
  $("#player-table-body").innerHTML = rows.slice(0, state.tableLimit).map((player) => {
    const item = projection(player.id);
    const selected = state.localSquad.includes(player.id);
    const addDisabled = selected || !recommendationsAllowed();
    return `<tr>
      <td><div class="player-cell"><span class="position-dot">${esc(POSITION_NAMES[player.position_id])}</span><div><strong>${esc(player.web_name)}</strong><small>${esc(teamName(player.team_id))} • ${esc(player.news || "พร้อมลง")}</small></div></div></td>
      <td>${esc(POSITION_NAMES[player.position_id])}</td>
      <td>${formatDecimal(player.price)}m</td>
      <td>${esc(nextOpponent(player.id))}</td>
      <td><strong>${formatDecimal(item.expected_points_next, 2)}</strong><small class="table-subline">อันดับ ${formatDecimal(item.ranking_score_next, 2)}</small></td>
      <td>${formatDecimal(item.expected_points_horizon, 2)}</td>
      <td>${formatDecimal(player.selected_by_percent)}%</td>
      <td><span class="risk ${esc(item.projection_confidence)}">${esc(confidenceLabel(item.projection_confidence))}</span><small class="table-subline">${formatDecimal(item.expected_minutes, 0)} นาที • ${formatDecimal(item.start_probability * 100, 0)}%</small></td>
      <td><button class="add-player ${selected ? "selected" : ""}" type="button" data-add-id="${player.id}" ${addDisabled ? "disabled" : ""} aria-label="${selected ? "อยู่ในทีมแล้ว" : !recommendationsAllowed() ? "Team ID ไม่ตรง" : `เพิ่ม ${esc(player.web_name)} เข้าทีม`}">${selected ? "✓" : "+"}</button></td>
    </tr>`;
  }).join("");
  if (!rows.length) $("#player-table-body").innerHTML = '<tr><td colspan="9" class="empty-state">ไม่พบผู้เล่น ลองเปลี่ยนคำค้นหรือตัวกรอง</td></tr>';
  $("#show-more").hidden = rows.length <= state.tableLimit;
}

function safeSourceUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function sourceTierLabel(value) {
  return ({
    official_club: "สโมสรทางการ",
    official_competition: "พรีเมียร์ลีก / FPL",
    predicted_lineup: "Predicted lineup",
    user_override: "ข้อมูลที่ยืนยันเอง"
  })[value] || value || "ไม่ทราบแหล่ง";
}

function claimTypeForSource(value) {
  return ["predicted_lineup", "user_override"].includes(value) ? "inference" : "fact";
}

function ownedSquadIds() {
  return (state.data.gameweek_decision.starting_xi?.squad || []).map((pick) => Number(pick.player_id));
}

function evidenceForPlayer(playerId) {
  const backend = (state.data.analysis.risk_layer?.evidence || [])
    .filter((item) => Number(item.player_id) === Number(playerId) && item.active)
    .map((item) => ({
      id: item.id,
      summary: item.summary,
      sourceTier: item.source_tier,
      sourceUrl: item.source_url,
      publishedAt: item.published_at,
      claimType: item.claim_type,
      category: item.category,
      label: item.source_label,
      freshness: item.freshness,
      backend: true
    }));
  const local = state.riskEntries
    .filter((item) => Number(item.playerId) === Number(playerId))
    .map((item) => ({ ...item, claimType: claimTypeForSource(item.sourceTier), ...riskEntryStatus(item), backend: false }));
  return [...local, ...backend].sort((a, b) => Number(b.active ?? true) - Number(a.active ?? true)
    || (RISK_SOURCE_WEIGHT[b.sourceTier] || 0) - (RISK_SOURCE_WEIGHT[a.sourceTier] || 0)
    || new Date(b.publishedAt) - new Date(a.publishedAt));
}

function renderRiskSources() {
  const layer = state.data.analysis.risk_layer;
  const cards = (layer.source_snapshot || []).map((source) => {
    const observed = source.observed_at ? new Date(source.observed_at) : null;
    const observedText = observed && Number.isFinite(observed.getTime())
      ? new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short" }).format(observed)
      : "ไม่ทราบเวลา";
    return `<article class="risk-source-card ${source.status === "available" || source.status === "loaded" ? "" : "warning"}">
      <span>${esc(source.kind === "fact" ? "ข้อเท็จจริง" : "หลายประเภท")}</span>
      <strong>${esc(source.source)}</strong><small>${esc(source.status)} • ตรวจเมื่อ ${esc(observedText)}</small>
    </article>`;
  });
  cards.push(`<article class="risk-source-card ${layer.warnings?.length ? "warning" : ""}">
    <span>Fallback</span><strong>${formatNumber(layer.evidence_count || 0)} evidence • ${formatNumber(layer.adjusted_player_count || 0)} adjusted</strong>
    <small>${esc(layer.warnings?.[0] || "แหล่งข่าวและกฎ validation พร้อมใช้งาน")}</small>
  </article>`);
  $("#risk-source-grid").innerHTML = cards.join("");
}

function renderRiskDesk() {
  const layer = state.data.analysis.risk_layer;
  const status = $("#risk-layer-status");
  const degraded = layer.status !== "ready" || layer.stale_curated_count > 0 || layer.invalid_curated_count > 0;
  status.textContent = !recommendationsAllowed() ? "หยุดคำแนะนำ" : degraded ? "ต้องตรวจแหล่งข่าว" : `✓ ${layer.version}`;
  status.classList.toggle("invalid", !recommendationsAllowed() || degraded);
  renderRiskSources();
  $("#risk-adjusted-count").textContent = `${formatNumber(totalAdjustedPlayerCount())} คนถูกปรับ`;

  const rows = ownedSquadIds().map((playerId) => {
    const player = state.playerById.get(playerId);
    const item = projection(playerId);
    const base = state.baseProjectionById.get(playerId) || item;
    const evidence = evidenceForPlayer(playerId);
    const context = item.risk_context;
    const pipelineAdjustment = (layer.adjustments || []).find((record) => Number(record.player_id) === playerId);
    const appliedEvidenceId = context?.evidence_id || context?.applied_evidence_id;
    const primary = evidence.find((record) => record.id === appliedEvidenceId) || evidence[0];
    const adjusted = Boolean(context);
    const url = safeSourceUrl(primary?.sourceUrl);
    const news = primary
      ? `${esc(primary.summary)}${url ? ` • <a href="${esc(url)}" target="_blank" rel="noreferrer">เปิดแหล่ง</a>` : ""}`
      : "ไม่พบข่าวเฉพาะราย — ใช้ความไม่แน่นอนของโมเดล";
    const claim = primary?.claimType || (primary?.sourceTier ? claimTypeForSource(primary.sourceTier) : null);
    const freshness = primary?.kind || primary?.freshness;
    const beforeMinutes = context?.source === "browser" ? base.expected_minutes : pipelineAdjustment?.before?.expected_minutes ?? base.expected_minutes;
    const beforeXp = context?.source === "browser" ? base.xp_next : pipelineAdjustment?.before?.expected_points_next ?? base.xp_next;
    return { player, item, primary, adjusted, news, claim, freshness, beforeMinutes, beforeXp };
  }).sort((a, b) => Number(b.adjusted) - Number(a.adjusted) || Number(Boolean(b.primary)) - Number(Boolean(a.primary)) || a.player.position_id - b.player.position_id);

  $("#risk-owned-list").innerHTML = rows.map(({ player, item, primary, adjusted, news, claim, freshness, beforeMinutes, beforeXp }) => `
    <div class="risk-player-row ${adjusted ? "adjusted" : ""}">
      <div><strong>${esc(player.web_name)}</strong><small>${esc(POSITION_NAMES[player.position_id])} • ${esc(teamName(player.team_id))} • ${esc(nextOpponent(player.id))}</small></div>
      <div class="risk-player-news">${news}<div class="risk-badges">
        <span class="risk-badge ${esc(claim || "")}">${esc(claim === "fact" ? "ข้อเท็จจริง" : claim === "inference" ? "ข้อสันนิษฐาน" : "ไม่มีข่าว")}</span>
        ${primary ? `<span class="risk-badge">${esc(sourceTierLabel(primary.sourceTier))}</span>` : ""}
        ${freshness && freshness !== "fresh" ? `<span class="risk-badge ${esc(freshness)}">${esc(freshness === "stale" ? "ข่าวเก่า" : freshness === "expired" ? "หมดอายุ" : freshness)}</span>` : ""}
        <span class="risk-badge ${esc(item.risk)}">risk ${esc(item.risk)}</span>
      </div></div>
      <div class="risk-player-impact"><strong>${formatDecimal(beforeMinutes, 0)} → ${formatDecimal(item.expected_minutes, 0)} นาที</strong><small>${formatDecimal(beforeXp, 2)} → ${formatDecimal(item.xp_next, 2)} xPts</small></div>
    </div>`).join("");

  $("#risk-local-list").innerHTML = state.riskEntries.length
    ? [...state.riskEntries].sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt)).map((entry) => {
      const player = state.playerById.get(Number(entry.playerId));
      const itemStatus = riskEntryStatus(entry);
      const claim = claimTypeForSource(entry.sourceTier);
      const url = safeSourceUrl(entry.sourceUrl);
      const impact = [entry.expectedMinutes == null ? null : `${entry.expectedMinutes} นาที`, entry.startProbability == null ? null : `${formatDecimal(entry.startProbability * 100, 0)}% ตัวจริง`].filter(Boolean).join(" • ") || "หลักฐานประกอบ ไม่มีตัวเลขปรับ";
      return `<article class="risk-local-item ${itemStatus.active ? "" : "inactive"}">
        <div><strong>${esc(player?.web_name || `Player ${entry.playerId}`)}</strong><small>${esc(sourceTierLabel(entry.sourceTier))} • ${esc(claim === "fact" ? "ข้อเท็จจริง" : "ข้อสันนิษฐาน")}</small></div>
        <p>${esc(entry.summary)}${url ? ` • <a href="${esc(url)}" target="_blank" rel="noreferrer">แหล่งข่าว</a>` : ""}<br><small>${esc(itemStatus.label)} • ${esc(impact)} • หมดอายุ GW${esc(entry.expiresGameweek)}</small></p>
        <button class="risk-remove" type="button" data-risk-remove="${esc(entry.id)}" aria-label="ลบหลักฐานของ ${esc(player?.web_name || "ผู้เล่น")}">×</button>
      </article>`;
    }).join("")
    : '<div class="empty-state">ยังไม่มีหลักฐานที่เพิ่มใน Browser — ระบบใช้ FPL status และ snapshot เป็นฐาน</div>';
}

function populateRiskForm() {
  const picks = (state.data.gameweek_decision.starting_xi?.squad || [])
    .map((pick) => state.playerById.get(Number(pick.player_id)))
    .filter(Boolean)
    .sort((a, b) => a.position_id - b.position_id || a.web_name.localeCompare(b.web_name));
  $("#risk-player").innerHTML = picks.map((player) => `<option value="${player.id}">${esc(POSITION_NAMES[player.position_id])} • ${esc(player.web_name)} (${esc(teamName(player.team_id))})</option>`).join("");
  const now = new Date();
  const localNow = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  $("#risk-published-at").value = localNow;
  $("#risk-expires-gw").value = state.data.game.next_gameweek?.id || "";
  $("#risk-expires-gw").min = state.data.game.next_gameweek?.id || 1;
}

function rerenderAfterRiskChange() {
  applyLocalRiskLayer();
  renderRiskDesk();
  renderTransferAdvisor();
  renderPlanner();
  renderDecisionCenter();
  renderOverview();
  renderCaptains();
  renderWarnings();
  renderRecommended();
  renderPlayerTable();
  renderLabSquad();
  renderBriefing();
  renderDiagnostics();
}

function localRiskBriefing() {
  const lines = ["", "## News & Risk จาก Browser", ""];
  if (!state.riskEntries.length) return `${lines.join("\n")}- ไม่มีหลักฐานเพิ่มใน Browser\n`;
  lines.push("- หลักฐานส่วนนี้เก็บเฉพาะ Browser และไม่แก้ snapshot สาธารณะ", "");
  state.riskEntries.forEach((entry) => {
    const player = state.playerById.get(Number(entry.playerId));
    const itemStatus = riskEntryStatus(entry);
    const claim = claimTypeForSource(entry.sourceTier) === "fact" ? "ข้อเท็จจริง" : "ข้อสันนิษฐาน";
    lines.push(`### ${player?.web_name || `Player ${entry.playerId}`}`);
    lines.push(`- ${claim} • ${sourceTierLabel(entry.sourceTier)} • ${itemStatus.label}`);
    lines.push(`- สรุป: ${entry.summary}`);
    lines.push(`- แหล่ง: ${entry.sourceUrl} • เวลา: ${entry.publishedAt} • หมดอายุ GW${entry.expiresGameweek}`);
    const context = projection(entry.playerId).risk_context;
    if (context?.evidence_id === entry.id) {
      lines.push(`- ผลที่ใช้จริง: ${formatDecimal(context.before.expected_minutes, 0)} → ${formatDecimal(context.after.expected_minutes, 0)} นาที; ${formatDecimal(context.before.start_probability * 100, 0)}% → ${formatDecimal(context.after.start_probability * 100, 0)}% ตัวจริง; ${formatDecimal(context.before.xp_next, 2)} → ${formatDecimal(context.after.xp_next, 2)} xPts`, "");
    } else {
      lines.push(`- ผลที่ใช้จริง: ไม่ปรับคำแนะนำ (${itemStatus.label} หรือมีแหล่งที่ลำดับสูงกว่า)`, "");
    }
  });
  return lines.join("\n");
}

function localTransferBriefing() {
  const settings = state.transferSettings;
  const scenarios = state.transferScenarios;
  if (!settings || !scenarios?.ready) {
    return "\n## Transfer Advisor จาก Browser\n\n- สถานะ: ยังไม่กรอก Free Transfer\n- ต้องกรอก FT และราคาขายจริงก่อนรับรองงบ\n";
  }
  const priceCount = Object.keys(settings.sellingPrices || {}).length;
  const lines = [
    "",
    "## Transfer Advisor จาก Browser",
    "",
    `- Free Transfer: ${settings.freeTransfers}`,
    `- เงินในธนาคาร: ${formatDecimal(settings.bank)}m`,
    `- ราคาขายที่กรอก: ${priceCount}/15 คน`,
    "- ข้อมูลส่วนนี้คำนวณใน Browser และไม่อยู่ใน snapshot สาธารณะ",
    ""
  ];
  scenarios.scenarios.forEach((scenario) => {
    const plan = scenario.plan;
    lines.push(`### ${scenario.label}`);
    if (!plan) {
      lines.push(`- สถานะ: ${scenario.unavailableReason || "ยังคำนวณไม่ได้"}`, "");
      return;
    }
    lines.push(`- คำตอบ: ${transferVerdictLabel(plan.recommendation)}`);
    lines.push(`- Transfers: ${plan.moves.length ? plan.moves.map((move) => `${move.out_name} → ${move.in_name}`).join("; ") : "Roll"}`);
    lines.push(`- Net gain 1/3/5 GW: ${signedPoints(plan.net[1])} / ${signedPoints(plan.net[3])} / ${signedPoints(plan.net[5])}`);
    lines.push(`- Hit: ${plan.hitCost ? `-${plan.hitCost}` : "0"}; downside 5 GW: ${signedPoints(plan.downsideNet[5])}`);
    lines.push(`- งบ: ${plan.certified ? "ยืนยันแล้ว" : "ยังไม่ยืนยันราคาขาย"}; เงินเหลือ ${formatDecimal(plan.bankAfter)}m`);
    lines.push(`- FT รอบถัดไป: ${plan.nextFt ?? "ไม่ทราบ"}; opportunity cost ${plan.ftOpportunityCost ?? "ไม่ทราบ"} FT`, "");
  });
  return lines.join("\n");
}

function localPlannerBriefing() {
  const planner = effectivePlanner();
  const settings = state.plannerSettings || {};
  const currentGameweek = Number(state.data.game.next_gameweek?.id);
  const saveStatus = plannerSaveStatus(planner);
  const selected = saveStatus === "current"
    ? settings.selectedChip
    : null;
  const lines = ["", "## Chip & Multi-GW Planner จาก Browser", ""];
  lines.push(`- แผนที่บันทึก GW${currentGameweek}: ${selected === "save" ? "เก็บชิป" : selected ? CHIP_LABELS[selected] : "ยังไม่ได้บันทึก"}`);
  lines.push(`- สถานะแผน: ${saveStatus} — ส่วนนี้อัปเดตตาม Browser และใช้แทนตัวเลข snapshot เมื่อข่าวเปลี่ยน`);
  lines.push(`- เส้นทางที่เลือก: ${settings.selectedPath || "roll"}`);
  (settings.savedPlan?.moves || []).forEach(move => lines.push(`- แผนที่เก็บไว้: GW${move.gameweek} ${move.out_name} → ${move.in_name}; bank ${formatDecimal(move.bank_after)}m`));
  lines.push(`- คำแนะนำปัจจุบัน: ${planner.recommendation?.label || "ยังประเมินไม่ได้"}`);
  if (selected && selected !== "save" && planner.chips?.[selected]) {
    const evaluation = planner.chips[selected];
    lines.push(`- กำไรคาดการณ์: ${formatDecimal(evaluation.current_gain, 2)}; ค่าเสียโอกาส: ${formatDecimal(evaluation.opportunity_cost, 2)}`);
  }
  Object.entries(planner.chips || {}).forEach(([chip, value]) => lines.push(`- ${CHIP_LABELS[chip]} ปัจจุบัน: ${plannerActionLabel(value.action)}, gain ${formatDecimal(value.current_gain, 2)}, opportunity cost ${formatDecimal(value.opportunity_cost, 2)}`));
  const overrides = Object.entries(currentPlannerOverrides()).filter(([, value]) => value !== "available");
  lines.push(`- สถานะที่เพิ่มใน Browser: ${overrides.length ? overrides.map(([chip, value]) => `${CHIP_LABELS[chip]}=${value}`).join(", ") : "ไม่มี"}`);
  lines.push("- สถานะนี้ไม่กดใช้ชิปหรือย้ายตัวใน FPL", "");
  return lines.join("\n");
}

function briefingText() {
  const status = runtimeState(state.data, {...state.runtime, valid: recommendationsAllowed()});
  const warning = status.kind === "ready" ? "" : `> คำเตือน ณ เวลาคัดลอก: ${status.message}\n\n`;
  return `${warning}${state.briefing.trimEnd()}\n${localRiskBriefing()}\n${localTransferBriefing()}\n${localPlannerBriefing()}`;
}

function renderBriefing() {
  if (state.runtime.partial) {
    $("#briefing-preview").textContent = "ไฟล์ Briefing ยังโหลดไม่สำเร็จ กดโหลดข้อมูลเว็บใหม่เพื่อลองอีกครั้ง คำแนะนำบนหน้านี้ยังมาจาก snapshot ที่ยืนยันทีมแล้ว";
    return;
  }
  if (!recommendationsAllowed()) {
    $("#briefing-preview").textContent = "หยุด AI Briefing: Team ID ที่ตั้งไว้ไม่ตรงกับ snapshot ปัจจุบัน";
    return;
  }
  const text = briefingText();
  $("#briefing-preview").textContent = text.length <= 9000
    ? text
    : `${text.slice(0, 6200)}\n\n… ตัดช่วงกลางใน preview …\n\n${text.slice(-2600)}`;
}

function renderDiagnostics() {
  const fetches = state.data.diagnostics.fetches;
  const modelQuality = state.data.analysis.model.quality || {};
  const stale = state.data.data_quality.is_stale || fetches.some((item) => item.source === "stale-cache");
  const modelInvalid = modelQuality.guardrails_passed === false;
  const invalid = stale || modelInvalid || !recommendationsAllowed();
  $("#system-status").textContent = !recommendationsAllowed()
    ? "Team ID ไม่ตรง"
    : stale ? "ข้อมูลบางส่วนต้องตรวจสอบ"
      : modelInvalid ? "Model guardrail ต้องตรวจสอบ" : "✓ Pipeline และ Model ปกติ";
  $("#system-status").classList.toggle("invalid", invalid);
  const distribution = modelQuality.distribution || {};
  const modelChip = `<span class="diagnostic-chip">${esc(state.data.analysis.model.version)} • ${esc(modelQuality.status || "unknown")} • p99 ${formatDecimal(distribution.p99, 2)} • max ${formatDecimal(distribution.max, 2)}</span>`;
  const transferAdvisor = state.data.analysis.recommendations.transfer_advisor;
  const transferChip = `<span class="diagnostic-chip">${esc(transferAdvisor.version)} • ${formatNumber(transferAdvisor.candidate_count)} candidates • budget gated</span>`;
  const riskLayer = state.data.analysis.risk_layer;
  const riskChip = `<span class="diagnostic-chip">${esc(riskLayer.version)} • ${esc(riskLayer.status)} • ${formatNumber(totalAdjustedPlayerCount())} adjusted</span>`;
  const planner = state.data.analysis.recommendations.chip_planner;
  const plannerChip = `<span class="diagnostic-chip">${esc(planner.version)} • ${esc(planner.status)} • ${formatNumber(planner.horizon?.count)} GW • one-chip gated</span>`;
  const releaseChip = `<span class="diagnostic-chip">เว็บ ${APP_RELEASE} • pipeline ${esc(state.data.release?.version || "legacy")} • schema ${esc(state.data.schema_version)}</span>`;
  const timeChip = `<span class="diagnostic-chip">Snapshot ${esc(state.data.generated_at)} • โหลดหน้านี้ ${esc(state.loadedAt)} • ${state.runtime.offline ? "offline cache" : "online"}</span>`;
  $("#diagnostics").innerHTML = releaseChip + timeChip + modelChip + riskChip + transferChip + plannerChip + fetches.map((item) => `<span class="diagnostic-chip">${esc(item.endpoint)} • ${esc(item.source)} • ${formatNumber(item.duration_ms)}ms</span>`).join("");
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    const copied = document.execCommand("copy");
    area.remove();
    if (!copied) throw new Error("Browser ไม่อนุญาตให้คัดลอก กรุณาดาวน์โหลดไฟล์ .md");
  }
}

function bindEvents() {
  $("#save-team-id").addEventListener("click", () => {
    const expectedTeamId = Number($("#team-id-input").value);
    if (!Number.isInteger(expectedTeamId) || expectedTeamId <= 0) {
      toast("กรุณากรอก Team ID เป็นตัวเลขที่มากกว่า 0");
      return;
    }
    saveSettings(expectedTeamId);
    location.reload();
  });
  ["#player-search", "#position-filter", "#team-filter", "#sort-filter"].forEach((selector) => {
    $(selector).addEventListener(selector === "#player-search" ? "input" : "change", () => {
      state.tableLimit = 40;
      renderPlayerTable();
    });
  });
  $("#show-more").addEventListener("click", () => { state.tableLimit += 40; renderPlayerTable(); });
  $("#transfer-free-transfers").addEventListener("change", (event) => {
    const value = Number(event.target.value);
    state.transferSettings.freeTransfers = Number.isInteger(value) && value >= 1 && value <= 5 ? value : null;
    updateTransferAdvice();
  });
  $("#transfer-bank").addEventListener("change", (event) => {
    const value = Number(event.target.value);
    if (!Number.isFinite(value) || value < 0) return toast("เงินในธนาคารต้องเป็น 0 หรือมากกว่า");
    state.transferSettings.bank = Math.round(value * 10) / 10;
    updateTransferAdvice();
  });
  $("#selling-price-grid").addEventListener("change", (event) => {
    const input = event.target.closest("[data-selling-price-id]");
    if (!input) return;
    const playerId = String(Number(input.dataset.sellingPriceId));
    const value = Number(input.value);
    if (input.value === "") delete state.transferSettings.sellingPrices[playerId];
    else if (!Number.isFinite(value) || value < 3 || value > 20) return toast("ราคาขายต้องอยู่ระหว่าง 3.0m–20.0m");
    else state.transferSettings.sellingPrices[playerId] = Math.round(value * 10) / 10;
    updateTransferAdvice();
  });
  $("#clear-transfer-settings").addEventListener("click", () => {
    localStorage.removeItem(transferStorageKey());
    state.transferSettings = {
      freeTransfers: null,
      bank: Number(state.data.analysis.recommendations.transfer_advisor.inputs?.bank || 0),
      sellingPrices: {}
    };
    renderTransferAdvisor();
    renderPlanner();
    renderDecisionCenter();
    renderBriefing();
    toast("ล้างข้อมูล Transfer Advisor แล้ว");
  });
  $("#risk-evidence-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!recommendationsAllowed()) return toast("แก้ Team ID ให้ตรงกันก่อนเพิ่มหลักฐาน");
    const sourceTier = $("#risk-source-tier").value;
    const sourceUrl = safeSourceUrl($("#risk-source-url").value.trim());
    const summary = $("#risk-summary").value.trim();
    const published = new Date($("#risk-published-at").value);
    const targetGameweek = Number(state.data.game.next_gameweek?.id);
    const expiresGameweek = Number($("#risk-expires-gw").value);
    const minutesRaw = $("#risk-minutes").value;
    const startRaw = $("#risk-start-probability").value;
    if (!summary) return toast("กรุณาสรุปข่าวหรือเหตุผล");
    if (!sourceUrl) return toast("ลิงก์แหล่งข่าวต้องขึ้นต้นด้วย http หรือ https");
    if (!Number.isFinite(published.getTime())) return toast("เวลาเผยแพร่ไม่ถูกต้อง");
    if (!Number.isInteger(expiresGameweek) || expiresGameweek < targetGameweek) return toast(`หลักฐานต้องหมดอายุ GW${targetGameweek} หรือหลังจากนั้น`);
    const expectedMinutes = minutesRaw === "" ? null : Number(minutesRaw);
    const startProbability = startRaw === "" ? null : Number(startRaw) / 100;
    if (expectedMinutes != null && (!Number.isFinite(expectedMinutes) || expectedMinutes < 0 || expectedMinutes > 90)) return toast("คาดนาทีต้องอยู่ระหว่าง 0–90");
    if (startProbability != null && (!Number.isFinite(startProbability) || startProbability < 0 || startProbability > 1)) return toast("โอกาสตัวจริงต้องอยู่ระหว่าง 0–100%");
    state.riskEntries.push({
      id: globalThis.crypto?.randomUUID?.() || `risk-${Date.now()}`,
      playerId: Number($("#risk-player").value),
      sourceTier,
      category: $("#risk-category").value,
      summary,
      sourceUrl,
      publishedAt: published.toISOString(),
      targetGameweek,
      expiresGameweek,
      expectedMinutes,
      startProbability,
      createdAt: new Date().toISOString()
    });
    saveRiskEntries();
    $("#risk-summary").value = "";
    $("#risk-source-url").value = "";
    $("#risk-minutes").value = "";
    $("#risk-start-probability").value = "";
    rerenderAfterRiskChange();
    toast(sourceTier === "predicted_lineup" ? "บันทึกเป็นข้อสันนิษฐานและจำกัดผลกระทบแล้ว" : "บันทึกหลักฐานและคำนวณคำแนะนำใหม่แล้ว");
  });
  $("#risk-local-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-risk-remove]");
    if (!button) return;
    state.riskEntries = state.riskEntries.filter((entry) => entry.id !== button.dataset.riskRemove);
    saveRiskEntries();
    rerenderAfterRiskChange();
    toast("ลบหลักฐานและคืนค่าการคำนวณแล้ว");
  });
  $("#clear-risk-evidence").addEventListener("click", () => {
    localStorage.removeItem(riskStorageKey());
    state.riskEntries = [];
    rerenderAfterRiskChange();
    toast("ล้างหลักฐานใน Browser แล้ว");
  });
  $("#chip-planner").addEventListener("change", (event) => {
    const select = event.target.closest("[data-planner-chip-state]");
    if (!select) return;
    const chip = select.dataset.plannerChipState;
    const value = select.value;
    if (!recommendationsAllowed() || state.data.analysis.recommendations.chip_planner.chip_state?.[chip]?.available !== true) return;
    beginPlannerDraft();
    if (value === "pending") {
      Object.keys(state.plannerSettings.chipOverrides).forEach((item) => {
        if (state.plannerSettings.chipOverrides[item] === "pending") state.plannerSettings.chipOverrides[item] = "available";
      });
      state.plannerSettings.selectedChip = chip;
    } else if (value === "used" && state.plannerSettings.selectedChip === chip) {
      state.plannerSettings.selectedChip = null;
    }
    state.plannerSettings.chipOverrides[chip] = value;
    state.plannerSettings.targetGameweek = Number(state.data.game.next_gameweek?.id);
    state.plannerSettings.savedAt = null;
    renderPlanner(); renderDecisionCenter(); renderBriefing();
  });
  $("#chip-planner").addEventListener("click", (event) => {
    const pathButton = event.target.closest("[data-planner-path]");
    if (pathButton && recommendationsAllowed()) {
      beginPlannerDraft();
      state.plannerSettings.selectedPath = pathButton.dataset.plannerPath;
      renderPlanner(); renderDecisionCenter(); renderBriefing();
      return;
    }
    const button = event.target.closest("[data-planner-select]");
    if (!button) return;
    if (!recommendationsAllowed()) return;
    beginPlannerDraft();
    state.plannerSettings.selectedChip = button.dataset.plannerSelect;
    state.plannerSettings.targetGameweek = Number(state.data.game.next_gameweek?.id);
    state.plannerSettings.savedAt = null;
    renderPlanner(); renderDecisionCenter(); renderBriefing();
    toast(state.plannerSettings.selectedChip === "save" ? "เลือกเก็บชิปแล้ว — กดบันทึกเพื่อยืนยันแผน" : `เลือก ${CHIP_LABELS[state.plannerSettings.selectedChip]} แล้ว — กดบันทึกเพื่อยืนยันแผน`);
  });
  $("#save-planner").addEventListener("click", () => {
    if (!decisionActionsAllowed()) return toast("ข้อมูลเก่า ออฟไลน์ หรือผ่าน deadline แล้ว กรุณาโหลดใหม่ก่อนบันทึก");
    if (Number(state.plannerSettings.targetGameweek) !== Number(state.data.game.next_gameweek?.id)) return toast("แผนเก่าหมดอายุแล้ว กรุณาเลือกแผนใหม่ก่อน");
    const planner = effectivePlanner();
    const chip = state.plannerSettings.selectedChip;
    if (!chip) return toast("เลือกชิปหรือเลือกเก็บชิปก่อนบันทึก");
    if (chip !== "save" && !planner.chips?.[chip]?.available) return toast("ชิปที่เลือกใช้ไม่ได้แล้ว กรุณาเลือกใหม่");
    const path = state.plannerSettings.selectedPath;
    if (path !== "roll" && !planner.transfer_paths?.[path]?.valid) return toast("งบของเส้นทางนี้ไม่ผ่าน กรุณาแก้ข้อมูลหรือเลือก Roll");
    if (["free_hit", "wildcard"].includes(chip) && path !== "roll") return toast("Free Hit/Wildcard เป็นทีมจำลองแยกจาก transfer ปกติ กรุณาเลือก Roll เพื่อบันทึกชิปนี้");
    try { savePlannerSettings(); } catch (error) { return toast(error.message); }
    renderPlanner(); renderDecisionCenter(); renderBriefing();
    renderDecisionLog();
    toast("บันทึกแผน Gameweek นี้ใน Browser แล้ว");
  });
  $("#clear-planner").addEventListener("click", () => {
    localStorage.removeItem(plannerStorageKey());
    state.plannerSettings = defaultPlannerSettings();
    renderPlanner(); renderDecisionCenter(); renderBriefing();
    toast("ล้างแผน Multi-GW ใน Browser แล้ว");
  });
  $("#player-table-body").addEventListener("click", (event) => {
    const button = event.target.closest("[data-add-id]");
    if (button) addPlayer(button.dataset.addId);
  });
  $("#lab-squad-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-remove-id]");
    if (button) removePlayer(button.dataset.removeId);
  });
  $("#swap-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-swap-out]");
    if (!button) return;
    state.localSquad = state.localSquad.map((id) => id === Number(button.dataset.swapOut) ? Number(button.dataset.swapIn) : id);
    saveSquad();
    renderLabSquad();
    renderPlayerTable();
    toast("ทดลอง swap แล้ว");
  });
  $("#use-recommended").addEventListener("click", () => {
    const squad = currentDecision().starting_xi.squad || [];
    if (squad.length !== 15) return toast("ยังไม่มีทีมจริง 15 คนในแผนนี้");
    state.localSquad = squad.map((pick) => pick.player_id);
    saveSquad(); renderLabSquad(); renderPlayerTable(); toast("บันทึกทีมจริงใน Browser แล้ว");
  });
  $("#use-published").addEventListener("click", () => {
    state.localSquad = state.data.team.picks.map((pick) => pick.element);
    saveSquad(); renderLabSquad(); renderPlayerTable(); toast("นำทีม FPL สาธารณะล่าสุดมาใช้แล้ว");
  });
  $("#clear-squad").addEventListener("click", () => {
    state.localSquad = []; saveSquad(); renderLabSquad(); renderPlayerTable(); toast("ล้าง Squad Lab แล้ว");
  });
  $("#export-squad").addEventListener("click", () => {
    const payload = { schemaVersion: 2, teamId: state.data.manager.team_id, season: state.data.identity.season, generatedAt: new Date().toISOString(), playerIds: state.localSquad, validation: validateLocalSquad(state.localSquad) };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url; link.download = `fpl-squad-${state.data.identity.season}-${state.data.manager.team_id}.json`; link.click(); URL.revokeObjectURL(url);
  });
  $("#copy-briefing").addEventListener("click", async () => {
    if (!recommendationsAllowed() || state.runtime.partial) return;
    try { await copyText(briefingText()); toast("คัดลอก Briefing พร้อม Transfer และ Chip plan แล้ว"); }
    catch (error) { toast(error.message); }
  });
  bindDecisionLogEvents();
  bindComparisonEvents();
  bindDecisionCardEvents();
}

async function boot() {
  // Update the shell even if a data or render failure prevents a successful boot.
  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
  $("#refresh-data").addEventListener("click", () => location.reload());
  const markNavigation = () => $$(".topbar nav a").forEach(link => {
    if (link.hash === (location.hash || "#this-gameweek")) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
  window.addEventListener("hashchange", markNavigation);
  markNavigation();
  try {
    const qaState = ["localhost", "127.0.0.1"].includes(location.hostname) ? new URLSearchParams(location.search).get("qaState") : null;
    const resource = path => qaState ? `${path}?qaState=${encodeURIComponent(qaState)}` : path;
    const [dataResponse, briefingResponse] = await Promise.allSettled([
      fetchResource(resource("./data/latest.json")), fetchResource(resource("./data/briefing.md"))
    ]);
    if (dataResponse.status !== "fulfilled") throw new Error(`โหลดข้อมูลทีมไม่สำเร็จ (${dataResponse.reason.message}) ตรวจการเชื่อมต่อแล้วลองใหม่`);
    try { state.data = JSON.parse(dataResponse.value.text); }
    catch { throw new Error("ไฟล์ข้อมูลทีมอ่านไม่ได้ กรุณาสร้าง snapshot ใหม่"); }
    const compatibilityError = snapshotCompatibility(state.data);
    if (compatibilityError) { const error = new Error(compatibilityError); error.kind = "incompatible"; throw error; }
    state.loadedAt = new Date().toISOString();
    state.runtime.partial = briefingResponse.status !== "fulfilled";
    state.runtime.offline = navigator.onLine === false || dataResponse.value.cached || Boolean(briefingResponse.value?.cached);
    assessFreshness(state.data);
    state.briefing = briefingResponse.value?.text || "";
    state.settings = loadSettings();
    state.identityCheck = validateIdentity();
    state.playerById = new Map(state.data.catalog.players.map((player) => [player.id, player]));
    state.baseProjectionById = new Map(state.data.analysis.projections.map((item) => [item.player_id, clone(item)]));
    state.projectionById = new Map(state.data.analysis.projections.map((item) => [item.player_id, clone(item)]));
    state.teamById = new Map(state.data.catalog.teams.map((team) => [team.id, team]));
    state.transferSettings = loadTransferSettings();
    state.plannerSettings = loadPlannerSettings();
    state.riskEntries = recommendationsAllowed() ? loadRiskEntries() : [];
    applyLocalRiskLayer();
    state.localSquad = recommendationsAllowed()
      ? loadStoredSquad().filter((id) => state.playerById.has(id))
      : [];

    renderIdentity();
    populateRiskForm();
    renderRiskDesk();
    renderTransferAdvisor();
    renderPlanner();
    renderDecisionCenter();
    renderOverview();
    renderCaptains();
    renderModel();
    renderWarnings();
    renderRecommended();
    populateFilters();
    renderPlayerTable();
    renderLabSquad();
    renderBriefing();
    renderDiagnostics();
    bindEvents();
    if (state.data.team.picks?.length === 15) $("#use-published").hidden = false;
    ["#use-recommended", "#use-published", "#copy-briefing", "#export-squad", "#clear-squad", "#transfer-free-transfers", "#transfer-bank", "#clear-transfer-settings", "#clear-risk-evidence", "#risk-evidence-form button", "#save-planner", "#clear-planner"].forEach((selector) => {
      $(selector).disabled = !recommendationsAllowed();
    });
    $$("#risk-evidence-form input, #risk-evidence-form select").forEach((element) => { element.disabled = !recommendationsAllowed(); });
    if (currentDecision().starting_xi.status === "unavailable") {
      $("#use-recommended").disabled = true;
    }
    $("#download-briefing").hidden = !recommendationsAllowed();
    renderRuntimeStatus();
    $("#dashboard-content").hidden = false;
    $("#dashboard-content").setAttribute("aria-busy", "false");
    const updateTimeState = () => {
      const before = $("#runtime-state").dataset.kind;
      const riskBefore = state.activeRiskAdjustments.length;
      assessFreshness(state.data);
      applyLocalRiskLayer();
      const after = renderRuntimeStatus().kind;
      if (before !== after || riskBefore !== state.activeRiskAdjustments.length) {
        renderIdentity(); renderRiskDesk(); renderTransferAdvisor(); renderPlanner();
        renderDecisionCenter(); renderOverview(); renderCaptains(); renderRecommended();
        renderBriefing(); renderDiagnostics(); renderRuntimeStatus();
      }
    };
    window.addEventListener("offline", () => { state.runtime.offline = true; updateTimeState(); });
    // Keep cached data marked offline until it has actually been fetched again.
    window.addEventListener("online", () => { $("#runtime-help").textContent = "เชื่อมต่อได้แล้ว กดโหลดข้อมูลเว็บใหม่เพื่อยืนยันว่าได้ snapshot ล่าสุด"; });
    setInterval(updateTimeState, 30000);

  } catch (error) {
    console.error(error);
    $("#freshness-badge").textContent = "โหลดข้อมูลไม่สำเร็จ";
    $("#freshness-badge").classList.add("stale");
    $("#dashboard-content").hidden = true;
    $("#dashboard-content").setAttribute("aria-busy", "false");
    $("#runtime-state").dataset.kind = error.kind || "error";
    $("#runtime-state").textContent = `เปิด Dashboard ไม่สำเร็จ: ${error.message}`;
    $("#runtime-help").textContent = `เว็บ ${APP_RELEASE} • ข้อมูลที่บันทึกใน Browser ยังอยู่ กดโหลดใหม่เมื่อพร้อม หากออฟไลน์ครั้งแรกต้องเปิดออนไลน์ให้สำเร็จก่อน`;
  }
}

boot();
