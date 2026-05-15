# Startup script for SocialAutoPost with GPU acceleration
$env:SOCIALAUTOPOST_WHISPER_DEVICE="cuda"
$env:SOCIALAUTOPOST_WHISPER_COMPUTE_TYPE="int8"
$env:SOCIALAUTOPOST_FFMPEG_VIDEO_ENCODER="h264_nvenc"
$env:SOCIALAUTOPOST_FFMPEG_HWACCEL_TYPE="cuda"

Write-Host "Starting SocialAutoPost with GPU acceleration..." -ForegroundColor Green
Write-Host "Whisper Device: CUDA (int8)"
Write-Host "FFmpeg Encoder: NVENC"

python app.py
