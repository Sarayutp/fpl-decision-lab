# FPL Decision Lab

ระบบช่วยตัดสินใจ Fantasy Premier League แบบฟรี โปร่งใส และ web-first สำหรับ
ทีม `5105794` (`Sarayut FC`) ใช้ข้อมูลสาธารณะจาก FPL โดยไม่ขอรหัสผ่านหรือ session cookie

ระบบพื้นฐานครบระยะที่ 1–7 เดิมแล้ว การปรับผลิตภัณฑ์ v2 เสร็จ Phase 1, Phase 3,
Phase 4, Phase 5, Phase 6 และ Phase 7A ส่วน Phase 2 อยู่สถานะ `In review` ระหว่างสะสมผล backtest:
หน้า `This Gameweek` ใช้ทีมจริงของผู้ใช้เพื่อสรุป Transfer, Starting XI,
Captain/Vice, Bench และ Chip จาก decision contract ชุดเดียวกัน
โมเดล `xp-v2.0` แยก expected points ออกจาก ranking score พร้อม expected minutes,
confidence, ช่วงคะแนนและ quality flags ส่วน `Transfer Advisor` เปรียบเทียบ Roll,
1 FT, 2 FT และ -4 ด้วยผลสุทธิ 1/3/5 GW พร้อมตรวจงบจากราคาขายจริง ขณะที่
`News & Risk` แยกข่าวทางการออกจาก predicted lineup และแสดงผลต่อนาที/xPts ก่อน–หลัง
ส่วน `Chip & Multi-GW Planner` เทียบ BB/TC/FH/WC ในช่วง 3–6 GW พร้อมค่าเสียโอกาส,
สถานะชิปจากประวัติจริง และ transfer path หลัก/สำรอง

Phase 6 รุ่น `2.0.0-rc.1` เผยแพร่และตรวจรับแล้ว: เมนู responsive, สถานะข้อมูล/ออฟไลน์,
local decision log, version compatibility และ release smoke/rollback workflow.
Python 60, JavaScript 20 และ browser E2E 26 cases ผ่านใน CI พร้อม published smoke
และ hosted restore rehearsal ดู [ผลตรวจ Phase 6](docs/PHASE_6_QA.md)

## เปิดใช้งานทันที

Phase 7A [เปรียบเทียบฉบับร่าง Planner แบบ A/B](https://sarayutp.github.io/fpl-decision-lab/#scenario-comparison)
เฉพาะ GW ปัจจุบัน พร้อมตรวจ context และเก็บใน Browser เผยแพร่รุ่น `2.1.0-rc.1` แล้ว
Python 61, JavaScript 33 และ browser 38 cases ผ่าน พร้อม published smoke
ดู [ผลตรวจและขอบเขต](docs/PHASE_7A_QA.md).

Phase 7B เพิ่มการ์ดจากแผน A/B สำหรับดาวน์โหลด PNG/TXT หรือคัดลอก โดยไม่ใส่ชื่อทีม,
Team ID, งบหรือบันทึกส่วนตัว ไม่อัปโหลดหรือโพสต์อัตโนมัติ รุ่น `2.2.0-rc.1`
อยู่ระหว่างตรวจรับ ดู [ผลตรวจและข้อจำกัด](docs/PHASE_7B_QA.md). Phase 7 ส่วนอื่นยังไม่ได้เริ่ม

**Dashboard ออนไลน์:** [https://sarayutp.github.io/fpl-decision-lab/](https://sarayutp.github.io/fpl-decision-lab/)

ถ้าเห็นหน้าเว็บรุ่นเก่าหรือ `Unsupported schema version 2` ให้ refresh อีกครั้งเพื่อรับ
รุ่นใหม่ ไม่ต้องล้างข้อมูล Browser หรือทีมที่บันทึกไว้

ไม่ต้องเปิด MacBook และไม่ต้องติดตั้งโปรแกรม GitHub Actions จะดึงข้อมูล FPL,
คำนวณ xP/optimizer, ทดสอบ และ deploy หน้าใหม่ให้อัตโนมัติประมาณเวลา 01:17,
07:17, 13:17, 19:17 และรอบก่อน deadline ที่พบบ่อยเวลา 23:17 น. ตามเวลาไทย

ทีมที่ทดลองใน Squad Lab เก็บใน Browser ของอุปกรณ์นั้น หากเปลี่ยน Browser/อุปกรณ์
ให้กด `ส่งออก JSON` เพื่อเก็บรายชื่อไว้อ้างอิงก่อน ระบบออนไลน์ไม่เข้าไปแก้ทีมจริงใน FPL

ก่อนใช้ Transfer Advisor ให้กรอกจำนวน Free Transfer และราคาขายจริงเฉพาะผู้เล่นที่
อยู่ในแผน ข้อมูลนี้เก็บเฉพาะใน Browser ระบบจะไม่รับรองงบด้วยราคาปัจจุบันที่ประมาณแทน

ก่อนใช้คำแนะนำ ให้ตรวจ `Team Source of Truth` และความสดของข้อมูล หน้าเว็บจะหยุด
คำแนะนำทั้งหมดทันทีเมื่อ Team ID ไม่ตรงหรือ decision contract ไม่พร้อม

ก่อน deadline เปิด `News & Risk` เพื่อตรวจ FPL status และเพิ่มข่าวสโมสรที่ตรวจแล้ว
พร้อม URL/เวลา หลักฐานเกิน 24 ชั่วโมงหรือหมดอายุข้าม Gameweek จะไม่ถูกนำไปปรับคำแนะนำ

หน้า `Planner` ใช้กติกาชิป 2026/27 แบบสองชุดและไม่แนะนำชิปที่ประวัติ FPL ยืนยันว่า
ใช้ไปแล้ว ผู้ใช้เลือกและบันทึกแผนของ Gameweek ปัจจุบันใน Browser ได้ แผนเดิมจะถูกทำเครื่องหมาย
ว่าหมดอายุเมื่อ deadline ผ่าน แต่ระบบจะไม่กดใช้ชิปหรือย้ายตัวแทนผู้ใช้

## ใช้งานบน Mac (ทางเลือกสำหรับพัฒนา/ทดสอบ)

ต้องมี Python 3.11 ขึ้นไป จาก Terminal:

```bash
cd /Users/sarayutp/Project/10_FPL
./scripts/run_local.sh
```

จากนั้นเปิด [http://127.0.0.1:8000](http://127.0.0.1:8000) คำสั่งแรกจะสร้าง
virtual environment และติดตั้งแพ็กเกจให้เอง กด `Control+C` เพื่อหยุด local server

หากต้องการทดสอบการอัปเดตข้อมูลในเครื่อง:

```bash
./scripts/update_data.sh
```

## คำสั่งสำหรับนักพัฒนา

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m fpl_mvp all --force-refresh
python scripts/backtest_model.py --player-limit 100
pytest
python scripts/doctor.py
```

คำสั่งหลัก:

- `fpl-refresh refresh` — ดึง API, คำนวณ xP/optimizer และสร้าง briefing
- `fpl-refresh build-site` — ประกอบ static site ใน `dist/`
- `fpl-refresh all` — ทำทั้งสองขั้น

ตั้งค่าได้ผ่าน `FPL_TEAM_ID`, `FPL_BASE_URL`, `FPL_CACHE_DIR`,
`FPL_OUTPUT_PATH`, `FPL_BRIEFING_PATH`, `FPL_RISK_EVIDENCE_PATH` และ arguments จาก `--help`

## เอกสาร

- [Development Plan v2: จาก Dashboard สู่ผู้ช่วยตัดสินใจประจำ Gameweek](docs/DEVELOPMENT_PLAN_V2_TH.md)
- [คู่มือผู้ใช้](docs/USER_GUIDE_TH.md)
- [ใช้ร่วมกับ ChatGPT Plus](docs/CHATGPT_PLUS_GUIDE_TH.md)
- [การใช้งานและอัปเดตผ่าน GitHub Pages](docs/DEPLOY_GITHUB_PAGES_TH.md)
- [สถาปัตยกรรมและระยะที่ 1–7](docs/ARCHITECTURE.md)
- [Model card: xP และ optimizer](docs/MODEL_CARD.md)
- [การทดสอบและแก้ปัญหา](docs/TESTING.md)

## ข้อจำกัดสำคัญ

ก่อน deadline แรก FPL จะไม่เปิด endpoint picks ของทีม จึงต้องเลือกทีม 15 คนใน
Squad Lab ครั้งแรก ทีมนี้เก็บใน `localStorage` ของ Browser เครื่องนั้น หลัง deadline
ระบบจะอ่าน picks สาธารณะล่าสุดได้เอง

expected points เป็นค่าคาดการณ์ ไม่ใช่การรับประกันผลลัพธ์ ส่วน ranking score ใช้จัดอันดับ
และไม่ควรถูกอ่านเป็นแต้ม FPL อีกชุด Public API ไม่เปิด Free Transfer และราคาขายจริง
ครบถ้วน จึงต้องกรอกข้อมูลส่วนตัวเหล่านี้ก่อนระบบจะรับรองว่าแผนอยู่ในงบ
ข่าวสโมสรและ predicted lineup ไม่ได้ถูกรวบรวมอัตโนมัติทุกสโมสร ต้องบันทึกแหล่งที่ตรวจแล้ว
ในหน้า `News & Risk` หรือ `data/risk-evidence.json`; predicted lineup เป็นข้อสันนิษฐานเสมอ
