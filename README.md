# FPL Decision Lab

ระบบช่วยตัดสินใจ Fantasy Premier League แบบฟรี โปร่งใส และ local-first สำหรับ
ทีม `3647781` ใช้ข้อมูลสาธารณะจาก FPL โดยไม่ขอรหัสผ่านหรือ session cookie

ระบบครบระยะที่ 1–7 แล้ว: data pipeline, xP model, optimizer, Dashboard/PWA,
ChatGPT Plus briefing, GitHub Actions/Pages, tests และคู่มือ

Dashboard ออนไลน์: [https://sarayutp.github.io/fpl-decision-lab/](https://sarayutp.github.io/fpl-decision-lab/)

## เริ่มใช้งานบน Mac

ต้องมี Python 3.11 ขึ้นไป จาก Terminal:

```bash
cd /Users/sarayutp/Project/10_FPL
./scripts/run_local.sh
```

จากนั้นเปิด [http://127.0.0.1:8000](http://127.0.0.1:8000) คำสั่งแรกจะสร้าง
virtual environment และติดตั้งแพ็กเกจให้เอง กด `Control+C` เพื่อหยุด local server

หากติดตั้งไว้แล้วและต้องการอัปเดตข้อมูล:

```bash
./scripts/update_data.sh
```

## คำสั่งสำหรับนักพัฒนา

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m fpl_mvp all --force-refresh
pytest
python scripts/doctor.py
```

คำสั่งหลัก:

- `fpl-refresh refresh` — ดึง API, คำนวณ xP/optimizer และสร้าง briefing
- `fpl-refresh build-site` — ประกอบ static site ใน `dist/`
- `fpl-refresh all` — ทำทั้งสองขั้น

ตั้งค่าได้ผ่าน `FPL_TEAM_ID`, `FPL_BASE_URL`, `FPL_CACHE_DIR`,
`FPL_OUTPUT_PATH`, `FPL_BRIEFING_PATH` และ arguments จาก `--help`

## เอกสาร

- [คู่มือผู้ใช้](docs/USER_GUIDE_TH.md)
- [ใช้ร่วมกับ ChatGPT Plus](docs/CHATGPT_PLUS_GUIDE_TH.md)
- [นำขึ้น GitHub Pages ฟรี](docs/DEPLOY_GITHUB_PAGES_TH.md)
- [สถาปัตยกรรมและระยะที่ 1–7](docs/ARCHITECTURE.md)
- [Model card: xP และ optimizer](docs/MODEL_CARD.md)
- [การทดสอบและแก้ปัญหา](docs/TESTING.md)

## ข้อจำกัดสำคัญ

ก่อน deadline แรก FPL จะไม่เปิด endpoint picks ของทีม จึงต้องเลือกทีม 15 คนใน
Squad Lab ครั้งแรก ทีมนี้เก็บใน `localStorage` ของ Browser เครื่องนั้น หลัง deadline
ระบบจะอ่าน picks สาธารณะล่าสุดได้เอง

xP เป็นคะแนนจัดลำดับจากข้อมูล ไม่ใช่การรับประกันผลลัพธ์ และ public API ไม่เปิด
ราคาขายจริงของผู้เล่นในบัญชี จึงต้องตรวจงบ transfer ที่หน้า FPL อีกครั้งก่อนกดจริง
