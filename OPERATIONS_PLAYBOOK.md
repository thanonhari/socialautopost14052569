# SocialAutoPost Operations Playbook

## Related Documents

- [README](./README.md)
- [Workflow Guide](./WORKFLOW_GUIDE.md)
- [Product Backlog](./PRODUCT_BACKLOG.md)
- [GPU Troubleshooting](./GPU_TROUBLESHOOTING.md)
- [Troubleshooting Index](./TROUBLESHOOTING_INDEX.md)

## Purpose

This playbook is for operators who use `SocialAutoPost Local` in day-to-day content preparation and posting workflows.

## Start The App

Open PowerShell in the project folder:

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

Open:

```text
http://127.0.0.1:8765
```

## Supported Sources

Use one of these source types:

- `TikTok`
- `X/Twitter`
- `Reddit`
- `YouTube`
- local video file

Operational preference:

- prefer local files or controlled media URLs for production posting
- use TikTok URL ingest as a best-effort acquisition path only

If the source is restricted:

- use browser cookies from `Firefox`, `Chrome`, or `Edge`
- choose `auto` if unsure

## Recommended Job Settings

For most real jobs:

- `category = short`
- `normalize = true`
- `transcribe = true`
- `highlights = true`
- `highlight_length = 30`
- `rights_confirmed = true`

## Standard Processing Flow

After you submit a job, the system does this:

1. Read metadata.
2. Download the source video.
3. Save thumbnail if available.
4. Normalize to `1080x1920 MP4`.
5. Extract audio.
6. Generate transcript and subtitles.
7. Build highlights from transcript and scene changes.
8. Generate clip captions.
9. Run platform compatibility checks.
10. Build export package.

## Files To Check

The most important output files are:

- `source.mp4`
- `source.info.json`
- `normalized.mp4`
- `transcript.txt`
- `captions.srt`
- `highlights.json`
- `clips/clip_01.mp4`
- `clips/clip_01.caption.txt`
- `exports/index.json`
- `exports/clip_01/final.mp4`
- `exports/clip_01/caption.txt`

## Which File To Post

Preferred posting file:

- `exports/clip_xx/final.mp4`

Preferred caption file:

- `exports/clip_xx/caption.txt`

Avoid posting the full `source.mp4` unless there is a specific reason.

## Caption Review Rule

Always review captions before posting.

Important behavior:

- clip captions may be softened automatically when transcript text is explicit
- raw transcript is still preserved in the job artifacts

If you want raw transcript snippets in clip captions:

```powershell
$env:SOCIALAUTOPOST_SAFE_CAPTIONS="false"
```

## Manual Posting Workflow

Use this by default:

1. Open the job details page.
2. Review the generated clips.
3. Open `exports/index.json` if you need a quick summary.
4. Choose the best clip.
5. Use the paired exported caption.
6. Post manually to the destination platform.

Use manual posting when:

- the clip is sensitive
- the transcript needs review
- the source is long
- the source is from a third party
- the destination is `TikTok`

## Autopost Workflow

Autopost is available after a successful job.

Targets:

- `TikTok`
- `Reels`
- `Shorts`

Modes:

- `dry-run`
- `live`

Live mode requires:

- token
- endpoint
- optional signing secret

Recommended sequence:

1. Process source.
2. Review clips and captions.
3. Run `dry-run`.
4. Use `live` only after approval.

Production order:

1. `YouTube Shorts` native
2. `Instagram Reels` native
3. `TikTok` manual-first until official posting approval is complete

## Compatibility Rules

Check these before posting:

- aspect ratio is suitable
- codec is `H.264`
- container is `MP4`
- duration fits the platform
- caption is safe to publish

Practical rule:

- if the source is too long, use generated highlight clips instead

## Failure Handling

If a job fails:

1. Check the error message in the UI.
2. Check job logs.
3. Retry with browser cookies if the source may require login.
4. Retry with a different source type if the platform is unstable.
5. If the full URL ingest fails but direct download works, keep the source file and retry via local file upload.

## Daily Operator Checklist

Before posting:

- rights confirmed
- clip selected from exports, not raw source
- transcript reviewed
- caption reviewed
- compatibility reviewed
- explicit content checked
- final human approval completed

## Current Best Practice

The safest operational pattern today is:

1. ingest source
2. normalize
3. transcribe
4. generate highlights
5. review exported clips
6. post approved exports manually or via reviewed autopost
