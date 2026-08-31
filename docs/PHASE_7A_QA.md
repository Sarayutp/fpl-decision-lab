# Phase 7A — Compare plans A/B

วันที่: 31 สิงหาคม 2026 · release `2.1.0-rc.1` · สถานะ **In review**

## ขอบเขต

เก็บฉบับร่างจาก Planner เป็น A/B และเทียบเฉพาะ GW ปัจจุบัน ไม่เปลี่ยนแผนที่บันทึก
ใน Planner, Decision Journal หรือบัญชี FPL. ชิปและเส้นทางยังเลือกผ่าน Planner เดิม
ไม่มีการจัดอันดับผู้ชนะหรือแนะนำใช้ชิป/-4 จาก delta เพียงตัวเดียว

สูตร: xPts XI รวมกัปตัน + คะแนนเพิ่ม TC/BB − hit ของ GW นี้
Free Hit/Wildcard ใช้ XI จากทีมจำลองและไม่คิด hit ปกติ; ไม่บวก TC/BB ซ้อน
ราคาขายไม่ครบยังเทียบแบบประมาณได้แต่ไม่รับรองงบ; ต้องรู้ FT ก่อนเทียบแผนที่ย้ายตัวปกติ
future moves แสดงแยกและไม่นับในตัวเลขนี้; ไม่รวมมูลค่าชิป/FT หลัง GW ปัจจุบัน

## ผลตรวจในเครื่อง

- Python 61 tests และ JavaScript 33 tests ผ่าน (comparison logic ใหม่ 13 cases)
- Payload ยังอยู่ใน budget เดิม ไม่เพิ่มเพดานขนาดไฟล์เพื่อให้ผ่าน
- artifact รุ่นใหม่ตรวจ 10 ไฟล์; smoke checker ยังอ่าน artifact Phase 6 เดิม 9 ไฟล์ได้
- ชุด browser เตรียม 38 cases รวม capture/reload/export/delete, เปลี่ยนงบ และ stale/offline/deadline/mismatch
- ยังรอผล CI และ published smoke ของ commit รุ่นนี้ก่อนปิดงาน

## ข้อจำกัด

- local-first สองช่องต่อทีม/ฤดูกาล/GW ไม่มี import หรือ sync ข้ามอุปกรณ์
- แผนเก่าไม่ถูกแก้ตัวเลขย้อนหลัง; เมื่อข้อมูลเปลี่ยนต้องเลือกและเก็บ A/B ใหม่ทั้งคู่
- Export ที่ offline/stale มีสถานะ readonly และไม่มี delta ที่ใช้ตัดสินใจได้
- ราคาขายยังเป็น user input; หน้าเทียบแผนไม่ยืนยันบัญชี FPL แทนผู้ใช้
- ยังไม่ใช่ multi-GW comparison, rank simulation หรือหลักฐานว่าโมเดลแม่นขึ้น
- Phase 7 ส่วนอื่นและ Phase 2 backtest ยังไม่เสร็จ
