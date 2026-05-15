# SocialAutoPost Workflow Guide

## Related Documents

- [README](./README.md)
- [Operations Playbook](./OPERATIONS_PLAYBOOK.md)
- [Product Backlog](./PRODUCT_BACKLOG.md)
- [GPU Troubleshooting](./GPU_TROUBLESHOOTING.md)
- [Troubleshooting Index](./TROUBLESHOOTING_INDEX.md)

## Purpose

This guide describes the practical day-to-day workflow for using `SocialAutoPost Local` from source ingestion to ready-to-post output files.

## 1. Prepare The System

Start in the project directory:

```powershell
cd D:\Projects\socialautopost
```

Recommended runtime settings:

```powershell
$env:SOCIALAUTOPOST_WHISPER_DEVICE="cuda"
$env:SOCIALAUTOPOST_WHISPER_COMPUTE_TYPE="int8"
$env:SOCIALAUTOPOST_FFMPEG_VIDEO_ENCODER="h264_nvenc"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL="true"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL_TYPE="cuda"

python app.py
```

Open the app:

```text
http://127.0.0.1:8765
```

Notes:

- `Whisper` uses GPU when CUDA is available.
- `FFmpeg` uses NVIDIA NVENC for normalize and highlight export when enabled.
- If GPU transcription is unavailable, the app falls back automatically.

## 2. Choose The Source

You can ingest content from:

- `TikTok`
- `X/Twitter`
- `Reddit`
- `YouTube`
- local video files

Operational preference:

- prefer local video files or media URLs you control for production posting
- treat TikTok URL ingest as best-effort source acquisition, not a production contract

If a source requires login, age verification, or region access:

- choose browser cookies from `Firefox`, `Chrome`, or `Edge`
- use `auto` if you are unsure

## 3. Configure The Job

For most practical jobs, use:

- `normalize = true`
- `transcribe = true`
- `highlights = true`
- `highlight_length = 30`
- `rights_confirmed = true`

Choose a category:

- `short`
- `funny`
- `news`
- `other`

Recommended default:

- `category = short`
- `highlight_length = 30`

## 4. Submit The Job

After submission, the app processes the content in this order:

1. Read source metadata.
2. Download source media.
3. Save thumbnail when available.
4. Normalize video to `1080x1920 MP4`.
5. Extract audio if transcription is enabled.
6. Generate `transcript.txt` and `captions.srt`.
7. Select highlights using `transcript + scene change` scoring.
8. Generate clip captions.
9. Check compatibility for `TikTok`, `Reels`, and `Shorts`.
10. Build export package.

## 5. Review Job Output

Important output files inside each job folder:

- `source.mp4`
- `source.info.json`
- `source.image`, `source.webp`, or similar thumbnail
- `normalized.mp4`
- `audio.wav`
- `transcript.txt`
- `captions.srt`
- `highlights.json`
- `clips/clip_01.mp4`
- `clips/clip_01.caption.txt`
- `exports/index.json`
- `exports/clip_01/final.mp4`
- `exports/clip_01/caption.txt`
- `exports/clip_01/manifest.json`

## 6. Pick The Correct File For Posting

Do not default to posting the full source file.

Preferred posting file:

- `exports/clip_xx/final.mp4`

Preferred caption source:

- `exports/clip_xx/caption.txt`

Why:

- already normalized
- already clipped to a platform-friendly duration
- already paired with generated caption text

## 7. Check Compatibility Before Posting

Review the compatibility report before posting.

Typical checks:

- aspect ratio is `9:16`
- codec is `H.264`
- container is `MP4`
- duration fits platform limits
- file size is acceptable

Practical rule:

- if the full video is too long, use highlight clips instead

## 8. Review Captions

The app generates:

- a general caption draft
- platform-specific captions
- per-clip captions

Safe caption behavior:

- clip captions can automatically replace explicit transcript snippets with neutral text
- raw transcript is still preserved in transcript artifacts

If you want raw clip transcript text in captions:

```powershell
$env:SOCIALAUTOPOST_SAFE_CAPTIONS="false"
```

## 9. Manual Posting Workflow

This is currently the safest operational path.

Recommended steps:

1. Open job details in the app.
2. Review the `Manual Posting` section.
3. Choose the best clip from the generated highlights.
4. Open the exported `final.mp4`.
5. Open the exported `caption.txt`.
6. Post manually to the destination platform.

Use manual posting when:

- the content is sensitive
- the transcript needs review
- the source is long
- the destination is `TikTok`
- you want final human approval

## 10. Autopost Workflow

Autopost is available after successful processing.

Supported targets:

- `TikTok`
- `Reels`
- `Shorts`

Run modes:

- `dry-run`
- `live`

Live mode requires:

- per-platform token
- endpoint
- optional signing secret

Recommended approach:

1. Process source first.
2. Review clips and captions.
3. Run `dry-run`.
4. Use `live` only after confirming the payload is correct.

Recommended production order:

1. `Shorts` native upload
2. `Reels` native upload
3. `TikTok` live posting only after official API approval and audit readiness

## 11. Operational Rules

Before posting real content:

- confirm rights to reuse the source
- review transcript accuracy
- review clip captions for policy risk
- prefer exported clips over full source
- review platform compatibility status

## 12. Recommended Daily Workflow

For most real jobs:

1. Paste source URL.
2. Enable normalize, transcription, and highlights.
3. Use `30s` highlight length first.
4. Wait for processing to finish.
5. Review `highlights.json`, clip previews, and captions.
6. Pick the best exported clip.
7. Post manually or run autopost after review.

## Capability Backlog By Priority

### 1. Stabilize External Ingest

- handle intermittent `yt-dlp` failures better
- improve retry and backoff logic
- address source-specific network failures such as `WinError 10013`
- improve cookie and extractor diagnostics

### 2. Add Stronger Content Safety Controls

- detect sexual, violent, or otherwise unsafe transcript content
- add content risk scoring per clip
- gate autopost behind safety review
- improve caption sanitization beyond basic word matching

### 3. Improve Highlight Selection Quality

- combine transcript, scene change, OCR, and audio energy
- improve ranking for trailers, commentary, and talking-head content
- reduce low-value fallback windows
- better distinguish hook moments from filler

### 4. Add Review And Approval Workflow

- draft, reviewed, approved, blocked states
- operator approval before live autopost
- audit trail for approvals and retries
- better control for multi-user usage

### 5. Add Built-In Diagnostics UI

- show `Whisper CUDA` status
- show `NVENC` status
- show `yt-dlp` connectivity status
- show cookie availability and source access issues
- surface errors in UI without reading logs manually

### 6. Improve Caption Generation

- better platform-specific caption styles
- better multilingual caption handling
- safer default phrasing for risky content
- multiple tone presets such as neutral, teaser, factual, and dramatic

### 7. Add Visual Understanding

- OCR for on-screen text
- face and subject detection
- activity and object detection
- use visual cues to improve clip ranking

### 8. Add Batch Operations

- ingest many URLs at once
- queue prioritization
- selective retry
- bulk export summary

### 9. Add Brand Or Channel Profiles

- default hashtags
- banned words
- caption style preferences
- preferred platforms
- preferred highlight lengths

### 10. Expand Test Coverage

- ingest smoke tests
- highlight selector regression tests
- safe caption tests
- autopost adapter tests
- GPU and CPU fallback tests

## Current Reality Check

Today the most reliable pattern is:

- ingest source
- normalize
- transcribe
- generate highlights
- review exported clips
- post exported clips manually or through reviewed official-native autopost flow
