# Project Overview

## Summary

`socialautopost` is a local web workflow for ingesting media URLs, downloading usable media and metadata, normalizing video, and preparing files for social posting workflows.

The current local app runs at:

```text
http://127.0.0.1:8765
```

## Current Architecture

- `app.py` - Python standard-library local backend.
- `web/` - static frontend.
- `storage/jobs/<job_id>/` - output directory for each ingest job.
- `knowledge/` - durable LLM-maintained project wiki.

## Current Output Per Job

Typical successful job output:

```text
source.mp4
source.info.json
source.jpg or source.png
normalized.mp4
caption.txt
manifest.json
```

The UI shows job progress and can open each job's output folder in the OS file explorer.

When transcription is enabled, jobs also generate:

```text
audio.wav
transcript.txt
captions.srt
```

When highlight generation is enabled, jobs also generate:

```text
clips/clip_01.mp4
clips/clip_01.caption.txt
highlights.json
```

## Current Scope

Supported sources in the local app:

- X/Twitter URLs
- Reddit public video URLs
- YouTube and YouTube Shorts URLs
- local video uploads: `.mp4`, `.mov`, `.mkv`, `.webm`, `.m4v`

Not currently supported:

- general streaming/video sites that `yt-dlp` does not support
- sources with high copyright risk
- automatic posting to social platforms
- advanced highlight detection

## Safety Boundary

Use this workflow only for content the user owns, has permission to repost, or can otherwise lawfully process.
