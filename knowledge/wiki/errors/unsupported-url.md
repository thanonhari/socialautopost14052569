# Unsupported URL

## Symptom

`yt-dlp` reports:

```text
Unsupported URL
```

## Current Policy

Do not add a source to the local app simply because its page can be inspected. Add it only when:

- `yt-dlp` can download it reliably, or a lawful direct media URL is available.
- the source is appropriate for social repost workflows.
- the user owns or has permission to process the content.

## Example

`https://upde.cc/watch/31171` returned unsupported from `yt-dlp` and appeared to be a full series episode page with embedded third-party video. It was not added.

## Related

- [Unsupported Or Risky Sources](../platforms/unsupported-risky-sources.md)
