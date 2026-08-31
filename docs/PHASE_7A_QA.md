# Phase 7A — Compare plans A/B

วันที่: 31 สิงหาคม 2026 · release `2.1.0-rc.1` · สถานะ **Done — เผยแพร่และตรวจรับแล้ว**

## ขอบเขต

เก็บฉบับร่างจาก Planner เป็น A/B และเทียบเฉพาะ GW ปัจจุบัน ไม่เปลี่ยนแผนที่บันทึก
ใน Planner, Decision Journal หรือบัญชี FPL. ชิปและเส้นทางยังเลือกผ่าน Planner เดิม
ไม่มีการจัดอันดับผู้ชนะหรือแนะนำใช้ชิป/-4 จาก delta เพียงตัวเดียว

สูตร: xPts XI รวมกัปตัน + คะแนนเพิ่ม TC/BB − hit ของ GW นี้
Free Hit/Wildcard ใช้ XI จากทีมจำลองและไม่คิด hit ปกติ; ไม่บวก TC/BB ซ้อน
ราคาขายไม่ครบยังเทียบแบบประมาณได้แต่ไม่รับรองงบ; ต้องรู้ FT ก่อนเทียบแผนที่ย้ายตัวปกติ
future moves แสดงแยกและไม่นับในตัวเลขนี้; ไม่รวมมูลค่าชิป/FT หลัง GW ปัจจุบัน

## ผลตรวจ

- Python 61 tests และ JavaScript 33 tests ผ่าน (comparison logic ใหม่ 13 cases)
- Payload ยังอยู่ใน budget เดิม ไม่เพิ่มเพดานขนาดไฟล์เพื่อให้ผ่าน
- artifact รุ่นใหม่ตรวจ 10 ไฟล์; smoke checker ยังอ่าน artifact Phase 6 เดิม 9 ไฟล์ได้
- Browser 38 cases ผ่านใน CI แบบไม่มี flaky รวม capture/reload/export/delete, เปลี่ยนงบ และ stale/offline/deadline/mismatch
- รวม Python 61 + JavaScript 33 + browser 38 = 132 cases ผ่าน; ไม่ใช่หลักฐานยืนยันความแม่นของโมเดล
- Browser จริงบน QA origin: เก็บ A/B, โหลดใหม่, แสดง delta 0 สำหรับแผนเหมือนกัน และเปลี่ยน FT แล้วทั้งสองแผนเป็น `changed`/ไม่แสดง delta
- 375px: root overflow 0, unlabeled controls 0, ready ของ fixture ประมาณ 325ms; ตรวจหน้าตามือถือและ desktop แล้ว ไม่ใช่ Core Web Vitals บนอุปกรณ์จริง

## หลักฐานการเผยแพร่

- [PR #2](https://github.com/Sarayutp/fpl-decision-lab/pull/2) merge commit `a3ff5dcd845f02f9f77bc6697067cd00fb26dfb3`
- [PR CI แบบ clean pass](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33351958714) และ [main CI](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33352139299) ผ่าน
- [Deployment](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33352139290) ผ่านทั้ง build, browser release gate, deploy และ published smoke
- Build `b276298127b2b5de`, snapshot `2026-08-31T02:55:12.707411+00:00`, schema 2, Team ID `5105794`
- ดาวน์โหลด `validated-site` มาตรวจ hash ครบ 10 ไฟล์ และตรวจ URL จริงพร้อม expected build เดียวกันผ่านอีกครั้ง
- Browser บน [เว็บจริง](https://sarayutp.github.io/fpl-decision-lab/#scenario-comparison) แสดง Sarayut FC, runtime `ready`, web/pipeline `2.1.0-rc.1` และหน้าเปรียบเทียบตามรุ่นที่เผยแพร่
- การลองบันทึก/ลบ A/B ทำบน QA origin แยกด้วยทีมจำลอง ไม่แก้ Planner/Journal บนเว็บจริงหรือบัญชี FPL

## CI stability

CI แรกรายงาน 37 ผ่าน + 1 flaky: `chromium_headless_shell` รับ SIGSEGV ระหว่าง mobile context
ไม่ใช่ assertion ของ A/B ที่ตก จึงเปลี่ยนเป็น full Chromium new headless (`channel: chromium`)
และเปิด `failOnFlakyTests` ให้ release ไม่ผ่านหากยังต้อง retry ตาม
[เอกสาร browser channels](https://playwright.dev/docs/browsers) และ
[การบังคับ fail เมื่อ flaky](https://playwright.dev/docs/api/class-testconfig#test-config-fail-on-flaky-tests).
รอบใหม่ข้างต้นผ่าน 38 cases โดยไม่มี flaky ก่อนเผยแพร่ ไม่ถือว่ารอบ 37+1 เป็น clean pass

## ข้อจำกัด

- local-first สองช่องต่อทีม/ฤดูกาล/GW ไม่มี import หรือ sync ข้ามอุปกรณ์
- แผนเก่าไม่ถูกแก้ตัวเลขย้อนหลัง; เมื่อข้อมูลเปลี่ยนต้องเลือกและเก็บ A/B ใหม่ทั้งคู่
- Export ที่ offline/stale มีสถานะ readonly และไม่มี delta ที่ใช้ตัดสินใจได้
- ราคาขายยังเป็น user input; หน้าเทียบแผนไม่ยืนยันบัญชี FPL แทนผู้ใช้
- ยังไม่ใช่ multi-GW comparison, rank simulation หรือหลักฐานว่าโมเดลแม่นขึ้น
- ยังไม่ได้ทดสอบบน iPhone/Safari หรือ VoiceOver จริง
- Phase 7 ส่วนอื่นและ Phase 2 backtest ยังไม่เสร็จ
