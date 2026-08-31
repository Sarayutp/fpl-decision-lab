"use strict";

const APP_RELEASE = "2.0.0-rc.1";
const SNAPSHOT_SCHEMA = 2;

function snapshotCompatibility(data) {
  if (data?.schema_version !== SNAPSHOT_SCHEMA) return "รุ่นข้อมูลไม่รองรับ กรุณาอัปเดตเว็บและข้อมูลพร้อมกัน";
  const versions = [
    [data.gameweek_decision?.version, /^gameweek-decision-5\./],
    [data.analysis?.model?.version, /^xp-v2\./],
    [data.analysis?.recommendations?.transfer_advisor?.version, /^transfer-advisor-1\./],
    [data.analysis?.risk_layer?.version, /^risk-layer-1\./],
    [data.analysis?.recommendations?.chip_planner?.version, /^chip-planner-1\./]
  ];
  if (versions.some(([value, pattern]) => !pattern.test(value || ""))) return "รุ่นโมเดลหรือคำแนะนำไม่ตรงกับเว็บ กรุณาสร้าง release ใหม่ทั้งชุด";
  if (!data.identity || !data.data_quality || !data.manager || !data.game || !data.team
    || !Array.isArray(data.catalog?.players) || !Array.isArray(data.catalog?.teams)
    || !Array.isArray(data.analysis?.projections) || !Array.isArray(data.diagnostics?.fetches)
    || !data.analysis.model.score_definitions || !data.gameweek_decision.starting_xi
    || !data.gameweek_decision.bench || !data.gameweek_decision.captaincy) return "ข้อมูลสำคัญไม่ครบ กรุณา refresh pipeline ใหม่";
  if (!Number.isFinite(Date.parse(data.generated_at)) || !Number.isFinite(Date.parse(data.data_quality.oldest_source_at))) return "ไม่ทราบเวลาของข้อมูล จึงยังใช้คำแนะนำไม่ได้";
  if (data.analysis.model.quality?.guardrails_passed !== true) return "โมเดลไม่ผ่านเกณฑ์คุณภาพ จึงยังใช้คำแนะนำไม่ได้";
  const source = data.gameweek_decision.source || {};
  if (source.model_version !== data.analysis.model.version
    || source.transfer_advisor_version !== data.analysis.recommendations.transfer_advisor.version
    || source.risk_layer_version !== data.analysis.risk_layer.version
    || source.chip_planner_version !== data.analysis.recommendations.chip_planner.version) return "คำแนะนำและโมเดลมาจากคนละรุ่น กรุณาสร้างใหม่ทั้งชุด";
  return null;
}

function assessFreshness(data, now = Date.now()) {
  const quality = data.data_quality;
  const elapsed = (now - Date.parse(quality.oldest_source_at)) / 3600000;
  quality.age_hours = Math.max(Number(quality.age_hours || 0), elapsed, 0);
  quality.is_stale = Boolean(quality.is_stale) || !Number.isFinite(elapsed)
    || elapsed < -0.1 || quality.age_hours > Number(quality.stale_after_hours || 24);
  const deadline = Date.parse(data.game.next_gameweek?.deadline_time);
  return { stale: quality.is_stale, deadlinePassed: Number.isFinite(deadline) && deadline <= now };
}

async function fetchResource(url, timeoutMs = 12000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {cache: "no-store", signal: controller.signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    // Read the body inside the timeout too; a stalled response must not leave the UI loading forever.
    const text = await response.text();
    return {text, cached: response.headers.get("X-FPL-Cache") === "offline"};
  } finally { clearTimeout(timer); }
}

function runtimeState(data, {offline = false, partial = false, valid = true, now = Date.now()} = {}) {
  if (!valid) return {kind: "mismatch", message: "หยุดคำแนะนำ: ทีม, Gameweek หรือ Briefing ไม่ตรงกัน ตรวจรายละเอียดด้านล่าง"};
  const freshness = assessFreshness(data, now);
  if (freshness.deadlinePassed) return {kind: "deadline", message: "ผ่าน deadline ของข้อมูลชุดนี้แล้ว โหลด snapshot ใหม่ก่อนบันทึกแผนหรือใช้ชิป"};
  if (offline) return {kind: "offline", message: "ออฟไลน์ / ใช้ข้อมูลสำรอง — อ่านแผนเดิมได้ แต่ต้องเชื่อมต่อและตรวจข่าวก่อนตัดสินใจ"};
  if (freshness.stale) return {kind: "stale", message: "ข้อมูลเก่าหรือเวลาต้นทางไม่ถูกต้อง — อ่านเพื่ออ้างอิงได้ แต่ต้อง refresh ก่อนตัดสินใจ"};
  if (partial) return {kind: "partial", message: "โหลด Briefing ไม่สำเร็จ — ยังดูคำแนะนำจาก snapshot ได้ แต่ปิดการคัดลอกจนกว่าจะโหลดไฟล์ครบ"};
  if (data.gameweek_decision.status === "unavailable") return {kind: "empty", message: "ยังไม่มีทีมสาธารณะครบสำหรับแนะนำ — ดูผู้เล่นและ Diagnostics ได้ แล้วโหลดใหม่หลัง FPL ประกาศทีม"};
  return {kind: "ready", message: "โหลดข้อมูลครบแล้ว • ตรวจชื่อทีมและข่าวก่อน deadline ทุกครั้ง"};
}

function writeLocal(key, payload) {
  try { localStorage.setItem(key, JSON.stringify(payload)); return true; }
  catch { return false; }
}

function downloadJSON(payload, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"}));
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
