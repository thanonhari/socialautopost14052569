from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import hmac
import hashlib
from dataclasses import asdict, dataclass, field
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
STORAGE_ROOT = ROOT / "storage"
JOBS_ROOT = STORAGE_ROOT / "jobs"
JOBS_INDEX = STORAGE_ROOT / "jobs.json"
OAUTH_ROOT = STORAGE_ROOT / "oauth"

ALLOWED_HOSTS = {
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
        for line in output.splitlines()[-40:]:
            append_log(job_id, line)
    if process.returncode != 0:
        raise RuntimeError(output or f"Command failed with exit code {process.returncode}")
    return process


def validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must start with http:// or https://")
    if parsed.netloc.lower() not in ALLOWED_HOSTS:
        raise ValueError("This prototype currently accepts X/Twitter, Reddit, and YouTube URLs only")


def cookie_browser_candidates(browser: str) -> list[str]:
    if browser == "auto":
        return ["firefox", "chrome", "edge", "none"]
    return [browser]


def yt_dlp_base_args(browser: str) -> list[str]:
    args = ["yt-dlp"]
    if browser in {"firefox", "chrome", "edge"}:
        args.extend(["--cookies-from-browser", browser])
    return args


def run_yt_dlp_with_cookie_fallback(
    job_id: str,
    selected_browser: str,
    args: list[str],
    cwd: Path,
) -> tuple[subprocess.CompletedProcess[str], str]:
    errors: list[str] = []
    for browser in cookie_browser_candidates(selected_browser):
        try:
            update_job(job_id, step=f"Trying cookies: {browser}")
            command = yt_dlp_base_args(browser) + args
            result = run_command(job_id, command, cwd)
            append_log(job_id, f"Using cookies mode: {browser}")
            return result, browser
        except RuntimeError as exc:
            message = str(exc)
            errors.append(f"{browser}: {message}")
            append_log(job_id, f"Cookie mode failed ({browser}): {message}")
            if selected_browser != "auto":
                break
    raise RuntimeError("\n\n".join(errors))


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
        download_cmd = yt_dlp_base_args(effective_browser) + [
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
        thumbnail = find_first(job_dir, ["source.jpg", "source.webp", "source.png"])
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
            "suggested_platforms": ["TikTok", "Instagram Reels", "YouTube Shorts"],
            "notes": "Use only content you own or have permission to repost.",
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        files["manifest"] = rel_path(manifest_path)

        update_job(job_id, status="done", step="Ready", files=files, compatibility=comp_report, progress=100)
    except Exception as exc:
        update_job(job_id, status="failed", step="Failed", error=str(exc), progress=100)
        append_log(job_id, f"ERROR: {exc}")


def process_file_job(job_id: str, job: Job, job_dir: Path) -> None:
    update_job(job_id, status="running", step="Preparing local file", progress=15)
    uploaded_path = job_dir / job.source_file
    if not uploaded_path.exists():
        raise RuntimeError("Uploaded source file was not found")

    source_path = job_dir / f"source{uploaded_path.suffix.lower()}"
    if uploaded_path != source_path:
        shutil.move(str(uploaded_path), str(source_path))

    update_job(job_id, step="Reading local metadata", progress=35)
    title = Path(job.source_file).stem or "Local video"
    duration = probe_duration(job_id, source_path, job_dir)
    info_path = job_dir / "source.info.json"
    metadata = {
        "source_type": "file",
        "title": title,
        "uploader": "local",
        "duration": duration,
        "filename": job.source_file,
        "ext": source_path.suffix.lstrip("."),
    }
    info_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    files = {
        "source_video": rel_path(source_path),
        "metadata": rel_path(info_path),
    }
    update_job(job_id, title=title, uploader="local", duration=duration, files=files, progress=55)

    normalized_path = source_path
    if job.normalize:
        normalized_path = normalize_video(job_id, source_path, job_dir)
        files["normalized_video"] = rel_path(normalized_path)
        update_job(job_id, files=files, progress=85)

    if job.transcribe:
        transcription_files = create_transcription_artifacts(job_id, source_path, job_dir)
        files.update(transcription_files)
        update_job(job_id, files=files, progress=92)

    if job.highlights:
        highlight_files = create_highlight_artifacts(job_id, source_path, job_dir, files, duration, job.highlight_length)
        files.update(highlight_files)
        update_job(job_id, files=files, progress=94)

    update_job(job_id, step="Creating caption draft", progress=96)
    caption_path = job_dir / "caption.txt"
    caption = build_caption(title=title, uploader="local", category=job.category, url=f"local file: {job.source_file}")
    caption_path.write_text(caption, encoding="utf-8")
    files["caption"] = rel_path(caption_path)

    platform_captions_path = job_dir / "captions.platform.json"
    platform_captions = build_platform_captions(
        title=title,
        uploader="local",
        category=job.category,
        source=f"local file: {job.source_file}",
    )
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
        uploader="local",
        duration=duration,
    )
    files.update(export_files)

    manifest_path = job_dir / "manifest.json"
    manifest = {
        "job_id": job_id,
        "source_type": "file",
        "source_url": "",
        "source_file": job.source_file,
        "rights_confirmed": job.rights_confirmed,
        "category": job.category,
        "transcribe": job.transcribe,
        "highlights": job.highlights,
        "highlight_length": job.highlight_length,
        "title": title,
        "uploader": "local",
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
        "suggested_platforms": ["TikTok", "Instagram Reels", "YouTube Shorts"],
        "notes": "Use only content you own or have permission to repost.",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    files["manifest"] = rel_path(manifest_path)
    update_job(job_id, status="done", step="Ready", files=files, compatibility=comp_report, progress=100)


def probe_duration(job_id: str, source_video: Path, job_dir: Path) -> float | None:
    try:
        result = run_command(
            job_id,
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source_video),
            ],
            job_dir,
        )
        return float(result.stdout.strip())
    except Exception as exc:
        append_log(job_id, f"Duration probe failed: {exc}")
        return None


def normalize_video(job_id: str, source_video: Path, job_dir: Path) -> Path:
    update_job(job_id, step="Normalizing video", progress=65)
    normalized_path = job_dir / "normalized.mp4"
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_video),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(normalized_path),
    ]
    run_command(job_id, ffmpeg_cmd, job_dir)
    return normalized_path


def get_video_metadata(job_id: str, video_path: Path, job_dir: Path) -> dict[str, object]:
    try:
        result = run_command(
            job_id,
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,codec_name:format=duration,format_name",
                "-of",
                "json",
                str(video_path),
            ],
            job_dir,
        )
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        fmt = data.get("format", {})
        return {
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "duration": float(fmt.get("duration", 0)),
            "codec": stream.get("codec_name", "unknown"),
            "format": fmt.get("format_name", "unknown"),
            "size_bytes": int(video_path.stat().st_size),
        }
    except Exception as exc:
        append_log(job_id, f"Metadata probe failed: {exc}")
        return {}


def validate_platform_compatibility(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
    if not metadata:
        return {}

    w = int(metadata.get("width", 0))
    h = int(metadata.get("height", 0))
    d = float(metadata.get("duration", 0))
    codec = str(metadata.get("codec", ""))
    fmt = str(metadata.get("format", ""))
    size_bytes = int(metadata.get("size_bytes", 0))

    aspect_ratio = w / h if h > 0 else 0
    is_9_16 = 0.55 <= aspect_ratio <= 0.575  # 9/16 is 0.5625
    is_1_1 = 0.98 <= aspect_ratio <= 1.02
    is_h264 = codec in {"h264", "avc1"}
    is_mp4 = "mp4" in fmt
    size_mb = size_bytes / (1024 * 1024) if size_bytes else 0.0

    report = {}

    # TikTok
    tiktok_ok = True
    tiktok_issues = []
    if not is_9_16:
        tiktok_ok = False
        tiktok_issues.append("Aspect ratio is not 9:16")
    if h < 1280:
        tiktok_ok = False
        tiktok_issues.append("Resolution is below 720x1280")
    if d < 3:
        tiktok_ok = False
        tiktok_issues.append("Duration is too short (min 3s)")
    if d > 600:
        tiktok_ok = False
        tiktok_issues.append("Duration is too long (max 10m)")
    if not is_h264:
        tiktok_ok = False
        tiktok_issues.append("Video codec is not H.264")
    if not is_mp4:
        tiktok_ok = False
        tiktok_issues.append("Container is not MP4")
    if size_mb > 287:
        tiktok_ok = False
        tiktok_issues.append("File size is over 287 MB")
    report["tiktok"] = {"ok": tiktok_ok, "issues": tiktok_issues}

    # Reels
    reels_ok = True
    reels_issues = []
    if not is_9_16:
        reels_ok = False
        reels_issues.append("Aspect ratio is not 9:16")
    if h < 1280:
        reels_ok = False
        reels_issues.append("Resolution is below 720x1280")
    if d > 90:
        reels_ok = False
        reels_issues.append("Duration is too long (max 90s)")
    if not is_h264:
        reels_ok = False
        reels_issues.append("Video codec is not H.264")
    if not is_mp4:
        reels_ok = False
        reels_issues.append("Container is not MP4")
    if size_mb > 100:
        reels_ok = False
        reels_issues.append("File size is over 100 MB")
    report["reels"] = {"ok": reels_ok, "issues": reels_issues}

    # Shorts
    shorts_ok = True
    shorts_issues = []
    if not (is_9_16 or is_1_1):  # 9:16 or 1:1
        shorts_ok = False
        shorts_issues.append("Aspect ratio is not 9:16 or 1:1")
    if d > 60:
        shorts_ok = False
        shorts_issues.append("Duration is too long (max 60s)")
    if not is_h264:
        shorts_ok = False
        shorts_issues.append("Video codec is not H.264")
    if not is_mp4:
        shorts_ok = False
        shorts_issues.append("Container is not MP4")
    if size_mb > 256:
        shorts_ok = False
        shorts_issues.append("File size is over 256 MB")
    report["shorts"] = {"ok": shorts_ok, "issues": shorts_issues}

    return report


def build_compatibility_report(job_id: str, files: dict[str, str], job_dir: Path) -> dict[str, dict[str, dict[str, object]]]:
    report: dict[str, dict[str, dict[str, object]]] = {}
    video_keys = ["source_video", "normalized_video"] + sorted(
        key for key in files.keys() if key.startswith("highlight_clip_")
    )
    for key in video_keys:
        rel = files.get(key)
        if not rel:
            continue
        path = ROOT / rel
        if not path.exists():
            append_log(job_id, f"Compatibility skipped: missing file for {key}")
            continue
        metadata = get_video_metadata(job_id, path, job_dir)
        if not metadata:
            continue
        report[key] = validate_platform_compatibility(metadata)
    return report


def create_export_package(
    job_id: str,
    job: Job,
    job_dir: Path,
    files: dict[str, str],
    compatibility: dict[str, dict[str, dict[str, object]]],
    title: str,
    uploader: str,
    duration: float | None,
) -> dict[str, str]:
    highlights_rel = files.get("highlights")
    if not highlights_rel:
        return {}
    highlights_path = ROOT / highlights_rel
    if not highlights_path.exists():
        return {}

    try:
        highlights = json.loads(highlights_path.read_text(encoding="utf-8"))
    except Exception as exc:
        append_log(job_id, f"Export package skipped: invalid highlights.json ({exc})")
        return {}
    if not isinstance(highlights, list) or not highlights:
        return {}

    exports_root = job_dir / "exports"
    exports_root.mkdir(parents=True, exist_ok=True)
    export_index: list[dict[str, object]] = []
    result_files: dict[str, str] = {}

    for index, clip in enumerate(highlights, start=1):
        clip_file = str(clip.get("file") or "")
        clip_path = ROOT / clip_file if clip_file else None
        if not clip_path or not clip_path.exists():
            continue

        export_dir = exports_root / f"clip_{index:02}"
        export_dir.mkdir(parents=True, exist_ok=True)
        final_path = export_dir / "final.mp4"
        shutil.copy2(clip_path, final_path)

        caption_text = str(clip.get("caption") or "").strip()
        if not caption_text:
            cap_file = str(clip.get("caption_file") or "")
            cap_path = ROOT / cap_file if cap_file else None
            if cap_path and cap_path.exists():
                caption_text = cap_path.read_text(encoding="utf-8", errors="replace").strip()
        if not caption_text:
            caption_text = "Short highlight clip.\n\n#Shorts #Reels #TikTok"
        caption_path = export_dir / "caption.txt"
        caption_path.write_text(caption_text + "\n", encoding="utf-8")

        clip_key = f"highlight_clip_{index:02}"
        clip_manifest = {
            "job_id": job_id,
            "clip_index": index,
            "title": title,
            "uploader": uploader,
            "category": job.category,
            "rights_confirmed": job.rights_confirmed,
            "source_url": job.url,
            "source_type": job.source_type,
            "source_file": job.source_file,
            "final_video": rel_path(final_path),
            "caption_file": rel_path(caption_path),
            "duration": clip.get("duration", duration),
            "start": clip.get("start"),
            "end": clip.get("end"),
            "reason": clip.get("reason", ""),
            "compatibility": compatibility.get(clip_key, {}),
            "suggested_platforms": ["TikTok", "Instagram Reels", "YouTube Shorts"],
        }
        clip_manifest_path = export_dir / "manifest.json"
        clip_manifest_path.write_text(json.dumps(clip_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        export_index.append(
            {
                "clip_index": index,
                "folder": rel_path(export_dir),
                "final_video": rel_path(final_path),
                "caption_file": rel_path(caption_path),
                "manifest": rel_path(clip_manifest_path),
            }
        )
        result_files[f"export_clip_{index:02}"] = rel_path(final_path)
        result_files[f"export_caption_{index:02}"] = rel_path(caption_path)
        result_files[f"export_manifest_{index:02}"] = rel_path(clip_manifest_path)

    if not export_index:
        return {}

    index_path = exports_root / "index.json"
    index_path.write_text(json.dumps(export_index, ensure_ascii=False, indent=2), encoding="utf-8")
    result_files["exports_index"] = rel_path(index_path)
    return result_files


def run_autopost_task(job_id: str, platforms: list[str], language: str, dry_run: bool) -> None:
    job_dir = JOBS_ROOT / job_id
    report_path = job_dir / "autopost.report.json"
    queue_path = job_dir / "autopost.queue.json"
    control_path = job_dir / "autopost.control.json"
    audit_path = job_dir / "autopost.audit.jsonl"
    try:
        with jobs_lock:
            job = jobs[job_id]
        exports_index_rel = job.files.get("exports_index")
        if not exports_index_rel:
            raise RuntimeError("No export package found. Create highlights first.")
        exports_index_path = ROOT / exports_index_rel
        if not exports_index_path.exists():
            raise RuntimeError("Export index file was not found")

        exports_index = json.loads(exports_index_path.read_text(encoding="utf-8"))
        if not isinstance(exports_index, list) or not exports_index:
            raise RuntimeError("Export index is empty")

        caption_variants = {}
        platform_caption_rel = job.files.get("platform_captions")
        if platform_caption_rel:
            platform_caption_path = ROOT / platform_caption_rel
            if platform_caption_path.exists():
                caption_variants = json.loads(platform_caption_path.read_text(encoding="utf-8"))

        started_at = time.time()
        operator = str(job.autopost_report.get("operator", "unknown")) if isinstance(job.autopost_report, dict) else "unknown"
        write_autopost_control(control_path, "active")
        operator = str(job.autopost_report.get("operator", "unknown")) if isinstance(job.autopost_report, dict) else "unknown"
        append_audit_event(audit_path, "autopost_started", {"job_id": job_id, "platforms": platforms, "dry_run": dry_run, "language": language, "operator": operator})
        token_check = get_autopost_token_status(platforms)
        endpoint_check = get_autopost_endpoint_status(platforms)
        results: list[dict[str, object]] = []
        queue_items: list[dict[str, object]] = []
        for item in exports_index:
            clip_index = int(item.get("clip_index", 0))
            final_video = str(item.get("final_video", ""))
            for platform in platforms:
                wait_for_autopost_resume(job_id, control_path, audit_path)
                post_id = f"{platform}_{job_id}_{clip_index:02}_{int(time.time())}"
                caption = str(caption_variants.get(platform, {}).get(language, "")).strip()
                if not caption:
                    caption = f"{job.title or 'SocialAutoPost Clip'}\n\n#shortvideo"
                caption_preview = normalize_caption_text(caption, 220)
                result = {
                    "clip_index": clip_index,
                    "platform": platform,
                    "language": language,
                    "dry_run": dry_run,
                    "status": "simulated" if dry_run else "ready",
                    "video_file": final_video,
                    "caption_preview": caption_preview,
                    "caption": caption,
                    "post_id": post_id,
                    "timestamp": time.time(),
                    "delivery_state": "queued",
                }
                queue_items.append(
                    {
                        "post_id": post_id,
                        "clip_index": clip_index,
                        "platform": platform,
                        "delivery_state": "queued",
                        "updated_at": time.time(),
                    }
                )
                write_autopost_queue(queue_path, queue_items)
                append_audit_event(audit_path, "delivery_queued", {"job_id": job_id, "post_id": post_id, "platform": platform, "clip_index": clip_index, "operator": operator})

                result["delivery_state"] = "sending"
                update_queue_state(queue_items, post_id, "sending")
                write_autopost_queue(queue_path, queue_items)
                append_audit_event(audit_path, "delivery_sending", {"job_id": job_id, "post_id": post_id, "platform": platform, "clip_index": clip_index, "operator": operator})

                if dry_run:
                    result["status"] = "simulated"
                    result["delivery_state"] = "simulated"
                elif not token_check.get(platform, False):
                    result["status"] = "blocked"
                    result["error"] = f"Missing token env: {autopost_token_env(platform)}"
                    result["delivery_state"] = "blocked"
                elif not endpoint_check.get(platform, False):
                    result["status"] = "blocked"
                    result["error"] = f"Missing endpoint env: {autopost_endpoint_env(platform)}"
                    result["delivery_state"] = "blocked"
                else:
                    result = autopost_send_live(platform, result)
                    result["delivery_state"] = "posted" if result.get("status") == "posted" else "failed"

                update_queue_state(queue_items, post_id, str(result.get("delivery_state", "failed")))
                write_autopost_queue(queue_path, queue_items)
                append_audit_event(
                    audit_path,
                    "delivery_finished",
                    {
                        "job_id": job_id,
                        "post_id": post_id,
                        "platform": platform,
                        "clip_index": clip_index,
                        "status": result.get("status"),
                        "delivery_state": result.get("delivery_state"),
                        "remote_id": result.get("remote_id", ""),
                        "operator": operator,
                    },
                )
                results.append(result)

        report = {
            "status": "done",
            "started_at": started_at,
            "finished_at": time.time(),
            "dry_run": dry_run,
            "language": language,
            "platforms": platforms,
            "token_status": token_check,
            "endpoint_status": endpoint_check,
            "queue_file": rel_path(queue_path),
            "control_file": rel_path(control_path),
            "audit_file": rel_path(audit_path),
            "results": results,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        with jobs_lock:
            job = jobs[job_id]
            job.files["autopost_report"] = rel_path(report_path)
            job.files["autopost_queue"] = rel_path(queue_path)
            job.files["autopost_control"] = rel_path(control_path)
            job.files["autopost_audit"] = rel_path(audit_path)
        save_jobs()
        append_audit_event(audit_path, "autopost_finished", {"job_id": job_id, "status": "done", "operator": operator})
        update_job(job_id, autopost_status="done", autopost_report=report, files=jobs[job_id].files, autopost_control="active")
    except Exception as exc:
        error_report = {
            "status": "failed",
            "finished_at": time.time(),
            "error": str(exc),
            "dry_run": dry_run,
            "language": language,
            "platforms": platforms,
        }
        report_path.write_text(json.dumps(error_report, ensure_ascii=False, indent=2), encoding="utf-8")
        with jobs_lock:
            job = jobs[job_id]
            job.files["autopost_report"] = rel_path(report_path)
            job.files["autopost_queue"] = rel_path(queue_path)
            job.files["autopost_control"] = rel_path(control_path)
            job.files["autopost_audit"] = rel_path(audit_path)
        save_jobs()
        append_audit_event(audit_path, "autopost_failed", {"job_id": job_id, "error": str(exc), "operator": operator if 'operator' in locals() else "unknown"})
        update_job(job_id, autopost_status="failed", autopost_report=error_report, files=jobs[job_id].files, autopost_control="active")
        append_log(job_id, f"Autopost failed: {exc}")


def append_audit_event(audit_path: Path, action: str, payload: dict[str, object]) -> None:
    record = {
        "timestamp": time.time(),
        "action": action,
        "payload": payload,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def resolve_operator(headers: object | None = None, payload: dict[str, object] | None = None) -> str:
    if payload:
        operator = str(payload.get("operator", "")).strip()
        if operator:
            return operator[:120]
    if headers:
        operator = str(headers.get("x-operator", "")).strip()
        if operator:
            return operator[:120]
    return "unknown"


def write_autopost_control(control_path: Path, state: str) -> None:
    control_path.write_text(json.dumps({"updated_at": time.time(), "state": state}, ensure_ascii=False, indent=2), encoding="utf-8")


def read_autopost_control(control_path: Path) -> str:
    if not control_path.exists():
        return "active"
    try:
        payload = json.loads(control_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "active"
    state = str(payload.get("state", "active")).strip().lower()
    return state if state in {"active", "paused"} else "active"


def wait_for_autopost_resume(job_id: str, control_path: Path, audit_path: Path) -> None:
    was_paused = False
    while read_autopost_control(control_path) == "paused":
        if not was_paused:
            append_audit_event(audit_path, "autopost_paused", {"job_id": job_id})
            update_job(job_id, autopost_control="paused")
            was_paused = True
        time.sleep(1.0)
    if was_paused:
        append_audit_event(audit_path, "autopost_resumed", {"job_id": job_id})
        update_job(job_id, autopost_control="active")


def run_autopost_retry_task(job_id: str, retry_targets: list[dict[str, object]]) -> None:
    job_dir = JOBS_ROOT / job_id
    report_path = job_dir / "autopost.report.json"
    queue_path = job_dir / "autopost.queue.json"
    control_path = job_dir / "autopost.control.json"
    audit_path = job_dir / "autopost.audit.jsonl"
    try:
        with jobs_lock:
            job = jobs[job_id]
        caption_variants = {}
        platform_caption_rel = job.files.get("platform_captions")
        if platform_caption_rel:
            platform_caption_path = ROOT / platform_caption_rel
            if platform_caption_path.exists():
                caption_variants = json.loads(platform_caption_path.read_text(encoding="utf-8"))
        exports_index_rel = job.files.get("exports_index")
        if not exports_index_rel:
            raise RuntimeError("No export package found")
        exports_index = json.loads((ROOT / exports_index_rel).read_text(encoding="utf-8"))
        export_map = {int(item.get("clip_index", 0)): item for item in exports_index}

        write_autopost_control(control_path, "active")
        token_check = get_autopost_token_status([str(item["platform"]) for item in retry_targets])
        endpoint_check = get_autopost_endpoint_status([str(item["platform"]) for item in retry_targets])
        queue_items: list[dict[str, object]] = []
        results: list[dict[str, object]] = []
        for target in retry_targets:
            wait_for_autopost_resume(job_id, control_path, audit_path)
            clip_index = int(target["clip_index"])
            platform = str(target["platform"])
            language = str(target.get("language", "en"))
            export_item = export_map.get(clip_index)
            if not export_item:
                continue
            final_video = str(export_item.get("final_video", ""))
            post_id = f"{platform}_{job_id}_{clip_index:02}_{int(time.time())}"
            caption = str(caption_variants.get(platform, {}).get(language, "")).strip()
            if not caption:
                caption = f"{job.title or 'SocialAutoPost Clip'}\n\n#shortvideo"
            result = {
                "clip_index": clip_index,
                "platform": platform,
                "language": language,
                "dry_run": False,
                "status": "ready",
                "video_file": final_video,
                "caption_preview": normalize_caption_text(caption, 220),
                "caption": caption,
                "post_id": post_id,
                "timestamp": time.time(),
                "delivery_state": "queued",
            }
            queue_items.append({"post_id": post_id, "clip_index": clip_index, "platform": platform, "delivery_state": "queued", "updated_at": time.time()})
            write_autopost_queue(queue_path, queue_items)
            append_audit_event(audit_path, "delivery_retry_queued", {"job_id": job_id, "post_id": post_id, "platform": platform, "clip_index": clip_index, "operator": operator})
            result["delivery_state"] = "sending"
            update_queue_state(queue_items, post_id, "sending")
            write_autopost_queue(queue_path, queue_items)

            if not token_check.get(platform, False):
                result["status"] = "blocked"
                result["error"] = f"Missing token env: {autopost_token_env(platform)}"
                result["delivery_state"] = "blocked"
            elif not endpoint_check.get(platform, False):
                result["status"] = "blocked"
                result["error"] = f"Missing endpoint env: {autopost_endpoint_env(platform)}"
                result["delivery_state"] = "blocked"
            else:
                result = autopost_send_live(platform, result)
                result["delivery_state"] = "posted" if result.get("status") == "posted" else "failed"

            update_queue_state(queue_items, post_id, str(result.get("delivery_state", "failed")))
            write_autopost_queue(queue_path, queue_items)
            append_audit_event(audit_path, "delivery_retry_finished", {"job_id": job_id, "post_id": post_id, "status": result.get("status"), "delivery_state": result.get("delivery_state"), "operator": operator})
            results.append(result)

        report = {
            "status": "done",
            "started_at": time.time(),
            "finished_at": time.time(),
            "retry": True,
            "results": results,
            "queue_file": rel_path(queue_path),
            "control_file": rel_path(control_path),
            "audit_file": rel_path(audit_path),
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        with jobs_lock:
            job = jobs[job_id]
            job.files["autopost_report"] = rel_path(report_path)
            job.files["autopost_queue"] = rel_path(queue_path)
            job.files["autopost_control"] = rel_path(control_path)
            job.files["autopost_audit"] = rel_path(audit_path)
        save_jobs()
        update_job(job_id, autopost_status="done", autopost_report=report, files=jobs[job_id].files, autopost_control="active")
    except Exception as exc:
        append_audit_event(audit_path, "autopost_retry_failed", {"job_id": job_id, "error": str(exc), "operator": operator if 'operator' in locals() else "unknown"})
        update_job(job_id, autopost_status="failed", autopost_report={"status": "failed", "error": str(exc), "retry": True}, autopost_control="active")


def write_autopost_queue(queue_path: Path, queue_items: list[dict[str, object]]) -> None:
    payload = {
        "updated_at": time.time(),
        "items": queue_items,
    }
    queue_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def update_queue_state(queue_items: list[dict[str, object]], post_id: str, state: str) -> None:
    for item in queue_items:
        if str(item.get("post_id")) == post_id:
            item["delivery_state"] = state
            item["updated_at"] = time.time()
            return


def autopost_token_env(platform: str) -> str:
    env_map = {
        "tiktok": "SOCIALAUTOPOST_TIKTOK_TOKEN",
        "reels": "SOCIALAUTOPOST_REELS_TOKEN",
        "shorts": "SOCIALAUTOPOST_SHORTS_TOKEN",
    }
    return env_map.get(platform, "")


def autopost_adapter_mode(platform: str) -> str:
    env_name = f"SOCIALAUTOPOST_{platform.upper()}_ADAPTER"
    value = os.environ.get(env_name, "").strip().lower()
    if platform == "shorts" and value == "native":
        return "native"
    return "webhook"


def autopost_endpoint_env(platform: str) -> str:
    env_map = {
        "tiktok": "SOCIALAUTOPOST_TIKTOK_ENDPOINT",
        "reels": "SOCIALAUTOPOST_REELS_ENDPOINT",
        "shorts": "SOCIALAUTOPOST_SHORTS_ENDPOINT",
    }
    return env_map.get(platform, "")


def autopost_signing_secret_env(platform: str) -> str:
    env_map = {
        "tiktok": "SOCIALAUTOPOST_TIKTOK_SIGNING_SECRET",
        "reels": "SOCIALAUTOPOST_REELS_SIGNING_SECRET",
        "shorts": "SOCIALAUTOPOST_SHORTS_SIGNING_SECRET",
    }
    return env_map.get(platform, "")


def get_autopost_token_status(platforms: list[str]) -> dict[str, bool]:
    status: dict[str, bool] = {}
    for platform in platforms:
        env_name = autopost_token_env(platform)
        status[platform] = bool(env_name and os.environ.get(env_name))
    return status


def get_autopost_endpoint_status(platforms: list[str]) -> dict[str, bool]:
    status: dict[str, bool] = {}
    for platform in platforms:
        if autopost_adapter_mode(platform) == "native":
            status[platform] = True
            continue
        env_name = autopost_endpoint_env(platform)
        status[platform] = bool(env_name and os.environ.get(env_name))
    return status


def build_webhook_signature(secret: str, timestamp: str, body: bytes) -> str:
    signed = f"{timestamp}.".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def extract_remote_post_fields(response_body: str) -> dict[str, object]:
    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    data_obj = payload.get("data")
    nested_id = data_obj.get("id") if isinstance(data_obj, dict) else None
    remote_id = payload.get("id") or payload.get("post_id") or nested_id
    remote_status = payload.get("status") or payload.get("state") or payload.get("result")
    remote_url = payload.get("url") or payload.get("post_url") or payload.get("link")
    result: dict[str, object] = {}
    if remote_id is not None:
        result["remote_id"] = str(remote_id)
    if remote_status is not None:
        result["remote_status"] = str(remote_status)
    if remote_url is not None:
        result["remote_url"] = str(remote_url)
    return result


def autopost_send_live(platform: str, base_result: dict[str, object]) -> dict[str, object]:
    if platform == "shorts" and autopost_adapter_mode(platform) == "native":
        return autopost_send_youtube_shorts_native(base_result)
    output = dict(base_result)
    token_env = autopost_token_env(platform)
    endpoint_env = autopost_endpoint_env(platform)
    token = os.environ.get(token_env, "").strip() if token_env else ""
    endpoint = os.environ.get(endpoint_env, "").strip() if endpoint_env else ""
    if not token:
        output["status"] = "blocked"
        output["error"] = f"Missing token env: {token_env}"
        return output
    if not endpoint:
        output["status"] = "blocked"
        output["error"] = f"Missing endpoint env: {endpoint_env}"
        return output

    payload = {
        "platform": platform,
        "post_id": output.get("post_id"),
        "video_file": output.get("video_file"),
        "caption": output.get("caption", ""),
        "language": output.get("language", "en"),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    timeout_seconds = parse_env_int("SOCIALAUTOPOST_AUTOPOST_TIMEOUT_SEC", 20, minimum=5, maximum=120)
    max_retries = parse_env_int("SOCIALAUTOPOST_AUTOPOST_RETRIES", 2, minimum=0, maximum=5)
    idempotency_key = str(output.get("post_id") or f"{platform}_{int(time.time())}")
    signing_secret_env = autopost_signing_secret_env(platform)
    signing_secret = os.environ.get(signing_secret_env, "").strip() if signing_secret_env else ""
    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {token}",
        "User-Agent": "SocialAutoPostLocal/0.1",
        "X-Idempotency-Key": idempotency_key,
        "X-Timestamp": timestamp,
    }
    if signing_secret:
        headers["X-Signature"] = build_webhook_signature(signing_secret, timestamp, body)
    attempt = 0
    while attempt <= max_retries:
        request = Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                output["status"] = "posted"
                output["http_status"] = int(getattr(response, "status", 200))
                output["response_preview"] = normalize_caption_text(response_body, 220)
                output.update(extract_remote_post_fields(response_body))
                output["attempt"] = attempt + 1
                return output
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
            output["http_status"] = int(exc.code)
            output["error"] = normalize_caption_text(error_body, 220)
            output["attempt"] = attempt + 1
            if exc.code in {429, 500, 502, 503, 504} and attempt < max_retries:
                time.sleep((attempt + 1) * 1.2)
                attempt += 1
                continue
            output["status"] = "failed"
            return output
        except URLError as exc:
            output["error"] = str(exc.reason)
            output["attempt"] = attempt + 1
            if attempt < max_retries:
                time.sleep((attempt + 1) * 1.2)
                attempt += 1
                continue
            output["status"] = "failed"
            return output
        except Exception as exc:
            output["status"] = "failed"
            output["error"] = str(exc)
            output["attempt"] = attempt + 1
            return output
    return output


def autopost_send_youtube_shorts_native(base_result: dict[str, object]) -> dict[str, object]:
    output = dict(base_result)
    token = get_youtube_shorts_access_token()
    if not token:
        output["status"] = "blocked"
        output["error"] = "Missing usable YouTube Shorts access token or refresh-token configuration"
        return output

    video_file = str(output.get("video_file", "")).strip()
    if not video_file:
        output["status"] = "failed"
        output["error"] = "Missing video file"
        return output
    video_path = ROOT / video_file
    if not video_path.exists():
        output["status"] = "failed"
        output["error"] = f"Video file not found: {video_file}"
        return output

    title = normalize_caption_text(str(output.get("caption", "")).splitlines()[0].strip() or "SocialAutoPost Short", 100)
    description = normalize_caption_text(str(output.get("caption", "")).strip(), 5000)
    privacy_status = os.environ.get("SOCIALAUTOPOST_SHORTS_PRIVACY_STATUS", "private").strip().lower() or "private"
    category_id = os.environ.get("SOCIALAUTOPOST_SHORTS_CATEGORY_ID", "22").strip() or "22"
    made_for_kids = os.environ.get("SOCIALAUTOPOST_SHORTS_MADE_FOR_KIDS", "false").strip().lower() in {"1", "true", "yes", "on"}
    timeout_seconds = parse_env_int("SOCIALAUTOPOST_AUTOPOST_TIMEOUT_SEC", 20, minimum=5, maximum=120)

    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }
    session_uri = youtube_start_resumable_upload(token, metadata, video_path, timeout_seconds)
    upload_result = youtube_upload_file_to_session(session_uri, video_path, timeout_seconds)
    output["status"] = "posted"
    output["http_status"] = int(upload_result.get("http_status", 200))
    output["response_preview"] = normalize_caption_text(str(upload_result.get("response_body", "")), 220)
    output.update(extract_remote_post_fields(str(upload_result.get("response_body", ""))))
    return output


def youtube_start_resumable_upload(token: str, metadata: dict[str, object], video_path: Path, timeout_seconds: int) -> str:
    body = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
    mime_type = mimetypes.guess_type(video_path.name)[0] or "application/octet-stream"
    request = Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": str(len(body)),
            "X-Upload-Content-Length": str(video_path.stat().st_size),
            "X-Upload-Content-Type": mime_type,
            "User-Agent": "SocialAutoPostLocal/0.1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            session_uri = response.headers.get("Location", "").strip()
            if not session_uri:
                raise RuntimeError("YouTube upload session did not return a Location header")
            return session_uri
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        raise RuntimeError(f"YouTube session init failed ({exc.code}): {normalize_caption_text(error_body, 220)}") from exc
    except URLError as exc:
        raise RuntimeError(f"YouTube session init failed: {exc.reason}") from exc


def youtube_upload_file_to_session(session_uri: str, video_path: Path, timeout_seconds: int) -> dict[str, object]:
    mime_type = mimetypes.guess_type(video_path.name)[0] or "application/octet-stream"
    body = video_path.read_bytes()
    request = Request(
        session_uri,
        data=body,
        headers={
            "Content-Type": mime_type,
            "Content-Length": str(len(body)),
        },
        method="PUT",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return {
                "http_status": int(getattr(response, "status", 200)),
                "response_body": response.read().decode("utf-8", errors="replace"),
            }
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        raise RuntimeError(f"YouTube upload failed ({exc.code}): {normalize_caption_text(error_body, 220)}") from exc
    except URLError as exc:
        raise RuntimeError(f"YouTube upload failed: {exc.reason}") from exc


def get_youtube_shorts_access_token() -> str:
    token_env = autopost_token_env("shorts")
    direct_token = os.environ.get(token_env, "").strip()
    expires_at = parse_env_float("SOCIALAUTOPOST_SHORTS_TOKEN_EXPIRES_AT", 0.0)
    now = time.time()
    if direct_token and (expires_at <= 0 or now < expires_at - 60):
        return direct_token

    cached = load_youtube_shorts_token_cache()
    cached_token = str(cached.get("access_token", "")).strip()
    cached_expires_at = float(cached.get("expires_at", 0.0) or 0.0)
    if cached_token and now < cached_expires_at - 60:
        return cached_token

    refresh_token = os.environ.get("SOCIALAUTOPOST_SHORTS_REFRESH_TOKEN", "").strip()
    client_id = os.environ.get("SOCIALAUTOPOST_SHORTS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SOCIALAUTOPOST_SHORTS_CLIENT_SECRET", "").strip()
    if not (refresh_token and client_id and client_secret):
        return direct_token

    refreshed = refresh_google_access_token(refresh_token, client_id, client_secret)
    access_token = str(refreshed.get("access_token", "")).strip()
    expires_in = float(refreshed.get("expires_in", 0.0) or 0.0)
    if access_token and expires_in > 0:
        save_youtube_shorts_token_cache(
            {
                "access_token": access_token,
                "expires_at": time.time() + expires_in,
                "token_type": refreshed.get("token_type", "Bearer"),
                "scope": refreshed.get("scope", ""),
            }
        )
    return access_token


def youtube_shorts_token_cache_path() -> Path:
    OAUTH_ROOT.mkdir(parents=True, exist_ok=True)
    return OAUTH_ROOT / "shorts.token.json"


def load_youtube_shorts_token_cache() -> dict[str, object]:
    path = youtube_shorts_token_cache_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_youtube_shorts_token_cache(payload: dict[str, object]) -> None:
    path = youtube_shorts_token_cache_path()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh_google_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict[str, object]:
    body_text = (
        f"client_id={urlencode_value(client_id)}&"
        f"client_secret={urlencode_value(client_secret)}&"
        f"refresh_token={urlencode_value(refresh_token)}&"
        "grant_type=refresh_token"
    )
    body = body_text.encode("utf-8")
    request = Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(body)),
            "User-Agent": "SocialAutoPostLocal/0.1",
        },
        method="POST",
    )
    timeout_seconds = parse_env_int("SOCIALAUTOPOST_AUTOPOST_TIMEOUT_SEC", 20, minimum=5, maximum=120)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
            if not isinstance(payload, dict):
                raise RuntimeError("Google token endpoint returned invalid JSON")
            return payload
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        raise RuntimeError(f"Google token refresh failed ({exc.code}): {normalize_caption_text(error_body, 220)}") from exc
    except URLError as exc:
        raise RuntimeError(f"Google token refresh failed: {exc.reason}") from exc


def urlencode_value(value: str) -> str:
    return quote(value, safe="")


def parse_env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def parse_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def create_transcription_artifacts(job_id: str, source_video: Path, job_dir: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    update_job(job_id, step="Extracting audio", progress=86)
    audio_path = job_dir / "audio.wav"
    try:
        run_command(
            job_id,
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source_video),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(audio_path),
            ],
            job_dir,
        )
        files["audio"] = rel_path(audio_path)
    except Exception as exc:
        error_path = job_dir / "transcription.error.txt"
        error_path.write_text(f"Audio extraction failed:\n{exc}", encoding="utf-8")
        append_log(job_id, f"Transcription skipped: {exc}")
        files["transcription_error"] = rel_path(error_path)
        return files

    update_job(job_id, step="Transcribing audio", progress=88)
    try:
        segments = transcribe_audio(job_id, audio_path)
        transcript_path = job_dir / "transcript.txt"
        srt_path = job_dir / "captions.srt"
        transcript_path.write_text("\n".join(segment["text"] for segment in segments).strip() + "\n", encoding="utf-8")
        srt_path.write_text(format_srt(segments), encoding="utf-8")
        files["transcript"] = rel_path(transcript_path)
        files["captions"] = rel_path(srt_path)
    except Exception as exc:
        error_path = job_dir / "transcription.error.txt"
        error_path.write_text(f"Transcription failed:\n{exc}", encoding="utf-8")
        append_log(job_id, f"Transcription failed: {exc}")
        files["transcription_error"] = rel_path(error_path)
    return files


def transcribe_audio(job_id: str, audio_path: Path) -> list[dict[str, object]]:
    model_name = os.environ.get("SOCIALAUTOPOST_WHISPER_MODEL", "tiny")
    append_log(job_id, f"Loading faster-whisper model: {model_name}")
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    raw_segments, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        vad_filter=True,
    )
    language = getattr(info, "language", "unknown")
    append_log(job_id, f"Detected language: {language}")
    segments: list[dict[str, object]] = []
    for segment in raw_segments:
        text = segment.text.strip()
        if text:
            segments.append({"start": float(segment.start), "end": float(segment.end), "text": text})
    if not segments:
        segments.append({"start": 0.0, "end": 1.0, "text": "[No speech detected]"})
    return segments


def format_srt(segments: list[dict[str, object]]) -> str:
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        start = format_srt_time(float(segment["start"]))
        end = format_srt_time(float(segment["end"]))
        text = str(segment["text"])
        blocks.append(f"{index}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


def format_srt_time(seconds: float) -> str:
    milliseconds = int(round(max(0.0, seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def create_highlight_artifacts(
    job_id: str,
    source_video: Path,
    job_dir: Path,
    current_files: dict[str, str],
    duration: float | None,
    target_length: int,
) -> dict[str, str]:
    update_job(job_id, step="Creating highlight clips", progress=93)
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(exist_ok=True)

    windows = choose_highlight_windows(job_dir, duration, target_length)
    manifest_items: list[dict[str, object]] = []
    files: dict[str, str] = {}

    for index, window in enumerate(windows, start=1):
        clip_path = clips_dir / f"clip_{index:02}.mp4"
        run_command(
            job_id,
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{window['start']:.3f}",
                "-t",
                f"{window['duration']:.3f}",
                "-i",
                str(source_video),
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-movflags",
                "+faststart",
                str(clip_path),
            ],
            job_dir,
        )
        label = f"highlight_clip_{index:02}"
        files[label] = rel_path(clip_path)
        caption_path = clips_dir / f"clip_{index:02}.caption.txt"
        clip_caption = build_clip_caption(index, window)
        caption_path.write_text(clip_caption, encoding="utf-8")
        files[f"highlight_caption_{index:02}"] = rel_path(caption_path)
        manifest_items.append(
            {
                "file": rel_path(clip_path),
                "caption_file": rel_path(caption_path),
                "start": round(float(window["start"]), 3),
                "end": round(float(window["end"]), 3),
                "duration": round(float(window["duration"]), 3),
                "reason": window["reason"],
                "text": window.get("text", ""),
                "score": round(float(window.get("score", 0.0)), 3),
                "score_breakdown": window.get("score_breakdown", []),
                "caption": clip_caption,
            }
        )

    highlights_path = job_dir / "highlights.json"
    highlights_path.write_text(json.dumps(manifest_items, ensure_ascii=False, indent=2), encoding="utf-8")
    files["highlights"] = rel_path(highlights_path)
    return files


def choose_highlight_windows(job_dir: Path, duration: float | None, target_length: int) -> list[dict[str, object]]:
    target_length = max(5, min(60, int(target_length or 15)))
    srt_path = job_dir / "captions.srt"
    if srt_path.exists():
        segments = parse_srt_segments(srt_path.read_text(encoding="utf-8", errors="replace"))
        speech_segments = [segment for segment in segments if segment["text"] != "[No speech detected]"]
        if speech_segments:
            scored = score_transcript_segments(speech_segments, duration, target_length)
            ranked = sorted(scored, key=lambda item: float(item["score"]), reverse=True)
            windows: list[dict[str, object]] = []
            for segment in ranked:
                start, end = build_window_bounds(segment, duration, target_length)
                if is_overlapping_existing(windows, start, end):
                    continue
                windows.append(
                    {
                        "start": start,
                        "end": end,
                        "duration": max(1.0, end - start),
                        "reason": segment["reason"],
                        "text": segment["text"],
                        "score": segment["score"],
                        "score_breakdown": segment["score_breakdown"],
                    }
                )
                if len(windows) >= 3:
                    break
            if windows:
                return sorted(windows, key=lambda item: float(item["start"]))

    total = float(duration or target_length)
    windows = []
    start = 0.0
    for _ in range(min(3, max(1, int((total + target_length - 1) // target_length)))):
        end = min(total, start + target_length)
        if end <= start:
            break
        windows.append(
            {
                "start": start,
                "end": end,
                "duration": end - start,
                "reason": "fallback timed clip",
                "text": "",
            }
        )
        start = end
    return windows or [
        {
            "start": 0.0,
            "end": 1.0,
            "duration": 1.0,
            "reason": "fallback opening clip",
            "text": "",
        }
    ]


def is_overlapping_existing(windows: list[dict[str, object]], start: float, end: float) -> bool:
    for window in windows:
        existing_start = float(window["start"])
        existing_end = float(window["end"])
        if start < existing_end and end > existing_start:
            return True
    return False


def build_clip_caption(index: int, window: dict[str, object]) -> str:
    text = normalize_caption_text(str(window.get("text") or "").strip())
    heading = f"Clip {index:02}"
    body = text if text else "Short highlight clip."
    return (
        f"{heading}\n\n"
        f"{body}\n\n"
        "#Shorts #Reels #TikTok\n\n"
        "Check usage rights before reposting."
    )


def min_duration_end(candidate_end: float, total_duration: float | None) -> float:
    if total_duration is None:
        return max(1.0, candidate_end)
    return min(float(total_duration), max(1.0, candidate_end))


def parse_srt_segments(content: str) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start_raw, end_raw = [part.strip() for part in lines[1].split("-->", 1)]
        text = " ".join(lines[2:]).strip()
        segments.append(
            {
                "start": parse_srt_time(start_raw),
                "end": parse_srt_time(end_raw),
                "text": text,
            }
        )
    return segments


def score_transcript_segments(
    segments: list[dict[str, object]],
    duration: float | None,
    target_length: int,
) -> list[dict[str, object]]:
    scored: list[dict[str, object]] = []
    transcript_end = max((float(segment["end"]) for segment in segments), default=float(target_length))
    total_duration = float(duration or max(float(target_length), transcript_end))
    for segment in segments:
        text = str(segment["text"]).strip()
        if not text:
            continue
        score, reasons = score_transcript_text(text, float(segment["start"]), float(segment["end"]), total_duration, target_length)
        scored.append(
            {
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "text": text,
                "score": score,
                "score_breakdown": reasons,
                "reason": "transcript segment scoring",
            }
        )
    return scored


def score_transcript_text(
    text: str,
    start: float,
    end: float,
    total_duration: float,
    target_length: int,
) -> tuple[float, list[dict[str, object]]]:
    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9']+", lowered)
    token_count = len(tokens)
    char_count = len(text)
    score = 0.0
    breakdown: list[dict[str, object]] = []

    def add(label: str, value: float) -> None:
        nonlocal score
        if value == 0:
            return
        score += value
        breakdown.append({"label": label, "value": round(value, 3)})

    if token_count <= 6:
        add("too_short_penalty", -0.6)
    elif token_count <= 14:
        add("compact_length_bonus", 0.8)
    elif token_count <= 28:
        add("balanced_length_bonus", 1.0)
    else:
        add("long_text_bonus", 0.4)

    if char_count >= 18:
        add("substantial_text_bonus", min(1.0, char_count / 120.0))

    keyword_weights = {
        "why": 0.7,
        "how": 0.6,
        "what": 0.5,
        "because": 0.7,
        "breaking": 1.0,
        "news": 0.7,
        "update": 0.6,
        "important": 0.7,
        "insane": 0.8,
        "crazy": 0.7,
        "amazing": 0.6,
        "huge": 0.6,
        "goal": 0.8,
        "win": 0.8,
        "final": 0.8,
        "must": 0.5,
        "should": 0.4,
        "can't": 0.5,
        "cannot": 0.5,
        "won't": 0.5,
        "vs": 0.5,
        "fix": 0.6,
        "problem": 0.6,
        "warning": 0.6,
        "cook": 0.8,
        "arsenal": 0.5,
        "psg": 0.5,
    }
    keyword_hits: list[str] = []
    for word, weight in keyword_weights.items():
        if word in lowered:
            keyword_hits.append(word)
            add(f"keyword:{word}", weight)

    if "?" in text:
        add("question_bonus", 0.7)
    if "!" in text or "‼" in text:
        add("excitement_bonus", 0.5)
    if ":" in text or "—" in text or "-" in text:
        add("structure_bonus", 0.3)
    if text.count('"') >= 2 or text.count("'") >= 2:
        add("quote_bonus", 0.2)

    uppercase_words = sum(1 for token in text.split() if len(token) > 2 and token.isupper())
    if uppercase_words:
        add("emphasis_bonus", min(0.6, uppercase_words * 0.15))

    position = ((start + end) / 2.0) / max(total_duration, 1.0)
    position_bonus = 1.0 - abs(position - 0.35) * 0.9
    add("position_bonus", max(0.0, position_bonus))

    window_span = max(0.1, end - start)
    duration_ratio = min(2.0, window_span / max(float(target_length), 1.0))
    if 0.75 <= duration_ratio <= 1.35:
        add("target_length_fit", 0.6)
    elif duration_ratio < 0.75:
        add("short_segment_penalty", -0.4)
    else:
        add("long_segment_penalty", -0.2)

    if keyword_hits and token_count >= 5:
        add("keyword_density_bonus", min(0.7, len(keyword_hits) * 0.12))

    return score, breakdown


def build_window_bounds(segment: dict[str, object], duration: float | None, target_length: int) -> tuple[float, float]:
    total = float(duration or max(float(target_length), float(segment["end"]) + 1.0))
    target_length = max(5, min(60, int(target_length or 15)))
    segment_start = max(0.0, float(segment["start"]))
    segment_end = max(segment_start + 0.5, float(segment["end"]))

    margin = 0.9 if target_length <= 15 else 1.2 if target_length <= 30 else 1.5
    start = max(0.0, segment_start - margin)
    end = min(total, max(segment_end + margin, start + target_length))

    if end - start < target_length and total >= target_length:
        shift_left = min(start, target_length - (end - start))
        start -= shift_left
        end = min(total, start + target_length)

    if end <= start:
        end = min(total, start + 1.0)

    return start, end


def normalize_caption_text(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return text


def parse_srt_time(value: str) -> float:
    match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", value)
    if not match:
        return 0.0
    hours, minutes, seconds, millis = [int(part) for part in match.groups()]
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def parse_highlight_length(value: object) -> int:
    try:
        length = int(value)
    except (TypeError, ValueError):
        return 15
    if length not in {15, 30, 60}:
        return 15
    return length


def parse_multipart_form(headers: object, body: bytes) -> tuple[dict[str, str], dict[str, object]]:
    content_type = headers.get("content-type", "")
    raw_message = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n"
        "\r\n"
    ).encode("utf-8") + body
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    fields: dict[str, str] = {}
    file_data: dict[str, object] = {}
    if not message.is_multipart():
        raise ValueError("Expected multipart form data")
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename:
            file_data = {"field": name, "filename": filename, "content": payload}
        else:
            charset = part.get_content_charset() or "utf-8"
            fields[name] = payload.decode(charset, errors="replace")
    return fields, file_data


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


def build_caption(title: str, uploader: str, category: str, url: str) -> str:
    tag_map = {
        "short": ["#Shorts", "#ShortClip"],
        "funny": ["#Funny", "#Clip"],
        "news": ["#News", "#Update"],
        "other": ["#Video", "#Social"],
    }
    tags = " ".join(tag_map.get(category, tag_map["other"]))
    return (
        f"{title}\n\n"
        f"Source: {uploader}\n"
        f"{tags}\n\n"
        f"Original: {url}\n"
        "Check usage rights before reposting."
    )


def build_platform_captions(title: str, uploader: str, category: str, source: str) -> dict[str, dict[str, str]]:
    tag_map = {
        "short": {
            "tiktok": "#fyp #viral #shortvideo",
            "reels": "#reels #reelsvideo #instareels",
            "shorts": "#shorts #youtubeshorts #shortvideo",
        },
        "funny": {
            "tiktok": "#funny #comedy #fyp",
            "reels": "#funnyreels #comedy #reels",
            "shorts": "#funny #shorts #comedy",
        },
        "news": {
            "tiktok": "#news #update #fyp",
            "reels": "#news #reels #update",
            "shorts": "#news #shorts #update",
        },
        "other": {
            "tiktok": "#video #fyp #social",
            "reels": "#reels #video #social",
            "shorts": "#shorts #video #social",
        },
    }
    tags = tag_map.get(category, tag_map["other"])
    clean_title = normalize_caption_text(title, 120)

    return {
        "tiktok": {
            "en": (
                f"{clean_title}\n\n"
                "Watch till the end and share your take.\n"
                f"{tags['tiktok']}\n\n"
                f"Source: {uploader}\n"
                f"Original: {source}"
            ),
            "th": (
                f"{clean_title}\n\n"
                "ดูจนจบแล้วคอมเมนต์ความเห็นได้เลย\n"
                f"{tags['tiktok']}\n\n"
                f"ที่มา: {uploader}\n"
                f"ต้นฉบับ: {source}"
            ),
        },
        "reels": {
            "en": (
                f"{clean_title}\n\n"
                "Save this reel and send it to a friend.\n"
                f"{tags['reels']}\n\n"
                f"Source: {uploader}\n"
                f"Original: {source}"
            ),
            "th": (
                f"{clean_title}\n\n"
                "เซฟคลิปนี้แล้วส่งต่อให้เพื่อนได้เลย\n"
                f"{tags['reels']}\n\n"
                f"ที่มา: {uploader}\n"
                f"ต้นฉบับ: {source}"
            ),
        },
        "shorts": {
            "en": (
                f"{clean_title}\n\n"
                "Title: {clean_title}\n"
                f"Description: Quick short clip with context.\n{tags['shorts']}\n\n"
                f"Source: {uploader}\n"
                f"Original: {source}"
            ),
            "th": (
                f"{clean_title}\n\n"
                f"ชื่อคลิป: {clean_title}\n"
                f"คำอธิบาย: สรุปสั้นกระชับ พร้อมบริบทสำคัญ\n{tags['shorts']}\n\n"
                f"ที่มา: {uploader}\n"
                f"ต้นฉบับ: {source}"
            ),
        },
    }


class AppHandler(BaseHTTPRequestHandler):
    server_version = "SocialAutoPostLocal/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/jobs":
            self.send_json(list_jobs())
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            job = get_job(job_id)
            if not job:
                self.send_json({"error": "Job not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(job)
            return
        if parsed.path.startswith("/files/"):
            self.send_file(ROOT / unquote(parsed.path.removeprefix("/files/")))
            return
        self.send_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/jobs/upload":
            self.handle_upload_job()
            return
        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/autopost/retry"):
            job_id = parsed.path.split("/")[-3]
            self.handle_autopost_retry(job_id)
            return
        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/autopost/pause"):
            job_id = parsed.path.split("/")[-3]
            self.handle_autopost_pause(job_id)
            return
        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/autopost/resume"):
            job_id = parsed.path.split("/")[-3]
            self.handle_autopost_resume(job_id)
            return
        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/autopost"):
            job_id = parsed.path.split("/")[-2]
            self.handle_autopost(job_id)
            return
        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/open-folder"):
            job_id = parsed.path.split("/")[-2]
            self.handle_open_folder(job_id)
            return
        if parsed.path != "/api/jobs":
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self.read_json()
            url = str(payload.get("url", "")).strip()
            category = str(payload.get("category", "short"))
            browser = str(payload.get("browser", "none"))
            normalize = bool(payload.get("normalize", True))
            transcribe = bool(payload.get("transcribe", False))
            highlights = bool(payload.get("highlights", False))
            highlight_length = parse_highlight_length(payload.get("highlight_length", 15))
            rights_confirmed = bool(payload.get("rights_confirmed", False))
            validate_source_url(url)
            if category not in {"short", "funny", "news", "other"}:
                category = "other"
            if browser not in {"auto", "none", "firefox", "chrome", "edge"}:
                browser = "auto"
            if not rights_confirmed:
                raise ValueError("Please confirm you own this content or have permission to reuse it")
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        job = Job(
            id=uuid.uuid4().hex[:12],
            url=url,
            category=category,
            browser=browser,
            normalize=normalize,
            transcribe=transcribe,
            highlights=highlights,
            highlight_length=highlight_length,
            rights_confirmed=rights_confirmed,
        )
        with jobs_lock:
            jobs[job.id] = job
        save_jobs()
        threading.Thread(target=process_job, args=(job.id,), daemon=True).start()
        self.send_json(asdict(job), HTTPStatus.CREATED)

    def handle_upload_job(self) -> None:
        try:
            content_length = int(self.headers.get("content-length", "0"))
            if content_length <= 0:
                raise ValueError("Upload body is empty")
            if content_length > MAX_UPLOAD_BYTES:
                max_mb = MAX_UPLOAD_BYTES // 1024 // 1024
                raise ValueError(f"Upload is too large. Max size is {max_mb} MB")

            body = self.rfile.read(content_length)
            fields, file_item = parse_multipart_form(self.headers, body)
            if file_item.get("field") != "file" or not file_item.get("filename"):
                raise ValueError("Missing video file")

            original_name = safe_filename(Path(str(file_item["filename"])).name, "upload.mp4")
            extension = Path(original_name).suffix.lower()
            if extension not in ALLOWED_UPLOAD_EXTENSIONS:
                allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
                raise ValueError(f"Unsupported file type. Allowed: {allowed}")

            category = str(fields.get("category", "short"))
            if category not in {"short", "funny", "news", "other"}:
                category = "other"
            normalize = str(fields.get("normalize", "true")).lower() in {"1", "true", "yes", "on"}
            transcribe = str(fields.get("transcribe", "false")).lower() in {"1", "true", "yes", "on"}
            highlights = str(fields.get("highlights", "false")).lower() in {"1", "true", "yes", "on"}
            highlight_length = parse_highlight_length(fields.get("highlight_length", "15"))
            rights_confirmed = str(fields.get("rights_confirmed", "false")).lower() in {"1", "true", "yes", "on"}
            if not rights_confirmed:
                raise ValueError("Please confirm you own this content or have permission to reuse it")

            job = Job(
                id=uuid.uuid4().hex[:12],
                url=f"local file: {original_name}",
                category=category,
                browser="none",
                normalize=normalize,
                transcribe=transcribe,
                highlights=highlights,
                highlight_length=highlight_length,
                rights_confirmed=rights_confirmed,
                source_type="file",
                source_file=original_name,
            )
            job_dir = JOBS_ROOT / job.id
            job_dir.mkdir(parents=True, exist_ok=True)
            upload_path = job_dir / original_name
            upload_path.write_bytes(bytes(file_item["content"]))

            with jobs_lock:
                jobs[job.id] = job
            save_jobs()
            threading.Thread(target=process_job, args=(job.id,), daemon=True).start()
            self.send_json(asdict(job), HTTPStatus.CREATED)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def handle_autopost(self, job_id: str) -> None:
        try:
            payload = self.read_json()
            operator = resolve_operator(self.headers, payload)
            dry_run = bool(payload.get("dry_run", True))
            language = str(payload.get("language", "en")).lower()
            if language not in {"en", "th"}:
                language = "en"
            raw_platforms = payload.get("platforms", ["tiktok", "reels", "shorts"])
            if not isinstance(raw_platforms, list):
                raise ValueError("platforms must be a list")
            platforms = [str(item).lower() for item in raw_platforms if str(item).lower() in {"tiktok", "reels", "shorts"}]
            if not platforms:
                platforms = ["tiktok", "reels", "shorts"]

            with jobs_lock:
                job = jobs.get(job_id)
            if not job:
                self.send_json({"error": "Job not found"}, HTTPStatus.NOT_FOUND)
                return
            if job.status != "done":
                raise ValueError("Job is not ready yet")
            if job.autopost_status == "running":
                raise ValueError("Autopost is already running")

            update_job(
                job_id,
                autopost_status="running",
                autopost_report={
                    "status": "running",
                    "started_at": time.time(),
                    "platforms": platforms,
                    "dry_run": dry_run,
                    "language": language,
                    "operator": operator,
                },
            )
            threading.Thread(
                target=run_autopost_task,
                args=(job_id, platforms, language, dry_run),
                daemon=True,
            ).start()
            self.send_json({"ok": True, "status": "running"})
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def handle_autopost_pause(self, job_id: str) -> None:
        try:
            operator = resolve_operator(self.headers, None)
            with jobs_lock:
                job = jobs.get(job_id)
            if not job:
                self.send_json({"error": "Job not found"}, HTTPStatus.NOT_FOUND)
                return
            control_path = JOBS_ROOT / job_id / "autopost.control.json"
            write_autopost_control(control_path, "paused")
            audit_path = JOBS_ROOT / job_id / "autopost.audit.jsonl"
            append_audit_event(audit_path, "operator_pause", {"job_id": job_id, "operator": operator})
            update_job(job_id, autopost_control="paused")
            self.send_json({"ok": True, "control": "paused"})
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def handle_autopost_resume(self, job_id: str) -> None:
        try:
            operator = resolve_operator(self.headers, None)
            with jobs_lock:
                job = jobs.get(job_id)
            if not job:
                self.send_json({"error": "Job not found"}, HTTPStatus.NOT_FOUND)
                return
            control_path = JOBS_ROOT / job_id / "autopost.control.json"
            write_autopost_control(control_path, "active")
            audit_path = JOBS_ROOT / job_id / "autopost.audit.jsonl"
            append_audit_event(audit_path, "operator_resume", {"job_id": job_id, "operator": operator})
            update_job(job_id, autopost_control="active")
            self.send_json({"ok": True, "control": "active"})
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def handle_autopost_retry(self, job_id: str) -> None:
        try:
            operator = resolve_operator(self.headers, None)
            with jobs_lock:
                job = jobs.get(job_id)
            if not job:
                self.send_json({"error": "Job not found"}, HTTPStatus.NOT_FOUND)
                return
            if job.autopost_status == "running":
                raise ValueError("Autopost is already running")
            report = job.autopost_report if isinstance(job.autopost_report, dict) else {}
            prior_results = report.get("results", [])
            retry_targets = [
                {
                    "clip_index": int(item.get("clip_index", 0)),
                    "platform": str(item.get("platform", "")).lower(),
                    "language": str(item.get("language", "en")).lower(),
                }
                for item in prior_results
                if str(item.get("delivery_state", "")).lower() in {"failed", "blocked"}
            ]
            if not retry_targets:
                raise ValueError("No failed or blocked deliveries to retry")

            update_job(
                job_id,
                autopost_status="running",
                autopost_control="active",
                autopost_report={
                    "status": "running",
                    "started_at": time.time(),
                    "retry": True,
                    "retry_count": len(retry_targets),
                    "operator": operator,
                },
            )
            audit_path = JOBS_ROOT / job_id / "autopost.audit.jsonl"
            append_audit_event(audit_path, "operator_retry", {"job_id": job_id, "retry_count": len(retry_targets), "operator": operator})
            threading.Thread(target=run_autopost_retry_task, args=(job_id, retry_targets), daemon=True).start()
            self.send_json({"ok": True, "status": "running", "retry_count": len(retry_targets)})
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def handle_open_folder(self, job_id: str) -> None:
        try:
            with jobs_lock:
                job = jobs.get(job_id)
            if not job:
                self.send_json({"error": "Job not found"}, HTTPStatus.NOT_FOUND)
                return

            job_dir = (JOBS_ROOT / job_id).resolve()
            jobs_root = JOBS_ROOT.resolve()
            if not str(job_dir).startswith(str(jobs_root)) or not job_dir.exists():
                self.send_json({"error": "Job folder not found"}, HTTPStatus.NOT_FOUND)
                return

            if os.name == "nt":
                subprocess.Popen(["explorer", str(job_dir)])
            else:
                opener = shutil.which("xdg-open") or shutil.which("open")
                if not opener:
                    raise RuntimeError("No folder opener was found for this OS")
                subprocess.Popen([opener, str(job_dir)])
            self.send_json({"ok": True, "path": str(job_dir)})
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def read_json(self) -> dict[str, object]:
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def send_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
        if not str(file_path).startswith(str(ROOT)):
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
        print(f"{self.address_string()} - {format % args}")


def list_jobs() -> list[dict[str, object]]:
    with jobs_lock:
        return [asdict(job) for job in sorted(jobs.values(), key=lambda item: item.created_at, reverse=True)]


def get_job(job_id: str) -> dict[str, object] | None:
    with jobs_lock:
        job = jobs.get(job_id)
        return asdict(job) if job else None


def main() -> None:
    if not shutil.which("yt-dlp"):
        raise SystemExit("yt-dlp was not found in PATH")
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg was not found in PATH")
    load_jobs()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), AppHandler)
    print(f"SocialAutoPost local web: http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
