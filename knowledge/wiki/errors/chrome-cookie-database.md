# Chrome Cookie Database Error

## Symptom

`yt-dlp` fails with:

```text
ERROR: Could not copy Chrome cookie database.
```

## Context

Observed with:

```powershell
yt-dlp --cookies-from-browser chrome --dump-json --no-playlist "https://x.com/Arywn_Ltp/status/2054521748498829736?s=20"
```

## Likely Cause

On Windows, Chrome can lock or protect the cookie database. `yt-dlp` cannot copy it.

## Working Fix

Use Firefox cookies or the app's Auto mode:

```powershell
yt-dlp --cookies-from-browser firefox --dump-json --no-playlist "URL"
```

The app's Auto mode tries:

```text
firefox -> chrome -> edge -> none
```

## Related

- [X / Twitter](../platforms/x-twitter.md)
- [yt-dlp Chrome cookie issue](../../raw/links.md)
