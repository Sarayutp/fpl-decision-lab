"use strict";

const STORAGE_KEY = "fpl-decision-lab:squad:v1";
const POSITION_LIMITS = { 1: 2, 2: 5, 3: 5, 4: 3 };
const POSITION_NAMES = { 1: "GKP", 2: "DEF", 3: "MID", 4: "FWD" };
const FORMATIONS = [[3,4,3], [3,5,2], [4,3,3], [4,4,2], [4,5,1], [5,2,3], [5,3,2], [5,4,1]];

const state = {
  data: null,
  briefing: "",
  playerById: new Map(),
  projectionById: new Map(),
  teamById: new Map(),
  localSquad: [],
  tableLimit: 40,
  deadlineTimer: null
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

function loadStoredSquad() {
  try {
    const payload = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    return Array.isArray(payload.playerIds)
      ? payload.playerIds.map(Number).filter((id) => Number.isInteger(id))
      : [];
  } catch {
    return [];
  }
}

function saveSquad() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    schemaVersion: 1,
    teamId: state.data.manager.team_id,
    playerIds: state.localSquad,
    updatedAt: new Date().toISOString()
  }));
}

function projection(playerId) {
  return state.projectionById.get(Number(playerId)) || {
    xp_next: 0,
    xp_horizon: 0,
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

function renderOverview() {
  const { data } = state;
  const next = data.game.next_gameweek;
  const initial = data.analysis.recommendations.initial_squad;
  const generated = new Date(data.generated_at);
  const ageHours = Math.max(0, (Date.now() - generated.getTime()) / 3600000);
  const freshness = $("#freshness-badge");
  freshness.textContent = ageHours < 1 ? "ข้อมูลใหม่ไม่ถึง 1 ชม." : `ข้อมูลอายุ ${Math.floor(ageHours)} ชม.`;
  freshness.classList.toggle("stale", ageHours > 24);

  $("#deadline-title").textContent = next?.name || "Season complete";
  $("#deadline-local").textContent = next
    ? new Intl.DateTimeFormat("th-TH", { dateStyle: "full", timeStyle: "short" }).format(new Date(next.deadline_time))
    : "ไม่มี deadline ถัดไป";
  updateCountdown(next?.deadline_time);
  $("#next-action").textContent = data.team.picks
    ? "ตรวจข่าว แล้วตัดสินใจ transfer ก่อนล็อกทีม"
    : "สร้างทีมเริ่มต้น 15 คน แล้วตรวจข่าวก่อนยืนยันใน FPL";

  $("#overall-rank").textContent = formatNumber(data.manager.overall_rank);
  $("#overall-points").textContent = data.manager.overall_points == null
    ? "ฤดูกาลยังไม่เริ่ม"
    : `${formatNumber(data.manager.overall_points)} คะแนน`;
  $("#recommended-xp").textContent = initial.status === "unavailable" ? "—" : formatDecimal(initial.xp_with_captain, 2);
  $("#recommended-formation").textContent = initial.formation ? `Formation ${initial.formation}` : "ยังไม่มีทีมแนะนำ";
  $("#recommended-cost").textContent = initial.cost == null ? "—" : `${formatDecimal(initial.cost)}m`;
  $("#recommended-bank").textContent = initial.money_left == null ? "—" : `เหลือ ${formatDecimal(initial.money_left)}m`;
  $("#model-horizon").textContent = `${data.analysis.model.horizon} GW`;
  $("#model-version").textContent = data.analysis.model.version;
}

function renderCaptains() {
  const candidates = state.data.analysis.recommendations.captain_candidates.slice(0, 5);
  $("#captain-list").classList.remove("skeleton-lines");
  $("#captain-list").innerHTML = candidates.map((item, index) => `
    <div class="captain-row">
      <span class="captain-rank">${index + 1}</span>
      <div><strong>${esc(item.name)}</strong><small>${esc(teamName(item.team_id))} • ${esc(nextOpponent(item.player_id))} • ${formatDecimal(item.price)}m</small></div>
      <span class="xp-number">${formatDecimal(item.xp_next, 2)}</span>
    </div>
  `).join("");
}

function renderModel() {
  const model = state.data.analysis.model;
  const labels = [
    ["คะแนนพื้นฐาน", "คะแนนต่อเกม + คะแนนต่อ fixture โดย shrink sample ขนาดเล็ก"],
    ["โปรแกรม", "ปรับความยาก, เหย้า/เยือน และรวม Double/Blank GW"],
    ["โอกาสลง", "ลดคะแนนตามสถานะและ chance of playing จาก FPL"],
    ["Optimizer", "แก้งบ, ตำแหน่ง, formation และโควตา 3 คนต่อสโมสรพร้อมกัน"]
  ];
  $("#model-explainer").classList.remove("skeleton-lines");
  $("#model-explainer").innerHTML = labels.map(([title, text]) => `
    <div class="model-step"><span></span><div><strong>${title}</strong><small>${text}</small></div></div>
  `).join("") + `<p class="model-note">${esc(model.limitations[2])}</p>`;
}

function renderWarnings() {
  const warnings = [...state.data.diagnostics.warnings];
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
    <div class="player-label"><strong>${esc(pick.name)}</strong><small>${formatDecimal(pick.xp_next, 2)} xP • ${formatDecimal(pick.price)}m</small></div>
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
  const initial = state.data.analysis.recommendations.initial_squad;
  const validity = $("#squad-validity");
  if (initial.status === "unavailable" || !initial.picks?.length) {
    validity.textContent = "optimizer ไม่พร้อม";
    validity.classList.add("invalid");
    $("#recommended-pitch").innerHTML = `<div class="empty-state">${esc(initial.reason || "ไม่มีข้อมูลเพียงพอ")}</div>`;
    return;
  }
  validity.textContent = initial.validation.valid ? "✓ ผ่านกติกา FPL" : "ต้องตรวจสอบ";
  validity.classList.toggle("invalid", !initial.validation.valid);
  renderPitch(initial.picks, "#recommended-pitch", "#recommended-bench");
}

function validateLocalSquad(ids) {
  const players = ids.map((id) => state.playerById.get(id)).filter(Boolean);
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
  if (cost > 100.0001) violations.push(`เกินงบ ${(cost - 100).toFixed(1)}m`);
  if (Math.max(0, ...Object.values(teamCounts)) > 3) violations.push("เกิน 3 คนจากสโมสรเดียว");
  return { valid: violations.length === 0, violations, cost, bank: 100 - cost, positionCounts, teamCounts };
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
        .sort((a, b) => projection(b.id).xp_next - projection(a.id).xp_next);
      starters.push(...pool.slice(0, count));
    }
    const score = starters.reduce((sum, player) => sum + projection(player.id).xp_next, 0);
    if (!best || score > best.score) best = { starters, score, formation: `${defenders}-${midfielders}-${forwards}` };
  }
  const captainOrder = [...best.starters].sort((a, b) => projection(b.id).xp_next - projection(a.id).xp_next);
  const captain = captainOrder[0];
  const vice = captainOrder.find((player) => player.team_id !== captain.team_id) || captainOrder[1];
  const starterIds = new Set(best.starters.map((player) => player.id));
  const bench = selected
    .filter((player) => !starterIds.has(player.id))
    .sort((a, b) => (a.position_id === 1) - (b.position_id === 1) || projection(b.id).xp_next - projection(a.id).xp_next);
  return {
    ...best,
    captainId: captain.id,
    viceId: vice.id,
    xpWithCaptain: best.score + projection(captain.id).xp_next,
    bench
  };
}

function renderLabSquad() {
  const validation = validateLocalSquad(state.localSquad);
  const lineup = computeLineup(state.localSquad);
  $("#lab-player-count").textContent = `${state.localSquad.length}/15`;
  $("#lab-cost").textContent = `${formatDecimal(validation.cost)}m`;
  $("#lab-bank").textContent = `${formatDecimal(validation.bank)}m`;
  $("#lab-xp").textContent = lineup ? formatDecimal(lineup.xpWithCaptain, 2) : "—";
  $("#lab-formation").textContent = lineup ? `Formation ${lineup.formation}` : "ยังไม่ครบ 15 คน";
  const validityElement = $("#lab-validity");
  validityElement.className = `lab-validity ${validation.valid ? "valid" : state.localSquad.length ? "invalid" : ""}`;
  validityElement.textContent = validation.valid ? "✓ ทีมนี้ผ่านงบ ตำแหน่ง และโควตาสโมสร" : validation.violations.join(" • ") || "เริ่มเลือกผู้เล่นด้านล่าง";

  const container = $("#lab-squad-list");
  if (!state.localSquad.length) {
    container.className = "lab-squad-list empty-state";
    container.textContent = "เลือก “ใช้ทีมแนะนำ” หรือเพิ่มผู้เล่นจากตาราง";
  } else {
    container.className = "lab-squad-list";
    const starterIds = new Set(lineup?.starters.map((player) => player.id) || []);
    container.innerHTML = [...state.localSquad]
      .map((id) => state.playerById.get(id))
      .filter(Boolean)
      .sort((a, b) => a.position_id - b.position_id || projection(b.id).xp_next - projection(a.id).xp_next)
      .map((player) => {
        const tags = [];
        if (lineup?.captainId === player.id) tags.push("C");
        if (lineup?.viceId === player.id) tags.push("VC");
        if (lineup && !starterIds.has(player.id)) tags.push("BENCH");
        return `<div class="lab-player"><div><strong>${esc(player.web_name)} ${tags.length ? `(${tags.join("/")})` : ""}</strong><small>${esc(POSITION_NAMES[player.position_id])} • ${esc(teamName(player.team_id))} • ${formatDecimal(player.price)}m • ${formatDecimal(projection(player.id).xp_next, 2)} xP</small></div><button class="remove-player" type="button" data-remove-id="${player.id}" aria-label="นำ ${esc(player.web_name)} ออกจากทีม">×</button></div>`;
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
  const suggestions = calculateSwaps(validation);
  const container = $("#swap-list");
  if (!suggestions.length) {
    container.className = "swap-list empty-state";
    container.textContent = state.localSquad.length ? "ไม่พบ swap ที่เพิ่ม xP ภายใต้งบปัจจุบัน" : "จะคำนวณเมื่อมีผู้เล่นในทีม";
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
  const id = Number(playerId);
  if (state.localSquad.includes(id)) return;
  const player = state.playerById.get(id);
  const validation = validateLocalSquad(state.localSquad);
  if (!player || state.localSquad.length >= 15) return toast("ทีมมีผู้เล่นครบ 15 คนแล้ว");
  if ((validation.positionCounts[player.position_id] || 0) >= POSITION_LIMITS[player.position_id]) return toast(`${POSITION_NAMES[player.position_id]} ครบโควตาแล้ว`);
  if ((validation.teamCounts[player.team_id] || 0) >= 3) return toast(`มีผู้เล่นจาก ${teamName(player.team_id)} ครบ 3 คนแล้ว`);
  if (validation.cost + player.price > 100.0001) return toast("งบไม่พอสำหรับผู้เล่นคนนี้");
  state.localSquad.push(id);
  saveSquad();
  renderLabSquad();
  renderPlayerTable();
}

function removePlayer(playerId) {
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
    if (sort === "price_asc") return a.price - b.price || projection(b.id).xp_next - projection(a.id).xp_next;
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
    return `<tr>
      <td><div class="player-cell"><span class="position-dot">${esc(POSITION_NAMES[player.position_id])}</span><div><strong>${esc(player.web_name)}</strong><small>${esc(teamName(player.team_id))} • ${esc(player.news || "พร้อมลง")}</small></div></div></td>
      <td>${esc(POSITION_NAMES[player.position_id])}</td>
      <td>${formatDecimal(player.price)}m</td>
      <td>${esc(nextOpponent(player.id))}</td>
      <td><strong>${formatDecimal(item.xp_next, 2)}</strong></td>
      <td>${formatDecimal(item.xp_horizon, 2)}</td>
      <td>${formatDecimal(player.selected_by_percent)}%</td>
      <td><span class="risk ${esc(item.risk)}">${esc(item.risk)}</span></td>
      <td><button class="add-player ${selected ? "selected" : ""}" type="button" data-add-id="${player.id}" ${selected ? "disabled" : ""} aria-label="${selected ? "อยู่ในทีมแล้ว" : `เพิ่ม ${esc(player.web_name)} เข้าทีม`}">${selected ? "✓" : "+"}</button></td>
    </tr>`;
  }).join("");
  $("#show-more").hidden = rows.length <= state.tableLimit;
}

function renderBriefing() {
  $("#briefing-preview").textContent = state.briefing.slice(0, 7000);
}

function renderDiagnostics() {
  const fetches = state.data.diagnostics.fetches;
  const stale = fetches.some((item) => item.source === "stale-cache");
  $("#system-status").textContent = stale ? "ใช้ stale cache บางส่วน" : "✓ Pipeline ปกติ";
  $("#system-status").classList.toggle("invalid", stale);
  $("#diagnostics").innerHTML = fetches.map((item) => `<span class="diagnostic-chip">${esc(item.endpoint)} • ${esc(item.source)} • ${formatNumber(item.duration_ms)}ms</span>`).join("");
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
    document.execCommand("copy");
    area.remove();
  }
}

function bindEvents() {
  ["#player-search", "#position-filter", "#team-filter", "#sort-filter"].forEach((selector) => {
    $(selector).addEventListener(selector === "#player-search" ? "input" : "change", () => {
      state.tableLimit = 40;
      renderPlayerTable();
    });
  });
  $("#show-more").addEventListener("click", () => { state.tableLimit += 40; renderPlayerTable(); });
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
    state.localSquad = state.data.analysis.recommendations.initial_squad.picks.map((pick) => pick.player_id);
    saveSquad(); renderLabSquad(); renderPlayerTable(); toast("บันทึกทีมแนะนำใน Browser แล้ว");
  });
  $("#use-published").addEventListener("click", () => {
    state.localSquad = state.data.team.picks.map((pick) => pick.element);
    saveSquad(); renderLabSquad(); renderPlayerTable(); toast("นำทีม FPL สาธารณะล่าสุดมาใช้แล้ว");
  });
  $("#clear-squad").addEventListener("click", () => {
    state.localSquad = []; saveSquad(); renderLabSquad(); renderPlayerTable(); toast("ล้าง Squad Lab แล้ว");
  });
  $("#export-squad").addEventListener("click", () => {
    const payload = { teamId: state.data.manager.team_id, generatedAt: new Date().toISOString(), playerIds: state.localSquad, validation: validateLocalSquad(state.localSquad) };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url; link.download = "fpl-squad.json"; link.click(); URL.revokeObjectURL(url);
  });
  $("#copy-briefing").addEventListener("click", async () => { await copyText(state.briefing); toast("คัดลอก Briefing แล้ว — นำไปวางใน ChatGPT ได้เลย"); });
}

async function boot() {
  try {
    const [dataResponse, briefingResponse] = await Promise.all([
      fetch("./data/latest.json", { cache: "no-store" }),
      fetch("./data/briefing.md", { cache: "no-store" })
    ]);
    if (!dataResponse.ok) throw new Error(`latest.json: HTTP ${dataResponse.status}`);
    if (!briefingResponse.ok) throw new Error(`briefing.md: HTTP ${briefingResponse.status}`);
    state.data = await dataResponse.json();
    state.briefing = await briefingResponse.text();
    if (state.data.schema_version !== 1) throw new Error(`Unsupported schema version ${state.data.schema_version}`);
    state.playerById = new Map(state.data.catalog.players.map((player) => [player.id, player]));
    state.projectionById = new Map(state.data.analysis.projections.map((item) => [item.player_id, item]));
    state.teamById = new Map(state.data.catalog.teams.map((team) => [team.id, team]));
    state.localSquad = loadStoredSquad().filter((id) => state.playerById.has(id));

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

    if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
      navigator.serviceWorker.register("./sw.js").catch(() => {});
    }
  } catch (error) {
    console.error(error);
    $("#freshness-badge").textContent = "โหลดข้อมูลไม่สำเร็จ";
    $("#freshness-badge").classList.add("stale");
    $("#next-action").textContent = "รัน data refresh และเปิดผ่าน local web server";
    toast(`เปิด Dashboard ไม่สำเร็จ: ${error.message}`);
  }
}

boot();
