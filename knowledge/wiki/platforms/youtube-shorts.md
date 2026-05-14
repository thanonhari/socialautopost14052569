# YouTube Shorts

## Summary

YouTube Shorts URLs can work with the local `yt-dlp` workflow.

## Working Example

Tested URL:

```text
https://youtube.com/shorts/g7_BueEFjtA?si=hkpYnVlaLEBdutxq
```

Observed:

- title: `Why PSG Will COOK Arsenal In The UCL Final`
- duration: about 53 seconds
- vertical video available up to 2160x3840
- local job succeeded with normalized output and 3 highlight clips

Successful local job:

```text
storage/jobs/1695d58d34c9/
```

Output included:

```text
source.mp4
source.info.json
source.webp
normalized.mp4
clips/clip_01.mp4
clips/clip_02.mp4
clips/clip_03.mp4
highlights.json
caption.txt
manifest.json
```

## Note

`yt-dlp` emitted a warning that no supported JavaScript runtime was found. YouTube extraction still worked, but future yt-dlp versions may need a JS runtime such as Deno or Node configured for full YouTube extraction.
