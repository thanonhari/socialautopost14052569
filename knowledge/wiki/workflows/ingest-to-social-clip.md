# Ingest To Social Clip Workflow

## Summary

The core workflow is:

```text
Source URL or local file
-> yt-dlp metadata/download or local metadata probe
-> ffmpeg normalization
-> optional audio extraction and transcription
-> optional highlight clip export
-> caption draft
-> manifest for downstream posting pipeline
```

## Steps

1. User submits a URL or uploads a local video file.
2. For URL jobs, backend validates host allowlist.
3. For URL jobs, backend reads metadata with `yt-dlp --dump-json --no-playlist`.
4. For URL jobs, backend downloads best media with `yt-dlp`.
5. For file jobs, backend saves the upload and probes duration with `ffprobe`.
6. Backend writes `source.info.json`.
7. Backend writes thumbnail if available.
8. Backend normalizes video to vertical `1080x1920` MP4 when enabled.
9. Backend extracts `audio.wav` and creates `transcript.txt` plus `captions.srt` when transcription is enabled.
10. Backend exports one to three highlight clips, per-clip captions, and `highlights.json` when highlight generation is enabled.
11. Backend writes `caption.txt`.
12. Backend writes `manifest.json`.

The backend updates `progress` throughout the pipeline so the UI can show a progress bar. The details panel can open the job output folder through `/api/jobs/<job_id>/open-folder`.

## Normalize Target

Current target:

```text
container: mp4
video: h264
audio: aac
size: 1080x1920
```

## Next Steps

- Improve semantic highlight selection from transcript.
- Add platform-specific export checks.
