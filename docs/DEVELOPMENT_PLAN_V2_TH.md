# FPL Decision Lab v2 — Development Plan

อัปเดตล่าสุด: 31 สิงหาคม 2026

เอกสารนี้เป็นแผนพัฒนารอบใหม่ต่อจากระบบระยะที่ 1–7 เดิม โดยเปลี่ยนจุดเน้นจาก
“Dashboard สำหรับดูข้อมูล FPL” เป็น “ผู้ช่วยตัดสินใจก่อน deadline สำหรับทีมของผู้ใช้จริง”

## เป้าหมายผลิตภัณฑ์

ก่อน deadline ผู้ใช้ควรเปิดหน้าแรกแล้วตอบคำถามต่อไปนี้ได้ภายใน 30 วินาที:

1. ควรเปลี่ยนตัวหรือเก็บ Free Transfer
2. ควรจัด 11 ตัวจริงอย่างไร
3. ใครควรเป็นกัปตันและรองกัปตัน
4. ควรเรียงตัวสำรองอย่างไร
5. ควรใช้หรือเก็บชิป

ทีมอ้างอิงสำหรับตรวจความถูกต้องในรอบพัฒนานี้คือ `Sarayut FC` (Team ID
`5105794`) ไม่ใช่ Team ID `3647781` ที่ยังปรากฏอยู่ในระบบเดิม

## หลักการพัฒนา

- **Correct before clever:** ถ้าระบุตัวตนทีมหรือ Gameweek ผิด ต้องหยุดคำแนะนำทันที
- **Action before analytics:** หน้าแรกต้องเริ่มจากสิ่งที่ควรทำ ไม่ใช่ตารางข้อมูลจำนวนมาก
- **Feasible recommendations:** ทุกคำแนะนำต้องผ่านงบ ตำแหน่ง โควตาสโมสร และจำนวน transfer
- **Facts separated from estimates:** ข่าวยืนยัน, ค่าโมเดล และข้อสันนิษฐานต้องแสดงแยกกัน
- **No unexplained hits or chips:** ไม่เสนอการติดลบหรือใช้ชิปโดยไม่มีผลตอบแทนและค่าเสียโอกาส
- **User remains in control:** ระบบวิเคราะห์และจัดแผน แต่ไม่กดเปลี่ยนทีมจริงโดยอัตโนมัติ

## ภาพรวม Roadmap

| Milestone | Phase | ผลลัพธ์หลัก | ระยะเวลาโดยประมาณ |
|---|---|---|---:|
| M1: Trusted Assistant | 0–1 | ใช้ทีมถูกต้องและมีหน้าตัดสินใจประจำ GW | 4–7 วันพัฒนา |
| M2: Better Decisions | 2–4 | xP น่าเชื่อถือ, transfer คุ้มค่า, มีข่าวและความเสี่ยง | 12–20 วันพัฒนา |
| M3: Multi-GW Planner | 5 | วางแผนชิปและ transfer หลาย GW | 5–8 วันพัฒนา |
| M4: Production Ready | 6 | UX, QA, monitoring และ release process พร้อมใช้งาน | 3–5 วันพัฒนา |
| Optional | 7 | Mini-league strategy และฟีเจอร์ขั้นสูง | ประเมินภายหลัง |

ระยะเวลาเป็น effort สำหรับผู้พัฒนาหนึ่งคน ไม่รวมเวลารอข้อมูลภายนอก และควรปรับหลัง
แตกงานเป็น issue จริง

---

## Phase 0 — Source of Truth & Account Integrity

**ลำดับความสำคัญ:** P0 — ต้องเสร็จก่อนเปิดใช้คำแนะนำรุ่นใหม่

**สถานะ:** Done — 28 สิงหาคม 2026

**ระยะเวลาโดยประมาณ:** 1–2 วันพัฒนา

**เป้าหมาย:** เว็บต้องรู้ว่ากำลังวิเคราะห์ทีมใด ข้อมูลมาจากเมื่อใด และเป็นทีมปัจจุบันจริงหรือไม่

### งานที่ต้องทำ

- [x] ย้าย Team ID ออกจากค่าที่ hard-code และกำหนดได้จากหน้าเว็บ/การตั้งค่า
- [x] ตั้งทีมเริ่มต้นสำหรับการตรวจรับเป็น Team ID `5105794`
- [x] เพิ่ม Identity Banner: ชื่อทีม, ชื่อผู้จัดการ, Team ID, Gameweek และเวลาที่อัปเดต
- [x] เปรียบเทียบ Team ID ใน snapshot, briefing และทีมที่ผู้ใช้เลือกทุกครั้ง
- [x] หยุดสร้างคำแนะนำเมื่อ Team ID หรือ Gameweek ไม่ตรง พร้อมบอกวิธีแก้ที่ชัดเจน
- [x] แยกสถานะ “ทีมที่ประกาศล่าสุดจาก public API” ออกจาก “แผนที่ยังไม่ยืนยันก่อน deadline”
- [x] แยกข้อมูล Squad Lab ใน `localStorage` ตาม Team ID และฤดูกาล
- [x] แสดง freshness ของข้อมูล และเตือนเมื่อข้อมูลสำคัญเก่ากว่า 24 ชั่วโมง
- [x] เพิ่ม data provenance ว่าแต่ละส่วนมาจาก FPL API, ผู้ใช้กรอก หรือโมเดล
- [x] เพิ่ม test สำหรับการสลับ Team ID, stale data และ local squad ข้ามบัญชี

### สิ่งส่งมอบ

- หน้า Settings/Team Setup ที่อ่านง่าย
- identity และ freshness block ที่ใช้ร่วมกันทุกหน้า
- validation gate ก่อน optimizer และ AI briefing
- migration สำหรับข้อมูล Squad Lab เดิมโดยไม่ทำให้ทีมผู้ใช้สูญหาย

### Acceptance criteria

- [x] หน้าเว็บแสดง `Sarayut FC`, Team ID `5105794` และข้อมูลสรุปตรงกับแหล่งจริง
- [x] เมื่อ snapshot เป็น Team ID `3647781` ระบบไม่แสดงคำแนะนำปะปนเป็นทีมปัจจุบัน
- [x] ข้อมูลเกิน 24 ชั่วโมงมีคำเตือนเด่นชัดก่อนส่วนคำแนะนำ
- [x] เปิดสอง Team ID ใน Browser เดียวกันแล้วทีมใน Squad Lab ไม่ปะปนกัน
- [x] briefing ที่คัดลอกออกไประบุ Team ID, Gameweek และเวลาข้อมูลครบถ้วน

### ยังไม่ทำใน Phase นี้

- เปลี่ยนโมเดล xP
- แนะนำ transfer หลาย Gameweek
- เชื่อมบัญชีด้วย password หรือ session cookie

---

## Phase 1 — This Gameweek Decision Center

**ลำดับความสำคัญ:** P0/P1

**สถานะ:** Done — 30 สิงหาคม 2026

**ระยะเวลาโดยประมาณ:** 3–5 วันพัฒนา

**เป้าหมาย:** เปลี่ยนหน้าแรกให้เป็นคำตอบประจำ Gameweek ที่นำไปทำตามได้ทันที

### งานที่ต้องทำ

- [x] สร้างหน้า `This Gameweek` เป็นหน้าเริ่มต้น
- [x] แสดง deadline พร้อมเวลาท้องถิ่นและสถานะข้อมูลล่าสุด
- [x] สรุปคำแนะนำ 5 ช่อง: Transfer, Starting XI, Captain/Vice, Bench และ Chip
- [x] ใช้ optimizer จัดเฉพาะผู้เล่น 15 คนที่ผู้ใช้มีอยู่สำหรับ XI/C/VC/bench
- [x] แสดงเหตุผลสั้น ๆ ใต้ทุกคำแนะนำ พร้อมเปิดดูรายละเอียดได้
- [x] แสดงแผนหลักหนึ่งชุด และทางเลือก `ปลอดภัย` / `เน้นเพดาน` เมื่อมีเหตุผลรองรับ
- [x] แสดง formation และตรวจว่าตัวจริง/สำรองถูกกฎ FPL
- [x] แยก `Recommended action` ออกจาก `Model confidence`
- [x] ทำปุ่มคัดลอก AI briefing จากคำแนะนำชุดเดียวกับที่แสดงบนหน้าเว็บ
- [x] ย้าย Player Explorer, Squad Lab และ Diagnostics ไปเป็นเครื่องมือรอง
- [x] ปรับ mobile layout ให้เห็นคำตอบสำคัญก่อนโดยไม่ต้องเลื่อนหลายหน้าจอ

### โครงสร้างข้อมูลที่ควรมี

```text
gameweek_decision
├── identity + freshness
├── transfer_action
├── starting_xi + formation
├── captain + vice_captain
├── bench_order
├── chip_action
├── reasons + confidence
└── alternatives + warnings
```

### Acceptance criteria

- [x] ผู้ใช้มองเห็นคำตอบทั้ง 5 ข้อได้ภายใน 30 วินาทีบนมือถือ
- [x] Starting XI มีเฉพาะผู้เล่นที่อยู่ในทีมปัจจุบันครบ 11 คน
- [x] Bench มี 4 คน เรียงผู้รักษาประตูและผู้เล่นสนามถูกต้อง
- [x] formation, captain และ vice-captain ผ่านกฎ FPL ทุกครั้ง
- [x] หน้าเว็บ, JSON และ AI briefing ให้คำแนะนำชุดเดียวกัน
- [x] เมื่อข้อมูลไม่พอ ระบบแสดง `ยังแนะนำไม่ได้` แทนการเดา

### Definition of Done สำหรับ M1

Phase 0 และ Phase 1 ผ่าน acceptance criteria ทั้งหมด และทดสอบกับทีมจริงอย่างน้อย
หนึ่ง Gameweek ก่อนถือว่าเว็บเป็น Personal Gameweek Decision Assistant รุ่นแรก

**ผลตรวจรับ M1:** ผ่านกับ `Sarayut FC` ใน Gameweek 3 เมื่อ 30 สิงหาคม 2026
ทั้ง desktop/mobile และกรณี Team ID ไม่ตรง โดยไม่มี console error

---

## Phase 2 — xP Model v2 & Confidence

**ลำดับความสำคัญ:** P1

**สถานะ:** In review — implementation เสร็จ 30 สิงหาคม 2026; รอสะสม backtest

**ระยะเวลาโดยประมาณ:** 4–7 วันพัฒนา

**เป้าหมาย:** ทำให้คะแนนคาดการณ์เสถียร อธิบายได้ และไม่ตอบสนองเกินไปกับข้อมูลต้นฤดูกาล

### งานที่ต้องทำ

- [x] แยก `expected points` ออกจาก `ranking score` ให้ชัดเจน
- [x] ใช้ prior จากฤดูกาลก่อน/ราคา/บทบาท แล้วค่อยลดน้ำหนักเมื่อมี sample ฤดูกาลใหม่มากขึ้น
- [x] สร้างโมเดล expected minutes และโอกาสลงตัวจริง
- [x] เพิ่มปัจจัยเกมรุกและเกมรับของทีม, home/away และความยากคู่แข่ง
- [x] เพิ่ม xG/xA หรือ xGI, set pieces, penalties และ clean-sheet probability เมื่อข้อมูลพร้อม
- [x] รองรับ Double/Blank Gameweek โดยไม่คูณความคาดหวังแบบง่ายเกินไป
- [x] แสดงช่วงความไม่แน่นอนและ data-quality flag ต่อผู้เล่น
- [x] จำกัด Captain Radar ให้เน้นผู้เล่นที่มีเพดานและนาทีสูง โดยยกเว้นกองหลังเฉพาะกรณีมีหลักฐานชัด
- [x] บันทึก feature contribution หรือเหตุผลสำคัญที่ทำให้ xP สูง/ต่ำ
- [x] สร้าง backtest แบบ rolling โดยไม่ใช้ข้อมูลอนาคต
- [x] เปรียบเทียบ baseline เช่น FPL `ep_next`, คะแนนเฉลี่ย และโมเดลเดิม

### ตัวชี้วัดตรวจโมเดล

- MAE ของคะแนนผู้เล่น
- Rank correlation ระหว่าง xP กับคะแนนจริง
- Top-k hit rate สำหรับ XI และ captain shortlist
- Calibration ของโอกาสลงตัวจริงและ clean sheet
- ความเสถียรของอันดับผู้เล่นเมื่อข้อมูลใหม่มีเพียงหนึ่งนัด

ตัวชี้วัดเหล่านี้ใช้เปรียบเทียบรุ่น ไม่ควรกำหนดเป้าตัวเลขจนกว่าจะมี baseline ที่วัดซ้ำได้

### Acceptance criteria

- [x] backtest ทำซ้ำได้และป้องกัน data leakage
- [ ] โมเดล v2 ดีกว่า baseline อย่างมีนัยสำคัญเชิงใช้งานในอย่างน้อย 2 ตัวชี้วัดหลัก
- [x] ผู้เล่น sample ต่ำไม่กระโดดขึ้นอันดับสูงเพราะผลงานเพียงนัดเดียวโดยไม่มีคำเตือน
- [x] ทุก xP แสดง freshness, expected minutes และเหตุผลหลักได้
- [x] Captain Radar ไม่เลือกตัวเลือกผิดธรรมชาติหากไม่มีหลักฐานด้านเพดานคะแนนรองรับ
- [x] อัปเดต Model Card พร้อมข้อจำกัดและผล backtest

### ผลตรวจระหว่างทาง

- live profile 623 คน: maximum ลดจาก 17.81 เป็น 7.33 และ p99 ลดจาก 12.79 เป็น 4.88
- low-sample projection สูงกว่า 10 เหลือ 0 คน และ model guardrails ผ่าน
- rolling backtest 40 คนไม่มี leakage แต่มี evaluation เพียง GW2 หนึ่ง Gameweek
- v2 ชนะ recent-points baseline ใน MAE และ rank correlation แต่ยังไม่ชนะ price/role prior

จึงคงสถานะ `In review` และยังไม่ติ๊ก acceptance ข้อเปรียบเทียบ baseline จนกว่าจะมีอย่างน้อย
3 evaluation Gameweeks; การเขียนว่า `Done` ก่อนหน้านั้นจะให้ความมั่นใจเกินหลักฐาน

---

## Phase 3 — Transfer Advisor & Budget Reality

**ลำดับความสำคัญ:** P1

**สถานะ:** Done — 30 สิงหาคม 2026

**ระยะเวลาโดยประมาณ:** 4–7 วันพัฒนา

**เป้าหมาย:** แนะนำเฉพาะ transfer ที่ทำได้จริงและคุ้มค่าหลังคิด hit และช่วงเวลาถือครอง

### งานที่ต้องทำ

- [x] รับจำนวน Free Transfer, เงินในธนาคาร และราคาขายจริงจากผู้ใช้เมื่อ public API ไม่มี
- [x] สร้าง scenario `Roll`, `1 FT`, `2 FT` และ `-4` แยกกัน
- [x] ตรวจงบ, ตำแหน่ง, โควตาสโมสร และผู้เล่นเข้า/ออกทุก scenario
- [x] คำนวณ projected gain สุทธิใน 1, 3 และ 5 GW
- [x] หัก hit และแสดงค่าเสียโอกาสจากการใช้ Free Transfer
- [x] ใส่ confidence และ sensitivity ต่อ minutes/fixture ในคำแนะนำ
- [x] ให้ผลลัพธ์เป็น `Do`, `Consider` หรือ `Roll` พร้อมเหตุผล
- [x] แสดงทางเลือกอย่างน้อยหนึ่งตัวเมื่อเป้าหมายหลักเสี่ยงหรือราคาขยับ
- [x] แยกโหมด `Wildcard Lab` ออกจากคำแนะนำ transfer ประจำสัปดาห์อย่างชัดเจน
- [x] ห้ามนำ full-squad optimizer มาแสดงเหมือนเป็นแผน transfer ปกติ

### เกณฑ์เสนอการติดลบ

ระบบจะเสนอ `-4` ได้เมื่อ projected gain สุทธิหลังหัก 4 แต้มเป็นบวกในช่วงเวลาที่ระบุ,
มี expected minutes เหนือเกณฑ์ และยังคุ้มภายใต้ sensitivity case ที่สมเหตุสมผล
หากไม่ผ่าน ให้แสดงเป็นทางเลือกที่ไม่แนะนำเท่านั้น

### Acceptance criteria

- [x] ทุก transfer ที่ระบบรับรองทำได้จริงด้วยงบและข้อจำกัดของทีม
- [x] แสดงต้นทุน, ผลตอบแทน 1/3/5 GW และเหตุผลของช่วงถือครอง
- [x] ไม่มีคำแนะนำ `-4` โดยไม่แสดง net gain และ downside case
- [x] ถ้าราคาขายจริงไม่ทราบ ระบบไม่รับรองว่า transfer ทำได้ และขอค่าจากผู้ใช้ก่อน
- [x] แผน transfer ไม่ถูกปะปนกับการสร้างทีม 15 คนใหม่
- [x] มี automated tests ครอบคลุมงบ, hit, club quota และ edge cases

### ผลส่งมอบ

- `transfer-advisor-1.0` สร้าง candidate shortlist จากทีมจริงที่ประกาศล่าสุด และหน้าเว็บ
  ค้นแผนหลายตัวเลือกภายใต้ข้อมูลส่วนตัวที่ผู้ใช้กรอก
- ข้อมูล Free Transfer และราคาขายใช้ storage namespace ตามฤดูกาลและ Team ID
  และจะถูกต่อท้าย briefing เฉพาะตอนคัดลอก
- ราคาปัจจุบันใช้สร้าง shortlist ได้ แต่แผนจะขึ้นว่า “ต้องยืนยันราคา” จนกว่าจะมีราคาขายจริง
- เกณฑ์ `-4` ตรวจผลสุทธิ, downside, expected minutes, start probability และ confidence;
  ถ้าไม่ผ่านจะแสดงเป็น “พิจารณา” หรือ “เก็บ FT” ไม่ใช่ “ทำ”
- Browser QA ผ่าน desktop/mobile, persistence, Team ID gate, briefing copy และไม่มี
  console error; การคำนวณ scenarios ชุดทดสอบใช้เวลาประมาณ 0.12 วินาที
- กติกาอ้างอิงจาก [FPL transfer rules](https://www.premierleague.com/en/news/2174907)
  และ [FPL FAQ](https://www.premierleague.com/en/news/4661030)

---

## Phase 4 — News, Minutes & Risk Layer

**ลำดับความสำคัญ:** P1/P2

**สถานะ:** Done (30 สิงหาคม 2026)

**ระยะเวลาโดยประมาณ:** 4–6 วันพัฒนา

**เป้าหมาย:** นำข่าวล่าสุดมาใช้ปรับความเสี่ยงโดยแยกข้อเท็จจริงออกจากข้อสันนิษฐาน

### งานที่ต้องทำ

- [x] ดึงสถานะ availability จาก FPL และ timestamp ล่าสุด
- [x] รองรับข่าวแถลงของสโมสรจากแหล่งทางการ พร้อมลิงก์และเวลาที่เผยแพร่
- [x] รองรับ minutes/การเดินทางจากบอลกลางสัปดาห์ใน evidence contract เดียวกัน
- [x] ใช้ predicted lineup เป็นแหล่งรองและบังคับป้ายว่าเป็นการคาดการณ์
- [x] คำนวณ start probability และ expected minutes adjustment
- [x] แสดง risk badge: injury, rotation, suspension, travel และ data stale
- [x] ทำ manual override พร้อมเหตุผลและ Gameweek ที่หมดอายุ
- [x] เก็บ source snapshot เพื่อ audit ว่าคำแนะนำ ณ เวลานั้นใช้ข้อมูลใด
- [x] เพิ่ม pre-deadline refresh และ fallback เมื่อแหล่งข่าวใช้ไม่ได้

### Acceptance criteria

- [x] ทุกข่าวมี source, timestamp และประเภท `ข้อเท็จจริง` หรือ `ข้อสันนิษฐาน`
- [x] ข่าวสำคัญเปลี่ยน expected minutes และคำแนะนำอย่างตรวจสอบย้อนกลับได้
- [x] ข่าวเก่าหรือแหล่งข้อมูลล้มเหลวมีคำเตือน ไม่ถูกแสดงเสมือนข้อมูลล่าสุด
- [x] manual override ไม่ค้างข้าม Gameweek โดยไม่ตั้งใจ
- [x] ระบบยังทำงานได้เมื่อ news source บางแหล่งไม่พร้อม

### สิ่งที่ส่งมอบจริง

- `risk-layer-1.0` ใช้ FPL availability เป็น fallback อัตโนมัติ และรับ curated evidence
  จาก `data/risk-evidence.json` โดย validate source URL, เวลา, ประเภทคำกล่าว และวันหมดอายุ
- ลำดับแหล่งข้อมูลคือข่าวสโมสรทางการ, FPL/การแข่งขันทางการ, override ของผู้ใช้ และ
  predicted lineup; แหล่งหลังสุดเป็นข้อสันนิษฐานและถูกจำกัดผลกระทบไม่เกิน ±15 นาที/±15%
- ทุก adjustment เก็บค่าก่อน–หลังและ evidence ID ใน snapshot; XI, กัปตัน, สำรอง และ
  Transfer Advisor ใช้ค่าหลัง Risk Check ชุดเดียวกัน
- หน้า `News & Risk` เพิ่มหลักฐานชั่วคราวใน Browser ได้ ข้อมูลแยกตามฤดูกาลและ Team ID
  และผูกกับ Gameweek เป้าหมาย จึงไม่ไหลไปใช้ข้าม GW โดยไม่ตั้งใจ
- GitHub Actions มีรอบ refresh เพิ่มก่อน deadline ที่พบบ่อย พร้อม stale-cache/FPL fallback;
  unit tests ครอบคลุมข่าวเก่า, evidence ผิดรูปแบบ, override หมดอายุ และ source file หาย
- ระบบไม่ scrape ข่าวสโมสรแบบไร้การควบคุม ผู้ใช้หรือผู้ดูแลต้องใส่รายการที่ตรวจแล้วพร้อม
  URL และเวลา เพื่อรักษาคุณภาพและลิขสิทธิ์ของแหล่งข่าว

---

## Phase 5 — Chip & Multi-GW Planner

**ลำดับความสำคัญ:** P2

**สถานะ:** Done (31 สิงหาคม 2026)

**ระยะเวลาโดยประมาณ:** 5–8 วันพัฒนา

**เป้าหมาย:** วางแผน transfer และชิปจากค่าเสียโอกาสหลาย Gameweek ไม่ตัดสินจาก GW เดียว

### งานที่ต้องทำ

- [x] สร้าง planner ระยะ 3–6 GW พร้อม fixture horizon
- [x] เก็บสถานะชิปที่มีอยู่และกฎฤดูกาลปัจจุบัน
- [x] ประเมิน Bench Boost จากคะแนนคาดการณ์ของสำรองทั้ง 4 คนเทียบโอกาสในอนาคต
- [x] ประเมิน Triple Captain จาก ceiling, minutes และ fixture concentration
- [x] แยก Wildcard planner และ Free Hit planner เป็น scenario อิสระ
- [x] แสดง `Use now` / `Save` พร้อม opportunity cost และ Gameweek ทางเลือก
- [x] สร้าง transfer path หลักและแผนสำรองหากราคา/ข่าวเปลี่ยน
- [x] ให้ผู้ใช้บันทึก plan และอัปเดตเมื่อ deadline ผ่าน
- [x] ตรวจ chip rules และจำนวนครั้งที่ใช้ได้จากกฎล่าสุดก่อนเปิดคำแนะนำ

### Acceptance criteria

- [x] ทุกคำแนะนำชิปมีเหตุผล, expected gain, ความเสี่ยง และ Gameweek เปรียบเทียบ
- [x] Bench Boost ประเมินจากผู้เล่นครบ 15 คนและจัด XI/bench ถูกกฎ
- [x] ไม่แนะนำชิปที่ใช้ไปแล้วหรือผิดกฎฤดูกาล
- [x] แผน 3–6 GW ยังคงผ่านงบและข้อจำกัดหลังทุก transfer
- [x] การเปลี่ยนสมมติฐานสำคัญทำให้เห็นผลกระทบต่อแผนได้
- [x] ระบบไม่กดใช้ชิปหรือยืนยัน transfer ใน FPL แทนผู้ใช้

### สิ่งที่ส่งมอบและผลตรวจ

- `chip-planner-1.0` และ `gameweek-decision-5.0` เชื่อม JSON, หน้าเว็บ และ Briefing แล้ว
- Free Hit มีทีมจำลองสำหรับ GW เดียวและคืนทีมเดิม; Wildcard มีทีมจำลองระยะหลาย GW แยกกัน
- transfer path ประเมินกำไรจาก XI+C เทียบ Roll, วางได้สูงสุดสอง moves ในช่วงที่เห็น
  และแผนสำรองจะไม่ซื้อเป้าหมายแรกของแผนหลักซ้ำ
- บันทึกทั้งชิปและเส้นทางพร้อม snapshot ของแผน; ข้อมูล/ข่าว/ราคาขายเปลี่ยนจะขอทบทวน
  และสถานะชิปชั่วคราวไม่ถูกใช้ข้าม Gameweek
- กติกาที่ตรวจเมื่อ 30 สิงหาคม 2026 ถูกผูกกับฤดูกาล 2026/27; ฤดูกาลใหม่ที่ยังไม่ตรวจจะถูกบล็อก
- ตรวจผ่าน Python 54 tests, Browser logic 6 tests และ doctor 15/15; ทดสอบการบันทึก/เปิดใหม่
  และเพิ่มข่าวจำลองบน Browser จริงแล้ว โดยนำข้อมูล QA ที่สร้างออกหลังทดสอบ
- ราคาขายอนาคตยังเป็นสมมติฐาน และไม่มีการรับประกันแต้ม/ไม่มี global multi-GW optimization
  ที่ครอบคลุมทุกเส้นทาง; Phase 2 ยังรอผล backtest เพิ่มตามเดิม

---

## Phase 6 — UX, QA & Production Release

**ลำดับความสำคัญ:** P2

**สถานะ:** Done — 31 สิงหาคม 2026; CI, เว็บไซต์จริง และ hosted restore rehearsal ผ่านแล้ว

**ระยะเวลาโดยประมาณ:** 3–5 วันพัฒนา

**เป้าหมาย:** ทำให้ระบบเร็ว เข้าใจง่าย ทดสอบได้ และ deploy อย่างมั่นใจ

### งานที่ต้องทำ

- [x] จัด navigation ใหม่: This Gameweek, Transfers, Planner, Players และ Diagnostics
- [x] ทำ responsive QA บนมือถือ แท็บเล็ต และ desktop
- [x] ตรวจ keyboard navigation, contrast, screen-reader labels และ reduced motion — automated baseline ผ่าน; ไม่ใช่ full VoiceOver/WCAG audit
- [x] เพิ่ม loading, empty, stale, partial failure และ offline states
- [x] เพิ่ม unit, integration และ end-to-end tests สำหรับ flow หลัก (Python 60, JavaScript 20 และ browser E2E 26 cases ผ่านใน CI)
- [x] สร้าง fixture สำหรับ regression ของทีมจริงโดยไม่เก็บข้อมูลลับ
- [x] เพิ่ม schema/version compatibility ระหว่าง pipeline กับหน้าเว็บ
- [x] เพิ่ม deployment smoke test และวิธี rollback (local artifact restore และ hosted restore rehearsal ผ่านแล้ว)
- [x] บันทึก model version, data timestamp และ release version บนหน้า Diagnostics
- [x] อัปเดตคู่มือผู้ใช้, architecture, testing และ model card
- [x] เพิ่ม decision log แบบ local-first เพื่อเทียบคำแนะนำกับผลจริงโดยไม่ส่งข้อมูลออก

### Release gates

- [x] Flow `เลือกทีม → refresh → รับคำแนะนำ → copy briefing` ผ่าน Browser จริงและชุดอัตโนมัติใน CI
- [x] ไม่พบ P0/P1 bug ค้างจากขอบเขต local QA นี้ (ไม่ใช่การรับรองว่าไม่มีบั๊กทุกกรณี)
- [x] stale/mismatch/error states ผ่านการทดสอบ
- [x] หน้า This Gameweek ใช้งานได้บนหน้าจอมือถือทั่วไป (375px, tablet 768px, desktop 1280px)
- [x] performance และ accessibility ผ่าน baseline เริ่มต้นและ CI keyboard gate; ไม่มี historical timing จึงไม่อ้างว่าเร็วกว่า Phase 5
- [x] GitHub Pages deploy ผ่าน smoke test และมีวิธีย้อนรุ่นที่ทดลองแล้ว — hosted restore ใช้ artifact รุ่นเดียวกันเพื่อไม่เปลี่ยนผู้ใช้กลับไปโค้ดเก่า

### สิ่งที่ส่งมอบ

- release candidate `2.0.0-rc.1`, content-hashed asset URLs, build ID และ SHA-256 manifest
- Decision log เก็บ forecast, XI/C/VC/bench, แผนชิป/ย้ายตัว, version และผลที่ผู้ใช้กรอก
  แยกตามทีม/ฤดูกาล สูงสุด 100 รายการ พร้อม export และลบเฉพาะรายการ
- บันทึกแผนใหม่ไม่ได้เมื่อข้อมูลเก่า ออฟไลน์ หรือผ่าน deadline; ยังอ่านข้อมูลอ้างอิงได้
- [เว็บไซต์ออนไลน์](https://sarayutp.github.io/fpl-decision-lab/) เผยแพร่แล้ว; ผลตรวจและลิงก์ CI/deploy/restore อยู่ใน [PHASE_6_QA.md](PHASE_6_QA.md)
- ผู้ใช้ cache รุ่นเดิมอาจต้อง refresh หนึ่งครั้ง; ไม่ต้องล้างข้อมูลทีมที่บันทึกใน Browser
- การตรวจอุปกรณ์จริง Safari/iOS และ VoiceOver ยังเป็นงานติดตาม ไม่รวมในผล automated baseline นี้
- Phase 2 ยัง `In review` ตามเดิม ไม่ได้ยกระดับความแม่นของโมเดลเพราะ UI/QA ผ่าน

---

## Phase 7 — Advanced Strategy (Optional)

เริ่มหลัง M1–M4 ใช้งานได้จริงและมีข้อมูลเพียงพอว่าผู้ใช้ต้องการ

**สถานะ:** In progress — Phase 7A เผยแพร่แล้ว; Phase 7B (Decision card) อยู่ระหว่างตรวจรับ 31 สิงหาคม 2026; ส่วนอื่นยัง Deferred

**ระยะเวลาโดยประมาณ:** ประเมินหลังเก็บ feedback จาก v2

- [ ] Mini-league mode: ปรับความเสี่ยงตามแต้มตาม/นำและจำนวน GW ที่เหลือ
- [ ] Effective ownership และ rank-risk simulation
- [ ] Fixture swing และ watchlist alerts
- [ ] รองรับหลายทีม/หลายบัญชีโดยแยกข้อมูลสมบูรณ์
- [x] Compare scenarios แบบ side-by-side เฉพาะ GW ปัจจุบัน (Phase 7A)
- [ ] แชร์ decision card ที่ไม่เปิดเผยข้อมูลเกินจำเป็น
- [ ] Notification ก่อน deadline เมื่อข่าวทำให้คำแนะนำเปลี่ยน

ฟีเจอร์ใน Phase นี้ต้องไม่ทำให้คำตอบหลักประจำ Gameweek ซับซ้อนขึ้น

### Phase 7A — Compare plans A/B

**สถานะ:** Done — รุ่น `2.1.0-rc.1` เผยแพร่พร้อม CI และ published smoke ผ่าน 31 สิงหาคม 2026

เริ่มจากการเทียบแผนใน GW ปัจจุบัน โดยใช้ Planner/โมเดลเดิม ไม่เริ่ม mini-league,
EO/rank simulation หรือ notification ก่อนมี feedback เพิ่ม ส่วน Phase 2 ยังคง In review

- [x] เก็บฉบับร่างของ Planner เป็นแผน A/B โดยไม่กดบันทึก Planner หรือเปลี่ยนบัญชี FPL
- [x] แสดงย้ายตัว, ชิป, XI/C/VC/bench, xPts ก่อน/หลังชิปและหัก hit, งบและความเสี่ยงคู่กัน
- [x] ใช้เฉพาะ GW ปัจจุบัน ไม่รวม move ใน GW อื่นหรือมูลค่าชิป/FT ในอนาคตเป็นส่วนต่าง
- [x] ตรวจ XI 11 + bench 4, club quota, ชิปที่ใช้ได้, FT, งบ และความตรงกันของ transfer path
- [x] แยก storage ตามทีม/ฤดูกาล/GW; freeze ตัวเลขและหยุด delta เมื่อ snapshot/ข่าว/ราคา/โมเดลเปลี่ยน
- [x] มี export JSON และลบเฉพาะช่องที่ยืนยัน; storage เสีย/เต็มไม่เขียนทับเดิมและไม่อ้างว่าบันทึกสำเร็จ
- [x] Browser CI และ published smoke ผ่านก่อนปิดงานส่วนนี้ (รวม Python/JS/browser 132 cases)

ขอบเขตแรกยังไม่มีเลือก A/B ไปใช้โดยอัตโนมัติ, import, แชร์ออนไลน์ หรือเทียบผลทั้งช่วงหลาย GW
ไม่ใช้ delta นี้แทนเกณฑ์แนะนำ -4 ของ Transfer Advisor ผลตรวจ: [PHASE_7A_QA.md](PHASE_7A_QA.md)

### Phase 7B — Decision card สำหรับแชร์

**สถานะ:** In review — รุ่น `2.2.0-rc.1`; เริ่ม 31 สิงหาคม 2026

ต่อยอดแผน A/B โดยให้ดาวน์โหลด/คัดลอกการ์ดที่ผู้ใช้ตรวจแล้ว ไม่เริ่มระบบโพสต์ออนไลน์
หรือ notifications และไม่เพิ่มแหล่งข้อมูล/ค่าใช้จ่ายภายนอก

- [x] เลือก A/B และดูตัวอย่าง PNG พร้อมข้อความเดียวกันที่อ่านได้ด้วย screen reader
- [x] แสดง GW, XI/C/VC/bench, ชิป, ย้ายตัว, xPts สุทธิหลัง hit และข้อจำกัด/เวลาโมเดล
- [x] ใช้ allowlist ไม่ส่งออกชื่อทีม/ผู้จัดการ, Team ID, งบ, ราคาขาย, ชื่อแผนและบันทึกส่วนตัว
- [x] ดาวน์โหลด PNG/TXT หรือคัดลอกโดยไม่ upload/post และไม่เขียน Planner/Journal
- [x] ตรวจ context และ record ซ้ำก่อน export; เปลี่ยนแผน/ข่าว/ราคา/slot ล้าง preview เดิม
- [x] ปิดการสร้าง/ส่งออกเมื่อ offline/stale/deadline/mismatch; รองรับ canvas/clipboard failure
- [ ] Browser CI และ published smoke ผ่านก่อนปิดงานส่วนนี้

การ์ดยังเปิดเผยรายชื่อและแผนของผู้ใช้ ไม่ใช่การ anonymize อย่างสมบูรณ์ และไฟล์ที่ส่งออกไปแล้ว
เรียกคืนหรือปรับตามข่าวไม่ได้ ไม่ใช่ผลทั้งช่วงหลาย GW หรือคำแนะนำให้ใช้ชิป/-4
ผลตรวจ: [PHASE_7B_QA.md](PHASE_7B_QA.md)

---

## ลำดับการเริ่มงานที่แนะนำ

### Sprint 1 — แก้ “ทีมไม่ตรง” ให้จบ

1. ทำ Team ID configuration และ identity banner
2. เพิ่ม mismatch/freshness gates
3. namespace Squad Lab ตามบัญชี
4. เขียน test และตรวจรับกับ Team ID `5105794`

### Sprint 2 — ส่งมอบหน้า This Gameweek

1. กำหนด `gameweek_decision` data contract
2. ทำ owned-squad optimizer สำหรับ XI/C/VC/bench
3. สร้าง decision cards และ responsive layout
4. ทำให้หน้าเว็บกับ AI briefing ใช้ผลลัพธ์เดียวกัน

### Sprint 3 เป็นต้นไป

ทำ Phase 2 และ 3 เป็นลำดับถัดไป จากนั้นเพิ่ม News/Risk, Multi-GW Planner และ QA
ตามลำดับ โดยไม่ควรเริ่ม Phase 5 ก่อน transfer recommendation ผ่าน budget reality

## การติดตามสถานะ

ใช้สถานะเดียวกันทุก Phase:

- `Not started` — ยังไม่เริ่ม
- `In progress` — มีเจ้าของงานและกำลังพัฒนา
- `In review` — โค้ดเสร็จและกำลังทดสอบ/ตรวจรับ
- `Done` — ผ่าน acceptance criteria ทั้งหมด
- `Blocked` — ระบุ blocker และผู้ตัดสินใจถัดไป

ทุก issue ควรผูกกับ Phase, priority, acceptance criterion และหลักฐานการทดสอบ
เมื่อปิด Phase ให้อัปเดต checklist ในเอกสารนี้พร้อมลิงก์ไปยัง release หรือผลตรวจรับ

## สิ่งที่ไม่อยู่ในขอบเขตของ v2

- เก็บ password, session cookie หรือรหัสยืนยันของบัญชี FPL
- กด transfer, เปลี่ยน captain หรือใช้ชิปในเว็บไซต์ FPL โดยอัตโนมัติ
- รับประกันคะแนนหรืออันดับ
- ซื้อ data provider แบบเสียเงินก่อนพิสูจน์ว่าข้อมูลฟรีไม่เพียงพอ
- เพิ่มฟีเจอร์ social/mini-league ก่อนแก้ความถูกต้องและการตัดสินใจหลัก

## นิยามความสำเร็จของผลิตภัณฑ์

v2 ถือว่าประสบความสำเร็จเมื่อเว็บใช้ทีมจริงอย่างถูกต้อง สร้างคำแนะนำที่ทำได้จริง
อธิบายความเสี่ยงได้ และผู้ใช้ตัดสินใจครบทั้ง transfer, XI, captain, bench และ chip
ได้จากหน้าเดียว โดยไม่ต้องตีความ Dashboard หลายส่วนเอง
