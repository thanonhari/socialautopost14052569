# SocialAutoPost Roadmap

## Goal

Build a local web app that turns source media into short-form social-ready assets.

The intended pipeline:

```text
URL or local video
-> ingest media and metadata
-> normalize video
-> optional transcription and captions
-> optional highlight clips
-> caption drafts and manifest
-> review/export for posting
```

The app currently runs locally at:

```text
http://127.0.0.1:8765
```

## Current Status

Status: working prototype.

The app can ingest media, create normalized videos, generate optional transcripts, export highlight clips, and open job folders from the browser UI.

## Supported Sources

Implemented:

- X/Twitter URLs
- Reddit public video URLs
- YouTube / YouTube Shorts URLs
- Local video uploads

Local upload formats:

```text
.mp4, .mov, .mkv, .webm, .m4v
```

Not planned right now:

- full-series/movie streaming sites
- unsupported `yt-dlp` sites
- sources with unclear or high copyright risk

## Output Per Job

Each job is stored in:

```text
storage/jobs/<job_id>/
```

Typical files:

```text
source.mp4
source.info.json
source.jpg / source.png / source.webp
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

Not every job creates every file. For example, `audio.wav`, `transcript.txt`, and `captions.srt` are created only when transcription is enabled.

## Completed Steps

### 1. Local Web App

Done.

- Python standard-library backend in `app.py`
- Static frontend in `web/`
- Local server at `127.0.0.1:8765`
- Job list and job details panel
- File links for generated outputs

### 2. URL Ingest

Done.

Implemented with `yt-dlp`.

Supported platforms:

- X/Twitter
- Reddit
- YouTube / YouTube Shorts

Important fixes:

- X/Twitter uses cookie fallback: Firefox -> Chrome -> Edge -> none
- Reddit no longer forces thumbnail conversion to JPG
- YouTube Shorts added to allowlist and tested successfully

### 3. Local File Upload

Done.

Users can upload local video files from the browser UI.

Backend endpoint:

```text
POST /api/jobs/upload
```

### 4. Video Normalization

Done.

Uses `ffmpeg` to create:

```text
normalized.mp4
```

Current target:

```text
1080x1920
H.264 video
AAC audio
MP4 container
```

### 5. Progress Bar

Done.

Each job tracks a `progress` field and the UI shows progress bars in:

- job list
- job details panel

### 6. Open Output Folder

Done.

The details panel has an `Open folder` button.

Backend endpoint:

```text
POST /api/jobs/<job_id>/open-folder
```

On Windows, this opens the job folder in Explorer.

### 7. Optional Transcription

Done.

When `Transcribe audio` is enabled, the app creates:

```text
audio.wav
transcript.txt
captions.srt
```

Current implementation:

- extracts audio with `ffmpeg`
- transcribes with local `faster-whisper`
- default model: `tiny`

Optional environment variable:

```powershell
$env:SOCIALAUTOPOST_WHISPER_MODEL="base"
```

### 8. Highlight Clips

Done as basic implementation.

When `Create highlight clips` is enabled, the app creates:

```text
clips/clip_01.mp4
clips/clip_01.caption.txt
highlights.json
```

Current behavior:

- supports 15, 30, or 60 second clip length
- creates up to 3 clips
- if transcript has speech, it chooses ranked transcript segments
- if no transcript or no speech exists, it falls back to timed clips from the start

### 9. Per-Clip Captions

Done as basic implementation.

Each highlight clip gets a matching caption draft:

```text
clips/clip_01.caption.txt
```

The `highlights.json` file also stores the caption text.

### 10. Project Knowledge Wiki

Done.

Persistent project knowledge is stored in:

```text
knowledge/
```

Start here:

```text
knowledge/wiki/index.md
knowledge/wiki/log.md
knowledge/AGENTS.md
```

## Verified Jobs

### Local Upload

```text
storage/jobs/93c996c827d0/
```

Verified:

- upload
- metadata
- normalization
- caption draft
- manifest

### Transcription

```text
storage/jobs/92b1b6125127/
```

Verified:

- audio extraction
- transcript output
- SRT captions

The test file had no speech, so output was:

```text
[No speech detected]
```

### Multi-Highlight Export

```text
storage/jobs/b1a2ed492905/
```

Verified:

- multiple clips
- per-clip caption files
- `highlights.json`

### YouTube Shorts

```text
storage/jobs/1695d58d34c9/
```

Verified:

- YouTube Shorts metadata
- video download
- thumbnail
- normalized video
- 3 highlight clips

## Known Issues And Notes

### YouTube JavaScript Runtime Warning

`yt-dlp` warned that no supported JavaScript runtime was found for YouTube extraction.

Current status:

- YouTube Shorts still works now
- future `yt-dlp` versions may require setting up a JS runtime such as Deno or Node

### Chrome Cookie Database Error

Chrome cookies can fail with:

```text
Could not copy Chrome cookie database
```

Current fix:

- use Auto cookie mode
- prefer Firefox cookies

### Highlight Selection Is Still Basic

Current highlight selection is mechanical:

- longest transcript segment when speech exists
- fallback timed clips when speech is unavailable

It does not yet understand meaning, topic, emotion, punchline, or virality.

## Remaining Steps

### Step 11. Smarter Highlight Selection

Status: done.

Highlight selection now uses transcript scoring instead of only longest-segment selection.

It considers:

- transcript meaning
- topic changes
- strong statements
- hooks
- funny moments
- newsworthy moments
- repeated keywords

Expected outputs remain:

```text
clips/clip_01.mp4
clips/clip_01.caption.txt
highlights.json
```

The `highlights.json` file now includes scoring metadata and reasons per clip.

### Step 12. Clip Preview In UI

Status: done.

The details panel can preview:

- `source.mp4`
- `normalized.mp4`
- highlight clips

Users can switch preview sources before opening files or exporting clips.

### Step 13. Platform Export Checks

Status: done.

Add validation for TikTok, Instagram Reels, and YouTube Shorts:

- duration limits
- resolution
- aspect ratio
- file size
- codec/container

### Step 14. Caption Generator Improvements

Status: done.

Improve captions per platform:

- TikTok tone
- Reels tone
- Shorts title/description
- hashtags
- source attribution
- Thai/English variants

### Step 15. Rights/Safety Checklist

Status: done.

Before export, add a checkbox or manifest field confirming:

```text
I own this content or have permission to reuse it.
```

### Step 16. Export Package

Status: done.

Create a clean export folder per clip:

```text
exports/
  clip_01/
    final.mp4
    caption.txt
    manifest.json
```

### Step 17. Optional Auto-Posting

Status: in progress (advanced prototype).

Current implementation adds a safe dry-run autopost workflow from the UI with per-clip result reporting.
It now also includes mode/language/platform controls and token preflight checks for live-mode attempts.
Live-mode now supports webhook-style adapters via per-platform token+endpoint env configuration.
Live webhook requests now include retry/backoff, idempotency key, and optional HMAC signature (`X-Signature`, `X-Timestamp`).

Still required before live posting:

- platform-native API adapters (replace generic webhook path where needed)
- OAuth/token lifecycle management (refresh/expiry/revocation)
- robust rate limit + policy handling per platform
- replay cache / nonce validation in production receiver
- delivery state reconciliation (queued/processing/published/failed)
- operator controls (pause/retry/cancel) and audit logs

Recommended order:

```text
review/export workflow first
auto-posting later
```

## Recommended Next Action

Harden Step 17 for live posting.

The practical implementation path:

1. Add delivery state machine + retry queue persistence (`queued -> sending -> posted/failed`) in job artifacts. (Done in prototype via `autopost.queue.json`)
2. Add replay protection cache to receiver (nonce or idempotency store with TTL).
3. Implement first platform-native adapter end-to-end (pick one: YouTube Shorts or TikTok) with real response mapping.
4. Add operator actions in UI (`Retry failed`, `Pause`, `Resume`) and append-only audit log per job.
5. Enable live mode by default only after production endpoint verification and policy checks.

## What Is Still Left

The core media pipeline is complete. Remaining work is productionization for auto-posting:

1. Replay protection cache in receiver (`nonce` / idempotency TTL store).
2. First platform-native adapter (instead of generic webhook) end-to-end.
3. OAuth/token lifecycle automation (refresh, expiry handling, revocation path).
4. Operator controls in UI (`Retry failed`, `Pause`, `Resume`) and audit trail.
5. Policy/guardrails for production enablement (rate limits, account safety checks, approval gates).

## Work Deployment Checklist

If you plan to continue this at work, use this rollout checklist:

1. Define architecture boundary:
   - Keep this app as media prep + dispatch orchestrator.
   - Put platform credentials and posting endpoints behind a controlled internal service.
2. Secrets and config:
   - Move env secrets to your org secret manager (not local shell env).
   - Separate `dev/staging/prod` tokens and endpoints.
3. Security:
   - Enforce HMAC verification on receiver.
   - Add replay cache with TTL and strict timestamp skew checks.
4. Reliability:
   - Persist queue and run retries via background worker process (not only request thread).
   - Add dead-letter handling for repeated failures.
5. Compliance and governance:
   - Add approval workflow before live post.
   - Log actor, time, payload hash, result, and remote post id for audits.
6. Observability:
   - Add metrics: queue depth, success rate, retries, p95 post latency.
   - Add alerting for failure bursts and token/auth failures.
7. Release strategy:
   - Run dry-run in staging against mock endpoints.
   - Shadow live mode on one low-risk account first.
   - Gradually increase account scope after stability checks.

## Current Tooling

Installed/available:

- `yt-dlp`
- `ffmpeg`
- `faster-whisper`
- Chrome DevTools MCP
- Context7 MCP
- `ui-ux-pro-max` Codex skill

Useful references:

- `README.md`
- `knowledge/wiki/index.md`
- `knowledge/wiki/experiments/experiment-log.md`
