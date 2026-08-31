"use strict";

const DECISION_LOG_PREFIX = "fpl-decision-lab:decisions:v1";
const DECISION_LOG_LIMIT = 100;

function decisionLogKey() {
  return `${DECISION_LOG_PREFIX}:${state.data.identity.season}:${state.data.manager.team_id}`;
}

function loadDecisionLog() {
  try {
    const payload = JSON.parse(localStorage.getItem(decisionLogKey()) || "null");
    if (!payload) return {entries: [], error: null};
    if (payload.schemaVersion !== 1 || payload.teamId !== state.data.manager.team_id
      || payload.season !== state.data.identity.season || !Array.isArray(payload.entries)
      || payload.entries.length > DECISION_LOG_LIMIT
      || payload.entries.some(entry => !entry.id || !Number.isFinite(Date.parse(entry.savedAt))
        || !Array.isArray(entry.lineup?.picks) || !Array.isArray(entry.moves) || !entry.assumptions
        || !Number.isFinite(entry.expectedPoints))) {
      return {entries: [], error: "ประวัติเดิมไม่ตรงรุ่นหรือเสียหาย ระบบจะไม่เขียนทับข้อมูลเดิม"};
    }
    return {entries: payload.entries, error: null};
  } catch { return {entries: [], error: "อ่านประวัติไม่ได้ อาจถูกปิด storage — ระบบจะไม่เขียนทับข้อมูลเดิม"}; }
}

function persistDecisionLog(entries) {
  return writeLocal(decisionLogKey(), {schemaVersion: 1, teamId: state.data.manager.team_id,
    season: state.data.identity.season, entries});
}

function createDecisionRecord(note = "", now = new Date()) {
  if (!recommendationsAllowed() || !decisionActionsAllowed()) throw new Error("ต้องใช้ข้อมูลทีมที่ตรงกันและยังไม่ผ่าน deadline");
  const decision = currentDecision();
  if (decision.starting_xi.squad?.length !== 15) throw new Error("ยังไม่มีทีมครบ 15 คน");
  const planner = effectivePlanner();
  const saveStatus = plannerSaveStatus(planner);
  if (state.plannerSettings.savedAt && saveStatus !== "current") throw new Error("แผนเดิมเปลี่ยนหรือหมดอายุ ตรวจและบันทึก Planner ใหม่ก่อนลงประวัติ");
  const saved = saveStatus === "current" ? state.plannerSettings.savedPlan : null;
  const gw = Number(state.data.game.next_gameweek.id);
  const path = saved?.path || "roll";
  const chip = saved?.chip || "save";
  const firstWeek = planner.transfer_paths?.[path]?.weekly?.find(week => week.gameweek === gw);
  const ids = ["free_hit", "wildcard"].includes(chip) ? saved.replacementSquadIds
    : firstWeek?.squad_ids || decision.starting_xi.squad.map(pick => pick.player_id);
  const lineup = plannerWeekForSquad(ids, gw);
  if (!lineup || lineup.picks?.length !== 15) throw new Error("จัดทีมสำหรับบันทึกไม่สำเร็จ");
  const extra = chip === "triple_captain" ? lineup.triple_captain_gain : chip === "bench_boost" ? lineup.bench_boost_gain : 0;
  return {
    id: `${now.getTime()}-${Math.random().toString(36).slice(2, 9)}`,
    savedAt: now.toISOString(), gameweek: gw, sourceGeneratedAt: state.data.generated_at,
    release: APP_RELEASE, model: state.data.analysis.model.version,
    note: String(note).trim().slice(0, 500), chip, path,
    selectionBasis: saved ? "saved_planner" : "owned_squad_no_transfers_no_chip",
    lineup: clone(lineup), moves: clone(saved?.moves || []),
    expectedPoints: Math.round((lineup.base_xp_with_captain + extra) * 100) / 100,
    assumptions: {freeTransfers: state.transferSettings.freeTransfers, pricesConfirmed: Boolean(saved?.priceCertified),
      activeRisk: clone(state.activeRiskAdjustments), hit: 0},
    actual: null
  };
}

function decisionDifference(entry) {
  return entry.actual?.samePlan && Number.isFinite(entry.actual.points)
    ? Math.round((entry.actual.points - entry.expectedPoints) * 100) / 100 : null;
}

function renderDecisionLog() {
  const {entries, error} = loadDecisionLog();
  const valid = recommendationsAllowed();
  $("#decision-log-status").textContent = error || `${entries.length}/${DECISION_LOG_LIMIT} รายการ • เก็บเฉพาะ Browser นี้ ไม่ส่งออกอัตโนมัติ`;
  $("#record-decision").disabled = !valid || !decisionActionsAllowed() || Boolean(error) || entries.length >= DECISION_LOG_LIMIT || currentDecision().starting_xi.squad?.length !== 15;
  $("#export-decision-log").disabled = !valid || Boolean(error) || !entries.length;
  if (!valid || error || !entries.length) {
    $("#decision-log-list").innerHTML = `<p class="empty-state">${esc(!valid ? "ตรวจ Team ID ให้ตรงก่อนเปิดประวัติ" : error || "ยังไม่มีบันทึก เลือกแผนใน Planner แล้วกดบันทึกการตัดสินใจ")}</p>`;
    return;
  }
  $("#decision-log-list").innerHTML = [...entries].reverse().map(entry => {
    const difference = decisionDifference(entry);
    const captain = entry.lineup.captain?.name || "—";
    return `<article class="panel decision-log-entry" data-log-entry="${esc(entry.id)}">
      <h3>GW${esc(entry.gameweek)} • ${esc(captain)} (C)</h3>
      <p>${esc(new Date(entry.savedAt).toLocaleString("th-TH"))} • ${esc(entry.lineup.formation)} • ${esc(CHIP_LABELS[entry.chip] || "เก็บชิป")} • ${esc(entry.path)}</p>
      <p>xPts รวม C/ชิป ${formatDecimal(entry.expectedPoints, 2)} • ผลจริง ${entry.actual ? formatDecimal(entry.actual.points, 0) : "ยังไม่กรอก"}${difference == null ? "" : ` • ต่าง ${signedPoints(difference)}`}</p>
      ${entry.note ? `<p class="log-note">${esc(entry.note)}</p>` : ""}
      <details><summary>ทีมและสมมติฐานที่บันทึก</summary><p>${esc(entry.lineup.picks.map(pick => `${pick.name}${pick.starter ? "" : " (สำรอง)"}`).join(" • "))}</p>
      <p>${esc(entry.model)} • release ${esc(entry.release)} • snapshot ${esc(entry.sourceGeneratedAt)}</p>
      <p>${esc(entry.moves.map(move => `GW${move.gameweek} ${move.out_name} → ${move.in_name}`).join("; ") || "ไม่ย้ายตัว")}</p>
      <p>FT ${esc(entry.assumptions.freeTransfers ?? "ยังไม่ยืนยัน")} • ราคาขาย ${entry.assumptions.pricesConfirmed ? "ยืนยันแล้ว" : "ยังไม่ยืนยัน"} • hit ตามแผน 0</p></details>
      <form data-log-result="${esc(entry.id)}" class="log-result-form">
        <label>คะแนนจริงสุทธิของ GW นี้<input name="actualPoints" type="number" min="-100" max="400" step="1" required value="${entry.actual?.points ?? ""}"></label>
        <label class="checkbox-label"><input type="checkbox" name="samePlan" ${entry.actual?.samePlan ? "checked" : ""}>ใช้ทีม, C/VC, ชิป และ hit ตามบันทึกนี้</label>
        <button class="button button-ghost" type="submit">บันทึกผล GW${esc(entry.gameweek)}</button>
      </form>
      <small>ผลจริงที่คุณกรอกเอง ไม่ได้ยืนยันจาก FPL; เทียบส่วนต่างเมื่อใช้แผนเดียวกันเท่านั้น และไม่ใช่หลักฐานว่าโมเดลแม่นจาก GW เดียว</small>
      <details class="log-delete"><summary>ลบรายการนี้</summary><p>ส่งออกก่อนลบหากต้องการสำรอง รายการที่ลบกู้คืนไม่ได้จากเว็บ</p><button class="button button-danger" type="button" data-log-delete="${esc(entry.id)}">ยืนยันลบบันทึก GW${esc(entry.gameweek)}</button></details>
    </article>`;
  }).join("");
}

function bindDecisionLogEvents() {
  $("#record-decision").addEventListener("click", () => {
    try {
      const log = loadDecisionLog();
      if (log.error) throw new Error(log.error);
      if (log.entries.length >= DECISION_LOG_LIMIT) throw new Error("ประวัติเต็มแล้ว ส่งออกและลบรายการที่ไม่ใช้ก่อน");
      const record = createDecisionRecord($("#decision-note").value);
      if (!persistDecisionLog([...log.entries, record])) throw new Error("บันทึกไม่ได้: Browser ปิด storage หรือพื้นที่เต็ม กรุณาส่งออกข้อมูลสำรอง");
      $("#decision-note").value = "";
      renderDecisionLog(); toast("บันทึกการตัดสินใจในเครื่องแล้ว");
    } catch (error) { toast(error.message); }
  });
  $("#export-decision-log").addEventListener("click", () => {
    if (!recommendationsAllowed()) return;
    const log = loadDecisionLog();
    if (!log.error) downloadJSON({schemaVersion:1, teamId:state.data.manager.team_id, season:state.data.identity.season, entries:log.entries}, `fpl-decisions-${state.data.manager.team_id}.json`);
  });
  $("#decision-log-list").addEventListener("submit", event => {
    const form = event.target.closest("[data-log-result]");
    if (!form) return;
    event.preventDefault();
    if (!recommendationsAllowed()) return;
    const points = Number(form.elements.actualPoints.value);
    if (!Number.isInteger(points) || points < -100 || points > 400) return toast("คะแนนต้องเป็นจำนวนเต็ม -100 ถึง 400");
    const log = loadDecisionLog();
    if (log.error) return toast(log.error);
    const entries = log.entries.map(entry => entry.id === form.dataset.logResult ? {...entry, actual: {
      points, samePlan: form.elements.samePlan.checked, source: "user_reported", updatedAt: new Date().toISOString()
    }} : entry);
    if (!persistDecisionLog(entries)) return toast("บันทึกผลไม่ได้ กรุณาตรวจพื้นที่ Browser");
    renderDecisionLog(); toast("บันทึกผลจริงที่คุณกรอกแล้ว");
  });
  $("#decision-log-list").addEventListener("click", event => {
    const button = event.target.closest("[data-log-delete]");
    if (!button || !recommendationsAllowed()) return;
    const log = loadDecisionLog();
    if (log.error) return;
    if (!persistDecisionLog(log.entries.filter(entry => entry.id !== button.dataset.logDelete))) return toast("ลบไม่สำเร็จ");
    renderDecisionLog(); toast("ลบบันทึกที่เลือกแล้ว กู้คืนได้จากไฟล์ที่ส่งออกไว้เท่านั้น");
  });
}
