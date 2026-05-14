# ffmpeg

## Summary

`ffmpeg` is used to normalize downloaded media into a vertical MP4 suitable for short-form social platforms.

## Current Normalize Command Shape

The app scales input to fit inside 1080x1920, pads if needed, converts video to H.264, audio to AAC, and writes a fast-start MP4.

Current target:

```text
1080x1920
h264
aac
mp4
```

## Known Tradeoff

Padding preserves the original frame without cropping. This is safer for general ingest, but not always the most engaging short-form layout. Future versions could add crop/fill modes.
