# Model Card — Explainable xP v2.0

อัปเดตล่าสุด: 31 สิงหาคม 2026

## Phase 6: การทบทวนผลจริง

Decision log บันทึก forecast พร้อม release/model version และทีมที่เลือกใน Browser
ผลจริงที่ผู้ใช้กรอกเป็น `user_reported` ไม่ใช่ข้อมูลที่ยืนยันจาก FPL ระบบแสดงส่วนต่างเฉพาะ
เมื่อผู้ใช้ยืนยันว่า XI/C/VC/ชิป/hit ตรงกับบันทึก ผลต่างมีความผันผวนและไม่ใช่ causal uplift
หรือหลักฐานความแม่นจากตัวอย่างเดียว Phase 2 ยังคงรอข้อมูล backtest เพิ่มตามเดิม
การผ่าน UI, schema หรือ release tests ไม่ได้หมายความว่า prediction ผ่านการสอบเทียบแล้ว

## เป้าหมาย

คาดคะแนน FPL สำหรับ Gameweek ถัดไปและช่วง 5 GW โดยลดการตอบสนองเกินไปกับผลงาน
เพียง 1–2 นัด พร้อมแสดง expected minutes, โอกาสตัวจริง, ช่วงความไม่แน่นอน,
confidence และธงคุณภาพข้อมูล

โมเดลมีคะแนนสองชนิดที่ห้ามใช้แทนกัน:

- `expected_points` หรือ `xPts` คือคะแนน FPL ที่คาดก่อนคูณกัปตัน
- `ranking_score` คือ expected points ที่ปรับความมั่นใจเล็กน้อยเพื่อใช้เรียงผู้เล่น

field `xp_next` และ `xp_horizon` ยังคงอยู่เพื่อ compatibility แต่มีค่าเท่ากับ
`expected_points_next` และ `expected_points_horizon` ไม่ใช่ ranking score

## Prior และการ shrink

เมื่อไม่มีประวัติฤดูกาลก่อนครบทุกคน ระบบใช้ prior จากตำแหน่งและราคา:

```text
observed_weight = current_minutes / (current_minutes + 900)
points_per_90   = prior × (1 - observed_weight)
                + observed_points_per_90 × observed_weight
```

observed points ต่อ 90 นาทีถูกจำกัดช่วงก่อน blend เพื่อไม่ให้หนึ่งนัดดันคะแนนสูงผิดปกติ
ราคาเป็นเพียง proxy ของบทบาท จึงแสดง `small_sample` และ confidence ต่ำจนกว่าจะมีนาที
สะสมมากขึ้น

## Expected minutes และโอกาสตัวจริง

role prior จากตำแหน่ง/ราคาถูก blend กับนาทีและ starts ปัจจุบัน โดยให้น้ำหนักข้อมูลใหม่:

```text
role_weight = completed_team_matches / (completed_team_matches + 4)
```

ผู้เล่นที่ไม่มีนาทีหลังทีมแข่งอย่างน้อยสองนัดถูกลด role prior เพิ่มเติม สถานะบาดเจ็บ,
แบน และ chance of playing จะลดทั้ง expected minutes และ start probability

หลังสร้าง baseline แล้ว `risk-layer-1.0` อาจปรับเฉพาะ Gameweek ถัดไปจากหลักฐานที่ผ่าน
validation ทุก adjustment เก็บ source, เวลา, evidence ID และค่าก่อน–หลัง predicted lineup
ถูกบังคับเป็น inference และจำกัดการเปลี่ยนไม่เกิน ±15 นาที/±15% โอกาสตัวจริง
หลักฐานเกิน 24 ชั่วโมงหรือหมดอายุไม่เปลี่ยน projection

## ปัจจัยคะแนน

- current-season points ต่อ 90 นาทีแบบ shrink
- expected goal involvements ต่อ 90 นาที เมื่อ FPL มีค่า
- ลำดับ penalties, direct free kicks และ corners เมื่อมีค่า
- FPL `ep_next` น้ำหนัก 25% และ blend เพียงครั้งเดียวต่อ Gameweek
- fixture difficulty และ home/away
- team attack/defence strength เฉพาะเมื่อ FPL เผยค่าที่ไม่เป็นศูนย์
- availability, Double/Blank Gameweek และ fatigue discount สำหรับนัดที่สอง
- clean-sheet probability แบบ heuristic สำหรับ GKP/DEF เพื่ออธิบายความเสี่ยง

## Double และ Blank Gameweek

Blank ได้ expected points และ expected minutes เป็นศูนย์ Double รวม projection ราย fixture
แต่ลด expected minutes ของนัดที่สองเหลือ 90% และไม่บวก `ep_next` ซ้ำสองครั้ง

## Confidence และช่วงคะแนน

confidence score ใช้ sample minutes, หลักฐานบทบาท, availability certainty และการมี
official estimate แบ่งเป็น `low`, `medium`, `high` ช่วงคะแนนเป็น decision range เพื่อ
สื่อความไม่แน่นอน ยังไม่ใช่ prediction interval ที่ผ่าน statistical calibration

ธงหลัก:

- `small_sample`
- `early_season`
- `no_minutes`
- `official_estimate_missing`
- `team_strength_unavailable`
- `double_gameweek` / `blank_gameweek`
- `risk_layer_adjusted` และ `risk_injury` / `risk_rotation` / `risk_suspension` /
  `risk_travel` เมื่อมี evidence ที่ active

## Captain score

Captain Radar ใช้ expected points, expected minutes, start probability, attacking signal
และเพดานของช่วงคะแนน ผู้เล่นต้องผ่านเกณฑ์นาทีและโอกาสตัวจริงก่อน กองหลัง/ผู้รักษาประตู
มี penalty เล็กน้อยเพื่อป้องกันตัวเลือกผิดธรรมชาติจาก clean sheet ระยะสั้น

## Optimizer

MILP และ owned-squad selector ใช้ `ranking_score` เลือก squad/XI และใช้
`captain_score` เลือก C/VC แต่รายงานผลรวมเป็น expected points จริง ข้อจำกัดงบ,
ตำแหน่ง, formation และโควตาสโมสรเหมือนเดิม

## Chip & Multi-GW Planner

`chip-planner-1.0` ใช้ expected points ราย Gameweek เพื่อจัด XI/C/VC/bench ของทีมจริง
ในช่วง 3–6 GW และรายงาน marginal gain ของ Bench Boost/Triple Captain ส่วน Free Hit และ
Wildcard ใช้ legal 15-player optimizer เป็น scenario เปรียบเทียบ ค่า opportunity cost คือ
ผลต่างระหว่าง GW ปัจจุบันกับ GW ที่ดีที่สุดที่มองเห็น ไม่ใช่ค่าของทั้งฤดูกาล

FH/WC จะไม่ขึ้น `ใช้ตอนนี้` หากผู้เล่นในทีมจริงที่มี confidence ระดับ medium/high ต่ำกว่า
70% แม้ expected gain ดิบสูง เพื่อลดการใช้ชิปจากสัญญาณต้นฤดูกาลที่ยังไม่นิ่ง Planner ใช้
ราคาปัจจุบันในการคัดเลือกและตรวจเส้นทาง จึงต้องยืนยันราคาขายจริงและ FT ใน Transfer Advisor
ก่อนทำจริง

Free Hit ใช้ objective หนึ่ง GW ส่วน Wildcard ใช้ balanced horizon คนละการแก้ปัญหา
ค่าเปรียบเทียบของชิปไม่ข้ามชุดครึ่งฤดูกาล (GW19/20) และไม่อ้างว่า GW นอกช่วงโมเดลด้อยกว่า
Bench Boost ใช้ผลรวมสำรองก่อนหักโอกาส autosub; Wildcard เทียบ no-transfer baseline
ไม่ใช่ค่ากำไรสุทธิเทียบเส้นทาง FT ที่ดีที่สุด จึงต้องพิจารณาแผนปกติคู่กัน

transfer path ใช้ shortlist แบบ greedy สูงสุดสอง moves จากนั้นประเมิน legal XI+C
ทุก GW ไม่ใช่ global search ของทุกลำดับการย้ายและทุก chip combination แผนสำรองตัดผู้เล่น
ขาเข้าเป้าหมายแรกของแผนหลักออกทั้งเส้นทาง งบใช้ราคาปัจจุบันจนกว่าจะกรอกราคาขายจริง

## Quality guardrails

Live profile วันที่ 30 สิงหาคม 2026 จำนวน 623 คน:

| Metric | v1 | v2 |
|---|---:|---:|
| median GW ถัดไป | 0.71 | 1.41 |
| p90 | 5.25 | 2.95 |
| p99 | 12.79 | 4.88 |
| maximum | 17.81 | 7.33 |
| low-sample สูงกว่า 10 | ไม่ได้บล็อก | 0 |

build จะหยุดหาก single-fixture projection เกิน 12, มี low-sample projection เกิน 10,
model version ไม่ตรงกับ decision contract หรือ quality guardrails ไม่ผ่าน

## Rolling backtest

รันด้วย:

```bash
.venv/bin/python scripts/backtest_model.py --player-limit 100
```

ระบบใช้ expanding window และบังคับให้ training Gameweek ต่ำกว่า target Gameweek ทุกแถว
ผลรอบแรกจากผู้เล่น ownership สูง 40 คนมีเพียง GW2 หนึ่งช่วงประเมิน:

| Model | MAE | Rank correlation | Top-10 hit rate |
|---|---:|---:|---:|
| xP v2 | 2.8029 | 0.2526 | 0.30 |
| price/role prior | 2.7682 | 0.3057 | 0.40 |
| recent points | 4.2750 | 0.0932 | 0.40 |

v2 ชนะ recent-points baseline ใน MAE และ rank correlation แต่ยังไม่ชนะ price/role prior
และมี evaluation เพียงหนึ่ง Gameweek จึงมีสถานะ `insufficient_history` ต้องสะสมอย่างน้อย
3 evaluation Gameweeks ก่อนใช้ตัดสินว่าโมเดลดีกว่า baseline อย่างน่าเชื่อถือ

## ข้อจำกัด

- ยังไม่มี previous-season prior ที่ match ผู้เล่นครบทุกคน
- FPL ไม่เปิด historical `ep_next` ผ่าน element-summary จึง backfill baseline นี้ไม่ได้
- team strength ของฤดูกาลปัจจุบันยังเป็นศูนย์ ระบบจึง fallback ไป fixture difficulty
- clean-sheet probability และช่วงคะแนนยังไม่ผ่าน calibration ระยะยาว
- ไม่มี press conference NLP/ตัวรวบรวมข่าวทุกสโมสรอัตโนมัติ หรือ bookmaker odds;
  predicted lineup และข่าวทางการต้องเข้าผ่าน evidence ที่มี source/เวลา
- ราคาขายจริงของผู้จัดการไม่อยู่ใน public API
- ช่วง Planner ปัจจุบันเห็นเพียง 5 GW จึงยังไม่รู้ blank/double หรือโอกาสชิปหลัง horizon

สถานะโมเดล: `In review` จนกว่า rolling backtest จะมีอย่างน้อย 3 Gameweeks และผ่าน
acceptance criteria เทียบ baseline
