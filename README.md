# SocialAutoPost Local

Local web app for ingesting X/Twitter URLs, Reddit URLs, YouTube URLs, and local video files, then preparing media for social autopost workflows.

## Features

- Download video from supported X/Twitter, Reddit, and YouTube URLs with `yt-dlp`
- Upload local video files (`.mp4`, `.mov`, `.mkv`, `.webm`, `.m4v`)
- Use cookies from Firefox, Chrome, or Edge for sources that need login
- Auto cookie mode tries Firefox, Chrome, Edge, then no cookies
- Save metadata as `source.info.json`
- Save thumbnails when available
- Normalize video to `normalized.mp4` at 1080x1920 for TikTok, Reels, and Shorts
- Optionally extract audio and transcribe with local `faster-whisper`
- Generate `transcript.txt` and `captions.srt` when transcription is enabled
- Optionally create highlight clips under `clips/`
- Choose highlight clip length: 15, 30, or 60 seconds
- Generate `highlights.json` and per-clip caption files when highlight clips are enabled
- Generate a draft `caption.txt`
- Generate `manifest.json` for downstream pipeline steps
- Show job progress in the job list and details panel
- Open a job output folder from the job details panel
- Preview source, normalized, and highlight videos in the browser

## Run

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:8765
```

Change port:

```powershell
$env:SOCIALAUTOPOST_PORT=8787
python app.py
```

Change max upload size, in MB:

```powershell
$env:SOCIALAUTOPOST_MAX_UPLOAD_MB=1024
python app.py
```

Change the local Whisper model used for transcription:

```powershell
$env:SOCIALAUTOPOST_WHISPER_MODEL="base"
python app.py
```

Default model:

```text
tiny
```

## Autopost Live Mode (Webhook Adapter)

Autopost supports dry-run by default.  
For live mode, configure per-platform token + endpoint env vars:

```powershell
$env:SOCIALAUTOPOST_TIKTOK_TOKEN="your_token"
$env:SOCIALAUTOPOST_TIKTOK_ENDPOINT="https://your-api.example.com/tiktok/post"
$env:SOCIALAUTOPOST_TIKTOK_SIGNING_SECRET="your_hmac_secret"
$env:SOCIALAUTOPOST_REELS_TOKEN="your_token"
$env:SOCIALAUTOPOST_REELS_ENDPOINT="https://your-api.example.com/reels/post"
$env:SOCIALAUTOPOST_REELS_SIGNING_SECRET="your_hmac_secret"
$env:SOCIALAUTOPOST_SHORTS_TOKEN="your_token"
$env:SOCIALAUTOPOST_SHORTS_ENDPOINT="https://your-api.example.com/shorts/post"
$env:SOCIALAUTOPOST_SHORTS_SIGNING_SECRET="your_hmac_secret"
$env:SOCIALAUTOPOST_AUTOPOST_TIMEOUT_SEC="20"
$env:SOCIALAUTOPOST_AUTOPOST_RETRIES="2"
$env:SOCIALAUTOPOST_APPROVAL_PHRASE="APPROVED"
$env:SOCIALAUTOPOST_LIVE_MAX_DELIVERIES="3"
python app.py
```

### YouTube Shorts Native Adapter

For a native YouTube Shorts upload path, set:

```powershell
$env:SOCIALAUTOPOST_SHORTS_ADAPTER="native"
$env:SOCIALAUTOPOST_SHORTS_TOKEN="ya29..."
$env:SOCIALAUTOPOST_SHORTS_TOKEN_EXPIRES_AT="1767225600"
$env:SOCIALAUTOPOST_SHORTS_REFRESH_TOKEN="1//..."
$env:SOCIALAUTOPOST_SHORTS_CLIENT_ID="..."
$env:SOCIALAUTOPOST_SHORTS_CLIENT_SECRET="..."
$env:SOCIALAUTOPOST_SHORTS_PRIVACY_STATUS="private"
$env:SOCIALAUTOPOST_SHORTS_CATEGORY_ID="22"
$env:SOCIALAUTOPOST_SHORTS_MADE_FOR_KIDS="false"
```

Notes:

- `SOCIALAUTOPOST_SHORTS_TOKEN` must be an OAuth access token with `https://www.googleapis.com/auth/youtube.upload`
- If `SOCIALAUTOPOST_SHORTS_REFRESH_TOKEN`, `SOCIALAUTOPOST_SHORTS_CLIENT_ID`, and `SOCIALAUTOPOST_SHORTS_CLIENT_SECRET` are set, the app can refresh tokens automatically and cache them in `storage/oauth/shorts.token.json`
- Unverified API projects may upload as `private` only until Google API audit requirements are satisfied

Live requests send JSON with:

- `platform`
- `post_id`
- `video_file`
- `caption`
- `language`

Live request headers include:

- `Authorization: Bearer <token>`
- `X-Idempotency-Key`
- `X-Timestamp`
- `X-Signature` (when signing secret is configured, format `sha256=<hex_digest>`)

### Local Receiver Verification Example

A minimal receiver example is included at:

```text
examples/webhook_receiver_example.py
```

Run receiver:

```powershell
$env:SOCIALAUTOPOST_WEBHOOK_SIGNING_SECRET="same_secret_as_sender"
$env:SOCIALAUTOPOST_WEBHOOK_TIKTOK_SECRET="tiktok_secret"
$env:SOCIALAUTOPOST_WEBHOOK_REELS_SECRET="reels_secret"
$env:SOCIALAUTOPOST_WEBHOOK_SHORTS_SECRET="shorts_secret"
$env:SOCIALAUTOPOST_WEBHOOK_REPLAY_TTL_SEC="300"
python examples/webhook_receiver_example.py
```

Then point sender endpoint to:

```powershell
$env:SOCIALAUTOPOST_TIKTOK_ENDPOINT="http://127.0.0.1:8899/autopost"
$env:SOCIALAUTOPOST_TIKTOK_SIGNING_SECRET="same_secret_as_sender"
```

The sample receiver verifies `X-Signature` + `X-Timestamp` and returns normalized fields (`id`, `status`, `url`) that are captured by autopost reports.  
Secret resolution order: platform-specific (`SOCIALAUTOPOST_WEBHOOK_<PLATFORM>_SECRET`) then default (`SOCIALAUTOPOST_WEBHOOK_SIGNING_SECRET`).
Replay detection uses `X-Idempotency-Key`, then `post_id`, then falls back to the signature digest within the TTL window.

### Operator, Control, and Audit Flow

The UI now supports an `Operator` field in the toolbar. Autopost actions send that value through `X-Operator` and record it in the audit log.

Autopost runtime artifacts per job may now include:

- `autopost.report.json`
- `autopost.queue.json`
- `autopost.control.json`
- `autopost.audit.jsonl`

Current operator controls:

- Start autopost
- Pause
- Resume
- Retry failed

Live-mode guardrails:

- approval text must match `SOCIALAUTOPOST_APPROVAL_PHRASE`
- delivery count must not exceed `SOCIALAUTOPOST_LIVE_MAX_DELIVERIES`

## Output Structure

Each job is stored under:

```text
storage/jobs/<job_id>/
```

Example files:

```text
source.mp4
source.info.json
source.jpg or source.png
normalized.mp4
audio.wav
transcript.txt
captions.srt
clips/clip_01.mp4
clips/clip_01.caption.txt
highlights.json
caption.txt
manifest.json
```

## Notes

If Chrome shows `Could not copy Chrome cookie database`, use Auto or Firefox first. This is commonly caused by Chrome locking or protecting its cookie database on Windows.

Use this only with content you own or have permission to reuse, especially when reposting to another platform.
