# Python Env ที่ต้องใช้ (ทดสอบบนเครื่องอื่น) — 2026-05-15

โปรเจกต์นี้ “รันได้ด้วย Python standard library เป็นหลัก” แต่ต้องมีเครื่องมือภายนอกบางตัวใน PATH เพื่อให้ ingest/normalize/highlight ทำงานได้

## 1) สิ่งที่ต้องมี (ขั้นต่ำ)

- Windows + PowerShell
- Git
- Python `3.12+`
- `ffmpeg` และ `ffprobe` อยู่ใน `PATH`
- `yt-dlp` อยู่ใน `PATH`
- Browser อย่างน้อย 1 ตัวสำหรับดึง cookies (ถ้าใช้): `firefox` หรือ `chrome` หรือ `edge`

ตรวจสอบ:

```powershell
git --version
python --version
ffmpeg -version
ffprobe -version
yt-dlp --version
```

## 2) สร้าง virtualenv (แนะนำ)

```powershell
cd D:\Projects\socialautopost
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m py_compile app.py
```

หมายเหตุ: ถ้าแค่ ingest + normalize + highlight โดยไม่ transcribe ปกติไม่ต้อง `pip install` อะไรเพิ่ม

## 3) Optional: Transcription (Whisper)

ถ้าจะเปิด `transcribe=true` ต้องติดตั้ง `faster-whisper`:

```powershell
pip install -U faster-whisper
```

ตั้งค่าให้ใช้ CPU (ค่าเริ่มต้น):

```powershell
$env:SOCIALAUTOPOST_WHISPER_DEVICE="cpu"
$env:SOCIALAUTOPOST_WHISPER_COMPUTE_TYPE="int8"
```

ถ้าต้องการใช้ GPU (CUDA) ต้องมี NVIDIA driver + CUDA runtime/แพ็กเกจที่เข้ากับ `faster-whisper` ในเครื่องนั้นก่อน แล้วค่อย:

```powershell
$env:SOCIALAUTOPOST_WHISPER_DEVICE="cuda"
$env:SOCIALAUTOPOST_WHISPER_COMPUTE_TYPE="int8"
```

## 4) Optional: GPU encode (ffmpeg NVENC)

ถ้าต้องการให้ encode เป็น GPU:

- ต้องใช้ `ffmpeg` build ที่รองรับ `h264_nvenc`
- ต้องมี NVIDIA driver ถูกต้อง

ตรวจ NVENC:

```powershell
ffmpeg -hide_banner -encoders | Select-String h264_nvenc
```

ค่าที่แนะนำสำหรับความเสถียร:

- ตั้ง encoder ได้ (ถ้าต้องการบังคับ) แต่ “อย่าบังคับ hwaccel decode” โดยไม่จำเป็น เพราะ source บางอัน (เช่น AV1) อาจ decode บน GPU ไม่ได้

```powershell
$env:SOCIALAUTOPOST_FFMPEG_VIDEO_ENCODER="h264_nvenc"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL_TYPE=""
```

## 5) Env ที่ใช้บ่อยสำหรับทดสอบ

ข้ามการ `yt-dlp -U` ตอนสตาร์ต (เร็วขึ้น):

```powershell
$env:SOCIALAUTOPOST_SKIP_YTDLP_UPDATE="true"
```

กำหนดพอร์ต (ถ้าชน):

```powershell
$env:SOCIALAUTOPOST_PORT="8765"
```

## 6) รันแอป

```powershell
python app.py
```

เปิด:

- `http://127.0.0.1:8765`
- diagnostics: `http://127.0.0.1:8765/api/diagnostics`

