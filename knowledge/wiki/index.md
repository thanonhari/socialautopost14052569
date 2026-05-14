# SocialAutoPost Wiki Index

## Overview

- [Project Overview](overview.md) - Current project purpose, architecture, and boundaries.

## Workflows

- [Ingest To Social Clip Workflow](workflows/ingest-to-social-clip.md) - URL to media, metadata, normalized video, caption draft, and manifest.
- [LLM Wiki Workflow](workflows/llm-wiki.md) - How this knowledge wiki should be maintained.

## Platforms

- [X / Twitter](platforms/x-twitter.md) - X URL ingest behavior, cookies, and working approach.
- [Reddit](platforms/reddit.md) - Reddit public video ingest behavior and fixes.
- [YouTube Shorts](platforms/youtube-shorts.md) - YouTube Shorts ingest behavior and notes.
- [Unsupported Or Risky Sources](platforms/unsupported-risky-sources.md) - Sources not suitable for the current workflow.

## Tools

- [yt-dlp](tools/yt-dlp.md) - Local usage notes for metadata and downloads.
- [ffmpeg](tools/ffmpeg.md) - Normalize/transcode notes.
- [MCP Servers](tools/mcp-servers.md) - Installed MCP servers and discovery reference.
- [Codex Skills](tools/codex-skills.md) - Installed skills relevant to this project.

## Errors

- [Chrome Cookie Database Error](errors/chrome-cookie-database.md) - Why Chrome cookies fail and the Firefox/Auto fallback.
- [Reddit Thumbnail Conversion Error](errors/reddit-thumbnail-conversion.md) - Why `--convert-thumbnails jpg` was removed.
- [Unsupported URL](errors/unsupported-url.md) - How to handle sites that yt-dlp does not support.

## Experiments

- [Experiment Log](experiments/experiment-log.md) - Concrete URLs tested and outcomes.
