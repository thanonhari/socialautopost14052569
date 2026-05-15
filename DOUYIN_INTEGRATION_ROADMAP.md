# Douyin Native Adapter Integration Roadmap

## Objective
Enhance the SocialAutoPost project by integrating a custom "Douyin Native Adapter" inspired by the `Evil0ctal/Douyin_TikTok_Download_API` project. This will bypass `yt-dlp` cookie limitations, enable watermark-free downloads, and utilize direct API access for Douyin (`v.douyin.com`, `douyin.com`) links.

## Architectural Approach
We will use a **Platform Adapter Pattern**:
- If URL is YouTube/Reddit/X -> use `yt-dlp` (existing pipeline).
- If URL is Douyin -> use `DouyinNativeAdapter` (new pipeline).
- The adapter will fetch the raw video URL (no-watermark) and metadata, then pass it to the existing GPU-accelerated FFmpeg/Whisper pipeline.

---

## Step 1: Environment & Dependencies
- [x] Create a requirements check for `httpx` (for async API requests) and `PyExecJS` / `js2py` (if JavaScript execution is needed for X-Bogus signature).
- [x] Document how the user should provide initial `ttwid` or `msToken` cookies in a configuration file (e.g., `storage/config/douyin_config.json`).
- [x] Verify JS runtime availability (Node.js) on the host machine for executing signature scripts.

## Step 2: Core Extraction Logic (`douyin_adapter.py`)
- [ ] **Short Link Resolver:** Implement logic to resolve `v.douyin.com` short links to full canonical URLs to extract the `item_id`.
- [ ] **Signature Generation:** Implement or integrate the X-Bogus / A-Bogus signature generation required by the Douyin Web API.
- [ ] **API Client:** Create a function to query `https://www.douyin.com/aweme/v1/web/aweme/detail/` using the `item_id` and required headers/signatures.
- [ ] **Data Parsing:** Extract the watermark-free video URL (`play_addr`), title, uploader name, and duration from the JSON response.
- [ ] **Download Function:** Implement a direct download function (using `httpx` or `requests`) to save the `source.mp4` to the job directory.

## Step 3: Application Integration (`app.py`)
- [ ] Import `douyin_adapter.py` into `app.py`.
- [ ] Modify `process_job` to check the URL host:
  - Add routing logic: `if host in {"douyin.com", "v.douyin.com"}: return process_douyin_job(job_id)`
- [ ] Write `process_douyin_job` function:
  - Call `DouyinNativeAdapter.fetch_metadata(url)`
  - Save `source.info.json`
  - Call `DouyinNativeAdapter.download_video(url, dest_path)`
  - Seamlessly hand off the downloaded `source.mp4` to the existing `normalize_video`, `create_transcription_artifacts`, and `create_highlight_artifacts` functions.

## Step 4: Verification & Testing
- [ ] **Test 1 (Metadata):** Verify the adapter can correctly extract the title and `item_id` from a `v.douyin.com` link.
- [ ] **Test 2 (Download):** Verify the adapter downloads a functional, watermark-free `.mp4` file.
- [ ] **Test 3 (End-to-End):** Run a full job through the API (`/api/jobs`). Confirm that GPU normalization (NVENC), GPU transcription (CUDA), and highlight generation work flawlessly with the new Douyin source file.
- [ ] **Test 4 (Cookie Expiry):** Document the behavior when the manual cookie expires and how the user updates it.

---
*Status: Initialized on 2026-05-15. Pending Step 1.*
