# Work Computer Quick Start (SocialAutoPost)

เอกสารนี้คือขั้นตอนสั้นๆ สำหรับตอนที่คุณ “ถึงเครื่องคอมที่ทำงานแล้ว” และต้องการเริ่มทำงานต่อทันที

## 0) เปิด PowerShell

ใช้ PowerShell ปกติ (ไม่ต้อง Admin ถ้า policy อนุญาต)

---

## 1) ตรวจเครื่องว่าพร้อมหรือยัง

```powershell
git --version
python --version
ffmpeg -version
yt-dlp --version
```

ถ้าคำสั่งไหนไม่เจอ ให้ติดตั้งตัวนั้นก่อน

---

## 2) ดึงโปรเจค (ครั้งแรก)

```powershell
cd D:\
mkdir Projects -Force
cd Projects
git clone https://github.com/thanonhari/socialautopost14052569.git
cd socialautopost14052569
```

ถ้าเคย clone แล้ว ให้ใช้:

```powershell
cd D:\Projects\socialautopost14052569
git checkout main
git pull
```

---

## 3) เปิด virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

---

## 4) ตั้งค่า env ขั้นต่ำ

```powershell
$env:SOCIALAUTOPOST_PORT="8765"
```

ถ้าจะทดสอบ autopost live webhook ให้ตั้งเพิ่ม:

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

---

## 5) เช็ก syntax ก่อนรัน

```powershell
python -m py_compile app.py examples\webhook_receiver_example.py
```

---

## 6) รันแอป

```powershell
python app.py
```

เปิด browser ที่:

- http://127.0.0.1:8765

---

## 7) ถ้าจะทดสอบ receiver ตัวอย่าง

เปิด PowerShell อีกหน้าต่าง:

```powershell
cd D:\Projects\socialautopost14052569
.\.venv\Scripts\Activate.ps1
$env:SOCIALAUTOPOST_WEBHOOK_SIGNING_SECRET="..."
python examples\webhook_receiver_example.py
```

receiver endpoint:

- http://127.0.0.1:8899/autopost

---

## 8) เริ่มทำงานต่อในทีม

สร้าง branch:

```powershell
git checkout -b feat/<topic>
```

ก่อน commit:

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

## 9) Troubleshooting สั้นๆ

- `git push` ไม่ได้: ตรวจสิทธิ์ GitHub + `gh auth login`
- เปิดพอร์ตไม่ได้: เปลี่ยนพอร์ต
  ```powershell
  $env:SOCIALAUTOPOST_PORT="8787"
  python app.py
  ```
- webhook live ขึ้น blocked: ตรวจ token/endpoint/signing secret env ว่าครบ

---

## 10) Security reminder

- ห้าม commit secret/token
- ใช้ secret manager ขององค์กร
- ทดสอบ live ด้วยบัญชี low-risk ก่อน
