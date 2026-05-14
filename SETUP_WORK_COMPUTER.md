# SocialAutoPost - Setup ที่เครื่องทำงาน

เอกสารนี้ใช้สำหรับดึงโปรเจคจาก GitHub และตั้งค่าให้พร้อมทำงานต่อที่เครื่องคอมในที่ทำงาน (Windows + PowerShell)

## 1) เตรียมเครื่อง

ติดตั้งให้ครบก่อน:

- Git
- Python 3.12+
- ffmpeg (ต้องมีใน PATH)
- yt-dlp (ต้องมีใน PATH)

ตรวจสอบ:

```powershell
git --version
python --version
ffmpeg -version
yt-dlp --version
```

---

## 2) Clone โปรเจคจาก GitHub

```powershell
cd D:\
mkdir Projects -Force
cd Projects
git clone https://github.com/thanonhari/socialautopost14052569.git
cd socialautopost14052569
```

---

## 3) สร้าง virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> หมายเหตุ: โปรเจคนี้หลักๆ ใช้ Python standard library  
> ถ้าต้องใช้ transcription ให้ติดตั้ง `faster-whisper` เพิ่มเองตามนโยบายเครื่อง/ทีม

---

## 4) ตั้งค่า Environment Variables (ขั้นต่ำ)

### พอร์ตแอป (optional)

```powershell
$env:SOCIALAUTOPOST_PORT="8765"
```

### ถ้าจะใช้ AutoPost แบบ Live (Webhook Adapter)

```powershell
$env:SOCIALAUTOPOST_TIKTOK_TOKEN="..."
$env:SOCIALAUTOPOST_TIKTOK_ENDPOINT="https://.../tiktok/post"
$env:SOCIALAUTOPOST_TIKTOK_SIGNING_SECRET="..."

$env:SOCIALAUTOPOST_REELS_TOKEN="..."
$env:SOCIALAUTOPOST_REELS_ENDPOINT="https://.../reels/post"
$env:SOCIALAUTOPOST_REELS_SIGNING_SECRET="..."

$env:SOCIALAUTOPOST_SHORTS_TOKEN="..."
$env:SOCIALAUTOPOST_SHORTS_ENDPOINT="https://.../shorts/post"
$env:SOCIALAUTOPOST_SHORTS_SIGNING_SECRET="..."

$env:SOCIALAUTOPOST_AUTOPOST_TIMEOUT_SEC="20"
$env:SOCIALAUTOPOST_AUTOPOST_RETRIES="2"
```

### ถ้าจะใช้ตัวอย่าง Webhook Receiver

```powershell
$env:SOCIALAUTOPOST_WEBHOOK_SIGNING_SECRET="..."
$env:SOCIALAUTOPOST_WEBHOOK_TIKTOK_SECRET="..."
$env:SOCIALAUTOPOST_WEBHOOK_REELS_SECRET="..."
$env:SOCIALAUTOPOST_WEBHOOK_SHORTS_SECRET="..."
```

---

## 5) ตรวจ syntax ก่อนรัน

```powershell
python -m py_compile app.py examples\webhook_receiver_example.py
```

---

## 6) รันแอป

```powershell
python app.py
```

เปิดใน browser:

- http://127.0.0.1:8765

---

## 7) รันตัวอย่าง receiver (ถ้าต้องทดสอบ webhook)

เปิดอีก PowerShell หนึ่งหน้าต่าง:

```powershell
cd D:\Projects\socialautopost14052569
.\.venv\Scripts\Activate.ps1
python examples\webhook_receiver_example.py
```

receiver จะฟังที่:

- http://127.0.0.1:8899/autopost

---

## 8) Workflow ทำงานต่อในทีม

ดึงล่าสุดก่อนเริ่มงาน:

```powershell
git checkout main
git pull
```

สร้าง branch ใหม่:

```powershell
git checkout -b feat/<topic>
```

ก่อนเปิด PR ให้เช็ก:

```powershell
python -m py_compile app.py examples\webhook_receiver_example.py
git status
```

commit + push:

```powershell
git add .
git commit -m "..."
git push -u origin feat/<topic>
```

---

## 9) หมายเหตุด้านความปลอดภัย

- ห้าม commit token/secret ลง repo
- ใช้ secret manager ขององค์กรสำหรับ staging/prod
- ใช้บัญชี low-risk สำหรับ shadow live test ก่อนเสมอ
