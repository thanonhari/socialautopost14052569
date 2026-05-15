# Troubleshooting Index

## Purpose

This document is the central index for common operational problems in `SocialAutoPost Local`.

Use it as the first stop when:

- a source URL fails to ingest
- GPU acceleration is not being used
- transcription is too slow
- highlights are weak or missing
- autopost does not behave as expected

## Documents

- [README](./README.md)
- [Workflow Guide](./WORKFLOW_GUIDE.md)
- [Operations Playbook](./OPERATIONS_PLAYBOOK.md)
- [Product Backlog](./PRODUCT_BACKLOG.md)
- [GPU Troubleshooting](./GPU_TROUBLESHOOTING.md)

## 1. Source Ingest Problems

### TikTok

Common issues:

- intermittent `yt-dlp` failures
- network errors such as `WinError 10013`
- extractor instability
- login or region restrictions

What to try:

1. retry the job
2. try browser cookies with `Firefox`, `Chrome`, or `Edge`
3. test the URL directly with `yt-dlp`
4. if direct download works but app ingest fails, download first and retry as local file

### YouTube

Common issues:

- warning about missing JavaScript runtime
- restricted or age-gated content
- format differences between test runs

What to try:

1. test the URL directly with `yt-dlp`
2. retry with cookies if the content is restricted
3. use generated highlight clips instead of the full source when the video is long

### X/Twitter

Common issues:

- cookie extraction failure from browser
- expired or inaccessible media
- rate limiting

What to try:

1. retry with another browser cookie source
2. test the URL directly with `yt-dlp`
3. confirm the tweet still serves media

### Reddit

Common issues:

- public media not resolving cleanly
- source post exists but video CDN response changes

What to try:

1. retry the URL
2. confirm the media is public
3. test direct `yt-dlp` access outside the app flow

## 2. GPU Problems

If GPU acceleration is the issue, use:

- [GPU Troubleshooting](./GPU_TROUBLESHOOTING.md)

Typical signs:

- `python.exe` does not appear in `nvidia-smi` during transcription
- `ffmpeg.exe` does not appear in `nvidia-smi` during encoding
- transcription falls back to CPU
- `cublas64_12.dll` errors appear

## 3. Transcription Problems

Common issues:

- transcription is too slow
- transcript language is poor
- transcript is low quality for non-English content
- no subtitles generated

What to check:

1. whether GPU transcription is active
2. whether audio extraction succeeded
3. whether the source has clean speech
4. whether the chosen Whisper model is too small

Practical fixes:

- use GPU with `SOCIALAUTOPOST_WHISPER_DEVICE="cuda"`
- use `SOCIALAUTOPOST_WHISPER_COMPUTE_TYPE="int8"`
- increase model size if accuracy matters more than speed

## 4. Highlight Problems

Common issues:

- highlights are weak
- transcript does not influence ranking enough
- scene-only windows dominate
- clips are too long or too short

What to check:

1. whether `transcribe=true`
2. whether `captions.srt` was created
3. whether `highlights.json` shows `transcript + scene scoring` or only `scene peak scoring`
4. whether the content is trailer-like or montage-heavy

Practical fixes:

- enable transcription
- use `30s` highlights first
- review `highlights.json`
- switch to manual selection when the auto ranking is weak

## 5. Caption Problems

Common issues:

- captions are too generic
- captions are too explicit
- captions do not fit the destination platform

What to check:

1. `caption.txt`
2. `captions.platform.json`
3. `clips/clip_xx.caption.txt`

Practical fixes:

- leave `SOCIALAUTOPOST_SAFE_CAPTIONS` enabled for sensitive content
- disable it only if you want raw transcript snippets
- manually review export captions before posting

## 6. Compatibility Problems

Common issues:

- full video is too long
- source codec is not `H.264`
- aspect ratio is not `9:16`

What to do:

1. review the compatibility report
2. prefer `normalized.mp4` over raw source
3. prefer `exports/clip_xx/final.mp4` over the full normalized video

## 7. Autopost Problems

Common issues:

- missing token
- missing endpoint
- webhook failure
- delivery state stuck or failed

What to check:

1. platform token env vars
2. endpoint env vars
3. signing secret if used
4. autopost report and queue artifacts

Recommended practice:

- use `dry-run` first
- move to `live` only after manual review
- prefer `Shorts` native first, `Reels` native second, and keep `TikTok` manual-first until official API readiness is complete

## 8. Recovery Path

If URL ingest is unstable but you still need to finish the job:

1. download the source directly with `yt-dlp`
2. upload the file through local file mode
3. run normalize, transcription, and highlights from the local file path

This is the safest fallback when third-party source access is inconsistent.

## 9. Production Path Drift

Problem:

- operators start relying on unstable URL ingest as if it were a guaranteed production source
- teams treat generic webhook posting as equivalent to a native platform adapter

Correction:

1. move unstable source acquisition to local file mode as soon as a source is captured
2. keep production posting centered on owned media files
3. prioritize `YouTube Shorts` native, then `Instagram Reels` native
4. keep `TikTok` on manual posting until official audit and posting requirements are satisfied
