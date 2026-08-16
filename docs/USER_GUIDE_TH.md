# คู่มือใช้งาน FPL Decision Lab

## ระบบนี้ช่วยอะไร

FPL Decision Lab รวมข้อมูล FPL, โปรแกรมแข่ง, คะแนนคาดการณ์ และกติกาการจัดทีมไว้
ในหน้าเดียว เป้าหมายคือช่วยลดการตัดสินใจจากอารมณ์ โดยยังให้คุณเป็นคนกด transfer
และยืนยันทีมในเว็บ FPL เองเสมอ

ระบบไม่ต้องใช้ server ที่เปิดตลอดเวลา มีสองวิธีใช้งาน:

1. รันบน Mac เฉพาะตอนต้องการใช้งาน
2. นำขึ้น GitHub Pages แล้วให้ GitHub Actions อัปเดตขณะที่ Mac ปิดอยู่

## เริ่มครั้งแรกบน MacBook Air

### 1. ตรวจ Python

เปิด Terminal แล้วรัน:

```bash
python3 --version
```

ต้องเป็น 3.11 ขึ้นไป หากไม่มี Python สามารถติดตั้ง Python 3.12 ผ่าน Homebrew หรือ
ดาวน์โหลดจาก python.org ได้

### 2. เปิดระบบ

```bash
cd /Users/sarayutp/Project/10_FPL
./scripts/run_local.sh
```

ครั้งแรกจะใช้เวลาติดตั้ง dependencies หลังเห็นข้อความ `Open
http://127.0.0.1:8000` ให้เปิด URL ดังกล่าวใน Safari หรือ Chrome

อย่าดับเบิลคลิก `index.html` โดยตรง เพราะ Browser จะไม่อนุญาตให้หน้าเว็บอ่านไฟล์
JSON บางชนิด ต้องเปิดผ่าน local URL ข้างต้น

เมื่อต้องการหยุด ให้กลับมาที่ Terminal แล้วกด `Control+C`

### 3. อัปเดตข้อมูลภายหลัง

```bash
cd /Users/sarayutp/Project/10_FPL
./scripts/update_data.sh
```

หาก local server เปิดอยู่ ให้ refresh หน้า Browser หลังคำสั่งจบ

## วิธีอ่านหน้า Dashboard

### ภาพรวม

- `Next decision` แสดงเวลานับถอยหลังตาม timezone ของเครื่อง
- `xP ทีมแนะนำ + กัปตัน` คือคะแนนคาดการณ์ของ XI รวมแต้มกัปตันสองเท่า
- `Captain Radar` เรียงตาม xP Gameweek ถัดไป ไม่ได้รวมข่าวด่วน
- แถบความสดของข้อมูลจะเตือนเมื่อ snapshot เก่ากว่า 24 ชั่วโมง

### ทีมแนะนำ

Optimizer เลือก 15 คนภายใต้กติกา:

- งบไม่เกิน 100.0
- GKP 2, DEF 5, MID 5, FWD 3
- ไม่เกิน 3 คนจากสโมสรเดียว
- XI เป็น formation ที่ถูกกติกา
- กัปตันและรองกัปตันอยู่คนละสโมสรเพื่อลดความเสี่ยงร่วม

ทีมนี้เป็น baseline เชิงตัวเลข ไม่จำเป็นต้องลอกทุกคน

### Squad Lab

ก่อน GW1 ให้กด `ใช้ทีมแนะนำ` แล้วปรับทีละคน หรือเลือกผู้เล่นจาก Player Explorer

- ทีมถูกเก็บไว้ใน Browser ด้วย `localStorage`
- หากล้างข้อมูลเว็บไซต์หรือเปลี่ยน Browser ทีมทดลองจะไม่ตามไปด้วย
- กด `ส่งออก JSON` เพื่อสำรองรายชื่อ Player IDs
- ระบบบล็อกการเพิ่มผู้เล่นเมื่อเกินงบ, ตำแหน่ง หรือ 3 คนต่อสโมสร
- `โอกาสอัปเกรด` เป็น swap ตำแหน่งเดียวที่อยู่ในงบและเพิ่ม xP

หลัง deadline เมื่อ FPL เปิด picks สาธารณะ ปุ่ม `ใช้ทีม FPL ล่าสุด` จะปรากฏ

### Player Explorer

ค้นหาชื่อ กรองตำแหน่ง/สโมสร และเรียงตาม:

- xP Gameweek ถัดไป
- xP 5 Gameweeks
- value score
- ownership
- ราคา

`Blank` หมายถึงไม่มี fixture ใน Gameweek เป้าหมาย ส่วน risk มาจากสถานะและ
chance of playing ที่ FPL เปิดเผย

## Routine ที่แนะนำต่อ Gameweek

### 3–5 วันก่อน deadline

1. อัปเดตข้อมูล
2. ดูโปรแกรม 5 GW ไม่ไล่ตามคะแนนสัปดาห์เดียว
3. เช็กจุดอ่อนใน Squad Lab และ swap ที่คะแนนเพิ่มจริง
4. หลีกเลี่ยง early transfer หากผู้เล่นมีเกมกลางสัปดาห์

### 24 ชั่วโมงก่อน deadline

1. เปิด AI Briefing และคัดลอกไป ChatGPT
2. ให้ ChatGPT ค้นข่าว press conference และ predicted lineup ล่าสุด
3. ตรวจราคาและราคาขายจริงในหน้า Transfers ของ FPL
4. เทียบความคุ้มของ hit: คะแนนเพิ่มคาดการณ์ต้องมากกว่าต้นทุนและความไม่แน่นอน

### 15–30 นาทีก่อน deadline

1. ตรวจ starting XI, captain, vice และ bench order
2. ตรวจธงบาดเจ็บ/เลื่อนเกมจาก FPL อีกครั้ง
3. กด Save My Team ใน FPL ด้วยตัวเอง
4. อย่ารอวินาทีสุดท้าย เพราะเว็บอาจหน่วง

## ความเป็นส่วนตัว

- เรียกเฉพาะ public FPL endpoints
- ไม่เก็บชื่อ manager ใน snapshot
- ไม่มี FPL password, cookie หรือ OpenAI API key ในระบบ
- GitHub Pages จะเผยแพร่ข้อมูลที่เป็นสาธารณะอยู่แล้ว รวมถึง Team ID และ picks หลัง
  deadline หากต้องการฟรีต้องใช้ public repository; ตรวจไฟล์ก่อน push ทุกครั้ง

## ตรวจสุขภาพระบบ

```bash
cd /Users/sarayutp/Project/10_FPL
source .venv/bin/activate
python scripts/doctor.py
pytest
```

ผลปกติควรเป็น `PASS` ทุกบรรทัดและ tests ผ่านทั้งหมด

