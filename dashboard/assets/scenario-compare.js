"use strict";

const COMPARISON_VERSION = "scenario-compare-1.0";
const COMPARISON_SLOTS = ["A", "B"];
const COMPARISON_PATHS = {roll: "ไม่ย้ายตัว", main: "เส้นทางหลัก", alternative: "เส้นทางสำรอง"};
const comparisonRound = value => Math.round(value * 100) / 100;

function comparisonStorageKey() {
  return `fpl-decision-lab:compare:v1:${state.data.identity.season}:${state.data.manager.team_id}:gw${state.data.game.next_gameweek?.id}`;
}

function comparisonContextKey() {
  const canonical = value => Array.isArray(value) ? value.map(canonical)
    : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;
  return JSON.stringify(canonical({version: COMPARISON_VERSION, release: APP_RELEASE,
    model: state.data.analysis.model.version, planner: state.data.analysis.recommendations.chip_planner.version,
    assumptions: JSON.parse(plannerAssumptionKey())}));
}

function comparisonLineupValid(lineup) {
  if (!Array.isArray(lineup?.picks) || lineup.picks.length !== 15 || !Array.isArray(lineup.bench) || lineup.bench.length !== 4) return false;
  const picks = lineup.picks;
  const ids = new Set(picks.map(p => p.player_id));
  if (ids.size !== 15 || picks.some(p => !Number.isInteger(p.player_id) || typeof p.name !== "string"
    || !Number.isInteger(p.team_id) || !Number.isFinite(p.xp_next) || p.xp_next < 0)) return false;
  if (Object.entries(POSITION_LIMITS).some(([position, count]) => picks.filter(p => p.position_id === Number(position)).length !== count)) return false;
  if (picks.some(p => picks.filter(other => other.team_id === p.team_id).length > 3)) return false;
  const starters = picks.filter(p => p.starter === true);
  const counts = [2,3,4].map(pos => starters.filter(p => p.position_id === pos).length);
  if (starters.length !== 11 || starters.filter(p => p.position_id === 1).length !== 1
    || !FORMATIONS.some(formation => formation.every((count, i) => count === counts[i]))) return false;
  if (lineup.formation !== counts.join("-") || new Set(lineup.bench.map(p => p.player_id)).size !== 4
    || lineup.bench.some(p => !ids.has(p.player_id) || starters.some(s => s.player_id === p.player_id))) return false;
  return lineup.captain?.player_id !== lineup.vice_captain?.player_id
    && [lineup.captain, lineup.vice_captain].every(p => starters.some(s => s.player_id === p?.player_id));
}

function comparisonRecordValid(record) {
  if (!record || record.version !== COMPARISON_VERSION || record.teamId !== state.data.manager.team_id
    || record.season !== state.data.identity.season || record.gameweek !== Number(state.data.game.next_gameweek?.id)
    || typeof record.label !== "string" || record.label.length > 120 || typeof record.contextKey !== "string"
    || !Number.isFinite(Date.parse(record.createdAt)) || !Number.isFinite(Date.parse(record.sourceGeneratedAt))
    || !["save", ...Object.keys(CHIP_LABELS)].includes(record.chip) || !Object.hasOwn(COMPARISON_PATHS, record.path)
    || !Array.isArray(record.moves) || record.moves.length > 15 || !Array.isArray(record.futureMoves) || record.futureMoves.length > 75
    || !Array.isArray(record.risks) || record.risks.length > 15 || record.risks.some(risk => typeof risk !== "string")
    || typeof record.model !== "string" || typeof record.release !== "string"
    || !comparisonLineupValid(record.lineup)) return false;
  const validMove = move => move && Number.isInteger(move.out_player_id) && Number.isInteger(move.in_player_id)
    && typeof move.out_name === "string" && typeof move.in_name === "string" && Number.isInteger(move.gameweek);
  if (record.moves.some(move => !validMove(move) || move.gameweek !== record.gameweek)
    || record.futureMoves.some(move => !validMove(move) || move.gameweek <= record.gameweek)) return false;
  const m = record.metrics;
  if (!m || ![m.basePoints,m.chipGain,m.hitCost,m.netPoints,m.bankAfter].every(Number.isFinite)
    || m.bankAfter < 0 || m.hitCost < 0 || m.hitCost % 4 !== 0 || typeof record.pricesConfirmed !== "boolean") return false;
  const captain = record.lineup.picks.find(p => p.player_id === record.lineup.captain.player_id);
  const base = record.lineup.picks.filter(p => p.starter).reduce((sum,p) => sum+p.xp_next,0) + captain.xp_next;
  const extra = record.chip === "triple_captain" ? captain.xp_next : record.chip === "bench_boost"
    ? record.lineup.picks.filter(p => !p.starter).reduce((sum,p) => sum+p.xp_next,0) : 0;
  return Math.abs(m.basePoints-comparisonRound(base)) < .011 && Math.abs(m.chipGain-comparisonRound(extra)) < .011
    && Math.abs(m.netPoints-comparisonRound(base+extra-m.hitCost)) < .011;
}

function loadComparisons() {
  const empty = {A: null, B: null};
  try {
    const raw = localStorage.getItem(comparisonStorageKey());
    if (raw === null) return {slots: empty, error: null};
    if (raw.length > 250000) throw new Error("oversized");
    const payload = JSON.parse(raw);
    if (payload?.schemaVersion !== 1 || payload.teamId !== state.data.manager.team_id
      || payload.season !== state.data.identity.season || payload.gameweek !== Number(state.data.game.next_gameweek?.id)
      || !payload.slots || Object.keys(payload.slots).sort().join() !== "A,B"
      || COMPARISON_SLOTS.some(slot => payload.slots[slot] !== null && !comparisonRecordValid(payload.slots[slot]))) throw new Error("invalid");
    return {slots: payload.slots, error: null};
  } catch { return {slots: empty, error: "อ่านแผน A/B ไม่ได้หรือข้อมูลเสียหาย — ระบบจะไม่เขียนทับข้อมูลเดิม"}; }
}

function persistComparisons(slots) {
  if (!COMPARISON_SLOTS.every(slot => slots[slot] === null || comparisonRecordValid(slots[slot]))) throw new Error("แผน A/B ไม่ผ่านการตรวจ");
  if (!writeLocal(comparisonStorageKey(), {schemaVersion: 1, teamId: state.data.manager.team_id,
    season: state.data.identity.season, gameweek: Number(state.data.game.next_gameweek.id), slots})) {
    throw new Error("บันทึก A/B ไม่สำเร็จ: Browser ปิด storage หรือพื้นที่เต็ม");
  }
}

function createComparisonRecord(label = "", now = new Date()) {
  if (!decisionActionsAllowed()) throw new Error("ตรวจทีมและโหลดข้อมูลใหม่ก่อนเก็บแผน A/B");
  const settings = state.plannerSettings;
  const gw = Number(state.data.game.next_gameweek.id);
  const chip = settings?.selectedChip;
  const pathName = settings?.selectedPath;
  if (Number(settings?.targetGameweek) !== gw) throw new Error("เลือกแผนสำหรับ Gameweek ปัจจุบันก่อน");
  if (!["save", ...Object.keys(CHIP_LABELS)].includes(chip)) throw new Error("เลือกชิปหรือเลือกเก็บชิปใน Planner ก่อน");
  if (!Object.hasOwn(COMPARISON_PATHS, pathName)) throw new Error("ไม่รู้จักเส้นทางที่เลือก");
  const planner = effectivePlanner();
  if (planner.status !== "ready") throw new Error("Planner ยังไม่พร้อม");
  if (chip !== "save" && !planner.chips?.[chip]?.available) throw new Error("ชิปนี้ใช้ไม่ได้แล้ว");
  const replacement = ["free_hit", "wildcard"].includes(chip);
  if (replacement && pathName !== "roll") throw new Error("Free Hit/Wildcard ต้องแยกจากเส้นทางย้ายตัวปกติ เลือก Roll ก่อน");
  if (replacement && planner.chips[chip].scenario_status === "review_required") throw new Error("ข่าวเปลี่ยนแล้ว ต้อง refresh ทีมจำลอง Free Hit/Wildcard ก่อน");
  const owned = (currentDecision().starting_xi.squad || []).map(p => p.player_id);
  if (owned.length !== 15 || new Set(owned).size !== 15 || owned.some(id => !state.playerById.has(id))) throw new Error("ทีมเดิมไม่ครบหรือมีผู้เล่นซ้ำ");
  let ids = [...owned];
  let moves = [];
  let futureMoves = [];
  if (replacement) {
    ids = planner.chips[chip].scenario?.squad_ids || [];
    const byPosition = (a,b) => (state.playerById.get(a)?.position_id || 0)-(state.playerById.get(b)?.position_id || 0) || a-b;
    const outgoing = owned.filter(id => !ids.includes(id)).sort(byPosition);
    const incoming = ids.filter(id => !owned.includes(id)).sort(byPosition);
    moves = outgoing.map((id,i) => ({gameweek: gw, out_player_id: id, in_player_id: incoming[i]}));
  } else if (pathName !== "roll") {
    const path = planner.transfer_paths?.[pathName];
    if (!path?.valid) throw new Error("เส้นทางนี้ไม่ผ่านงบหรือกฎทีม");
    moves = clone(path.moves || []).filter(move => Number(move.gameweek) === gw);
    futureMoves = clone(path.moves || []).filter(move => Number(move.gameweek) > gw);
    moves.forEach(move => {
      if (!ids.includes(move.out_player_id) || ids.includes(move.in_player_id)
        || state.playerById.get(move.out_player_id)?.position_id !== state.playerById.get(move.in_player_id)?.position_id) throw new Error("รายการย้ายตัวไม่ตรงกับทีมเดิม");
      ids = ids.map(id => id === move.out_player_id ? move.in_player_id : id);
    });
    const declared = path.weekly?.find(week => Number(week.gameweek) === gw)?.squad_ids;
    if (!declared || [...declared].sort((a,b)=>a-b).join() !== [...ids].sort((a,b)=>a-b).join()) throw new Error("ทีมหลังย้ายตัวไม่ตรงกับเส้นทาง");
  }
  if (ids.length !== 15 || ids.some(id => !state.playerById.has(id)
    || !projection(id).gameweeks?.some(row => Number(row.gameweek) === gw && Number.isFinite(row.expected_points)))) throw new Error("ผู้เล่นหรือคะแนนคาดการณ์สำหรับ GW นี้ไม่ครบ");
  const lineup = plannerWeekForSquad(ids, gw);
  if (!comparisonLineupValid(lineup)) throw new Error("XI, สำรอง หรือกัปตันไม่ผ่านกฎทีม");
  const freeTransfers = state.transferSettings?.freeTransfers;
  if (!replacement && moves.length && (!Number.isInteger(freeTransfers) || freeTransfers < 1 || freeTransfers > 5)) throw new Error("กรอก Free Transfer ก่อน เพื่อคำนวณแต้มติดลบให้ถูกต้อง");
  let bank = Number(state.transferSettings?.bank ?? state.data.manager.bank);
  let pricesConfirmed = true;
  if (!Number.isFinite(bank) || bank < 0) throw new Error("ตรวจเงินในธนาคารก่อน");
  moves = moves.map(move => {
    const outgoing = state.playerById.get(move.out_player_id);
    const incoming = state.playerById.get(move.in_player_id);
    if (!outgoing || !incoming) throw new Error("รายชื่อย้ายตัวไม่ครบ");
    const sell = state.transferSettings?.sellingPrices?.[String(outgoing.id)];
    if (sell == null) pricesConfirmed = false;
    const value = sell ?? outgoing.price;
    if (!Number.isFinite(value) || value < 0 || !Number.isFinite(incoming.price)) throw new Error("ราคาซื้อขายไม่ถูกต้อง");
    bank += value - incoming.price;
    return {...move, out_name: outgoing.web_name, in_name: incoming.web_name};
  });
  bank = comparisonRound(bank);
  if (bank < 0) throw new Error("งบหลังย้ายตัวติดลบ กรุณาตรวจราคาขายจริง");
  const hit = replacement ? 0 : Math.max(0, moves.length - (freeTransfers ?? 0)) * 4;
  const gain = chip === "triple_captain" ? lineup.triple_captain_gain : chip === "bench_boost" ? lineup.bench_boost_gain : 0;
  const risks = lineup.picks.filter(p => (p.starter || chip === "bench_boost")
    && (p.expected_minutes < 60 || p.start_probability < .65 || p.fixture_count === 0 || p.projection_confidence === "low"))
    .map(p => `${p.name}: ${Math.round(p.expected_minutes)} นาที / ${Math.round(p.start_probability*100)}% ตัวจริง / ${p.fixture_count} นัด / ${confidenceLabel(p.projection_confidence)}`);
  const record = {version: COMPARISON_VERSION, teamId: state.data.manager.team_id, season: state.data.identity.season,
    gameweek: gw, sourceGeneratedAt: state.data.generated_at, contextKey: comparisonContextKey(), createdAt: now.toISOString(),
    release: APP_RELEASE, model: state.data.analysis.model.version, label: String(label).trim().slice(0,120),
    chip, path: pathName, lineup: clone(lineup), moves, futureMoves, freeTransfers, pricesConfirmed, risks,
    metrics: {basePoints: comparisonRound(lineup.base_xp_with_captain), chipGain: comparisonRound(gain), hitCost: hit,
      netPoints: comparisonRound(lineup.base_xp_with_captain+gain-hit), bankAfter: bank}};
  if (!comparisonRecordValid(record)) throw new Error("ตัวเลขในแผนไม่ผ่านการตรวจ");
  return record;
}

function captureComparison(slot, label = "") {
  if (!COMPARISON_SLOTS.includes(slot)) throw new Error("ไม่รู้จักช่องแผน");
  const saved = loadComparisons();
  if (saved.error) throw new Error(saved.error);
  const record = createComparisonRecord(label);
  persistComparisons({...saved.slots, [slot]: record});
  return record;
}

function comparisonStatus(record) {
  if (!record) return "empty";
  if (!recommendationsAllowed() || !decisionActionsAllowed()) return "readonly";
  if (record.sourceGeneratedAt !== state.data.generated_at || record.contextKey !== comparisonContextKey()) return "changed";
  return "current";
}

function comparisonDifference(slots) {
  return COMPARISON_SLOTS.every(slot => comparisonStatus(slots[slot]) === "current")
    && slots.A.contextKey === slots.B.contextKey ? comparisonRound(slots.B.metrics.netPoints-slots.A.metrics.netPoints) : null;
}

function renderComparison() {
  const allowed = recommendationsAllowed();
  const saved = allowed ? loadComparisons() : {slots:{A:null,B:null}, error:"ตรวจ Team ID ให้ตรงก่อนเปิดแผน A/B"};
  const {slots, error} = saved;
  let draftError = null;
  try { createComparisonRecord(); } catch (problem) { draftError = problem.message; }
  $("#compare-draft-status").textContent = draftError || `ฉบับร่าง: ${CHIP_LABELS[state.plannerSettings.selectedChip] || "เก็บชิป"} • ${COMPARISON_PATHS[state.plannerSettings.selectedPath]} • GW${state.data.game.next_gameweek.id}`;
  $("#compare-status").textContent = error || "A/B เป็นสำเนาอ้างอิง เก็บเฉพาะ Browser นี้ ไม่เปลี่ยนแผนที่ยืนยันใน Planner หรือทีมใน FPL";
  COMPARISON_SLOTS.forEach(slot => {
    const button = $(`#compare-capture-${slot.toLowerCase()}`);
    button.disabled = Boolean(error || draftError);
    button.textContent = slots[slot] ? `แทนที่แผน ${slot} ด้วยฉบับร่าง` : `เก็บฉบับร่างเป็น ${slot}`;
  });
  $("#compare-export").disabled = Boolean(error) || !Object.values(slots).some(Boolean);
  $("#compare-board").innerHTML = COMPARISON_SLOTS.map(slot => {
    const item = slots[slot];
    const status = comparisonStatus(item);
    const title = item?.label || `แผน ${slot}`;
    return `<article class="panel compare-slot" data-compare-slot="${slot}" data-status="${status}">
      <span class="eyebrow">${slot}</span><h3>${esc(title)}</h3>
      <p>${item ? `GW${item.gameweek} • ${esc(CHIP_LABELS[item.chip] || "เก็บชิป")} • ${esc(COMPARISON_PATHS[item.path])}` : "เลือกชิป/เส้นทางใน Planner แล้วเก็บฉบับร่างลงช่องนี้"}</p>
      ${item ? `<p class="compare-status ${status === "current" ? "" : "warning"}">${status === "current" ? "ข้อมูลชุดปัจจุบัน" : status === "changed" ? "ข้อมูลหรือสมมติฐานเปลี่ยน — เก็บแผนนี้ใหม่ก่อนเทียบ" : "อ่านเพื่ออ้างอิงเท่านั้น — ยังใช้ส่วนต่างตัดสินใจไม่ได้"}</p>
        <small>เก็บ ${esc(new Date(item.createdAt).toLocaleString("th-TH"))} • ${esc(item.model)} • ${esc(item.release)}<br>Snapshot ${esc(item.sourceGeneratedAt)}</small>
        ${item.risks.length ? `<details><summary>รายละเอียดความเสี่ยง ${item.risks.length} คน</summary><ul>${item.risks.map(risk=>`<li>${esc(risk)}</li>`).join("")}</ul></details>` : ""}
        <details><summary>ลบเฉพาะแผน ${slot}</summary><p>ส่งออกก่อนลบหากต้องการสำรอง</p><button class="button button-danger" type="button" data-compare-delete="${slot}">ยืนยันลบแผน ${slot}</button></details>` : ""}</article>`;
  }).join("");
  const delta = comparisonDifference(slots);
  $("#compare-difference").dataset.comparable = String(delta !== null);
  $("#compare-difference").textContent = error || (delta === null
    ? "ยังไม่แสดงส่วนต่าง — ต้องมี A และ B ที่ตรงกับข้อมูล/สมมติฐานปัจจุบันทั้งคู่"
    : `B − A: ${signedPoints(delta)} xPts สุทธิ เฉพาะ GW${slots.A.gameweek} • ไม่ใช่คำแนะนำให้เลือกแผนที่แต้มสูงกว่าโดยอัตโนมัติ`);
  const rows = [
    ["ชิป", p => CHIP_LABELS[p.chip] || "เก็บชิป"],
    ["ย้ายตัวใน GW นี้", p => p.moves.length ? p.moves.map(m=>`${m.out_name} → ${m.in_name}`).join(" • ") : "ไม่ย้ายตัว"],
    ["xPts XI รวมกัปตัน ก่อนชิป/หัก hit", p => formatDecimal(p.metrics.basePoints,2)],
    ["คะแนนเพิ่มจาก TC / BB", p => signedPoints(p.metrics.chipGain)],
    ["แต้มติดลบ GW นี้", p => p.metrics.hitCost ? `−${p.metrics.hitCost}` : "0"],
    ["xPts สุทธิ GW นี้", p => formatDecimal(p.metrics.netPoints,2)],
    ["เงินเหลือหลังจัดแผน", p => `${formatDecimal(p.metrics.bankAfter)}m${p.chip === "free_hit" ? " (เฉพาะ GW Free Hit)" : ""}`],
    ["สถานะงบ", p => !p.moves.length ? "ไม่ต้องขายผู้เล่น" : p.pricesConfirmed ? "ราคาขายที่ผู้ใช้กรอกครบ (ไม่ได้ยืนยันกับ FPL)" : "ประมาณเท่านั้น — ยังไม่ยืนยันราคาขายครบ"],
    ["กัปตัน / รอง", p => `${p.lineup.captain.name} (C) / ${p.lineup.vice_captain.name} (VC)`],
    ["11 ตัวจริง", p => `${p.lineup.formation} • ${p.lineup.picks.filter(x=>x.starter).map(x=>x.name).join(" • ")}`],
    ["สำรองตามลำดับ", p => p.lineup.bench.map(x=>x.position_id === 1 ? `${x.name} (GK)` : x.name).join(" • ")],
    ["นาที / ความมั่นใจที่ต้องตรวจ", p => p.risks.length ? `${p.risks.length} คนมีธงนาที/โอกาสตัวจริง/ความมั่นใจต่ำ — เปิดรายละเอียดความเสี่ยงในกล่องแผน` : "ไม่พบธงตามเกณฑ์นี้ แต่ยังต้องตรวจข่าวก่อน deadline"],
    ["ย้ายตัวใน GW อื่น (ไม่นับในส่วนต่าง)", p => p.futureMoves.map(m=>`GW${m.gameweek} ${m.out_name} → ${m.in_name}`).join(" • ") || "ไม่มี"],
  ];
  $("#compare-table-body").innerHTML = rows.map(([label,value]) => `<tr><th scope="row">${esc(label)}</th>${COMPARISON_SLOTS.map(slot=>`<td>${slots[slot] ? esc(value(slots[slot])) : "—"}</td>`).join("")}</tr>`).join("");
  $("#compare-table-wrap").hidden = !Object.values(slots).some(Boolean);
}

function bindComparisonEvents() {
  COMPARISON_SLOTS.forEach(slot => $(`#compare-capture-${slot.toLowerCase()}`).addEventListener("click", () => {
    try {
      captureComparison(slot, $("#compare-label").value); $("#compare-label").value = "";
      renderComparison(); toast(`เก็บแผน ${slot} แล้ว — ไม่เปลี่ยนแผนที่ยืนยันใน Planner`);
    } catch (error) { toast(error.message); }
  }));
  $("#compare-export").addEventListener("click", () => {
    if (!recommendationsAllowed()) return;
    const saved = loadComparisons();
    if (saved.error) return toast(saved.error);
    downloadJSON({version: COMPARISON_VERSION, teamId: state.data.manager.team_id, season: state.data.identity.season,
      gameweek: state.data.game.next_gameweek.id, exportedAt: new Date().toISOString(),
      statuses: Object.fromEntries(COMPARISON_SLOTS.map(slot=>[slot,comparisonStatus(saved.slots[slot])])),
      difference: comparisonDifference(saved.slots), scope: "current_gameweek_only_not_a_recommendation", slots: saved.slots},
    `fpl-compare-${state.data.manager.team_id}-gw${state.data.game.next_gameweek.id}.json`);
  });
  $("#compare-board").addEventListener("click", event => {
    const button = event.target.closest("[data-compare-delete]");
    if (!button || !recommendationsAllowed() || !COMPARISON_SLOTS.includes(button.dataset.compareDelete)) return;
    try {
      const saved = loadComparisons(); if (saved.error) throw new Error(saved.error);
      persistComparisons({...saved.slots, [button.dataset.compareDelete]: null});
      renderComparison(); toast("ลบเฉพาะแผนที่เลือกแล้ว กู้คืนได้จากไฟล์ที่ส่งออกไว้เท่านั้น");
    } catch (error) { toast(error.message); }
  });
}
