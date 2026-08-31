# Phase 6 — Release candidate QA

วันที่ตรวจ: 31 สิงหาคม 2026 · รุ่น `2.0.0-rc.1` · สถานะ **In review**

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

## สิ่งที่ยังไม่ผ่าน release gate

- เตรียม Playwright 20 cases (desktop/mobile) แล้วและตรวจ discovery/syntax ผ่าน แต่ยังไม่ได้รัน CI ของ commit นี้
- ยังไม่ได้ทำ VoiceOver/manual screen-reader audit หรือทดสอบ Safari/iOS จริง
- ยังไม่ได้ push, deploy, smoke หรือ rollback บน GitHub Pages จริง ต้องให้ผู้ใช้ยืนยันก่อน
- หาก CI หรือ published smoke ไม่ผ่าน ให้คง Phase 6 เป็น In review ห้ามติดป้าย Done

## ขอบเขตข้อมูลทดสอบ

`tests/fixtures/owned-team-gw3.json.gz.b64` เป็น frozen fixture จาก public GW2 picks และ
model output สำหรับ GW3; Team ID แทนด้วย `990001`, ชื่อทีม `QA United`, manager `QA Manager`.
บีบอัดเพื่อไม่เพิ่ม snapshot ใหญ่ซ้ำอีกชุด; unit test ตรวจไม่มีชื่อ/Team ID เดิมหรือ secret fields
QA server ปรับเฉพาะเวลาให้คงสถานะ fresh/deadline ทดสอบซ้ำได้ โดยไม่เรียก FPL หรือใช้บัญชีจริง

Browser QA ใช้ `127.0.0.1:8011` แยกจากพรีวิวจริงพอร์ต 8000; ไม่มีการเปลี่ยนทีม/ชิปใน FPL
