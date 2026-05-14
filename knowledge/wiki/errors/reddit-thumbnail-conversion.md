# Reddit Thumbnail Conversion Error

## Symptom

Reddit video download succeeded, but the job failed with:

```text
ERROR: Preprocessing: Conversion failed!
```

## Cause

The app previously passed:

```text
--convert-thumbnails jpg
```

This caused a thumbnail conversion failure for a Reddit thumbnail even though media download and merge succeeded.

## Fix

Remove forced thumbnail conversion. Keep the thumbnail in the format returned by the source, such as `source.png`.

## Verified

After removing the conversion flag, the Reddit job completed successfully with:

```text
source.png
source.mp4
normalized.mp4
```
