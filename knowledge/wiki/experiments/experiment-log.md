# Experiment Log

## X / Twitter Video

URL:

```text
https://x.com/Arywn_Ltp/status/2054521748498829736?s=20
```

Result:

- Chrome cookies failed with `Could not copy Chrome cookie database`.
- Firefox cookies succeeded.
- App Auto mode succeeded.
- Output included `source.mp4`, `normalized.mp4`, metadata, thumbnail, caption, manifest.

## Reddit Video

URL:

```text
https://www.reddit.com/r/ArsenalFC/comments/1tbr24m/passion_for_the_badge/
```

Result:

- `yt-dlp` metadata succeeded.
- Video was 24 seconds, 720x1280.
- Initial job failed due to thumbnail JPG conversion.
- Removing forced thumbnail conversion fixed it.
- Successful output at `storage/jobs/4feda2941643/`.

## upde.cc

URL:

```text
https://upde.cc/watch/31171
```

Result:

- `yt-dlp` returned `Unsupported URL`.
- Page contained embedded `ok.ru/videoembed/...`.
- Not added due to unsupported extractor and copyright risk.

## Local File Upload

File:

```text
storage/test/upload-sample.mp4
```

Result:

- Uploaded through `/api/jobs/upload` using multipart form data.
- Job completed successfully.
- Successful output at `storage/jobs/93c996c827d0/`.
- Output included `source.mp4`, `source.info.json`, `normalized.mp4`, `caption.txt`, and `manifest.json`.

## Local Transcription

File:

```text
storage/test/upload-sample.mp4
```

Result:

- Uploaded through `/api/jobs/upload` with `transcribe=true`.
- Job completed successfully at `storage/jobs/92b1b6125127/`.
- Output included `audio.wav`, `transcript.txt`, and `captions.srt`.
- The generated test file contained a synthetic tone and no speech, so transcript output was `[No speech detected]`.

## Local Highlight Export

File:

```text
storage/test/upload-sample.mp4
```

Result:

- Uploaded through `/api/jobs/upload` with `transcribe=true` and `highlights=true`.
- Job completed successfully at `storage/jobs/fdd136cb964b/`.
- Output included `clips/clip_01.mp4` and `highlights.json`.
- Since the sample had no speech, highlight selection used the fallback opening clip.

## Multi-Highlight Export

File:

```text
storage/test/upload-sample-18s.mp4
```

Result:

- Uploaded through `/api/jobs/upload` with `highlights=true` and `highlight_length=15`.
- Job completed successfully at `storage/jobs/b1a2ed492905/`.
- Output included `clips/clip_01.mp4`, `clips/clip_02.mp4`, and matching `.caption.txt` files.
- `highlights.json` contained start/end/duration/reason/caption metadata per clip.

## YouTube Shorts

URL:

```text
https://youtube.com/shorts/g7_BueEFjtA?si=hkpYnVlaLEBdutxq
```

Result:

- `yt-dlp --dump-json --no-playlist` succeeded.
- App allowlist was extended to YouTube hosts.
- Job completed successfully at `storage/jobs/1695d58d34c9/`.
- Output included `source.mp4`, `source.webp`, `normalized.mp4`, and three 15-second highlight clips.
- `yt-dlp` emitted a JavaScript runtime warning for YouTube extraction.
