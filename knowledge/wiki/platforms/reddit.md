# Reddit

## Summary

Reddit public video URLs can work with `yt-dlp` without cookies.

## Working Example

Tested URL:

```text
https://www.reddit.com/r/ArsenalFC/comments/1tbr24m/passion_for_the_badge/
```

Observed:

- title: `Passion for the badge!`
- duration: 24 seconds
- video: 720x1280
- output succeeded after removing forced thumbnail JPG conversion

Successful local job:

```text
storage/jobs/4feda2941643/
```

Output files:

```text
source.mp4
normalized.mp4
source.info.json
source.png
caption.txt
manifest.json
```

## Important Fix

Do not force `--convert-thumbnails jpg` for Reddit. It caused a preprocessing failure even though video download succeeded.

## Related Pages

- [Reddit Thumbnail Conversion Error](../errors/reddit-thumbnail-conversion.md)
- [Experiment Log](../experiments/experiment-log.md)
