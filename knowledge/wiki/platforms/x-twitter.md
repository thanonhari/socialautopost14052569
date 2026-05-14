# X / Twitter

## Summary

X/Twitter URLs work with `yt-dlp`, but cookies are often required. Chrome cookies can fail on Windows; Firefox cookies worked in local testing.

## Working Approach

Use the app's `Cookies = Auto` mode or choose Firefox.

Observed working command:

```powershell
yt-dlp --cookies-from-browser firefox --dump-json --no-playlist "https://x.com/Arywn_Ltp/status/2054521748498829736?s=20"
```

## Local Result

Tested URL:

```text
https://x.com/Arywn_Ltp/status/2054521748498829736?s=20
```

Observed:

- metadata extraction succeeded with Firefox cookies
- video available at 720x1280
- duration about 1:03
- local web job succeeded using `browser = auto`

## Related Pages

- [Chrome Cookie Database Error](../errors/chrome-cookie-database.md)
- [yt-dlp](../tools/yt-dlp.md)
