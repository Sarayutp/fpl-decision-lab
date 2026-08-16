# Model Card — Explainable xP Lite 1.0

## เป้าหมาย

จัดอันดับผู้เล่นและสร้าง baseline squad ด้วยข้อมูลฟรีจาก FPL ไม่ได้พยายามทำนาย
คะแนนอย่างแม่นยำถึงทศนิยม ค่า xP จึงควรถูกอ่านเป็น preference score

## สูตรพื้นฐาน

สำหรับผู้เล่นแต่ละคน:

```text
reliability = min(1, max(starts, minutes / 90) / 12)
adjusted_ppg = reliability × points_per_game
             + (1 - reliability) × points_per_team_fixture

base = 0.45 × adjusted_ppg
     + 0.35 × points_per_team_fixture
     + 0.20 × FPL_ep_next
```

หาก `ep_next` ไม่มี จะ blend adjusted PPG กับ season rate 55/45 แทน

ก่อน season เริ่ม `points_per_team_fixture = total_points / 38` หลังมี completed
fixtures แล้ว denominator เปลี่ยนเป็นจำนวน fixture ที่ทีมเล่นจบ

ต่อ fixture:

```text
adjusted = base × difficulty_factor(position) × venue_factor
next_GW  = 0.65 × adjusted + 0.35 × FPL_ep_next
xP       = next_GW × availability
```

Double Gameweek รวมทุก fixture; Blank Gameweek ได้ 0

## Availability

ใช้ `chance_of_playing_next_round / 100` ก่อน หากไม่มีใช้ status mapping:

- available 1.00
- doubtful 0.75
- injured 0.10
- suspended 0.05
- unavailable/not selectable 0.00

## Fixture multipliers

Difficulty 3 เท่ากับ 1.00 โดย DEF/GKP ได้ผลจากความยากมากกว่าเล็กน้อย Home 1.03,
Away 0.98 ตัวเลขทั้งหมดอยู่ใน source และเปลี่ยนได้เมื่อมี backtest เพียงพอ

## Optimizer objective

MILP เลือก binary variables สำหรับ squad, starters, captain และ vice โดย maximize:

```text
0.28 × squad_horizon_xP
+ 0.72 × starter_next_xP
+ captain proxy (0.70 × next_xP + 0.10 × horizon_xP)
+ 0.03 × vice_next_xP
```

ข้อจำกัด hard constraints:

- 15 คน; 2/5/5/3 ตามตำแหน่ง
- cost ≤ 100.0
- club count ≤ 3
- XI 11 คน; GKP 1, DEF 3–5, MID 2–5, FWD 1–3
- captain/vice เป็น starter คนละคนและคนละสโมสร

## จุดแข็ง

- ฟรี, deterministic และ audit ได้
- เข้าใจ blank/double, fixture difficulty และ injury chance
- optimizer รับประกันข้อจำกัดแทนการเลือก greedy ทีละคน

## ข้อจำกัดและ bias

- ไม่มี bookmaker odds, predicted minutes หรือ press conference NLP
- สถิติอดีตอาจไม่สะท้อนบทบาทใหม่/ย้ายทีม/ผู้เล่นใหม่
- FPL `ep_next` เป็น input ภายนอกที่ไม่อธิบายสูตร
- ไม่มี exact selling price ของ manager
- model weights ยังไม่ผ่าน season-long calibration
- xP อาจชอบผู้เล่นเสถียรราคากลางมากกว่าตัว premium ที่มี upside สูง

## วิธีปรับรุ่นถัดไป

เก็บ prediction ก่อน deadline และ actual points หลัง Gameweek แล้ววัด MAE, rank
correlation, calibration by position และ optimizer regret ห้ามปรับ weight จากผลสัปดาห์
เดียว ควรใช้ rolling sample หลาย Gameweeks

