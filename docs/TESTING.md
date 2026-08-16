# Testing, Debugging and Troubleshooting

## ชุดตรวจมาตรฐาน

```bash
cd /Users/sarayutp/Project/10_FPL
source .venv/bin/activate
python -m compileall -q src tests
pytest
python -m fpl_mvp all --force-refresh
python scripts/doctor.py
```

## สิ่งที่ tests ครอบคลุม

- fresh cache, stale fallback, retry และ 404 semantics
- ไม่เรียก picks ก่อน GW1 deadline
- เรียกและรับ picks หลัง deadline / publication delay
- double/blank fixtures และ availability multiplier
- legal squad, lineup, captain/vice และ transfer affordability
- atomic static-site assembly

## Browser smoke test

```bash
python -m http.server 8000 --directory dist
```

ตรวจ desktop และ mobile width:

1. หน้าโหลดโดยไม่มี console error
2. deadline countdown เดิน
3. pitch มี XI 11 คนและ bench 4 คน
4. กดใช้ทีมแนะนำแล้วแสดง 15/15 และ validation ผ่าน
5. ลบ/เพิ่ม/swap ผู้เล่นได้
6. filter/search/sort ตารางทำงาน
7. copy briefing ทำงาน
8. reload แล้วยังมี local squad
9. offline reload หลัง service worker ติดตั้งแล้ว

## ปัญหาที่พบบ่อย

### `ModuleNotFoundError`

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

### Dashboard ขึ้น “โหลดข้อมูลไม่สำเร็จ”

อย่าเปิด `file://.../index.html` ให้รัน `./scripts/run_local.sh` และเปิด URL
`http://127.0.0.1:8000`

### FPL API 404 ที่ picks

ก่อน deadline เป็นพฤติกรรมปกติ หลัง deadline อาจมี publication delay ระบบจะคง
local squad และแสดง warning แทนการล้ม

### Internet ล่ม

Pipeline ใช้ stale cache หากเคยดึงข้อมูลสำเร็จ Dashboard ใช้ service-worker cache
หลังเคยเปิดอย่างน้อยหนึ่งครั้ง ต้องดู freshness badge ก่อนตัดสินใจ

### Optimizer infeasible

รัน refresh ใหม่และดู warnings สาเหตุทั่วไปคือ FPL เปิดผู้เล่นในบางตำแหน่งไม่พอหรือ
schema เปลี่ยน Pipeline จะยังสร้าง snapshot แต่ initial squad มี status unavailable

### Port 8000 ถูกใช้

```bash
python -m http.server 8080 --directory dist
```

แล้วเปิด `http://127.0.0.1:8080`

