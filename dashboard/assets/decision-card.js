"use strict";

const DECISION_CARD_VERSION = "decision-card-1.0";
let decisionCardPreview = null;

function shareableComparison(slot) {
  if (!COMPARISON_SLOTS.includes(slot)) throw new Error("เลือกแผน A หรือ B ก่อน");
  const saved = loadComparisons();
  if (saved.error) throw new Error(saved.error);
  const record = saved.slots[slot];
  if (!record || !comparisonRecordValid(record) || comparisonStatus(record) !== "current") {
    throw new Error("ต้องมีแผนที่ตรงกับข้อมูลปัจจุบัน ออนไลน์ และยังไม่ผ่าน deadline — เก็บ A/B ใหม่ก่อนสร้างการ์ด");
  }
  return record;
}

function createDecisionCard(slot) {
  const r = shareableComparison(slot);
  const clean = value => String(value).replace(/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g, " ").trim().slice(0,80);
  // Allowlist only. Names come from the public catalog, never saved labels/notes.
  const name = id => {
    const player = state.playerById.get(id);
    if (!player?.web_name) throw new Error("รายชื่อผู้เล่นไม่ครบ โหลดข้อมูลใหม่ก่อนสร้างการ์ด");
    return clean(player.web_name);
  };
  const captain = r.lineup.captain.player_id;
  const vice = r.lineup.vice_captain.player_id;
  const named = p => `${name(p.player_id)}${p.player_id === captain ? " (C)" : p.player_id === vice ? " (VC)" : ""}`;
  const bench = r.lineup.bench.map(p => r.lineup.picks.find(pick => pick.player_id === p.player_id));
  const positions = {1:"GK",2:"DEF",3:"MID",4:"FWD"};
  const n = value => value.toFixed(2);
  return {version: DECISION_CARD_VERSION, slot, gameweek: r.gameweek,
    title: `แผน ${slot} • GW${r.gameweek}`, subtitle: `FPL Decision Lab • ${clean(r.season)} • ฉบับร่าง`,
    score: `${n(r.metrics.netPoints)} xPts สุทธิ`,
    blocks: [
      {label:"ชิป", text:CHIP_LABELS[r.chip] || "เก็บชิป"},
      {label:"ย้ายตัวใน GW นี้", text:r.moves.length ? r.moves.map(m=>`${name(m.out_player_id)} → ${name(m.in_player_id)}`).join("\n") : "ไม่ย้ายตัว"},
      {label:`11 ตัวจริง • ${r.lineup.formation}`, text:Object.entries(positions).map(([pos,label])=>
        `${label}: ${r.lineup.picks.filter(p=>p.starter && p.position_id === Number(pos)).map(named).join(" • ")}`).join("\n")},
      {label:"กัปตัน / รอง", text:`${name(captain)} (C) / ${name(vice)} (VC)`},
      {label:"สำรอง", text:`GK: ${bench.filter(p=>p.position_id===1).map(named).join(" • ")}\n`+
        bench.filter(p=>p.position_id!==1).map((p,i)=>`${i+1}. ${named(p)}`).join(" • ")},
      {label:"ที่มาของคะแนน GW นี้", text:`XI รวมกัปตัน ${n(r.metrics.basePoints)} + TC/BB ${n(r.metrics.chipGain)} − hit ${r.metrics.hitCost} ≈ ${n(r.metrics.netPoints)} (ปัดเศษ)\n`+
        "ค่าประมาณ ไม่รับประกันผล • ไม่รวมมูลค่าชิป/FT หรือย้ายตัวใน GW อื่น"},
      {label:"ก่อนใช้แผน", text:`ผู้เล่นที่มีธงความเสี่ยง ${r.risks.length} คน • ตรวจข่าวและโอกาสลงสนามก่อน deadline\n`+
        "การ์ดไม่แสดงงบ ต้องตรวจราคาขายและ FT ใน Planner • ไม่ใช่คำแนะนำให้ใช้ชิปหรือติดลบ"},
      {label:"ข้อมูลอ้างอิง", text:`Snapshot ${new Date(r.sourceGeneratedAt).toISOString()}\n`+
        `Model ${clean(state.data.analysis.model.version)} • Web ${APP_RELEASE}\nสำเนาขณะสร้าง ไม่อัปเดตตามข่าว • ไม่ยืนยันสถานะทีมใน FPL`},
    ]};
}

function decisionCardText(card) {
  return [card.title,card.subtitle,card.score,...card.blocks.map(b=>`${b.label}\n${b.text}`)].join("\n\n");
}

function cardWrappedLines(text, measure, width) {
  const words = new Intl.Segmenter("th",{granularity:"word"});
  const letters = new Intl.Segmenter("th",{granularity:"grapheme"});
  return text.split("\n").flatMap(paragraph => {
    const lines = []; let line = "";
    for (const {segment} of words.segment(paragraph)) {
      if (line && measure(line+segment) > width) {lines.push(line.trimEnd());line="";}
      if (measure(segment) > width) {
        for (const {segment:letter} of letters.segment(segment)) {
          if (line && measure(line+letter)>width) {lines.push(line);line="";}
          line+=letter;
        }
      } else line+=segment;
    }
    lines.push(line.trimEnd()); return lines;
  });
}

function decisionCardImage(card) {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Browser สร้างภาพไม่ได้ ใช้ข้อความในการ์ดแทน");
  const font = size => `${size}px ui-sans-serif, system-ui, sans-serif`;
  const rows = []; let y = 50;
  const add = (text,size,color,gap=12) => {
    ctx.font=font(size);
    for (const line of cardWrappedLines(text,s=>ctx.measureText(s).width,704)) {
      rows.push({text:line,size,color,y}); y+=Math.ceil(size*1.6);
    }
    y+=gap;
  };
  add(card.subtitle,19,"#9ab0a8",8);
  add(card.title,38,"#edf8f2",8);
  add(card.score,44,"#c7ff69",22);
  for (const block of card.blocks) {add(block.label,21,"#61f2a7",0);add(block.text,24,"#edf8f2",22);}
  canvas.width=800;canvas.height=y+26;
  ctx.fillStyle="#0a1d19";ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.fillStyle="#61f2a7";ctx.fillRect(0,0,canvas.width,8);
  ctx.textBaseline="top";
  for (const row of rows) {ctx.font=font(row.size);ctx.fillStyle=row.color;ctx.fillText(row.text,48,row.y);}
  const image=canvas.toDataURL("image/png");
  if (!image.startsWith("data:image/png;base64,")) throw new Error("สร้างภาพ PNG ไม่สำเร็จ");
  return image;
}

function clearDecisionCard() {
  decisionCardPreview=null;
  $("#share-card-preview").hidden=true;
  $("#share-card-image").removeAttribute("src");
  $("#share-card-text").textContent="";
}

function checkedDecisionCard() {
  const slot = $("#share-card-slot").value;
  const record = shareableComparison(slot);
  if (!decisionCardPreview || decisionCardPreview.slot!==slot || decisionCardPreview.recordKey!==JSON.stringify(record)) {
    throw new Error("แผนเปลี่ยนแล้ว กดดูตัวอย่างการ์ดใหม่ก่อนส่งออก");
  }
  return decisionCardPreview;
}

function syncDecisionCard() {
  let problem=null;
  try {shareableComparison($("#share-card-slot").value);} catch(error) {problem=error.message;}
  $("#share-card-create").disabled=Boolean(problem);
  if (decisionCardPreview) {
    try {checkedDecisionCard();} catch {clearDecisionCard();}
  }
  $("#share-card-status").textContent=problem || (decisionCardPreview
    ? "ตรวจรายชื่อและข้อความด้านล่างก่อนส่งออก ไฟล์ที่ดาวน์โหลดแล้วเรียกคืนหรืออัปเดตจากเว็บนี้ไม่ได้"
    : "เลือก A หรือ B แล้วกดดูตัวอย่างก่อนส่งออก — ชื่อแผนที่ตั้งเองจะไม่ติดไปด้วย");
  for (const id of ["png","txt","copy"]) $("#share-card-"+id).disabled=!decisionCardPreview;
  $("#share-card-png").disabled=!decisionCardPreview?.image;
}

function bindDecisionCardEvents() {
  $("#share-card-slot").addEventListener("change",()=>{clearDecisionCard();syncDecisionCard();});
  $("#share-card-create").addEventListener("click",async()=>{
    try {
      await document.fonts?.ready;
      const slot=$("#share-card-slot").value, record=shareableComparison(slot), card=createDecisionCard(slot);
      let image=null;
      try {image=decisionCardImage(card);} catch {toast("สร้างภาพไม่ได้ แต่ยังคัดลอกหรือดาวน์โหลดข้อความได้");}
      decisionCardPreview={slot,recordKey:JSON.stringify(record),image,text:decisionCardText(card)};
      if (image) $("#share-card-image").src=image;
      else $("#share-card-image").removeAttribute("src");
      $("#share-card-image").hidden=!image;
      $("#share-card-text").textContent=decisionCardPreview.text;
      $("#share-card-preview").hidden=false;
      syncDecisionCard();
    } catch(error) {clearDecisionCard();syncDecisionCard();toast(error.message);}
  });
  for (const kind of ["png","txt","copy"]) $("#share-card-"+kind).addEventListener("click",async()=>{
    try {
      const preview=checkedDecisionCard();
      if (kind==="copy") {await copyText(preview.text);toast("คัดลอกเฉพาะข้อความในการ์ดแล้ว ยังไม่ได้ส่งให้ใคร");return;}
      if (kind==="png" && !preview.image) throw new Error("ไม่มีภาพ กรุณาสร้างตัวอย่างใหม่");
      const link=document.createElement("a");
      link.href=kind==="png" ? preview.image : "data:text/plain;charset=utf-8,"+encodeURIComponent(preview.text);
      link.download=`fpl-card-gw${state.data.game.next_gameweek.id}-${preview.slot}.${kind}`;
      link.click();
    } catch(error) {syncDecisionCard();toast(kind==="copy" ? "คัดลอกไม่ได้ ตรวจแผนปัจจุบันแล้วใช้ปุ่มดาวน์โหลดข้อความแทน" : error.message);}
  });
}
