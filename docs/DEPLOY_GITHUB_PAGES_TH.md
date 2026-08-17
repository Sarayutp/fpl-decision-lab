# GitHub Pages และการอัปเดตระบบออนไลน์

Repository: [https://github.com/Sarayutp/fpl-decision-lab](https://github.com/Sarayutp/fpl-decision-lab)  
Dashboard: [https://sarayutp.github.io/fpl-decision-lab/](https://sarayutp.github.io/fpl-decision-lab/)

## สถานะปัจจุบัน

ระบบ deploy สำเร็จแล้ว Dashboard และ automation ทำงานได้แม้ MacBook ปิดอยู่ GitHub Pages
บนแผน Free ใช้ฟรีกับ public repository ตาม
[เอกสาร GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

- Repository เป็น public และใช้สาขา `main`
- Pages Source เป็น `GitHub Actions`
- บังคับใช้ HTTPS แล้ว
- CI และ deployment ทำงานสำเร็จ
- การใช้งานทั่วไปไม่ต้องทำขั้นตอนติดตั้งด้านล่างซ้ำ

## สิ่งที่เตรียมไว้แล้ว

- `.github/workflows/ci.yml` ทดสอบทุก push/PR
- `.github/workflows/deploy-pages.yml` refresh, test, build และ deploy
- schedule 4 รอบต่อวัน: 07:17, 13:17, 19:17 และ 01:17 เวลาไทย
- รองรับปุ่ม `Run workflow` สำหรับอัปเดตทันที
- Team ID ตั้งไว้เป็น `3647781`

## สั่งอัปเดตทันที

1. เปิด [Refresh FPL Data and Deploy Pages](https://github.com/Sarayutp/fpl-decision-lab/actions/workflows/deploy-pages.yml)
2. กด `Run workflow`
3. เลือกสาขา `main` และยืนยัน
4. รอ `build` และ `deploy` เป็นสีเขียว
5. Refresh Dashboard และตรวจป้ายความสดของข้อมูล

## การติดตั้งครั้งแรกใน repository อื่น (ไม่ต้องทำกับระบบปัจจุบัน)

### 1. Repository

ระบบใช้ public repository `Sarayutp/fpl-decision-lab` และสาขา `main` หากต้องตั้งใหม่
ในบัญชีอื่น สามารถใช้คำสั่งต่อไปนี้จาก Terminal ในโปรเจกต์:

```bash
git init
git add .
git commit -m "Build FPL Decision Lab"
git branch -M main
git remote add origin https://github.com/Sarayutp/fpl-decision-lab.git
git push -u origin main
```

### 2. เปิด GitHub Pages ใน repository ใหม่

1. เข้า repository → `Settings`
2. เลือก `Pages`
3. ที่ Source เลือก `GitHub Actions`
4. เข้าแท็บ `Actions`
5. เปิด workflow `Refresh FPL Data and Deploy Pages`
6. กด `Run workflow`

เมื่อสำเร็จ URL จะอยู่ใน deployment ชื่อ `github-pages`

### 3. ทดสอบ

- เปิด URL และดูว่าจำนวนผู้เล่นไม่เป็น `—`
- เปิด `<URL>/data/latest.json`
- ตรวจ `generated_at` ว่าใหม่
- ลองใช้ Squad Lab แล้ว refresh หน้า ทีมควรยังอยู่
- ปิด Wi-Fi หลังเคยเปิดหน้าแล้ว refresh เพื่อทดสอบ offline cache

## การใช้โควตาฟรี

4 รอบต่อวันประมาณ 120 runs ต่อเดือน งานหนึ่งถูกจำกัด 12 นาทีและโดยปกติใช้ไม่ถึง
2 นาที หากต้องลดอีก ให้แก้ cron เหลือวันละ 2 รอบ หรือกด manual ใกล้ deadline

## ความปลอดภัยก่อนตั้ง repo เป็น public

ระบบไม่ต้องใช้ GitHub Secret และ `.gitignore` ตัด cache/venv ออกแล้ว อย่างไรก็ตาม
ให้ตรวจเสมอว่าไม่มีไฟล์ `.env`, password, cookie หรือ export อื่นที่คุณเพิ่มเองก่อน
`git add`

Snapshot ตั้งใจไม่เก็บชื่อจริงของ manager แต่มี Team ID, คะแนน, อันดับ และ picks ที่
FPL เปิดเป็นสาธารณะหลัง deadline

## ถ้า workflow ไม่ deploy

- ตรวจว่า Pages Source เป็น `GitHub Actions`
- เปิด log ของ job `build` ก่อน `deploy`
- ถ้า FPL API ล่ม ให้กด rerun; cache ของ GitHub runner ไม่รับประกันข้ามรอบ
- ถ้า tests ไม่ผ่าน workflow จะไม่เผยแพร่ข้อมูลเสีย
- schedule ของ GitHub อาจเริ่มช้ากว่าเวลาที่ตั้ง ไม่ควรใช้เป็นนาฬิกาวินาทีสุดท้าย
