# Testing, Debugging and Troubleshooting

## Release checks

คู่มือรุ่น `2.3.0-rc.1` เพิ่ม Python 14 cases (รวม 76), JS 3 cases (รวม 47)
และ browser desktop/mobile 16 cases (รวม 68; รอ CI) สำหรับ menu/TOC, Markdown download,
no-JS/no-data, error-state access, print, responsive/keyboard และ offline navigation แยกหน้า
รายละเอียดและสถานะเผยแพร่: [USER_GUIDE_QA.md](USER_GUIDE_QA.md)

Phase 7B เพิ่ม card/privacy tests 11 ข้อ (JS รวม 44), ตรวจ linked asset อีกหนึ่งกรณี
(Python รวม 62) และ browser card flow อีก 14 cases (รวม 52).
ผ่านทั้งหมด 158 cases พร้อม published smoke; ผลตรวจ: [PHASE_7B_QA.md](PHASE_7B_QA.md)

Phase 7A เพิ่ม comparison logic tests 13 ข้อ (JS รวม 33), Python legacy-manifest test
(รวม 61) และ browser A/B flow เพิ่ม 12 cases (desktop/mobile รวม 38).
ผลตรวจรุ่นนี้: [PHASE_7A_QA.md](PHASE_7A_QA.md); ตัวเลข Phase 6 ด้านล่างเป็นหลักฐานของรุ่นก่อน

ผลย้อนหลัง Phase 6: [PHASE_6_QA.md](PHASE_6_QA.md)

```bash
pytest
node --test tests/*.test.cjs
for file in dashboard/assets/*.js dashboard/sw.js; do node --check "$file"; done
python -m fpl_mvp build-site
python scripts/check_frontend.py
python scripts/smoke_site.py dist
python scripts/smoke_site.py http://127.0.0.1:8000
```

Python release tests ซ้อม restore ใน temporary directories โดยไม่เปลี่ยน production
JS tests ใช้ VM/fake cache ตรวจ deadline, identity/timestamp, storage failure, immutable log
และ offline provenance โดยไม่อ่าน storage จริงของผู้ใช้

### Browser QA ที่ทำซ้ำได้

```bash
python scripts/qa_server.py --port 8011
```

เปิด `http://127.0.0.1:8011/qa.html` เพื่อเลือก 375/768/1280px และ ready/stale/partial/
mismatch/incompatible/error/empty/deadline/offline fixture. QA นี้ไม่เรียก FPL จริง
และใช้ origin แยกจากพอร์ต 8000. แบบ offline fixture ตรวจข้อความ; การตรวจ cache จริง
ต้องเปิดหน้าแอปสำเร็จ รอ service worker ติดตั้ง แล้วหยุดเฉพาะ QA server และ reload

### Automated browser suite สำหรับ CI

```bash
npm ci
npx playwright install --with-deps chromium
# เปิด QA server ในอีก terminal ก่อน
npm run test:e2e
```

มี 26 cases สำหรับ Chromium desktop/mobile: ยืนยันทีม, refresh, copy clipboard, journal
persistence, actual result, data states, viewport 375/768/1280px, accessible names,
contrast baseline, skip-link focus และ reduced motion. ผ่าน CI แล้วเมื่อ 31 สิงหาคม 2026
พร้อม Python 60 และ JavaScript 20 tests; ลิงก์ผลจริงอยู่ใน [PHASE_6_QA.md](PHASE_6_QA.md)

Performance budget ใน `tests/fixtures/frontend-budget.json` เป็น baseline เริ่มต้น
ไม่ใช่ Core Web Vitals หรือ full accessibility certification. การตรวจบนอุปกรณ์จริง
Safari/iOS และ VoiceOver ยังเป็นงานติดตามนอก automated baseline ที่ผ่านแล้ว

## ชุดตรวจมาตรฐาน

```bash
cd /Users/sarayutp/Project/10_FPL
source .venv/bin/activate
python -m compileall -q src tests
pytest
node --test tests/planner_state.test.cjs
python -m fpl_mvp all --force-refresh
python scripts/backtest_model.py --player-limit 100
python scripts/doctor.py
```

## สิ่งที่ tests ครอบคลุม

- fresh cache, stale fallback, retry และ 404 semantics
- ไม่เรียก picks ก่อน GW1 deadline
- เรียกและรับ picks หลัง deadline / publication delay
- Team ID ใน request, snapshot และ briefing ต้องตรงกันก่อน build/deploy
- freshness warning เมื่อข้อมูลต้นทางเก่ากว่า 24 ชั่วโมง
- Squad Lab namespace แยกตามฤดูกาลและ Team ID
- double/blank fixtures และ availability multiplier
- xP v2 shrink, expected minutes, start probability, score separation และช่วงคะแนน
- FPL `ep_next` ถูก blend ครั้งเดียวใน Double Gameweek
- model distribution guardrails บล็อก low-sample outlier
- rolling backtest ใช้เฉพาะ Gameweek ก่อน target และมี leakage audit
- legal squad, lineup, captain/vice และ transfer affordability
- decision contract ใช้เฉพาะ owned squad 15 คน และสร้าง XI 11 + bench 4 คน
- Transfer Advisor ตรวจ Free Transfer, ราคาขายจริง, งบ, hit, club quota และ edge cases
- scenario Roll/1 FT/2 FT/-4 หัก hit และคำนวณ net/downside ครบ 1/3/5 GW
- ราคาขายไม่ครบจะไม่รับรอง affordability และ -4 ต้องผ่าน downside/minutes gate ก่อน `Do`
- Risk Layer บังคับ source/timestamp/fact-inference และปรับ expected minutes/xPts แบบ audit ได้
- predicted lineup ถูกบังคับเป็น inference และจำกัดผลกระทบ ส่วนข่าวเก่า/override หมดอายุไม่ถูกใช้
- curated evidence หายหรือ JSON เสียจะ fallback ไป FPL status โดย pipeline ยังสร้าง snapshot ได้
- Chip Planner ตรวจประวัติชิปสองชุด, GW1, Free Hit ติดกัน และ one-chip-per-GW
- BB ใช้ผู้เล่นครบ 15/XI 11/bench 4 ส่วน TC เปลี่ยนตามนาทีและโอกาสตัวจริง
- FH/WC มี confidence gate และ transfer path ผ่านงบ/ตำแหน่ง/club quota ทุก checkpoint
- Browser logic ตรวจแผน saved/changed/expired, สถานะ pending ข้าม GW, ราคาขายจริงทำให้งบไม่ผ่าน
  และข่าวกัปตันเปลี่ยน gain/เหตุผลทันที (ใช้ VM จำลอง ไม่มี Browser หรือข้อมูลบัญชีจริงใน unit tests)
- หน้าเว็บ, JSON และ briefing อ่านคำแนะนำจาก decision contract ชุดเดียวกัน
- atomic static-site assembly

Backtest ใน `data/model-backtest.json` อาจแสดง `insufficient_history` ในช่วงต้นฤดูกาล
ซึ่งไม่ถือเป็น pipeline failure แต่ `leakage_violations` ต้องเป็น 0 เสมอ และห้ามสรุปว่า
โมเดลดีกว่า baseline จนกว่าจะมี evaluation อย่างน้อย 3 Gameweeks

## Browser smoke test

```bash
python -m http.server 8000 --directory dist
```

ตรวจ desktop และ mobile width:

1. หน้าโหลดโดยไม่มี console error
2. identity banner แสดงชื่อทีม, Team ID, ฤดูกาลและ Gameweek ถูกต้อง
3. กรอก Team ID อื่นแล้ว decision cards ทั้ง 5, captain, Squad Lab และ briefing ถูกปิด
4. deadline countdown เดิน
5. `This Gameweek` แสดง Transfer, XI, Captain/Vice, Bench และ Chip ครบ
6. pitch มี XI 11 คนจากทีมจริงและ bench 4 คน
7. Captain Radar แสดง expected minutes และ confidence และไม่จัดอันดับจาก xPts อย่างเดียว
8. Player Explorer แยก expected points กับ ranking score และแสดงช่วงนาที
9. News & Risk แสดง source snapshot, fact/inference, เวลา และค่าก่อน–หลังของทีมจริง
10. เพิ่ม predicted lineup แล้วป้ายเป็นข้อสันนิษฐานและปรับไม่เกิน ±15 นาที/±15%
11. evidence active ทำให้ XI/C/VC/bench และ Transfer Advisor คำนวณใหม่
12. evidence เกิน 24 ชั่วโมงหรือหมดอายุยัง audit ได้แต่ไม่เปลี่ยนคำแนะนำ
13. reload แล้วยังมี evidence ของทีม/GW เดิม และไม่ถูกใช้เมื่อ target Gameweek เปลี่ยน
14. Transfer Advisor รอ Free Transfer โดยไม่เดาค่าเริ่มต้น
15. เมื่อเลือก 2 FT แผน 2 คนมี hit 0 และแผน 3 คนมี hit -4
16. แผนที่ยังขาดราคาขายแสดง “ต้องยืนยันราคา”; เมื่อกรอกครบจึงรับรองงบ
17. -4 แสดง net/downside 1/3/5 GW และไม่ขึ้น `ทำ` หาก confidence/minutes ไม่ผ่าน
18. reload แล้วยังมี FT/bank/ราคาขาย และ storage key มีฤดูกาลกับ Team ID
19. Planner แสดงช่วง 3–6 GW และการ์ด BB/TC/FH/WC พร้อม gain/opportunity cost
20. ชิปที่ FPL ยืนยันว่าใช้แล้วถูก disable และเลือกบันทึกไม่ได้
21. เปลี่ยนนาทีใน News & Risk แล้ว TC/BB ของ GW ปัจจุบันเปลี่ยนตาม
22. บันทึกแผนแล้ว reload ยังอยู่ และแสดง stale เมื่อ target Gameweek เปลี่ยน
23. copy briefing มีหัวข้อ `News & Risk จาก Browser`, `Transfer Advisor จาก Browser` และ `Chip & Multi-GW Planner จาก Browser`
24. กดใช้ทีมจริงในแผนแล้วแสดง 15/15 และ validation ผ่าน
25. ลบ/เพิ่ม/swap ผู้เล่นได้
26. filter/search/sort ตารางทำงาน
27. mobile width ไม่มี horizontal overflow และ cards เรียงหนึ่งคอลัมน์
28. offline reload หลัง service worker ติดตั้งแล้ว

Phase 5 ตรวจเมื่อ 31 สิงหาคม 2026: Python 54 tests, JavaScript 6 tests และ doctor 15/15
ผ่านครบ Browser จริงตรวจการบันทึกเส้นทาง/เปิดใหม่และข่าวจำลองเปลี่ยนแผนแล้ว
responsive QA และ offline regression ทำต่อและผ่านใน Phase 6 ตามรายงานด้านบน

## ปัญหาที่พบบ่อย

### เว็บรุ่นเดิมแสดง `Unsupported schema version 2`

Refresh หน้าเว็บอีกครั้งเพื่อรับ service worker และหน้าเว็บรุ่นใหม่ ไม่ต้องล้างข้อมูล
Browser; localStorage ของผู้ใช้ควรเก็บไว้เสมอ

### HTTP smoke บน Mac แจ้ง certificate verify failed

หาก Python ในเครื่องไม่มี CA bundle ให้ใช้ bundle จาก certifi ที่ติดตั้งพร้อม dependencies
โดยไม่ปิดการตรวจ TLS:

```bash
SSL_CERT_FILE="$(python -m certifi)" python scripts/smoke_site.py https://sarayutp.github.io/fpl-decision-lab/
```

### `ModuleNotFoundError`

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

### Dashboard ขึ้น “โหลดข้อมูลไม่สำเร็จ”

สำหรับการใช้งานทั่วไปให้เปิด
[Dashboard ออนไลน์](https://sarayutp.github.io/fpl-decision-lab/) และ refresh หนึ่งครั้ง
หากยังไม่สำเร็จ ให้ตรวจ
[GitHub Actions](https://github.com/Sarayutp/fpl-decision-lab/actions/workflows/deploy-pages.yml)

สำหรับการทดสอบ local อย่าเปิด `file://.../index.html` ให้รัน
`./scripts/run_local.sh` และเปิด `http://127.0.0.1:8000`

### FPL API 404 ที่ picks

ก่อน deadline เป็นพฤติกรรมปกติ หลัง deadline อาจมี publication delay ระบบจะคง
local squad และแสดง warning แทนการล้ม

### Internet ล่ม

Pipeline ใช้ stale cache หากเคยดึงข้อมูลสำเร็จ Dashboard ใช้ service-worker cache
หลังเคยเปิดอย่างน้อยหนึ่งครั้ง ต้องดู freshness badge ก่อนตัดสินใจ

### Optimizer infeasible

รัน refresh ใหม่และดู warnings สาเหตุทั่วไปคือ FPL เปิดผู้เล่นในบางตำแหน่งไม่พอหรือ
schema เปลี่ยน Pipeline จะยังสร้าง snapshot แต่ initial squad มี status unavailable

### Port 8000 ถูกใช้

```bash
python -m http.server 8080 --directory dist
```

แล้วเปิด `http://127.0.0.1:8080`
