# GPU Troubleshooting

## Purpose

This guide explains how to diagnose and fix cases where GPU acceleration is not being used correctly in `SocialAutoPost Local`.

The app can use GPU for two main workloads:

- `faster-whisper` transcription
- `FFmpeg NVENC` video encoding

If GPU is unavailable, the app may fall back to CPU, which makes processing slower.

## Common Symptoms

Typical signs that GPU support is not working:

- transcription is much slower than expected
- video normalization or highlight export is slow
- `nvidia-smi` does not show `python.exe` during transcription
- `nvidia-smi` does not show `ffmpeg.exe` during encoding
- jobs silently fall back to CPU
- runtime errors mention missing CUDA libraries

Common error examples:

- `Library cublas64_12.dll is not found or cannot be loaded`
- `Requested float16 compute type ... do not support efficient float16 computation`
- `ffmpeg` runs without `h264_nvenc`

## Step 1: Confirm The Machine Sees The GPU

Run:

```powershell
nvidia-smi
```

Expected result:

- an NVIDIA GPU appears in the output

Example from this machine:

- `NVIDIA GeForce GTX 1050 Ti`

## Step 2: Confirm FFmpeg Supports NVENC

Run:

```powershell
ffmpeg -hide_banner -encoders | Select-String -Pattern "nvenc"
```

Expected result:

- `h264_nvenc` appears in the encoder list

If it does not appear:

- the installed FFmpeg build does not support NVIDIA NVENC
- install a build that includes NVENC support

## Step 3: Use Recommended GPU Runtime Settings

Set these values before starting the app:

```powershell
$env:SOCIALAUTOPOST_WHISPER_DEVICE="cuda"
$env:SOCIALAUTOPOST_WHISPER_COMPUTE_TYPE="int8"
$env:SOCIALAUTOPOST_FFMPEG_VIDEO_ENCODER="h264_nvenc"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL="true"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL_TYPE="cuda"

python app.py
```

Notes:

- `int8` is the recommended `Whisper` compute type for older GPUs such as `GTX 1050 Ti`
- `float16` may fail on older cards or incomplete CUDA setups

## Step 4: Check GPU Usage During Real Work

### During transcription

Run a job with:

- `transcribe = true`

Then check:

```powershell
nvidia-smi
```

Expected result:

- `python.exe` appears in the GPU process list

### During video encoding

Run a job with:

- `normalize = true`
- or `highlights = true`

Then check:

```powershell
nvidia-smi
```

Expected result:

- `ffmpeg.exe` appears in the GPU process list

## Step 5: Fix Missing CUDA DLL Errors

### Symptom

You see:

- `Library cublas64_12.dll is not found or cannot be loaded`

### Cause

The CUDA runtime is incomplete inside the Python environment, or DLL search paths are not configured correctly.

### Fix

Install the required runtime package in the app's virtual environment:

```powershell
& "C:\Users\thanon.har\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -m pip install nvidia-cublas-cu12
```

This installs:

- `cublas64_12.dll`
- `cublasLt64_12.dll`
- related CUDA runtime files

The app also needs DLL search paths for:

- `ctranslate2`
- `nvidia\cublas\bin`
- `nvidia\cuda_nvrtc\bin`

In this project, that is handled in code so the runtime can preload the DLLs on Windows.

## Step 6: Fix Unsupported Whisper Compute Type

### Symptom

You see an error about `float16` or `int8_float16` not being supported efficiently.

### Cause

The GPU or backend does not support that compute mode well enough.

### Fix

Use:

```powershell
$env:SOCIALAUTOPOST_WHISPER_COMPUTE_TYPE="int8"
```

Recommended rule:

- use `int8` first on older consumer GPUs

## Step 7: Fix FFmpeg Not Using GPU

### Symptom

Encoding works, but `ffmpeg.exe` does not appear in `nvidia-smi`.

### Checks

1. confirm `h264_nvenc` exists
2. confirm the app is running with NVENC settings
3. confirm the job is actually doing `normalize` or `highlight` export

### Fix

Use:

```powershell
$env:SOCIALAUTOPOST_FFMPEG_VIDEO_ENCODER="h264_nvenc"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL="true"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL_TYPE="cuda"
```

## Step 8: Understand CPU Fallback

The app may still complete jobs even if GPU setup is incomplete.

Possible fallback behavior:

- `Whisper` tries `cuda`
- then tries a safer GPU mode
- then falls back to `cpu/int8`

This is useful for reliability, but slower.

If jobs succeed but performance is poor:

- inspect logs
- confirm whether GPU was actually used

## Step 9: Quick Diagnostic Sequence

Run these in order:

```powershell
nvidia-smi
ffmpeg -hide_banner -encoders | Select-String -Pattern "nvenc"
```

Then start the app with:

```powershell
$env:SOCIALAUTOPOST_WHISPER_DEVICE="cuda"
$env:SOCIALAUTOPOST_WHISPER_COMPUTE_TYPE="int8"
$env:SOCIALAUTOPOST_FFMPEG_VIDEO_ENCODER="h264_nvenc"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL="true"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL_TYPE="cuda"

python app.py
```

Then verify runtime:

- `python.exe` appears in `nvidia-smi` during transcription
- `ffmpeg.exe` appears in `nvidia-smi` during encoding

## Recommended Configuration For This Machine

For the current machine with `NVIDIA GeForce GTX 1050 Ti`, the recommended settings are:

```powershell
$env:SOCIALAUTOPOST_WHISPER_DEVICE="cuda"
$env:SOCIALAUTOPOST_WHISPER_COMPUTE_TYPE="int8"
$env:SOCIALAUTOPOST_FFMPEG_VIDEO_ENCODER="h264_nvenc"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL="true"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL_TYPE="cuda"
```

## Related Documents

- [README](./README.md)
- [Workflow Guide](./WORKFLOW_GUIDE.md)
- [Operations Playbook](./OPERATIONS_PLAYBOOK.md)
- [Product Backlog](./PRODUCT_BACKLOG.md)
- [Troubleshooting Index](./TROUBLESHOOTING_INDEX.md)
