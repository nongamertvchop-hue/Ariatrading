# Fix Error — Ariatrading Bug & Incident Hub

โฟลเดอร์นี้คือ **ศูนย์กลางสำหรับจัดการ Error / Bug / Incident ของ Ariatrading** และเป็นส่วนหนึ่งของกฎการพัฒนาโปรเจกต์

## ใช้ทำอะไร

ให้ใช้โฟลเดอร์ `Fix Error` สำหรับบันทึกและติดตามปัญหาจริงที่พบในทุกส่วนของระบบ เช่น

- Webaria / Frontend / UI / Chart
- Cloudflare Worker / API
- MT5 Bridge / MQL5
- Strategy / Signal / Backtest
- Python runtime / ML pipeline
- Order execution / Risk / Safety controls
- CI / Test / Build
- Deployment / Integration / Data pipeline

**ห้ามใช้โฟลเดอร์นี้เป็นที่เก็บปัญหาแบบลอย ๆ หรือรายการ TODO ทั่วไป** แต่ละรายการควรอธิบายปัญหาที่ตรวจพบจริง และต้องสามารถตรวจสอบย้อนกลับได้

## กฎบังคับเมื่อพบ Error

ทุกปัญหาที่มีผลต่อความถูกต้อง ความปลอดภัย หรือการใช้งานจริง ให้ดำเนินการตามลำดับ:

1. **Reproduce** — ทำให้ปัญหาเกิดซ้ำหรือเก็บหลักฐานที่ยืนยันปัญหา
2. **Observe** — บันทึกอาการ, input, environment และผลที่เกิดขึ้นจริง
3. **Root cause** — หาเหตุทางเทคนิค ไม่แก้ด้วยการเดา
4. **Fix** — แก้ที่ต้นเหตุโดยไม่ลด safety gate เพื่อให้ test ผ่าน
5. **Regression test** — เพิ่ม/แก้ test เพื่อป้องกันปัญหาเดิมกลับมา
6. **Verify deployment** — ตรวจว่าการแก้ไขถูก deploy และพฤติกรรมจริงตรงกับที่คาด

## กฎการปิด Error

ห้ามระบุว่า `FIXED` หรือ `CLOSED` เพียงเพราะโค้ดถูกแก้หรือ commit สำเร็จ

ต้องมีหลักฐานอย่างน้อยว่า:

- reproduce ได้และมี root cause ที่ชัดเจน
- regression test ผ่าน
- CI ที่เกี่ยวข้องผ่านจริง (ห้ามเรียก PASS ขณะ queued/in_progress)
- ถ้าเป็นปัญหา runtime/web/deployment ต้องตรวจพฤติกรรมหลัง deploy จริงด้วย

หากยังไม่มีหลักฐาน ให้สถานะเป็น `OPEN`, `INVESTIGATING`, `IN_PROGRESS` หรือ `BLOCKED` ตามความเหมาะสม

## ข้อห้าม

- ห้ามสร้าง fake UI state เพื่อให้ดูเหมือนระบบทำงาน
- ห้ามใช้ fake market data แล้วติดป้ายว่า LIVE
- ห้าม bypass strategy/execution safety gate เพื่อแก้ปัญหา UI หรือทำให้ demo ดูทำงาน
- ห้ามปิด bug โดยไม่มี reproduction/regression/deployment evidence
- ห้ามลดความปลอดภัยของระบบเพียงเพื่อให้ test หรือ CI ผ่าน

## รูปแบบไฟล์

ตั้งชื่อ issue ให้ค้นหาได้ง่าย เช่น:

- `WEB-001.md` — Web/UI
- `API-001.md` — API/Worker
- `MT5-001.md` — MT5 bridge/execution
- `STRAT-001.md` — strategy/signal
- `CI-001.md` — CI/build
- `DEPLOY-001.md` — deployment/integration

ทุก issue ควรมีอย่างน้อย: **Status, Severity, Reproduction, Observed Behavior, Expected Behavior, Root Cause, Fix, Regression Test, Verification Evidence**

โฟลเดอร์นี้จึงทำหน้าที่เป็นทั้ง **bug memory + incident log + regression contract** ของโปรเจกต์ เพื่อให้การพัฒนาครั้งต่อไปไม่ลืมปัญหาเดิมและไม่ประกาศความสำเร็จโดยไม่มีหลักฐานจริง
