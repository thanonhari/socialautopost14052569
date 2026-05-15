# สิ่งที่ต้องแก้ไข (อัปเดต: 2026-05-15)

เอกสารนี้สรุป “งานที่ควรแก้/ปรับปรุงต่อ” จากการทดสอบ ingest + normalize + highlight + export และการตรวจสอบการใช้ GPU/ffmpeg ในโปรเจกต์นี้

## สถานะล่าสุดที่ยืนยันแล้ว

- YouTube test URL: `https://youtu.be/1vIx2adSTqA?si=pHylRaewZb1n2KnR`
  - งานก่อนแก้ (job `7d724835b33f`) ล้ม เพราะ source เป็น `AV1` แล้วมีการบังคับ `-hwaccel cuda` ทำให้ decode ไม่ได้บน `GTX 1050 Ti`
  - งานหลังแก้ (job `175df8527346`) จบ `done` และ log แสดงว่าใช้ `-c:v h264_nvenc` ตอน encode (normalize + highlight clips)
- แก้ให้ ffmpeg “ลองรันแบบมี hwaccel แล้ว fallback ไปแบบไม่มี hwaccel” เมื่อเจอ error decode ที่เข้าข่าย (อยู่ใน `app.py`)

## ต้องแก้ (Bug / ความเสถียร)

- `collect_runtime_diagnostics()` รายงาน GPU แบบ hard-code/เดา (`"GTX 1050 Ti" if nvenc_available else ""`)
  - ควรแก้ให้ดึงชื่อ GPU จริง (เช่น `nvidia-smi --query-gpu=name --format=csv,noheader` ถ้ามี) และแยก “มี NVENC” ออกจาก “ชื่อการ์ดจอ”
  - เป้าหมาย: diagnostics ไม่ควรให้ข้อมูลผิด/ทำให้เข้าใจผิด

- `detect_ffmpeg_runtime()` ใช้ผลจาก `ffmpeg -encoders` เพื่อตัดสินว่า NVENC “มี/ไม่มี” แต่ยังไม่ validate การใช้งานจริง
  - ควรเพิ่ม sanity check แบบเบาๆ:
    - ตรวจว่า `ffmpeg -hide_banner -h encoder=h264_nvenc` ทำงาน
    - ถ้าพัง ให้ fallback ไป `libx264` แล้ว log เหตุผล

- `run_ffmpeg_media_command()` fallback logic อิงจากข้อความ error เป็นหลัก
  - ควรเพิ่ม marker/กรณีให้ครบ (เช่น `Device setup failed`, `No device available`, `Unknown error occurred` จาก ffmpeg/nvenc)
  - ควรจำกัดว่า fallback จะเกิด “ครั้งเดียว” ต่อ command เพื่อกันลูป retry ในอนาคต

- Highlight pipeline ยัง “ง่ายมาก” และไม่มีการรับประกันคุณภาพคลิป
  - ตอนนี้ตัดเป็น 3 ช่วงแบบคงที่จาก duration
  - ควรเพิ่ม:
    - กติกาไม่ตัดช่วงที่เป็น fade-in/fade-out
    - รองรับ “ตัดจาก transcript” เมื่อ `transcribe=true`
    - เก็บผลการเลือกช่วง (start/end) เป็นไฟล์ manifest ที่อ่านง่าย

## ควรแก้ (คุณภาพระบบ / UX / Operability)

- Log โตเกินจำเป็นจาก `yt-dlp --dump-json` (format list ใหญ่มาก)
  - ควรลด log:
    - เก็บ dump-json ลงไฟล์ `metadata.json` แล้ว log แค่สรุป (title/uploader/duration)
    - หรือ sanitize เฉพาะ key สำคัญก่อน append_log

- YouTube warning เรื่อง JS runtime:
  - `yt-dlp` แจ้งว่า “ไม่มี supported JavaScript runtime” ทำให้บาง format อาจหาย/แตกในอนาคต
  - ควรทำให้ชัดในระบบ:
    - เพิ่ม check ตอน startup ว่ามี `deno` หรือ runtime อื่นไหม
    - ถ้าไม่มี ให้ log เตือนแบบสั้น + ชี้วิธีแก้ (`--js-runtimes ...` หรือ install runtime)

- เลือก format จาก YouTube ให้เหมาะกับ pipeline มากขึ้น
  - ถ้าต้องการลดภาระ CPU decode: ให้พยายามเลือก source ที่เป็น `h264` ก่อน (ถ้ามี)
  - แนวทาง: เพิ่ม `yt-dlp` option แบบเลือก codec/ความละเอียดที่เหมาะ (เช่น prioritize `avc1` มากกว่า `av01`)

- ทำให้ “ใช้ GPU encode” เป็น policy ที่ควบคุมได้
  - ตอนนี้ default encoder เลือก `h264_nvenc` ถ้ามี
  - ควรเพิ่ม:
    - env/setting ระดับระบบ เช่น `SOCIALAUTOPOST_PREFER_GPU_ENCODE=true/false`
    - แยก `decode_hwaccel` ออกจาก `encode_gpu` อย่างชัดเจน (หลีกเลี่ยงปัญหา AV1 decode)

## งานเพิ่มเพื่อการตรวจสอบ (Verification)

- เพิ่ม endpoint หรือ log summary ที่บอกชัดว่า job นี้:
  - ใช้ encoder อะไร (`h264_nvenc` หรือ `libx264`)
  - มีการ fallback จาก hwaccel หรือไม่
  - เวลาแต่ละ step ใช้เท่าไหร่ (duration per step)

- เพิ่ม “ชุดทดสอบอย่างน้อย 3 เคส” เป็น checklist ใน repo:
  - YouTube ที่ video codec เป็น AV1 (ยืนยันว่าไม่ fail จาก hwaccel decode)
  - Reddit/X ที่เป็น H264 ปกติ (ยืนยันว่า pipeline จบ และสร้าง clips/export)
  - เคสสั้นมาก (< highlight_length) (ยืนยันว่า skip/ตัดช่วงถูก และไม่ค้าง)

## ไฟล์/จุดที่เกี่ยวข้อง (เพื่อไปแก้ง่าย)

- ffmpeg runtime + fallback: `app.py` (ฟังก์ชัน `detect_ffmpeg_runtime`, `run_ffmpeg_media_command`, `normalize_video`, `create_highlight_artifacts`)
- diagnostics: `app.py` (ฟังก์ชัน `collect_runtime_diagnostics`)
- YouTube ingest / yt-dlp: `app.py` (ส่วนที่เรียก `yt-dlp` และจัดการ log/metadata)

