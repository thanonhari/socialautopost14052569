# Unsupported Or Risky Sources

## Summary

Some URLs are technically inspectable but should not be added to the ingest workflow because they are unsupported by `yt-dlp`, require site-specific extraction, or have high copyright risk.

## upde.cc

Tested URL:

```text
https://upde.cc/watch/31171
```

Observed:

- `yt-dlp` reports unsupported URL.
- HTML contains an embed to `ok.ru/videoembed/...`.
- Content appears to be a full episode of a TV/series source.

Decision:

- Do not add `upde.cc` support to the local app.
- Avoid building extraction workflows for full-series streaming pages.

## Preferred Sources

- X/Twitter clips
- Reddit public videos
- owned video files
- direct media URLs the user has rights to use
- platform URLs where repost rights are clear
