# User guide — ผลตรวจเมนูวิธีใช้งาน

วันที่ 31 สิงหาคม 2026 · release `2.3.0-rc.1` · สถานะ **Done — เผยแพร่และตรวจรับแล้ว**

## ขอบเขต

- เพิ่มเมนูหลัก `วิธีใช้งาน` ทั้ง Dashboard และหน้า guide มี current-page marker
- คู่มือภาษาไทย 22 หัวข้อ: เริ่มใช้ ตรวจทีม เมนู XI/C/VC/bench คำศัพท์ Transfers ข่าว
  Planner A/B การ์ด Journal Players Squad Lab AI Briefing storage/privacy routine ตัวอย่าง
  troubleshooting การอัปเดต ข้อจำกัด และวิธีดาวน์โหลด/พิมพ์/พัฒนา
- ระบุชัดว่า Team ID เป็น guard ไม่ใช่ตัวดึง My Team สด, เลือกชิปไม่ใช่ activate จริง,
  ข้อจำกัด FT=0, ราคาขายกับราคาตลาด, forecast ไม่ใช่ผลจริง, JSON ยังไม่มี import/sync
- source เดียว `dashboard/guide.md` → HTML ตอน build และ Markdown download ตรงต้นฉบับ
- ไม่เปลี่ยนสูตรคะแนน ทีมจริง แผน ข่าว ราคา Journal หรือแผน A/B ที่บันทึกไว้

## ผลตรวจในเครื่องและ CI

- Python 76 tests และ JavaScript 47 tests ผ่าน; JS syntax / build / smoke / asset budgets ผ่าน
- unit tests ตรวจ H1 เดียว H2 ต่อเนื่องครบ 22, escape HTML, ปิด images/unsafe links,
  TOC และลิงก์กลับทุก section, guide ใน manifest และ rollback-compatible legacy manifest
- Browser จริงตรวจ desktop, 768px และ 375px: เมนู สารบัญ ตาราง และฟอนต์ไทย; ไม่มี page overflow
- เปิดเมนูคู่มือจาก Dashboard ที่ HTTP 503 ได้ โดยไม่โหลดข้อมูลทีมในหน้าคู่มือ
- Browser E2E 68 cases ผ่านโดยไม่มี flaky (รวมทั้งหมด 191 cases) โดย 16 cases ใหม่ตรวจ help/error/no-JS/no-data/download/
  native-print invocation/print CSS/375-768-1280px/keyboard/service-worker offline isolation
- asset budget เดิมไม่เพิ่ม: JS 189,296 / CSS 56,355 / snapshot 2,714,121 bytes
- แก้ inherited table min-width จาก Dashboard ที่ซ่อนคอลัมน์บนมือถือ และเพิ่ม gate ตรวจขอบตารางทุกตัว ไม่ใช้ root overflow อย่างเดียว
- ตรวจ artifact ย้อนหลัง Phase 6 (9 ไฟล์) และ Phase 7B (11 ไฟล์) ผ่านด้วย smoke checker ใหม่ โดยไม่ deploy ย้อนรุ่น
- [PR #4](https://github.com/Sarayutp/fpl-decision-lab/pull/4), merge `57da8739a0478bed2da3be28371802b77d4ddddc`
- [PR CI](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33402346308) และ [branch CI](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33402340073) ผ่าน

## หลักฐานการเผยแพร่

- [main CI](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33402690408) ผ่าน
- [Deployment](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33402690404) ผ่านทั้ง build, browser release gate 68 cases, deploy และ published smoke
- Build `a1de8e66539d61e1`, snapshot `2026-08-31T14:27:30.930978+00:00`, schema 2, Team ID `5105794`
- ดาวน์โหลด validated artifact ตรวจ SHA-256 ครบ 15 ไฟล์ และตรวจ URL จริงด้วย expected build เดียวกันผ่าน
- Browser จริงเปิดเมนูจาก Dashboard ไป [guide.html](https://sarayutp.github.io/fpl-decision-lab/guide.html) เห็น release `2.3.0-rc.1` และครบ 22 หัวข้อ
- ดาวน์โหลด Markdown ผ่านปุ่มจริงสำเร็จ; browser CI ตรวจเนื้อหาไฟล์ตรงต้นฉบับทุกตัวอักษร
- ไม่เขียนแผน Planner/A/B/Journal หรือแก้ทีมบน production ระหว่าง QA
- ยังมี upstream GitHub Actions Node 20 deprecation warnings ไม่ใช่ test/deploy failure

## ข้อจำกัดการตรวจ

การตรวจ Browser ไม่ใช่ full screen-reader/Safari/iPhone certification ปุ่ม PDF เปิด native print
การแบ่งหน้าขึ้นกับอุปกรณ์และการตั้งค่าพิมพ์ ผู้ใช้ควรดู print preview ก่อนบันทึก
คู่มือ offline ต้องเคยติดตั้ง cache สำเร็จ ไม่ใช่ first-visit offline. คู่มือไม่มีข่าวสดและไม่รับรองโมเดล
