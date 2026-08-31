# Phase 6 — Release candidate QA

วันที่ตรวจ: 31 สิงหาคม 2026 · รุ่น `2.0.0-rc.1` · สถานะ **Done — เผยแพร่และตรวจรับแล้ว**

## หลักฐานการเผยแพร่

- [เว็บไซต์จริง](https://sarayutp.github.io/fpl-decision-lab/) — Sarayut FC, Team ID `5105794`, เป้าหมาย GW3
- Release commit `4314da6597ac1244691485c9c76e04f5f9b37a8b` จาก [PR #1](https://github.com/Sarayutp/fpl-decision-lab/pull/1)
- Build ID `984449c719ddc84f`; snapshot `2026-08-31T01:48:48.121891+00:00` (08:48 เวลาไทย)
- [CI ของ PR](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33348609356) และ [CI บน main](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33348695199) ผ่าน: Python 60, JavaScript 20, browser E2E 26 cases
- [Deployment](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33348695204) ผ่านทั้ง refresh, tests, payload gates และ published smoke ของไฟล์สำคัญ 9 ไฟล์
- [Hosted restore rehearsal](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33348816315) ผ่าน โดยดาวน์โหลด `validated-site` จาก deployment ข้างต้นแล้วเผยแพร่ซ้ำ; build ID, hash และ timestamp เดิมตรงทั้งหมด
- Browser บน URL จริงแสดงสถานะ `ready`, ชื่อทีม/รุ่นตรงกัน และปุ่ม copy briefing แสดงสำเร็จพร้อม Team ID ที่ถูกต้อง

การซ้อม hosted restore ใช้ **รุ่นเดียวกันที่เพิ่งผ่านตรวจ** ไม่ได้ย้อนผู้ใช้ไปยังโค้ดเก่า
ส่วนการเปลี่ยน artifact A → B → restore A ที่ build ID ต่างกันตรวจแยกใน local integration test
ตาราง refresh เดิมยังเปิดอยู่ ไม่ได้เพิ่มหรือเปลี่ยนรอบเวลา

## ผลที่ยืนยันแล้วในเครื่อง

- Python 60 tests และ JavaScript 20 tests ผ่าน
- JavaScript syntax, Python compile, diff whitespace, dependency audit ผ่าน (npm ไม่พบช่องโหว่)
- Local artifact และ HTTP smoke ผ่าน: ตรวจ hash ของไฟล์สำคัญ 9 ไฟล์, Team ID, timestamp, release และ build ID
- ซ้อมเก็บ artifact A → สร้าง B → restore A ใน temporary directory ผ่าน และ timestamp เดิมยังอยู่
- Browser จริง: ยืนยันทีม → reload → รับคำแนะนำ → บันทึก Planner → ลงประวัติ → กรอกผลจริง → copy briefing → reload แล้วประวัติยังอยู่
- ปิด QA server จริง แล้วเปิด URL ใหม่ด้วย service-worker cache: หน้าเว็บยังอ่านได้ แสดง offline และไม่แนะนำใช้ชิป
- stale, partial briefing failure, mismatch, incompatible schema, HTTP failure, ทีมยังไม่ประกาศ และผ่าน deadline แสดงสถานะชัดเจน

## Responsive / accessibility baseline

| Viewport | หน้าไม่ล้นแนวนอน | เมนูหลัก | ช่องกรอกไม่มี label | เวลาถึง ready ของ fixture |
|---|---|---|---|---|
| 375px | ผ่าน | แสดง/เลื่อนในเมนูได้ | 0 | ประมาณ 0.13 วินาที |
| 768px | ผ่าน | แสดง | 0 | ประมาณ 0.13 วินาที |
| 1280px | ผ่าน | แสดง | 0 | ประมาณ 0.13 วินาที |

ตาราง Players เลื่อนได้ภายในกรอบโดยไม่ซ่อนคอลัมน์ความมั่นใจออกจากมือถือ
สีข้อความหลักกับพื้นหลังมี contrast 17.42:1; ข้อความรองบน panel 6.85:1
มี skip link, focus-visible, native labels และ reduced-motion stylesheet
ตัวเลขนี้เป็น fixture ในเครื่อง ไม่ใช่ Core Web Vitals หรือผลบนโทรศัพท์จริง
ไม่เคยบันทึกเวลา baseline Phase 5 จึงไม่อ้างว่า Phase 6 เร็วกว่าเดิมจากข้อมูลนี้

## ขอบเขตของผลตรวจและงานติดตาม

- Playwright 26 cases ผ่านบน hosted Chromium desktop/mobile รวม flow หลัก, safe states, viewport 375/768/1280px, accessible names ของ controls, contrast baseline, skip-link focus และ reduced motion
- นี่คือ accessibility baseline ตามขอบเขต Phase 6 ไม่ใช่การรับรอง WCAG ทั้งเว็บ; VoiceOver/manual screen-reader audit และ Safari/iOS บนอุปกรณ์จริงยังไม่ได้ทำ
- ผู้ใช้ที่มี service-worker cache ของรุ่น v7 เดิมอาจเห็นหน้าเก่าหรือ `Unsupported schema version 2` ครั้งแรก; ตรวจแล้วว่า refresh หน้าเว็บอีกครั้งรับรุ่นใหม่ได้ โดยไม่ล้าง localStorage
- GitHub มีคำเตือน Node 20 deprecation ใน upstream Pages/upload actions แต่รันด้วย Node 24 และงานผ่าน; ติดตามอัปเดต upstream ต่อไป
- Phase 2 ยังคง `In review` เพราะ backtest history ยังไม่พอ; การผ่าน release QA ไม่ใช่หลักฐานความแม่นของโมเดล
- ไม่มีการเปลี่ยนทีม ย้ายตัว หรือใช้ชิปในบัญชี FPL ระหว่างตรวจรับ

## ขอบเขตข้อมูลทดสอบ

`tests/fixtures/owned-team-gw3.json.gz.b64` เป็น frozen fixture จาก public GW2 picks และ
model output สำหรับ GW3; Team ID แทนด้วย `990001`, ชื่อทีม `QA United`, manager `QA Manager`.
บีบอัดเพื่อไม่เพิ่ม snapshot ใหญ่ซ้ำอีกชุด; unit test ตรวจไม่มีชื่อ/Team ID เดิมหรือ secret fields
QA server ปรับเฉพาะเวลาให้คงสถานะ fresh/deadline ทดสอบซ้ำได้ โดยไม่เรียก FPL หรือใช้บัญชีจริง

Browser QA ใช้ `127.0.0.1:8011` แยกจากพรีวิวจริงพอร์ต 8000; ไม่มีการเปลี่ยนทีม/ชิปใน FPL
