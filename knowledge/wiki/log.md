# Log

## [2026-05-13] init | Created SocialAutoPost LLM Wiki

Created the initial LLM-maintained wiki structure for the project based on Karpathy's LLM Wiki pattern. Seeded it with known local results from the current `socialautopost` workflow: X/Twitter ingest, Reddit ingest, yt-dlp/ffmpeg usage, MCP setup, and known errors.

## [2026-05-13] feature | Added local file upload ingest

Added `/api/jobs/upload` and frontend source selection for local video files. Verified with a generated MP4 sample. File jobs now copy the upload into a job directory, probe duration with `ffprobe`, normalize with `ffmpeg`, and produce metadata, caption, and manifest files.

## [2026-05-13] feature | Added job progress and folder opening

Added a `progress` field to jobs, progress bars in the job list and details panel, and `/api/jobs/<job_id>/open-folder` for opening a job output directory in Windows Explorer from the UI.

## [2026-05-13] feature | Added optional transcription and SRT captions

Added a `transcribe` job option. When enabled, jobs extract `audio.wav`, run local `faster-whisper`, and write `transcript.txt` plus `captions.srt`. Verified with a generated local MP4 sample; the sample had no speech, so the expected transcript was `[No speech detected]`.

## [2026-05-13] feature | Added basic highlight clip export

Added a `highlights` job option. When enabled, jobs export `clips/clip_01.mp4` and `highlights.json`. The first implementation chooses the longest transcript segment when speech exists, otherwise falls back to the opening clip. Verified with a generated local MP4 sample.

## [2026-05-13] feature | Added multi-highlight presets and per-clip captions

Added `highlight_length` with 15/30/60 second presets. Highlight export can now create up to three clips and writes a `.caption.txt` file for each clip. Verified with an 18-second generated sample that produced two highlight clips.

## [2026-05-13] platform | Added YouTube Shorts URL support

Extended the URL allowlist to YouTube hosts and verified a YouTube Shorts URL. The test job produced source media, thumbnail, normalized video, and three 15-second highlight clips. Recorded the yt-dlp warning about missing JavaScript runtime for future follow-up.

## [2026-05-13] feature | Improved highlight scoring

Replaced the basic "longest transcript segment" selection with a transcript scoring pass that considers text density, keywords, punctuation, and position. The resulting highlight metadata now includes score breakdowns for each selected clip.

## [2026-05-13] feature | Added clip preview in the details panel

Added a browser preview player to the job details panel so users can switch between `source.mp4`, `normalized.mp4`, and generated highlight clips before opening the folder or exporting files.

## [2026-05-14] feature | Added platform export checks and platform caption variants

Implemented platform compatibility checks for TikTok, Instagram Reels, and YouTube Shorts across source, normalized, and highlight clip files. Validation now covers duration, resolution, aspect ratio, file size, codec, and container, and is stored in both job state and `manifest.json`.

Improved caption generation by adding platform-specific caption variants with Thai/English outputs, hashtags, and source attribution. Jobs now write `captions.platform.json` in addition to `caption.txt`.

## [2026-05-14] safety | Added rights confirmation to job intake and manifests

Added a required rights confirmation checkbox in the job form for URL and local-file sources. Backend now validates `rights_confirmed` before accepting a job and persists the flag into each job's `manifest.json`.

## [2026-05-14] feature | Added per-clip export packaging

Implemented export packaging under `exports/clip_XX/` for highlight jobs. Each clip export now includes `final.mp4`, `caption.txt`, and `manifest.json`, plus an `exports/index.json` summary. Export metadata is also linked from the main job manifest as `exports_index`.

## [2026-05-14] feature | Added autopost dry-run flow

Added `POST /api/jobs/<job_id>/autopost` with asynchronous job-level autopost execution. The current implementation is dry-run oriented: it reads export packages, builds per-platform posting payload previews, and writes `autopost.report.json` plus job status (`autopost_status`, `autopost_report`) for UI tracking.

## [2026-05-14] feature | Added autopost preflight controls and live scaffolding

Extended the UI autopost panel with mode/language/platform controls and wired request payloads to backend. Added token preflight checks (`SOCIALAUTOPOST_TIKTOK_TOKEN`, `SOCIALAUTOPOST_REELS_TOKEN`, `SOCIALAUTOPOST_SHORTS_TOKEN`) and a live adapter scaffold so non-dry runs fail clearly with actionable status instead of silent placeholders.

## [2026-05-14] feature | Added live webhook adapter path for autopost

Implemented a concrete live adapter path that can POST to per-platform endpoints using bearer tokens from env. Added endpoint preflight checks (`SOCIALAUTOPOST_*_ENDPOINT`) and report fields for token/endpoint readiness, with explicit posted/failed/blocked statuses.

## [2026-05-14] reliability | Added retry/backoff and idempotency for live autopost

Hardened live autopost delivery with configurable timeout/retry envs (`SOCIALAUTOPOST_AUTOPOST_TIMEOUT_SEC`, `SOCIALAUTOPOST_AUTOPOST_RETRIES`), retry-on-transient HTTP/network errors, and `X-Idempotency-Key` headers to reduce duplicate post risk on retried requests.

## [2026-05-14] security | Added HMAC signing and response normalization for live webhook posting

Added optional per-platform HMAC signing secrets (`SOCIALAUTOPOST_*_SIGNING_SECRET`) to send `X-Signature` with `X-Timestamp` for webhook authenticity checks. Also added response-field normalization so autopost reports can consistently capture `remote_id`, `remote_status`, and `remote_url` when returned by downstream APIs.

## [2026-05-14] security | Added multi-tenant secret resolution in webhook receiver example

Extended `examples/webhook_receiver_example.py` to resolve signing secrets per platform (`tiktok`, `reels`, `shorts`) with fallback to a default shared secret. Platform can be resolved from payload `platform` and optional `X-Platform` header.

## [2026-05-14] reliability | Added autopost delivery state machine and persistent queue artifact

Autopost now tracks per-delivery state transitions (`queued -> sending -> posted/failed/blocked/simulated`) and writes queue progress to `autopost.queue.json` during execution. Job files now include both report and queue artifacts for operational traceability.

## [2026-05-14] security | Added replay protection cache to webhook receiver example

Extended `examples/webhook_receiver_example.py` with an in-memory TTL replay cache. The receiver now prefers `X-Idempotency-Key`, then `post_id`, then request signature to reject duplicate deliveries within the configured replay window.

## [2026-05-14] feature | Added YouTube Shorts native upload adapter prototype

Added a native live-post path for `shorts` using the YouTube Data API resumable upload flow. The current prototype starts an upload session, uploads the export MP4 directly, and maps the API response into normalized autopost result fields.

## [2026-05-14] feature | Added autopost operator controls and audit log prototype

Added pause/resume/retry control endpoints and UI buttons for autopost operations. The prototype now writes append-only audit events to `autopost.audit.jsonl` and uses `autopost.control.json` to coordinate pause/resume behavior with the running delivery loop.

## [2026-05-14] auth | Added refresh-token lifecycle support for YouTube Shorts native posting

Extended the Shorts native adapter to reuse valid access tokens, refresh expired tokens through Google's OAuth token endpoint, and persist a local token cache in `storage/oauth/shorts.token.json`. This reduces manual token rotation during repeated staging uploads.

## [2026-05-14] audit | Added operator attribution for autopost actions

Added operator attribution to autopost start/pause/resume/retry actions through `X-Operator` and request payload metadata. The UI now stores a local operator value and the audit log records that operator on delivery and control events.

## [2026-05-14] policy | Added live approval and delivery-count guardrails

Added a live-mode approval phrase check and a max-deliveries-per-job guardrail. Live autopost now requires a matching approval value and can be capped with `SOCIALAUTOPOST_LIVE_MAX_DELIVERIES` before any send begins.
