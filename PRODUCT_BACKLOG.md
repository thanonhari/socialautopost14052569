# SocialAutoPost Product Backlog

## Related Documents

- [README](./README.md)
- [Workflow Guide](./WORKFLOW_GUIDE.md)
- [Operations Playbook](./OPERATIONS_PLAYBOOK.md)
- [GPU Troubleshooting](./GPU_TROUBLESHOOTING.md)
- [Troubleshooting Index](./TROUBLESHOOTING_INDEX.md)

## Priority 1: Stabilize External Ingest

- fix intermittent `yt-dlp` failures across TikTok and YouTube
- address `WinError 10013` and similar source access failures
- improve retry and backoff strategy
- improve cookie-mode fallback diagnostics
- surface extractor-specific errors in the UI
- keep unstable source ingest from becoming a hidden production dependency

## Priority 1A: Official Posting Adapters

- finish `YouTube Shorts` native staging verification with real OAuth credentials
- build `Instagram Reels` native publish flow using exported media files
- keep `TikTok` manual-first until official posting API review and audit are complete
- avoid investing in scraper-based or unofficial posting paths for production

## Priority 2: Stronger Content Safety

- detect sexual, violent, and otherwise sensitive transcript content
- add clip-level risk scoring
- block or warn before autoposting risky clips
- improve caption sanitization beyond simple keyword replacement
- support policy-aware caption rewriting

## Priority 3: Better Highlight Selection

- combine transcript, scene change, OCR, and audio energy
- improve scoring for trailers and montage-heavy videos
- reduce weak fallback windows
- better rank opening hooks versus filler
- support different ranking strategies by content type

## Priority 4: Review And Approval System

- add statuses such as `draft`, `reviewed`, `approved`, and `blocked`
- require approval before live autopost
- add operator identity and audit trail
- preserve retry history and change history

## Priority 5: Diagnostics And Observability

- show `Whisper CUDA` status in the UI
- show `NVENC` status in the UI
- add `yt-dlp` connectivity checks
- show cookie availability and source access readiness
- provide structured error cards instead of only raw logs

## Priority 6: Smarter Caption Generation

- improve platform-specific caption templates
- improve multilingual caption output
- support multiple caption tones
- add factual mode for news and promo mode for entertainment
- add safer default phrasing for sensitive transcripts

## Priority 7: Visual Understanding

- OCR on video frames
- face and person detection
- object and action detection
- scene-type classification
- use visual features in highlight selection

## Priority 8: Batch Workflows

- submit many URLs in one batch
- prioritize queue execution
- retry only failed items
- generate batch export summaries
- track per-batch success rates

## Priority 9: Brand Or Channel Profiles

- channel-specific hashtags
- banned phrases
- preferred caption tone
- default highlight length
- per-channel platform targeting

## Priority 10: Automated Testing

- ingest smoke tests
- highlight selector regression tests
- safe-caption tests
- autopost adapter tests
- GPU and CPU fallback tests
- source-platform fixture coverage

## Priority 11: Local File Recovery Workflow

- convert failed URL jobs into local-file jobs quickly
- one-click reuse of a previously downloaded source
- preserve metadata when switching from URL to file mode

## Priority 12: Operational Reporting

- recent job success and failure dashboard
- platform compatibility summary by job
- autopost delivery summary
- export usage summary
- operator activity summary
