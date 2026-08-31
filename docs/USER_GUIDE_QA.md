# User guide — ผลตรวจเมนูวิธีใช้งาน

วันที่ 31 สิงหาคม 2026 · release `2.3.0-rc.1` · สถานะ **In review**

## ขอบเขต

- เพิ่มเมนูหลัก `วิธีใช้งาน` ทั้ง Dashboard และหน้า guide มี current-page marker
- คู่มือภาษาไทย 22 หัวข้อ: เริ่มใช้ ตรวจทีม เมนู XI/C/VC/bench คำศัพท์ Transfers ข่าว
  Planner A/B การ์ด Journal Players Squad Lab AI Briefing storage/privacy routine ตัวอย่าง
  troubleshooting การอัปเดต ข้อจำกัด และวิธีดาวน์โหลด/พิมพ์/พัฒนา
- ระบุชัดว่า Team ID เป็น guard ไม่ใช่ตัวดึง My Team สด, เลือกชิปไม่ใช่ activate จริง,
  ข้อจำกัด FT=0, ราคาขายกับราคาตลาด, forecast ไม่ใช่ผลจริง, JSON ยังไม่มี import/sync
- source เดียว `dashboard/guide.md` → HTML ตอน build และ Markdown download ตรงต้นฉบับ
- ไม่เปลี่ยนสูตรคะแนน ทีมจริง แผน ข่าว ราคา Journal หรือแผน A/B ที่บันทึกไว้

## ผลตรวจในเครื่อง

- Python 76 tests และ JavaScript 47 tests ผ่าน; JS syntax / build / smoke / asset budgets ผ่าน
- unit tests ตรวจ H1 เดียว H2 ต่อเนื่องครบ 22, escape HTML, ปิด images/unsafe links,
  TOC และลิงก์กลับทุก section, guide ใน manifest และ rollback-compatible legacy manifest
- Browser จริงตรวจ desktop, 768px และ 375px: เมนู สารบัญ ตาราง และฟอนต์ไทย; ไม่มี page overflow
- เปิดเมนูคู่มือจาก Dashboard ที่ HTTP 503 ได้ โดยไม่โหลดข้อมูลทีมในหน้าคู่มือ
- Browser E2E 68 cases เตรียมพร้อม โดย 16 cases ใหม่ตรวจ help/error/no-JS/no-data/download/
  native-print invocation/print CSS/375-768-1280px/keyboard/service-worker offline isolation
- asset budget เดิมไม่เพิ่ม: JS 189,296 / CSS 56,355 / snapshot 2,714,121 bytes
- แก้ inherited table min-width จาก Dashboard ที่ซ่อนคอลัมน์บนมือถือ และเพิ่ม gate ตรวจขอบตารางทุกตัว ไม่ใช้ root overflow อย่างเดียว

## รอการตรวจรับ

- CI browser ทั้งชุดผ่านโดยไม่มี flaky
- main deployment และ published smoke 15 ไฟล์ พร้อมบันทึก build/snapshot
- เปิดเมนูและหน้า guide จาก URL จริง

## ข้อจำกัดการตรวจ

การตรวจ Browser ไม่ใช่ full screen-reader/Safari/iPhone certification ปุ่ม PDF เปิด native print
การแบ่งหน้าขึ้นกับอุปกรณ์และการตั้งค่าพิมพ์ ผู้ใช้ควรดู print preview ก่อนบันทึก
คู่มือ offline ต้องเคยติดตั้ง cache สำเร็จ ไม่ใช่ first-visit offline. คู่มือไม่มีข่าวสดและไม่รับรองโมเดล
