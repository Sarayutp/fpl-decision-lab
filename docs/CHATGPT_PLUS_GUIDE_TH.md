# ใช้ FPL Decision Lab ร่วมกับ ChatGPT Plus

## หลักการ

ระบบนี้ตั้งใจไม่เรียก OpenAI API จึงไม่มีค่า token และไม่ต้องใส่ API key การใช้ AI
เกิดใน ChatGPT ที่คุณสมัคร Plus อยู่แล้ว โดยส่งเฉพาะ briefing ขนาดเล็กให้วิเคราะห์

หากวันหนึ่งต้องการให้โค้ดเรียก AI อัตโนมัติจริง จะเป็น OpenAI API ซึ่งมี credential
และ billing แยกจาก workflow นี้ ดูแนวทาง credential ของ API ได้จาก
[OpenAI API quickstart](https://platform.openai.com/docs/quickstart)

## วิธีเร็วที่สุด

1. เปิด Dashboard ไปที่ `AI Briefing`
2. กด `คัดลอกสำหรับ ChatGPT`
3. เปิด ChatGPT แล้ววางข้อความทั้งหมด
4. เปิด Web Search หากไม่ได้เปิดอัตโนมัติ
5. ให้ ChatGPT ตอบพร้อมแหล่งข่าวและเวลาอัปเดต

ไฟล์เดียวกันอยู่ที่ `data/briefing.md` และดาวน์โหลดจาก Dashboard ได้

## ตั้ง ChatGPT Project สำหรับ FPL

สร้าง Project ชื่อ `FPL 2026/27` แล้วใส่ Project instructions:

```text
ทำหน้าที่เป็น FPL decision reviewer ที่ระมัดระวัง
แยกข้อมูลจาก briefing, ข่าวที่ค้นเจอ และข้อสันนิษฐานออกจากกัน
ทุกครั้งต้องระบุ deadline, data freshness, transfer, XI, captain, vice,
bench order, ความเสี่ยง และแผนสำรอง
ห้ามอ้างว่าคะแนนคาดการณ์เป็นผลที่รับประกัน
```

ในแต่ละ Gameweek อัปโหลด `data/briefing.md` เวอร์ชันใหม่หรือวางจาก Dashboard
Project ช่วยเก็บบทสนทนาและแนวทางของคุณต่อเนื่อง แต่ให้ยืนยันข่าวใหม่ทุกสัปดาห์

## Prompt สำหรับการตัดสินใจ

ไฟล์ template อยู่ที่ `prompts/weekly-review-th.md` ใช้คำถามเพิ่มเติมได้ เช่น:

```text
เปรียบเทียบทางเลือก A กับ B ใน 5 Gameweeks โดยคิด -4 hit ให้ชัดเจน
รายงาน downside case หากผู้เล่นตัวหลักไม่ได้ลง และบอกว่าข้อมูลใดต้องเช็กอีก
```

## Scheduled Task ด้วย GitHub Pages

Scheduled Task ไม่ควรถูกใช้แทน pipeline คำนวณ ให้ GitHub Actions อัปเดตตัวเลข ส่วน
Task ทำหน้าที่เตือนและตรวจข่าวจากเว็บ โดยใช้ public briefing URL นี้:

```text
ทุกวันศุกร์เวลา 19:00 น. ตามเวลา Asia/Bangkok ให้เปิด
https://sarayutp.github.io/fpl-decision-lab/data/briefing.md
ตรวจว่าไฟล์ใหม่ไม่เกิน 24 ชั่วโมง แล้วค้นเว็บหา
ข่าวบาดเจ็บ press conference การแบน การเลื่อนเกม และ predicted lineup ที่เกี่ยวข้อง
แจ้งผมเฉพาะสิ่งที่อาจเปลี่ยน transfer, captain หรือ starting XI พร้อมลิงก์แหล่งข่าว
หากไฟล์เก่าให้เตือนว่า pipeline ต้องอัปเดต ห้ามตัดสินใจแทนหรืออ้างว่าได้กดทีมแล้ว
```

Scheduled Task ไม่สามารถพึ่งไฟล์ที่เก็บอยู่ใน Project เป็นแหล่งข้อมูลตอนรันแบบไม่มี
คนเฝ้า จึงควรชี้ไปที่ public briefing URL แทน ตัวอย่าง workflow ด้าน automation ดูได้ที่
[ChatGPT automation use cases](https://learn.chatgpt.com/use-cases?category=automation)

## Checklist ตรวจคำตอบ AI

- มีลิงก์และเวลาของข่าวหรือไม่
- แยก fact กับ inference หรือไม่
- ใช้ deadline และ Gameweek ถูกต้องหรือไม่
- คิดต้นทุน hit หรือไม่
- เช็ก selling price จริงไม่ได้หรือไม่ ถ้าไม่ได้ต้องเตือน
- มีแผนสำรองกรณีข่าวเปลี่ยนหรือไม่
