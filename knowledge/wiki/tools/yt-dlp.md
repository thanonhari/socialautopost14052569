# yt-dlp

## Summary

`yt-dlp` is the media ingest tool used by the local web app.

## Local Uses

Metadata:

```powershell
yt-dlp --dump-json --no-playlist "URL"
```

Metadata with Firefox cookies:

```powershell
yt-dlp --cookies-from-browser firefox --dump-json --no-playlist "URL"
```

Download best video/audio:

```powershell
yt-dlp --no-playlist -f "bv*+ba/b" --merge-output-format mp4 --write-thumbnail -o "source.%(ext)s" "URL"
```

## Current App Behavior

- Supports cookie fallback for X/Twitter: Auto tries Firefox, Chrome, Edge, none.
- Does not force thumbnail conversion.
- Writes metadata separately as `source.info.json`.

## Related Pages

- [Chrome Cookie Database Error](../errors/chrome-cookie-database.md)
- [Unsupported URL](../errors/unsupported-url.md)
