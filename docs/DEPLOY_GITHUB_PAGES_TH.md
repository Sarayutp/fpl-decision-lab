# GitHub Pages และการอัปเดตระบบออนไลน์

Repository: [https://github.com/Sarayutp/fpl-decision-lab](https://github.com/Sarayutp/fpl-decision-lab)  
Dashboard: [https://sarayutp.github.io/fpl-decision-lab/](https://sarayutp.github.io/fpl-decision-lab/)

## สถานะปัจจุบัน

**Phase 6 เผยแพร่แล้วเมื่อ 31 สิงหาคม 2026:** รุ่น `2.0.0-rc.1`, build
`984449c719ddc84f`, Team ID `5105794`. CI, published smoke และ hosted restore ผ่าน
ดู [หลักฐานและข้อจำกัดของผลตรวจ](PHASE_6_QA.md)

### ด่านก่อนและหลังเผยแพร่

1. CI ตรวจ Python/JS, contract, payload budget และ browser E2E 26 cases
2. build สร้าง `build-info.json` พร้อม build ID, release, timestamp และ SHA-256 ของไฟล์สำคัญ
3. workflow เก็บ `validated-site` ไว้ 30 วัน แล้ว upload Pages artifact
4. หลัง deploy สั่ง `smoke_site.py` ที่ URL จริงพร้อม expected build ID ถ้าไฟล์/ทีม/เวลาไม่ตรงให้ถือว่า release ยังไม่ผ่าน
5. เปิด Diagnostics ตรวจชื่อทีมและ snapshot รวมทั้งลอง This Gameweek/copy Briefing ใน Browser

### ย้อนรุ่นจาก artifact เดิม

1. หยุด schedule ของ workflow refresh ชั่วคราวในหน้า GitHub Actions เพื่อไม่ให้รอบถัดไปแทนที่รุ่นที่ย้อน
2. หา run ID ของ `Refresh FPL Data and Deploy Pages` ที่สำเร็จบน main และมี `validated-site` อายุไม่เกิน 30 วัน
3. Run workflow `Restore a validated Pages release` ใส่ run ID นั้น
4. workflow ตรวจว่าเป็น deployment run ที่สำเร็จจาก repository เดียวกัน ไม่รับ PR/fork แล้วตรวจ hash ก่อน deploy
5. หลัง deploy ตรวจ expected build ID อีกครั้ง และเปิดหน้าเว็บดูสถานะ stale/deadline ของข้อมูลเก่า
6. เมื่อแก้ปัญหาแล้วเผยแพร่รุ่นใหม่และเปิด schedule กลับ

การ restore **ไม่ refresh ข้อมูลเก่า** เพื่อรักษาความตรงกันของ artifact ทั้งชุด
จึงอาจแสดง stale หรือผ่าน deadline และต้องไม่ใช้แผนนั้นตัดสินใจจนกว่าจะ refresh รุ่นที่แก้แล้ว
ถ้า artifact หมดอายุ ให้สร้าง release จาก commit ที่รู้ว่าใช้งานได้และตรวจใหม่ทั้งชุด
ไม่ใช้ reset หรือแก้ history ของ repository เป็นขั้นตอน rollback

ซ้อม artifact A → B → restore A ในเครื่องแล้ว และ [ซ้อม workflow บน GitHub จริงผ่าน](https://github.com/Sarayutp/fpl-decision-lab/actions/runs/33348816315)
โดยใช้ artifact ของ deployment `33348695204` เผยแพร่ซ้ำเพื่อทดสอบเส้นทางกู้คืนโดยไม่เปลี่ยนโค้ด/เวลา snapshot ที่ผู้ใช้กำลังเห็น
ไม่จำเป็นต้องหยุด schedule ระหว่างการซ้อมแบบรุ่นเดียวกันครั้งนี้; รอบ refresh เดิมยังเปิดอยู่

ผู้ใช้ที่ cache เว็บรุ่น v7 เดิมไว้ควร refresh อีกครั้งหลังการเปิดครั้งแรกเพื่อรับรุ่นใหม่
ไม่ต้องล้าง localStorage เพราะจะทำให้แผนที่ผู้ใช้บันทึกไว้หาย

อ้างอิง: [GitHub custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
และ [ดาวน์โหลด artifact ข้าม workflow run](https://github.com/actions/download-artifact#download-artifacts-from-other-workflow-runs-or-repositories)

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
- schedule ปกติ 4 รอบต่อวัน: 07:17, 13:17, 19:17 และ 01:17 เวลาไทย
- รอบเสริม 23:17 เวลาไทย เพื่อให้ใกล้ deadline ที่พบบ่อยมากขึ้น
- รองรับปุ่ม `Run workflow` สำหรับอัปเดตทันที
- Team ID เริ่มต้นคือ `5105794` และเปลี่ยนได้ผ่าน Repository variable ชื่อ `FPL_TEAM_ID`

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

5 รอบต่อวันประมาณ 150 runs ต่อเดือน งานหนึ่งถูกจำกัด 12 นาทีและโดยปกติใช้ไม่ถึง
2 นาที หากต้องลดอีก ให้แก้ cron เหลือวันละ 2 รอบ หรือกด manual ใกล้ deadline

## ความปลอดภัยก่อนตั้ง repo เป็น public

ระบบไม่ต้องใช้ GitHub Secret และ `.gitignore` ตัด cache/venv ออกแล้ว อย่างไรก็ตาม
ให้ตรวจเสมอว่าไม่มีไฟล์ `.env`, password, cookie หรือ export อื่นที่คุณเพิ่มเองก่อน
`git add`

Snapshot มีชื่อทีม, ชื่อ manager, Team ID, คะแนน, อันดับ และ picks ที่ FPL เปิดเป็น
ข้อมูลสาธารณะ เพื่อใช้ยืนยันว่า pipeline กำลังวิเคราะห์ทีมถูกต้อง

## ถ้า workflow ไม่ deploy

- ตรวจว่า Pages Source เป็น `GitHub Actions`
- เปิด log ของ job `build` ก่อน `deploy`
- ถ้า FPL API ล่ม ให้กด rerun; cache ของ GitHub runner ไม่รับประกันข้ามรอบ
- ถ้า tests ไม่ผ่าน workflow จะไม่เผยแพร่ข้อมูลเสีย
- schedule ของ GitHub อาจเริ่มช้ากว่าเวลาที่ตั้ง ไม่ควรใช้เป็นนาฬิกาวินาทีสุดท้าย
