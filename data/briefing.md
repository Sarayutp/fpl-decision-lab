# FPL Decision Briefing

> ใช้ไฟล์นี้กับ ChatGPT Plus ได้โดยอัปโหลดหรือคัดลอกทั้งหมด ระบบนี้ไม่ต้องใช้ OpenAI API key

## คำสั่งสำหรับ ChatGPT

คุณคือผู้ช่วยวิเคราะห์ Fantasy Premier League ของผม ให้ใช้ข้อมูลเชิงตัวเลขด้านล่างเป็นฐาน แล้วค้นเว็บเพื่อยืนยันข่าวบาดเจ็บ การแถลงข่าว โอกาสลงตัวจริง และการเลื่อนโปรแกรมล่าสุดก่อนเสนอคำตอบ แยกข้อเท็จจริงออกจากข้อสันนิษฐานอย่างชัดเจน อย่าแนะนำการติดลบ 4 แต้มเว้นแต่คาดว่าคุ้มจริงในระยะที่ระบุ สรุปเป็น: (1) transfers (2) starting XI (3) captain/vice (4) bench order (5) ความเสี่ยง และทางเลือกสำรอง หากข้อมูลนี้เก่าเกิน 24 ชั่วโมงให้เตือนผมก่อน

## สถานะข้อมูล

- สร้างเมื่อ: 2026-08-31T00:46:08.026467+00:00
- สถานะความสด: fresh
- ข้อมูลต้นทางเก่าสุด: 2026-08-31T00:46:08.415361+00:00
- เป้าหมาย: Gameweek 3
- Deadline: 2026-09-04T17:30:00+00:00
- Team ID: 5105794
- ชื่อทีม: Sarayut FC
- ผู้จัดการ: Sarayut Pangsri
- ยืนยันตัวตนทีม: ผ่าน
- ฤดูกาล: 2026-27
- คะแนนรวม: 170
- อันดับรวม: 114569
- โมเดล: xp-v2.0
- Model guardrails: passed
- นิยาม expected points: Forecast FPL points before captain multiplier.
- นิยาม ranking score: Expected points with a modest confidence adjustment for ordering.
- Transfer Advisor: transfer-advisor-1.0 / needs_user_input
- Risk Layer: risk-layer-1.0 / ready
- Chip Planner: chip-planner-1.0 / ready
- ข่าวหมดอายุหลัง: 24 ชั่วโมง

## News, Minutes & Risk

- Evidence ทั้งหมด: 183
- Curated evidence ที่ active: 0
- ข่าวเก่า: 0; ไม่ผ่าน validation: 0
- ผู้เล่นที่ถูกปรับนาที: 0
- Predicted lineup ถูกจัดเป็นข้อสันนิษฐานและไม่ใช้แทนข่าวทางการ

### Evidence ที่เกี่ยวกับทีมจริง

- [fact] Rodon — injury: Hamstring injury - 50% chance of playing | FPL Public API | เผยแพร่ 2026-08-30T16:00:08.564382+00:00 | สถานะ fresh | https://fantasy.premierleague.com/api/bootstrap-static/

### ผลกระทบต่อโมเดล

- ไม่มีการปรับนาทีจาก curated evidence ใน snapshot นี้

## คำแนะนำประจำ Gameweek

- สถานะแผน: ready
- ความมั่นใจรวม: low
- แหล่งทีม: published หลัง GW2

### 1) Transfer

- คำตอบ: กรอกข้อมูล — ตั้งค่า Transfer Advisor
- ความมั่นใจ: unavailable
- แนะนำการติดลบ: ไม่
- ข้อมูลที่ยังต้องกรอก: free_transfers, selling_prices
- เงินในธนาคารจาก FPL ล่าสุด: 0.0m
- Candidate shortlist: 157 moves

### 2) Starting XI

- Formation: 3-5-2
- Expected points XI รวมกัปตัน: 56.20
- GKP Verbruggen — ตัวจริง, คู่แข่ง LEE (H), xPts 2.76 (ช่วง 0.00–6.19), นาที 67, start 78%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- DEF Calafiori — ตัวจริง, คู่แข่ง CHE (H), xPts 3.53 (ช่วง 0.00–7.32), นาที 73, start 88%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- DEF Thomas — ตัวจริง, คู่แข่ง MCI (A), xPts 2.75 (ช่วง 0.00–6.19), นาที 59, start 67%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- DEF Maguire — ตัวจริง, คู่แข่ง EVE (A), xPts 2.38 (ช่วง 0.00–5.68), นาที 69, start 80%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- MID B.Fernandes [C] — ตัวจริง, คู่แข่ง EVE (A), xPts 7.68 (ช่วง 2.63–12.73), นาที 83, start 98%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- MID M.Sangaré — ตัวจริง, คู่แข่ง SUN (H), xPts 4.68 (ช่วง 0.60–8.76), นาที 65, start 74%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- MID Mbeumo — ตัวจริง, คู่แข่ง EVE (A), xPts 4.41 (ช่วง 0.44–8.38), นาที 75, start 89%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- MID Groß — ตัวจริง, คู่แข่ง LEE (H), xPts 4.10 (ช่วง 0.23–7.97), นาที 64, start 74%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- MID Szoboszlai — ตัวจริง, คู่แข่ง IPS (A), xPts 4.00 (ช่วง 0.16–7.84), นาที 71, start 83%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- FWD Haaland [VC] — ตัวจริง, คู่แข่ง COV (H), xPts 7.33 (ช่วง 2.39–12.27), นาที 83, start 98%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- FWD João Pedro — ตัวจริง, คู่แข่ง ARS (A), xPts 4.90 (ช่วง 0.77–9.03), นาที 64, start 74%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable

### 3) Captain / Vice

- Captain: B.Fernandes — xPts 7.68, นาที 83, confidence=low, EVE (A)
- Vice: Haaland — xPts 7.33, นาที 83, confidence=low, COV (H)
- ความมั่นใจ: low

### 4) Bench Order

- FWD Calvert-Lewin — สำรองลำดับ 1, คู่แข่ง BHA (A), xPts 2.86 (ช่วง 0.00–6.32), นาที 58, start 65%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- DEF Van Hecke — สำรองลำดับ 2, คู่แข่ง NFO (A), xPts 1.86 (ช่วง 0.00–4.99), นาที 69, start 80%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- DEF Rodon — สำรองลำดับ 3, คู่แข่ง BHA (A), xPts 1.30 (ช่วง 0.00–4.45), นาที 32, start 37%, confidence=low, risk=medium, flags=small_sample,early_season,team_strength_unavailable
- GKP Kinsky — ผู้รักษาประตูสำรอง, คู่แข่ง NFO (A), xPts 2.03 (ช่วง 0.00–5.22), นาที 67, start 78%, confidence=low, risk=low, flags=small_sample,early_season,team_strength_unavailable
- Expected points ม้านั่งรวม: 8.05

### 5) Chip

- คำตอบ: ใช้ Triple Captain — ใช้ใน GW3 ตามเงื่อนไขก่อน deadline
- Bench Boost expected points ปัจจุบัน: 8.05
- กำไรชิปที่แนะนำ: 7.68
- ค่าเสียโอกาสที่มองเห็น: 0.00
- ความมั่นใจ: low

## Multi-GW & Chip Planner

- ช่วงที่มองเห็น: GW3, GW4, GW5, GW6, GW7
- กติกา: 2 ชุดต่อฤดูกาล; 1 ชิปต่อ GW=ใช่
- คำเตือนช่วงโมเดล: เปรียบเทียบเฉพาะ GW3–GW7 ยังไม่เห็นโอกาสหลังช่วงโมเดล
- Bench Boost: unavailable | กำไร GW ปัจจุบัน 8.05 | ดีที่สุดที่มองเห็น GW4 8.46 | ค่าเสียโอกาส 0.41 | เคยใช้ GW2
- Triple Captain: use_now | กำไร GW ปัจจุบัน 7.68 | ดีที่สุดที่มองเห็น GW3 7.68 | ค่าเสียโอกาส 0.00
- Free Hit: save | กำไร GW ปัจจุบัน 11.98 | ดีที่สุดที่มองเห็น GW3 11.98 | ค่าเสียโอกาส 0.00
- Wildcard: save | กำไร GW ปัจจุบัน 26.08 | ดีที่สุดที่มองเห็น GW3 26.08 | ค่าเสียโอกาส 0.00

### Transfer path 3–6 GW

- แผนหลัก: GW3 Kinsky → Tzolakis (bank 0.0m); GW4 Van Hecke → Hall (bank 0.0m); กำไรช่วงโมเดล 8.20; ผ่านงบ/กฎ=ใช่
- แผนสำรอง: GW3 Van Hecke → Hall (bank 0.0m); GW4 Rodon → Ajayi (bank 0.5m); กำไรช่วงโมเดล 5.51; ผ่านงบ/กฎ=ใช่
- งบใช้ราคาปัจจุบันเป็นค่าประมาณ ต้องยืนยันราคาขายจริงและ FT ใน Transfer Advisor ก่อนทำจริง

## ทางเลือกสำรอง

- แผนปลอดภัย: เก็บ FT และสลับรองกัปตันขึ้นเป็นกัปตันหากข่าวตัวเลือกหลักไม่ชัด
- แผนเน้นเพดาน: ใช้ XI, captain และ bench ตาม ranking score สูงสุด โดยยืนยันข่าวก่อน deadline

## ข้อเท็จจริงจากข้อมูล

- FPL เปิดเผยเงินในธนาคารล่าสุด 0.0m
- เลือกจากผู้เล่น 15 คนที่ FPL เปิดเผยหลัง GW2
- Risk Layer ปรับนาทีของผู้เล่น 0 คนจากหลักฐานที่ยังใช้ได้
- ผู้รักษาประตูสำรองแสดงแยกจากลำดับผู้เล่นสนาม

## ค่าประมาณจากโมเดล

- เลือก formation ด้วย ranking score ที่รวม expected points และความมั่นใจ
- B.Fernandes มี expected points 7.68 ช่วง 2.63–12.73 และคาดนาที 83
- เรียงตัวสำรองสนามตาม ranking score ถัดไป
- กำไรคาดการณ์ GW ปัจจุบัน 7.68 แต้ม; ดีสุดที่มองเห็น GW3 7.68 แต้ม

## ข้อจำกัดและสิ่งที่ต้องยืนยัน

- ต้องกรอก Free Transfer และราคาขายจริงก่อนรับรองว่าแผนทำได้
- ต้องยืนยันข่าวและโอกาสลงก่อน deadline
- ค่าเสียโอกาสในช่วงที่มองเห็น 0.00 แต้ม
- กัปตัน B.Fernandes เพดานช่วงคะแนน 12.73, 1 นัด, คาดนาที 83, ตัวจริง 98% — ต้องยืนยันข่าวก่อน deadline

## คำเตือนจากระบบ

- No curated club press or midweek evidence is active; FPL status remains the fallback.

## ข้อจำกัด

- expected points คือคะแนน FPL ที่คาด ไม่ใช่การรับประกันผลลัพธ์
- ranking score ใช้จัดอันดับและอาจไม่เท่ากับ expected points
- ช่วงคะแนนเป็น decision range ที่ยังไม่ผ่าน statistical calibration เต็มฤดูกาล
- ระบบยังไม่รู้ราคาขายจริงของผู้เล่นแต่ละคนจากบัญชีส่วนตัว
- Free Transfer และราคาขายที่กรอกใน Browser จะถูกต่อท้าย briefing ตอนกดคัดลอก
- Current price ใช้สร้าง shortlist เท่านั้น ไม่ใช้รับรองว่า transfer อยู่ในงบ
- ข่าวด่วนและ predicted lineup ต้องยืนยันจากเว็บใกล้ deadline
- ข่าวที่เก่ากว่า 24 ชั่วโมงหรือหมดอายุจะไม่ถูกใช้ปรับ expected minutes
- ทีมจาก public API คือทีมที่ประกาศล่าสุด ไม่ใช่การเปลี่ยนแปลงที่ยังไม่ผ่าน deadline

## แหล่งที่มาของข้อมูล

- ตัวตนทีมและทีมที่ประกาศล่าสุด: FPL Public API (ข้อเท็จจริง)
- ทีมใน Squad Lab: Browser localStorage (ผู้ใช้กรอกและไม่รวมอยู่ในไฟล์นี้)
- expected points, ranking score และคำแนะนำ: FPL Decision Lab model (ค่าประมาณ)
- availability: FPL Public API; ข่าวสโมสร/นาที/lineup: Risk Layer พร้อม source snapshot
- กติกา FT และ -4: Premier League FPL transfer rules (ข้อเท็จจริง)
- กติกาชิป 2026/27: Premier League FPL chip rules และ FAQ (ข้อเท็จจริง)
- [What's happening with FPL chips in 2026/27?](https://www.premierleague.com/en/news/4679879/whats-happening-with-fpl-chips-in-202627)
- [FPL 2026/27 FAQ](https://www.premierleague.com/en/news/4661030)
