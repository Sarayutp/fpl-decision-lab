# Phase 7B — Decision card สำหรับแชร์

วันที่: 31 สิงหาคม 2026 · release `2.2.0-rc.1` · สถานะ **In review**

## ขอบเขต

สร้างการ์ดจาก A/B ที่เก็บไว้สำหรับ GW ปัจจุบัน ดูตัวอย่างก่อนดาวน์โหลด PNG/TXT หรือคัดลอก
ชื่อแผนเป็น A/B ไม่ใช้ชื่อที่ผู้ใช้ตั้งเอง ไม่เปลี่ยน Planner, Journal, A/B หรือบัญชี FPL
ไม่มี backend ใหม่, upload, automatic post, API key หรือ dependency เพิ่ม

## ความถูกต้องและความเป็นส่วนตัว

- ใช้ allowlist สำหรับข้อมูลที่ส่งออก ไม่ serialize record ทั้งก้อน; ไม่มี Team ID, ชื่อทีม/ผู้จัดการ,
  งบ, ราคาขาย, labels, notes, URLs ของข่าวส่วนตัว, future moves หรือ context key ในไฟล์/ชื่อไฟล์
- ชื่อผู้เล่นอ้าง public catalog; แยก GK สำรองจากอันดับผู้เล่นสนาม 1–3 และแสดง C/VC
- คะแนนใช้ตัวเลข frozen จาก A/B หลัง chip/hit เฉพาะ GW นี้ ไม่เสนอผู้ชนะหรือรับรองงบ
- ต้อง current/online/fresh/ก่อน deadline/identity ตรง; ตรวจซ้ำก่อนส่งออก แม้ timer ยังไม่อัปเดต UI
- เปลี่ยน context, slot, แทนที่หรือลบ record ต้องสร้าง preview ใหม่ ไม่ส่งภาพเก่าที่ค้างไว้
- ภาพและข้อความสร้างจากข้อมูลชุดเดียวกัน; canvas ใช้ฟอนต์ระบบและความสูงตามเนื้อหา
- Canvas ล้มเหลวส่งออก TXT ได้; clipboard ถูกปฏิเสธไม่อ้างว่าคัดลอกสำเร็จ
- A/B JSON สำรองยังมีข้อมูลส่วนตัว จึงมีคำเตือนแยกจากการ์ดสำหรับแชร์

## ผลตรวจในเครื่อง

- Python 62 tests และ JavaScript 44 tests ผ่าน (card/privacy ใหม่ 11 cases)
- Browser suite เตรียม 52 cases รวม 14 cases ใหม่สำหรับ desktop/mobile; รอผล CI
- JS/CSS/snapshot ยังอยู่ใน budget เดิม; artifact รุ่นนี้ตรวจ 11 ไฟล์
- Browser จริงใช้ QA origin ว่างที่พอร์ต 8012 ไม่เขียนทับแผน QA ที่พอร์ตเดิมหรือแผนบนเว็บจริง
- ตัวอย่าง QA มี XI 11 + bench 4, C/VC, 56.20 xPts; PNG 800×1505 px และไม่มีชื่อแผนทดสอบ/Team ID/ชื่อทีมในข้อความส่งออก
- ต้องตรวจ Browser และ published smoke ครบก่อนปิดงาน

## ข้อจำกัด

- รายชื่อผู้เล่นและชิป/ย้ายตัวยังเผยแผน และอาจช่วยระบุเจ้าของทีมได้ ไม่ใช่ complete anonymization
- ภาพ/TXT/clipboard ที่ส่งออกแล้วเป็นสำเนาคงที่ เรียกคืนหรืออัปเดตจากเว็บไม่ได้
- ฟอนต์และความสูง PNG อาจต่างกันตามอุปกรณ์; ไม่ได้ทดสอบ Safari/iPhone/VoiceOver จริง
- Preview มีข้อความคู่กับภาพ แต่ไม่ใช่ full accessibility certification
- การทดสอบผ่านไม่ใช่หลักฐานว่าโมเดลแม่นขึ้น; Phase 2 backtest และ Phase 7 ส่วนอื่นยังไม่เสร็จ
