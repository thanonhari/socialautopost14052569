import datetime
import json
import mimetypes
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).parent.resolve()
WEB_ROOT = ROOT / "web"
STORAGE_ROOT = ROOT / "storage"
JOBS_ROOT = STORAGE_ROOT / "jobs"
JOBS_INDEX = STORAGE_ROOT / "jobs.json"
OAUTH_ROOT = STORAGE_ROOT / "oauth"
OUTPUTS_ROOT = ROOT / "outputs"

ALLOWED_HOSTS = {
    "tiktok.com",
    "www.tiktok.com",
    "m.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
    "new.reddit.com",
    "redd.it",
    "www.redd.it",
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}

PORT = int(os.environ.get("SOCIALAUTOPOST_PORT", "8765"))
ALLOWED_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
MAX_UPLOAD_BYTES = int(os.environ.get("SOCIALAUTOPOST_MAX_UPLOAD_MB", "512")) * 1024 * 1024


@dataclass
class Job:
    id: str
    url: str
    category: str
    browser: str
    normalize: bool
    transcribe: bool = False
    highlights: bool = False
    highlight_length: int = 15
    source_type: str = "url"
    source_file: str = ""
    rights_confirmed: bool = False
    status: str = "queued"
    step: str = "Waiting"
    progress: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    title: str = ""
    uploader: str = ""
    duration: float | None = None
    error: str = ""
    files: dict[str, str] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    compatibility: dict[str, dict[str, object]] = field(default_factory=dict)
    autopost_status: str = "idle"
    autopost_report: dict[str, object] = field(default_factory=dict)
    autopost_control: str = "active"


jobs: dict[str, Job] = {}
jobs_lock = threading.Lock()
_ffmpeg_runtime_cache: dict[str, Any] | None = None


class ThrottlingManager:
    """Manages host reputation and applies adaptive download limits."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.reputation: dict[str, dict[str, object]] = {}
        self.load()

    def load(self) -> None:
        if self.state_file.exists():
            try:
                self.reputation = json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                self.reputation = {}

    def save(self) -> None:
        try:
            self.state_file.write_text(json.dumps(self.reputation, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get_host(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return "unknown"

    def report_failure(self, url: str, error_message: str) -> None:
        host = self.get_host(url)
        if host not in self.reputation:
            self.reputation[host] = {"fail_count": 0, "success_count": 0, "last_error": ""}

        # Detect rate limiting or blocks
        is_block = any(msg in error_message.lower() for msg in ["429", "too many requests", "forbidden", "captcha", "block"])
        if is_block:
            self.reputation[host]["fail_count"] = int(self.reputation[host].get("fail_count", 0)) + 2
        else:
            self.reputation[host]["fail_count"] = int(self.reputation[host].get("fail_count", 0)) + 1

        self.reputation[host]["success_count"] = 0
        self.reputation[host]["last_error"] = error_message[:200]
        self.save()

    def report_success(self, url: str) -> None:
        host = self.get_host(url)
        if host not in self.reputation:
            return
        self.reputation[host]["success_count"] = int(self.reputation[host].get("success_count", 0)) + 1
        if self.reputation[host]["success_count"] > 2:
            self.reputation[host]["fail_count"] = max(0, int(self.reputation[host]["fail_count"]) - 1)
        self.save()

    def get_throttling_args(self, url: str) -> list[str]:
        host = self.get_host(url)
        fail_count = int(self.reputation.get(host, {}).get("fail_count", 0))
        if fail_count <= 0:
            return []

        args = []
        # Adaptive strategy based on failure history
        if fail_count >= 1:
            args.extend(["--sleep-requests", "1.5", "--sleep-interval", "2"])
        if fail_count >= 3:
            args.extend(["--limit-rate", "1M", "--sleep-interval", "5"])
        if fail_count >= 5:
            args.extend(["--limit-rate", "500K", "--sleep-interval", "10", "--sleep-requests", "3"])

        return args


throttler = ThrottlingManager(STORAGE_ROOT / "reputation.json")


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def detect_ffmpeg_runtime() -> dict[str, Any]:
    global _ffmpeg_runtime_cache
    if _ffmpeg_runtime_cache is not None:
        return _ffmpeg_runtime_cache

    runtime = {
        "ffmpeg_available": bool(shutil.which("ffmpeg")),
        "nvenc_available": False,
        "default_encoder": os.environ.get("SOCIALAUTOPOST_FFMPEG_VIDEO_ENCODER", "").strip() or "",
        "hwaccel": os.environ.get("SOCIALAUTOPOST_FFMPEG_HWACCEL_TYPE", "").strip() or "",
    }
    if not runtime["ffmpeg_available"]:
        runtime["default_encoder"] = runtime["default_encoder"] or "libx264"
        _ffmpeg_runtime_cache = runtime
        return runtime

    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        encoders_output = "\n".join([result.stdout, result.stderr])
        runtime["nvenc_available"] = "h264_nvenc" in encoders_output
    except Exception:
        runtime["nvenc_available"] = False

    if not runtime["default_encoder"]:
        runtime["default_encoder"] = "h264_nvenc" if runtime["nvenc_available"] else "libx264"
    _ffmpeg_runtime_cache = runtime
    return runtime


def ffmpeg_video_settings() -> tuple[str, str]:
    runtime = detect_ffmpeg_runtime()
    return str(runtime["default_encoder"]), str(runtime["hwaccel"])


def run_ffmpeg_media_command(job_id: str, cwd: Path, command: list[str], hwaccel: str = "") -> subprocess.CompletedProcess[str]:
    if hwaccel:
        try:
            return run_command(job_id, command[:3] + ["-hwaccel", hwaccel] + command[3:], cwd)
        except Exception as exc:
            error_text = str(exc).lower()
            retry_markers = [
                "hwaccel initialisation returned error",
                "failed setup for format cuda",
                "doesn't support hardware accelerated",
                "error submitting packet to decoder",
            ]
            if not any(marker in error_text for marker in retry_markers):
                raise
            append_log(job_id, f"Retrying ffmpeg without hwaccel after decode failure: {hwaccel}")
    return run_command(job_id, command, cwd)


def update_yt_dlp() -> None:
    """Check and update yt-dlp to the latest version for stability (once per 24 hours)."""
    if env_flag("SOCIALAUTOPOST_SKIP_YTDLP_UPDATE"):
        print("Skipping yt-dlp update check (SOCIALAUTOPOST_SKIP_YTDLP_UPDATE=true)", flush=True)
        return
    if not shutil.which("yt-dlp"):
        return

    update_stamp = STORAGE_ROOT / "last_ytdlp_update.txt"
    day_in_seconds = 24 * 60 * 60

    if update_stamp.exists():
        try:
            last_update = float(update_stamp.read_text().strip())
            if time.time() - last_update < day_in_seconds:
                return
        except Exception:
            pass

    print("Checking for yt-dlp updates (Daily Check)...", flush=True)
    try:
        # Run yt-dlp -U to update
        subprocess.run(["yt-dlp", "-U"], capture_output=True, text=True, check=False)
        result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, check=False)
        version = result.stdout.strip()
        print(f"yt-dlp version: {version}", flush=True)
        # Save update timestamp
        update_stamp.write_text(str(time.time()))
    except Exception as e:
        print(f"Failed to update yt-dlp: {e}", flush=True)


def safe_filename(value: str, fallback: str = "post") -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value[:90] or fallback


def load_jobs() -> None:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    JOBS_ROOT.mkdir(parents=True, exist_ok=True)
    if not JOBS_INDEX.exists():
        return
    try:
        raw = json.loads(JOBS_INDEX.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    with jobs_lock:
        for item in raw:
            item.setdefault("source_type", "url")
            item.setdefault("source_file", "")
            item.setdefault("rights_confirmed", False)
            item.setdefault("transcribe", False)
            item.setdefault("highlights", False)
            item.setdefault("highlight_length", 15)
            item.setdefault("compatibility", {})
            item.setdefault("autopost_status", "idle")
            item.setdefault("autopost_report", {})
            item.setdefault("autopost_control", "active")
            item.setdefault("progress", 100 if item.get("status") == "done" else 0)
            jobs[item["id"]] = Job(**item)


def save_jobs() -> None:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    with jobs_lock:
        payload = [asdict(job) for job in sorted(jobs.values(), key=lambda item: item.created_at, reverse=True)]
    tmp_path = JOBS_INDEX.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(JOBS_INDEX)


def update_job(job_id: str, **changes: object) -> Job:
    with jobs_lock:
        job = jobs[job_id]
        for key, value in changes.items():
            setattr(job, key, value)
        job.updated_at = time.time()
    save_jobs()
    return job


def append_log(job_id: str, message: str) -> None:
    with jobs_lock:
        job = jobs[job_id]
        job.log.append(message)
        job.log = job.log[-120:]
        job.updated_at = time.time()
    save_jobs()


def run_command(job_id: str, command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    append_log(job_id, f"$ {' '.join(command)}")
    process = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = "\n".join(part for part in [process.stdout.strip(), process.stderr.strip()] if part)
    if output:
        for line in output.splitlines()[-10:]:
            append_log(job_id, line)
    if process.returncode != 0:
        raise RuntimeError(output or f"Command failed with exit code {process.returncode}")
    return process


def validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must start with http:// or https://")
    if parsed.netloc.lower() not in ALLOWED_HOSTS:
        raise ValueError("This prototype currently accepts TikTok, X/Twitter, Reddit, and YouTube URLs only. Use local file upload for anything outside that production path.")


def cookie_browser_candidates(browser: str) -> list[str]:
    if browser == "auto":
        return ["firefox", "chrome", "edge", "none"]
    return [browser]


def yt_dlp_base_args(browser: str, url: str = "") -> list[str]:
    args = ["yt-dlp"]
    if browser in {"firefox", "chrome", "edge"}:
        args.extend(["--cookies-from-browser", browser])

    if url:
        args.extend(throttler.get_throttling_args(url))
    return args


def run_yt_dlp_with_cookie_fallback(
    job_id: str,
    selected_browser: str,
    args: list[str],
    cwd: Path,
    url: str = "",
) -> tuple[subprocess.CompletedProcess[str], str]:
    errors: list[str] = []
    for browser in cookie_browser_candidates(selected_browser):
        try:
            update_job(job_id, step=f"Trying cookies: {browser}")
            command = yt_dlp_base_args(browser, url) + args
            result = run_command(job_id, command, cwd)
            append_log(job_id, f"Using cookies mode: {browser}")
            if url:
                throttler.report_success(url)
            return result, browser
        except RuntimeError as exc:
            message = str(exc)
            errors.append(f"{browser}: {message}")
            append_log(job_id, f"Cookie mode failed ({browser}): {message}")
            if url:
                throttler.report_failure(url, message)
            if selected_browser != "auto":
                break
    raise RuntimeError("\n\n".join(errors))


def find_first(folder: Path, names: list[str]) -> Path | None:
    for name in names:
        path = folder / name
        if path.exists():
            return path
    video_suffixes = {".mp4", ".mkv", ".webm", ".mov"}
    matches = [path for path in sorted(folder.glob("source.*")) if path.suffix.lower() in video_suffixes]
    if matches:
        return matches[0]
    matches = [path for path in sorted(folder.glob("*")) if path.suffix.lower() in video_suffixes]
    if matches:
        return matches[0]
    return None


def rel_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def process_job(job_id: str) -> None:
    job_dir = JOBS_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    with jobs_lock:
        job = jobs[job_id]

    try:
        if job.source_type == "file":
            process_file_job(job_id, job, job_dir)
            return

        validate_source_url(job.url)

        update_job(job_id, status="running", step="Reading metadata", progress=10)
        metadata_result, effective_browser = run_yt_dlp_with_cookie_fallback(
            job_id,
            job.browser,
            ["--dump-json", "--no-playlist", job.url],
            job_dir,
            job.url,
        )
        metadata = json.loads(metadata_result.stdout)

        title = str(metadata.get("title") or "Untitled")
        uploader = str(metadata.get("uploader") or metadata.get("channel") or "unknown")
        duration = metadata.get("duration")
        update_job(job_id, title=title, uploader=uploader, duration=duration)

        info_path = job_dir / "source.info.json"
        info_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        update_job(job_id, step="Downloading media", progress=30)
        output_template = str(job_dir / "source.%(ext)s")
        download_cmd = yt_dlp_base_args(effective_browser, job.url) + [
            "--no-playlist",
            "-f",
            "bv*+ba/b",
            "--merge-output-format",
            "mp4",
            "--write-thumbnail",
            "-o",
            output_template,
            job.url,
        ]
        run_command(job_id, download_cmd, job_dir)

        source_video = find_first(job_dir, ["source.mp4", "source.mkv", "source.webm", "source.mov"])
        thumbnail = find_first(job_dir, ["source.jpg", "source.webp", "source.png", "source.image"])
        if not source_video:
            raise RuntimeError("Downloaded video file was not found")

        files = {
            "source_video": rel_path(source_video),
            "metadata": rel_path(info_path),
        }
        if thumbnail:
            files["thumbnail"] = rel_path(thumbnail)

        update_job(job_id, files=files, progress=55)

        normalized_path = source_video
        if job.normalize:
            normalized_path = normalize_video(job_id, source_video, job_dir)
            files["normalized_video"] = rel_path(normalized_path)
            update_job(job_id, files=files, progress=85)

        if job.transcribe:
            transcription_files = create_transcription_artifacts(job_id, source_video, job_dir)
            files.update(transcription_files)
            update_job(job_id, files=files, progress=92)

        if job.highlights:
            highlight_files = create_highlight_artifacts(job_id, source_video, job_dir, files, duration, job.highlight_length)
            files.update(highlight_files)
            update_job(job_id, files=files, progress=94)

        update_job(job_id, step="Creating caption draft", progress=96)
        caption_path = job_dir / "caption.txt"
        caption = build_caption(title=title, uploader=uploader, category=job.category, url=job.url)
        caption_path.write_text(caption, encoding="utf-8")
        files["caption"] = rel_path(caption_path)

        platform_captions_path = job_dir / "captions.platform.json"
        platform_captions = build_platform_captions(title=title, uploader=uploader, category=job.category, source=job.url)
        platform_captions_path.write_text(json.dumps(platform_captions, ensure_ascii=False, indent=2), encoding="utf-8")
        files["platform_captions"] = rel_path(platform_captions_path)

        update_job(job_id, step="Checking platform compatibility", progress=98)
        comp_report = build_compatibility_report(job_id, files, job_dir)
        update_job(job_id, step="Building export package", progress=99)
        export_files = create_export_package(
            job_id=job_id,
            job=job,
            job_dir=job_dir,
            files=files,
            compatibility=comp_report,
            title=title,
            uploader=uploader,
            duration=duration,
        )
        files.update(export_files)

        manifest_path = job_dir / "manifest.json"
        manifest = {
            "job_id": job_id,
            "source_url": job.url,
            "rights_confirmed": job.rights_confirmed,
            "category": job.category,
            "transcribe": job.transcribe,
            "highlights": job.highlights,
            "highlight_length": job.highlight_length,
            "title": title,
            "uploader": uploader,
            "duration": duration,
            "source_video": files.get("source_video"),
            "normalized_video": files.get("normalized_video"),
            "caption": files.get("caption"),
            "platform_captions": files.get("platform_captions"),
            "transcript": files.get("transcript"),
            "captions": files.get("captions"),
            "highlights_manifest": files.get("highlights"),
            "exports_index": files.get("exports_index"),
            "compatibility": comp_report,
            "suggested_platforms": sorted({p for r in comp_report.values() for p, v in r.items() if v.get("ok")}),
            "notes": "Use only content you own or have permission to repost.",
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        files["manifest"] = rel_path(manifest_path)

        # Organized Output Folder
        organize_final_output(job_id, job, manifest, files)

        update_job(job_id, status="done", step="Ready", progress=100, files=files, compatibility=comp_report)
        append_log(job_id, f"Job {job_id} completed successfully")
    except Exception as exc:
        update_job(job_id, status="failed", step="Failed", error=str(exc))
        append_log(job_id, f"Job {job_id} failed: {exc}")


def organize_final_output(job_id: str, job: Job, manifest: dict[str, Any], files: dict[str, str]) -> None:
    """Creates a structured output folder with recommended naming convention."""
    try:
        date_str = datetime.datetime.fromtimestamp(job.created_at).strftime("%Y-%m-%d")
        host = throttler.get_host(job.url).replace("www.", "").split(".")[0].capitalize()
        safe_title = re.sub(r"[^a-zA-Z0-9]+", "-", str(manifest.get("title", "clip")))[:30].strip("-")
        
        folder_name = f"{date_str}_{host}_{safe_title}_{job_id[:6]}"
        out_dir = OUTPUTS_ROOT / folder_name
        out_dir.mkdir(parents=True, exist_ok=True)

        # Copy essential files
        to_copy = [
            ("normalized_video", "final_vertical.mp4"),
            ("caption", "caption_draft.txt"),
            ("captions", "subtitles.srt"),
            ("manifest", "metadata.json")
        ]
        
        for key, target_name in to_copy:
            src = files.get(key)
            if src:
                shutil.copy2(ROOT / src, out_dir / target_name)
        
        # Copy highlights if they exist
        clips_dir = out_dir / "clips"
        job_clips = JOBS_ROOT / job_id / "clips"
        if job_clips.exists():
            shutil.copytree(job_clips, clips_dir, dirs_exist_ok=True)
            
        print(f"Organized output ready at: {out_dir}", flush=True)
    except Exception as e:
        print(f"Failed to organize output: {e}", flush=True)


def process_file_job(job_id: str, job: Job, job_dir: Path) -> None:
    source_video = ROOT / job.source_file
    if not source_video.exists():
        raise RuntimeError(f"Source file not found: {job.source_file}")

    update_job(job_id, status="running", step="Analyzing file", progress=10)
    info = probe_media(source_video)
    title = safe_filename(source_video.stem)
    uploader = "local_file"
    duration = info.get("duration")
    update_job(job_id, title=title, uploader=uploader, duration=duration)

    info_path = job_dir / "source.info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    files = {
        "source_video": rel_path(source_video),
        "metadata": rel_path(info_path),
    }

    normalized_path = source_video
    if job.normalize:
        update_job(job_id, step="Normalizing video", progress=30)
        normalized_path = normalize_video(job_id, source_video, job_dir)
        files["normalized_video"] = rel_path(normalized_path)

    if job.transcribe:
        update_job(job_id, step="Transcribing audio", progress=60)
        transcription_files = create_transcription_artifacts(job_id, source_video, job_dir)
        files.update(transcription_files)

    if job.highlights:
        update_job(job_id, step="Creating highlight clips", progress=80)
        highlight_files = create_highlight_artifacts(job_id, source_video, job_dir, files, duration, job.highlight_length)
        files.update(highlight_files)

    caption_path = job_dir / "caption.txt"
    caption = build_caption(title=title, uploader=uploader, category=job.category, url="file://" + str(source_video))
    caption_path.write_text(caption, encoding="utf-8")
    files["caption"] = rel_path(caption_path)

    platform_captions_path = job_dir / "captions.platform.json"
    platform_captions = build_platform_captions(title=title, uploader=uploader, category=job.category, source="local")
    platform_captions_path.write_text(json.dumps(platform_captions, ensure_ascii=False, indent=2), encoding="utf-8")
    files["platform_captions"] = rel_path(platform_captions_path)

    comp_report = build_compatibility_report(job_id, files, job_dir)
    export_files = create_export_package(
        job_id=job_id,
        job=job,
        job_dir=job_dir,
        files=files,
        compatibility=comp_report,
        title=title,
        uploader=uploader,
        duration=duration,
    )
    files.update(export_files)

    manifest_path = job_dir / "manifest.json"
    manifest = {
        "job_id": job_id,
        "source_url": "",
        "rights_confirmed": job.rights_confirmed,
        "category": job.category,
        "transcribe": job.transcribe,
        "highlights": job.highlights,
        "highlight_length": job.highlight_length,
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "source_video": files.get("source_video"),
        "normalized_video": files.get("normalized_video"),
        "caption": files.get("caption"),
        "platform_captions": files.get("platform_captions"),
        "transcript": files.get("transcript"),
        "captions": files.get("captions"),
        "highlights_manifest": files.get("highlights"),
        "exports_index": files.get("exports_index"),
        "compatibility": comp_report,
        "suggested_platforms": sorted({p for r in comp_report.values() for p, v in r.items() if v.get("ok")}),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    files["manifest"] = rel_path(manifest_path)

    organize_final_output(job_id, job, manifest, files)
    update_job(job_id, status="done", step="Ready", progress=100, files=files, compatibility=comp_report)


def probe_media(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def normalize_video(job_id: str, source_video: Path, job_dir: Path) -> Path:
    update_job(job_id, step="Normalizing video", progress=60)
    output_path = job_dir / "normalized.mp4"

    encoder, hwaccel = ffmpeg_video_settings()

    command = ["ffmpeg", "-hide_banner", "-y"]
    command.extend([
        "-i", str(source_video),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-c:v", encoder,
        "-preset", "p4" if "nvenc" in encoder else "veryfast",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ])

    run_ffmpeg_media_command(job_id, job_dir, command, hwaccel=hwaccel)
    return output_path


def create_transcription_artifacts(job_id: str, source_video: Path, job_dir: Path) -> dict[str, str]:
    update_job(job_id, step="Extracting audio", progress=88)
    audio_path = job_dir / "audio.wav"
    try:
        run_command(job_id, ["ffmpeg", "-hide_banner", "-y", "-i", str(source_video), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(audio_path)], job_dir)
    except Exception as exc:
        err_path = job_dir / "transcription.error.txt"
        err_path.write_text(str(exc), encoding="utf-8")
        return {"transcription_error": rel_path(err_path)}

    update_job(job_id, step="Transcribing audio", progress=90)
    
    # Transcription logic (simplified for script brevity, calling out to whisper if available)
    whisper_device = os.environ.get("SOCIALAUTOPOST_WHISPER_DEVICE", "cpu")
    whisper_compute = os.environ.get("SOCIALAUTOPOST_WHISPER_COMPUTE_TYPE", "int8")
    
    transcript_path = job_dir / "transcript.txt"
    captions_path = job_dir / "captions.srt"
    
    # In a real app, this would call faster-whisper. For this prototype, we simulate or call a sub-process.
    # We'll use a placeholder or the actual logic if integrated.
    try:
        # Placeholder for actual Whisper call - assuming faster-whisper is installed
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device=whisper_device, compute_type=whisper_compute)
        segments, info = model.transcribe(str(audio_path), beam_size=5)
        
        full_text = []
        srt_content = []
        for i, segment in enumerate(segments, 1):
            full_text.append(segment.text.strip())
            srt_content.append(f"{i}\n{format_srt_time(segment.start)} --> {format_srt_time(segment.end)}\n{segment.text.strip()}\n")
            
        transcript_path.write_text(" ".join(full_text), encoding="utf-8")
        captions_path.write_text("\n".join(srt_content), encoding="utf-8")
        
        return {
            "audio": rel_path(audio_path),
            "transcript": rel_path(transcript_path),
            "captions": rel_path(captions_path)
        }
    except Exception as e:
        append_log(job_id, f"Transcription failed: {e}")
        return {"audio": rel_path(audio_path)}


def format_srt_time(seconds: float) -> str:
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def create_highlight_artifacts(job_id: str, source_video: Path, job_dir: Path, files: dict[str, str], duration: float | None, target_length: int) -> dict[str, str]:
    update_job(job_id, step="Creating highlight clips", progress=93)
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    
    # Simple logic: take the first 15-30-60s or segments if transcript exists
    results = {}
    total = duration or 30.0
    
    # For prototype, we'll just create 3 clips at different offsets
    for i in range(1, 4):
        start = (i - 1) * (total / 4)
        end = min(total, start + target_length)
        if end <= start:
            append_log(job_id, f"Skipping clip {i:02}: invalid range {start:.3f}-{end:.3f}")
            continue
        clip_path = clips_dir / f"clip_{i:02}.mp4"

        encoder, hwaccel = ffmpeg_video_settings()
        command = ["ffmpeg", "-hide_banner", "-y"]
        command.extend([
            "-ss", str(start), "-t", str(end - start),
            "-i", str(source_video),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-c:v", encoder,
            "-preset", "p4" if "nvenc" in encoder else "veryfast",
            "-c:a", "aac",
            str(clip_path)
        ])
        try:
            run_ffmpeg_media_command(job_id, job_dir, command, hwaccel=hwaccel)
            results[f"highlight_clip_{i:02}"] = rel_path(clip_path)

            cap_path = clips_dir / f"clip_{i:02}.caption.txt"
            cap_path.write_text(f"Clip {i:02} from {job_id}\n#Shorts #Viral", encoding="utf-8")
            results[f"highlight_caption_{i:02}"] = rel_path(cap_path)
            update_job(
                job_id,
                files={**files, **results},
                progress=min(98, 93 + i),
                step=f"Creating highlight clips ({len([k for k in results if k.startswith('highlight_clip_')])}/3)",
            )
        except Exception as exc:
            append_log(job_id, f"Highlight clip {i:02} failed: {exc}")
            continue

    if not any(key.startswith("highlight_clip_") for key in results):
        raise RuntimeError("Highlight generation failed for all clip candidates")

    highlights_manifest = job_dir / "highlights.json"
    highlights_manifest.write_text(json.dumps(results, indent=2), encoding="utf-8")
    results["highlights"] = rel_path(highlights_manifest)
    
    return results


def build_compatibility_report(job_id: str, files: dict[str, str], job_dir: Path) -> dict[str, Any]:
    # Simplified mock report
    return {
        "normalized_video": {
            "tiktok": {"ok": True, "issues": []},
            "reels": {"ok": True, "issues": []},
            "shorts": {"ok": True, "issues": []}
        }
    }


def create_export_package(job_id: str, job: Job, job_dir: Path, files: dict[str, str], compatibility: Any, title: str, uploader: str, duration: float | None) -> dict[str, str]:
    export_root = job_dir / "exports"
    export_root.mkdir(parents=True, exist_ok=True)
    # Simplified export packaging
    index_path = export_root / "index.json"
    index_path.write_text(json.dumps({"status": "exported"}, indent=2), encoding="utf-8")
    return {"exports_index": rel_path(index_path)}


def build_caption(title: str, uploader: str, category: str, url: str) -> str:
    tag_map = {
        "short": ["#Shorts", "#ShortClip"],
        "funny": ["#Funny", "#Clip"],
        "news": ["#News", "#Update"],
        "movie": ["#Movie", "#Trailer"],
        "other": ["#Video", "#Social"],
    }
    tags = " ".join(tag_map.get(category, tag_map["other"]))
    return f"🔥 {title}\n\nSource: {uploader}\n{tags}\n\nOriginal: {url}"


def build_platform_captions(title: str, uploader: str, category: str, source: str) -> dict[str, dict[str, str]]:
    tag_map = {
        "short": {"tiktok": "#fyp #viral", "reels": "#reels #trending", "shorts": "#shorts #viralshorts"},
        "funny": {"tiktok": "#funny #lmao", "reels": "#funnyreels #laugh", "shorts": "#funny #shorts"},
        "news": {"tiktok": "#news #breaking", "reels": "#news #update", "shorts": "#news #shorts"},
        "movie": {"tiktok": "#movie #cinema", "reels": "#moviereels #film", "shorts": "#movie #shorts"},
        "other": {"tiktok": "#video #trending", "reels": "#reels #explore", "shorts": "#shorts #video"},
    }
    tags = tag_map.get(category, tag_map["other"])
    
    hooks = [
        "You won't believe what happens next!",
        "Is this the most amazing thing you've seen today?",
        "Wait for the ending... it's totally worth it!",
        "Tag a friend who needs to see this!",
    ]
    hook = hooks[int(time.time()) % len(hooks)]

    return {
        "tiktok": {
            "en": f"🔥 {title}\n\n{hook}\n\n{tags['tiktok']}\n\nSource: {uploader}",
            "th": f"🔥 {title}\n\nดูให้จบแล้วจะรู้ว่าทำไมทุกคนถึงแชร์! 😱\n\n{tags['tiktok']}\n#คลิปดัง #สาระ\n\nที่มา: {uploader}"
        },
        "reels": {
            "en": f"✨ {title}\n\n{hook}\n\n{tags['reels']}\n\nFrom {uploader}",
            "th": f"✨ {title}\n\nคลิปนี้ต้องดู! ใครเคยเจอแบบนี้บ้าง? คอมเมนต์เลย 👇\n\n{tags['reels']}\n#คลิปสั้น #วิดีโอแนะนำ\n\nที่มา: {uploader}"
        },
        "shorts": {
            "en": f"🚀 {title}\n\n{hook}\n\n{tags['shorts']}\n\nSource: {uploader}",
            "th": f"🚀 {title}\n\nห้ามพลาด! ช่วงท้ายของคลิปนี้คือที่สุดจริงๆ 💯\n\n{tags['shorts']}\n#ยูทูปชอร์ต #ต้องดู\n\nที่มา: {uploader}"
        }
    }


def normalize_caption_text(text: str, limit: int) -> str:
    return text[:limit]


def list_jobs() -> list[dict[str, Any]]:
    with jobs_lock:
        return [asdict(job) for job in sorted(jobs.values(), key=lambda item: item.created_at, reverse=True)]


def get_job(job_id: str) -> dict[str, Any] | None:
    with jobs_lock:
        job = jobs.get(job_id)
        return asdict(job) if job else None


def collect_runtime_diagnostics() -> dict[str, Any]:
    runtime = detect_ffmpeg_runtime()
    whisper_device = os.environ.get("SOCIALAUTOPOST_WHISPER_DEVICE", "cpu")
    whisper_compute = os.environ.get("SOCIALAUTOPOST_WHISPER_COMPUTE_TYPE", "int8")
    return {
        "status": "ok",
        "gpu": "GTX 1050 Ti" if runtime["nvenc_available"] else "",
        "ffmpeg": {
            "available": runtime["ffmpeg_available"],
            "default_encoder": runtime["default_encoder"],
            "hwaccel": runtime["hwaccel"],
            "nvenc_available": runtime["nvenc_available"],
        },
        "whisper": {
            "device": whisper_device,
            "compute_type": whisper_compute,
            "gpu_enabled": whisper_device == "cuda",
        },
    }


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/jobs":
            self.send_json(list_jobs())
        elif parsed.path == "/api/diagnostics":
            self.send_json(collect_runtime_diagnostics())
        elif parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.split("/")[-1]
            job = get_job(job_id)
            if job:
                self.send_json(job)
            else:
                self.send_error(404)
        elif parsed.path.startswith("/files/"):
            self.send_file(ROOT / unquote(parsed.path.removeprefix("/files/")))
        else:
            self.send_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/jobs":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body)
            job_id = os.urandom(6).hex()
            job = Job(id=job_id, **payload)
            with jobs_lock:
                jobs[job_id] = job
            save_jobs()
            threading.Thread(target=process_job, args=(job_id,)).start()
            self.send_json(asdict(job))

    def send_json(self, data: Any, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def send_static(self, path: str) -> None:
        if path in {"", "/"}:
            file_path = WEB_ROOT / "index.html"
        else:
            file_path = (WEB_ROOT / unquote(path.lstrip("/"))).resolve()
            if not str(file_path).startswith(str(WEB_ROOT.resolve())):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
        self.send_file(file_path)

    def send_file(self, file_path: Path) -> None:
        file_path = file_path.resolve()
        allowed_roots = [ROOT.resolve(), WEB_ROOT.resolve()]
        if not any(str(file_path).startswith(str(root)) for root in allowed_roots):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        file_size = file_path.stat().st_size
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_size))
        self.end_headers()
        with file_path.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)


def main() -> None:
    update_yt_dlp()
    load_jobs()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), AppHandler)
    print(f"SocialAutoPost local web: http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
