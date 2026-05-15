const jobsList = document.querySelector("#jobsList");
const jobDetails = document.querySelector("#jobDetails");
const jobsPanel = document.querySelector(".jobs");
const jobForm = document.querySelector("#jobForm");
const refreshBtn = document.querySelector("#refreshBtn");
const diagnosticsBtn = document.querySelector("#diagnosticsBtn");
const closeDiagnosticsBtn = document.querySelector("#closeDiagnosticsBtn");
const diagnosticsPanel = document.querySelector("#diagnosticsPanel");
const diagnosticsContent = document.querySelector("#diagnosticsContent");
const submitBtn = document.querySelector("#submitBtn");
const operatorInput = document.querySelector("#operatorInput");
const urlInput = document.querySelector("#urlInput");
const fileInput = document.querySelector("#fileInput");
const browserInput = document.querySelector("#browserInput");
const normalizeInput = document.querySelector("#normalizeInput");
const transcribeInput = document.querySelector("#transcribeInput");
const highlightsInput = document.querySelector("#highlightsInput");
const highlightLengthInput = document.querySelector("#highlightLengthInput");
const rightsInput = document.querySelector("#rightsInput");

let selectedJobId = null;
let latestJobs = [];
const selectedPreviewByJob = {};
const selectedManualClipByJob = {};
const selectedManualCaptionByJob = {};
const OPERATOR_STORAGE_KEY = "socialautopost.operator";
const fileTextCache = new Map();
const fileJsonCache = new Map();
const initialQuery = new URLSearchParams(window.location.search);
const compactLayoutQuery = window.matchMedia("(max-width: 980px)");
let jobsPanelCollapsed = false;

if (initialQuery.get("job_id")) {
  selectedJobId = initialQuery.get("job_id");
}

function applyInitialUrlPrefill() {
  const sourceUrl = initialQuery.get("url");
  if (!sourceUrl) return;
  const sourceModeInput = document.querySelector('input[name="sourceMode"][value="url"]');
  if (sourceModeInput) {
    sourceModeInput.checked = true;
  }
  urlInput.value = sourceUrl;
}

function ensureJobsToggle() {
  if (!jobsPanel || jobsPanel.querySelector("[data-jobs-toggle]")) return null;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary jobs-toggle hidden";
  button.dataset.jobsToggle = "true";
  button.addEventListener("click", () => {
    setJobsPanelCollapsed(!jobsPanelCollapsed);
  });
  jobsPanel.insertAdjacentElement("afterbegin", button);
  return button;
}

function jobsToggleButton() {
  return jobsPanel?.querySelector("[data-jobs-toggle]") || ensureJobsToggle();
}

function isCompactLayout() {
  return compactLayoutQuery.matches;
}

function updateJobsToggleState() {
  const button = jobsToggleButton();
  if (!button) return;
  if (!isCompactLayout()) {
    button.classList.add("hidden");
    button.textContent = "แสดงรายการงาน";
    button.setAttribute("aria-expanded", "true");
    return;
  }
  button.classList.remove("hidden");
  button.textContent = jobsPanelCollapsed ? "แสดงรายการงาน" : "ซ่อนรายการงาน";
  button.setAttribute("aria-expanded", String(!jobsPanelCollapsed));
}

function setJobsPanelCollapsed(collapsed) {
  jobsPanelCollapsed = Boolean(collapsed) && isCompactLayout();
  jobsPanel?.classList.toggle("collapsed", jobsPanelCollapsed);
  updateJobsToggleState();
}

function syncUrlState() {
  const next = new URLSearchParams(window.location.search);
  if (selectedJobId) {
    next.set("job_id", selectedJobId);
  } else {
    next.delete("job_id");
  }
  const trimmedUrl = (urlInput?.value || "").trim();
  if (sourceMode() === "url" && trimmedUrl) {
    next.set("url", trimmedUrl);
  } else {
    next.delete("url");
  }
  const nextQuery = next.toString();
  const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`;
  window.history.replaceState(null, "", nextUrl);
}

function currentSection() {
  return new URLSearchParams(window.location.search).get("section") || "";
}

function setSection(section) {
  const next = new URLSearchParams(window.location.search);
  if (section) {
    next.set("section", section);
  } else {
    next.delete("section");
  }
  const nextQuery = next.toString();
  const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`;
  window.history.replaceState(null, "", nextUrl);
}

function scrollToRequestedSection() {
  const section = currentSection();
  if (!section) return;
  const target = jobDetails.querySelector(`[data-section="${section}"]`);
  if (!target) return;
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function copyText(value, button, successLabel, fallbackLabel) {
  try {
    await navigator.clipboard.writeText(value);
    if (button) {
      const original = button.textContent;
      button.textContent = successLabel;
      setTimeout(() => {
        button.textContent = original || fallbackLabel;
      }, 1200);
    }
  } catch (error) {
    console.error(error);
    alert("ไม่สามารถคัดลอกลิงก์ได้");
  }
}

function currentOperator() {
  return (operatorInput?.value || "").trim();
}

function sourceMode() {
  return document.querySelector('input[name="sourceMode"]:checked').value;
}

function syncSourceMode() {
  const mode = sourceMode();
  document.querySelector(".source-url").classList.toggle("hidden", mode !== "url");
  document.querySelector(".source-file").classList.toggle("hidden", mode !== "file");
  document.querySelector(".cookies-field").classList.toggle("hidden", mode !== "url");
  urlInput.required = mode === "url";
  fileInput.required = mode === "file";
  syncUrlState();
}

function syncCompactLayout() {
  if (!isCompactLayout()) {
    setJobsPanelCollapsed(false);
    return;
  }
  updateJobsToggleState();
}

function syncHighlightMode() {
  highlightLengthInput.disabled = !highlightsInput.checked;
}

function formatTime(epoch) {
  return new Date(epoch * 1000).toLocaleString("th-TH", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatDuration(seconds) {
  if (!seconds) return "-";
  const total = Math.round(seconds);
  const mins = Math.floor(total / 60);
  const secs = String(total % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

function yesNo(value) {
  return value ? "พร้อม" : "ไม่พร้อม";
}

function escapeJson(value) {
  return escapeHtml(JSON.stringify(value, null, 2));
}

function statusText(status) {
  return {
    queued: "รอคิว",
    running: "กำลังทำงาน",
    done: "เสร็จแล้ว",
    failed: "ล้มเหลว",
  }[status] || status;
}

function progressValue(job) {
  const raw = Number(job.progress || 0);
  if (Number.isNaN(raw)) return job.status === "done" ? 100 : 0;
  return Math.max(0, Math.min(100, Math.round(raw)));
}

function isVideoPath(path) {
  return /\.(mp4|mov|mkv|webm|m4v)$/i.test(path || "");
}

function previewRank(key) {
  if (key === "source_video") return [0, 0];
  if (key === "normalized_video") return [1, 0];
  const match = key.match(/^highlight_clip_(\d+)$/);
  if (match) return [2, Number(match[1]) || 0];
  return [3, 0];
}

function previewLabel(key) {
  if (key === "source_video") return "วิดีโอต้นฉบับ";
  if (key === "normalized_video") return "วิดีโอที่ปรับแล้ว";
  const match = key.match(/^highlight_clip_(\d+)$/);
  if (match) return `ไฮไลต์ ${match[1]}`;
  return key.replaceAll("_", " ");
}

function previewItemsForJob(job) {
  return Object.entries(job.files || {})
    .filter(([, path]) => isVideoPath(path))
    .map(([key, path]) => ({
      key,
      label: previewLabel(key),
      path,
    }))
    .sort((left, right) => {
      const [leftGroup, leftOrder] = previewRank(left.key);
      const [rightGroup, rightOrder] = previewRank(right.key);
      if (leftGroup !== rightGroup) return leftGroup - rightGroup;
      if (leftOrder !== rightOrder) return leftOrder - rightOrder;
      return left.label.localeCompare(right.label);
    });
}

function exportClipItemsForJob(job) {
  const clips = new Map();
  Object.entries(job.files || {}).forEach(([key, path]) => {
    let match = key.match(/^export_clip_(\d+)$/);
    if (match) {
      const index = Number(match[1]);
      const item = clips.get(index) || { index };
      item.videoPath = path;
      clips.set(index, item);
      return;
    }
    match = key.match(/^export_caption_(\d+)$/);
    if (match) {
      const index = Number(match[1]);
      const item = clips.get(index) || { index };
      item.exportCaptionPath = path;
      clips.set(index, item);
      return;
    }
    match = key.match(/^highlight_caption_(\d+)$/);
    if (match) {
      const index = Number(match[1]);
      const item = clips.get(index) || { index };
      item.highlightCaptionPath = path;
      clips.set(index, item);
    }
  });
  return Array.from(clips.values()).sort((left, right) => left.index - right.index);
}

function manualPostingMarkup(job) {
  const clipItems = exportClipItemsForJob(job);
  if (!clipItems.length) {
    return "";
  }
  const selectedClip = selectedManualClipByJob[job.id] || String(clipItems[0].index);
  return `
    <h2 style="margin-top:16px">โพสต์ด้วยตนเอง</h2>
    <div class="manual-shell" data-manual-shell="1">
      <label class="field">
        <span>คลิป</span>
        <select data-manual-clip>
          ${clipItems
            .map(
              (item) => `
                <option value="${item.index}" ${String(item.index) === String(selectedClip) ? "selected" : ""}>
                  คลิป ${item.index.toString().padStart(2, "0")}
                </option>
              `,
            )
            .join("")}
        </select>
      </label>
      <label class="field">
        <span>ตัวเลือกคำบรรยาย</span>
        <select data-manual-caption>
          <option value="">กำลังโหลดตัวเลือก...</option>
        </select>
      </label>
      <div class="manual-links" data-manual-links>กำลังโหลดไฟล์...</div>
      <div class="mobile-action-bar">
        <div class="mobile-action-bar-title">Manual actions</div>
        <div class="manual-actions">
        <button class="secondary" type="button" data-manual-copy title="คัดลอกคำบรรยายตามที่แสดงในกล่องตัวอย่าง" aria-label="คัดลอกคำบรรยายตามที่แสดง">คัดลอกคำบรรยาย</button>
        <button class="secondary" type="button" data-manual-open title="เปิดวิดีโอคลิปที่เลือกในแท็บใหม่" aria-label="เปิดคลิปที่เลือก">เปิดคลิป</button>
        <button class="secondary" type="button" data-manual-copy-path title="คัดลอก path ของวิดีโอที่เลือก" aria-label="คัดลอก path ของวิดีโอที่เลือก">คัดลอก path วิดีโอ</button>
        <button class="secondary" type="button" data-manual-open-caption title="เปิดไฟล์คำบรรยายที่เลือกเมื่อเป็นตัวเลือกจากไฟล์" aria-label="เปิดไฟล์คำบรรยายที่เลือก">เปิดไฟล์คำบรรยาย</button>
        <button class="secondary" type="button" data-manual-open-folder title="เปิดโฟลเดอร์งานนี้ใน Explorer" aria-label="เปิดโฟลเดอร์งานนี้">เปิดโฟลเดอร์งาน</button>
        <button class="secondary" type="button" data-manual-copy-plain title="คัดลอกคำบรรยายแบบข้อความล้วน" aria-label="คัดลอกคำบรรยายแบบข้อความล้วน">คัดลอกคำบรรยายแบบข้อความล้วน</button>
        </div>
        </div>
      </div>
      <label class="field">
        <span>ตัวอย่างคำบรรยาย</span>
        <textarea class="manual-caption" data-manual-caption-text readonly>กำลังโหลดคำบรรยาย...</textarea>
      </label>
    </div>
  `;
}

async function fetchTextFile(path) {
  if (!path) return "";
  if (fileTextCache.has(path)) return fileTextCache.get(path);
  const response = await fetch(`/files/${encodeURI(path)}`);
  if (!response.ok) throw new Error(`ไม่สามารถอ่านไฟล์ได้: ${path}`);
  const text = await response.text();
  fileTextCache.set(path, text);
  return text;
}

async function fetchJsonFile(path) {
  if (!path) return null;
  if (fileJsonCache.has(path)) return fileJsonCache.get(path);
  const text = await fetchTextFile(path);
  const parsed = JSON.parse(text);
  fileJsonCache.set(path, parsed);
  return parsed;
}

async function manualCaptionOptionsForJob(job, clipIndex) {
  const clipItems = exportClipItemsForJob(job);
  const clip = clipItems.find((item) => item.index === Number(clipIndex)) || clipItems[0];
  const options = [];
  if (!clip) return options;
  if (clip.highlightCaptionPath) {
    options.push({
      key: `clip-${clip.index}`,
      label: `คลิป ${clip.index.toString().padStart(2, "0")} แบบร่าง`,
      type: "file",
      path: clip.highlightCaptionPath,
    });
  }
  if (clip.exportCaptionPath && clip.exportCaptionPath !== clip.highlightCaptionPath) {
    options.push({
      key: `export-${clip.index}`,
      label: `คลิป ${clip.index.toString().padStart(2, "0")} สำหรับส่งออก`,
      type: "file",
      path: clip.exportCaptionPath,
    });
  }
  if (job.files?.platform_captions) {
    try {
      const platformCaptions = await fetchJsonFile(job.files.platform_captions);
      ["tiktok", "reels", "shorts"].forEach((platform) => {
        const variants = platformCaptions?.[platform] || {};
        ["en", "th"].forEach((language) => {
          const text = variants?.[language];
          if (text) {
            options.push({
              key: `${platform}-${language}`,
              label: `${platform} ${language.toUpperCase()}`,
              type: "inline",
              text,
            });
          }
        });
      });
    } catch (error) {
      console.error(error);
    }
  }
  return options;
}

async function renderManualPosting(job) {
  const shell = jobDetails.querySelector("[data-manual-shell]");
  if (!shell) return;
  const clipItems = exportClipItemsForJob(job);
  if (!clipItems.length) return;

  const clipSelect = shell.querySelector("[data-manual-clip]");
  const captionSelect = shell.querySelector("[data-manual-caption]");
  const linksTarget = shell.querySelector("[data-manual-links]");
  const captionText = shell.querySelector("[data-manual-caption-text]");
  const copyButton = shell.querySelector("[data-manual-copy]");
  const openButton = shell.querySelector("[data-manual-open]");
  const copyPathButton = shell.querySelector("[data-manual-copy-path]");
  const openCaptionButton = shell.querySelector("[data-manual-open-caption]");
  const openFolderButton = shell.querySelector("[data-manual-open-folder]");
  const copyPlainButton = shell.querySelector("[data-manual-copy-plain]");

  let currentClip = null;
  let currentOption = null;

  async function updateManualPanel(preferredCaptionKey = null) {
    const selectedClipIndex = Number(clipSelect.value || clipItems[0].index);
    selectedManualClipByJob[job.id] = String(selectedClipIndex);
    const clip = clipItems.find((item) => item.index === selectedClipIndex) || clipItems[0];
    currentClip = clip;
    const options = await manualCaptionOptionsForJob(job, selectedClipIndex);
    let selectedCaption = preferredCaptionKey ?? selectedManualCaptionByJob[job.id];
    if (!options.some((item) => item.key === selectedCaption)) {
      selectedCaption = options[0]?.key || "";
    }
    selectedManualCaptionByJob[job.id] = selectedCaption;

    captionSelect.innerHTML = options.length
      ? options
          .map(
            (item) => `
              <option value="${escapeHtml(item.key)}" ${item.key === selectedCaption ? "selected" : ""}>
                ${escapeHtml(item.label)}
              </option>
            `,
          )
          .join("")
      : '<option value="">ไม่มีตัวเลือกคำบรรยาย</option>';
    captionSelect.value = selectedCaption;

    linksTarget.innerHTML = `
      <a class="file-link" href="/files/${encodeURI(clip.videoPath)}" target="_blank">
        <span>คลิปที่เลือก</span>
        <span>${escapeHtml(clip.videoPath.split("/").pop())}</span>
      </a>
      ${
        clip.exportCaptionPath
          ? `
            <a class="file-link" href="/files/${encodeURI(clip.exportCaptionPath)}" target="_blank">
              <span>คำบรรยายสำหรับส่งออก</span>
              <span>${escapeHtml(clip.exportCaptionPath.split("/").pop())}</span>
            </a>
          `
          : ""
      }
    `;

    currentOption = options.find((item) => item.key === captionSelect.value) || options[0];
    if (!currentOption) {
      captionText.value = "ไม่มีตัวเลือกคำบรรยาย";
      openCaptionButton.disabled = true;
      return;
    }
    selectedManualCaptionByJob[job.id] = currentOption.key;
    openCaptionButton.disabled = currentOption.type !== "file";
    captionText.value =
      currentOption.type === "file" ? await fetchTextFile(currentOption.path) : String(currentOption.text || "");
  }

  clipSelect.addEventListener("change", () => updateManualPanel());
  captionSelect.addEventListener("change", () => updateManualPanel(captionSelect.value));
  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(captionText.value || "");
      copyButton.textContent = "คัดลอกแล้ว";
      setTimeout(() => {
        copyButton.textContent = "คัดลอกคำบรรยาย";
      }, 1200);
    } catch (error) {
      console.error(error);
      alert("ไม่สามารถคัดลอกคำบรรยายได้");
    }
  });
  copyPlainButton.addEventListener("click", async () => {
    try {
      const plain = String(captionText.value || "")
        .replace(/\r\n/g, "\n")
        .replace(/\r/g, "\n");
      await navigator.clipboard.writeText(plain);
      copyPlainButton.textContent = "คัดลอกแล้ว";
      setTimeout(() => {
        copyPlainButton.textContent = "คัดลอกคำบรรยายแบบข้อความล้วน";
      }, 1200);
    } catch (error) {
      console.error(error);
      alert("ไม่สามารถคัดลอกคำบรรยายแบบข้อความล้วนได้");
    }
  });
  openButton.addEventListener("click", () => {
    if (currentClip?.videoPath) {
      window.open(`/files/${encodeURI(currentClip.videoPath)}`, "_blank");
    }
  });
  copyPathButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(currentClip?.videoPath || "");
      copyPathButton.textContent = "คัดลอกแล้ว";
      setTimeout(() => {
        copyPathButton.textContent = "คัดลอก path วิดีโอ";
      }, 1200);
    } catch (error) {
      console.error(error);
      alert("ไม่สามารถคัดลอก path วิดีโอได้");
    }
  });
  openCaptionButton.addEventListener("click", () => {
    if (currentOption?.type === "file" && currentOption.path) {
      window.open(`/files/${encodeURI(currentOption.path)}`, "_blank");
    }
  });
  openFolderButton.addEventListener("click", () => openFolder(job.id, openFolderButton));
  await updateManualPanel();
}

async function fetchJobs() {
  const response = await fetch("/api/jobs");
  latestJobs = await response.json();
  if (selectedJobId && !latestJobs.some((job) => job.id === selectedJobId)) {
    selectedJobId = null;
    setJobsPanelCollapsed(false);
    syncUrlState();
  }
  renderJobs();
  if (selectedJobId) {
    const current = latestJobs.find((job) => job.id === selectedJobId);
    renderDetails(current);
  }
}

function renderJobs() {
  if (!latestJobs.length) {
    jobsList.innerHTML = '<div class="empty">ยังไม่มีงาน</div>';
    return;
  }

  jobsList.innerHTML = latestJobs
    .map((job) => {
      const title = escapeHtml(job.title || job.url);
      const source = job.source_type === "file" ? "ไฟล์ในเครื่อง" : "ลิงก์";
      const progress = progressValue(job);
      return `
        <article class="job-card ${job.id === selectedJobId ? "active" : ""}" data-id="${job.id}">
          <div class="job-head">
            <div class="job-title">${title}</div>
            <span class="badge ${job.status}">${statusText(job.status)}</span>
          </div>
          <div class="progress" aria-label="ความคืบหน้าของงาน">
            <div class="progress-fill ${job.status}" style="width:${progress}%"></div>
          </div>
          <div class="meta">
            ${progress}% · ${escapeHtml(job.step)} · ${escapeHtml(source)} · ${escapeHtml(job.category)} · ${formatDuration(job.duration)}<br />
            ${formatTime(job.created_at)}
          </div>
        </article>
      `;
    })
    .join("");

  document.querySelectorAll(".job-card").forEach((card) => {
    card.addEventListener("click", () => {
      selectedJobId = card.dataset.id;
      syncUrlState();
      renderJobs();
      renderDetails(latestJobs.find((job) => job.id === selectedJobId));
      if (isCompactLayout()) {
        setJobsPanelCollapsed(true);
      }
    });
  });
}

function renderDetails(job) {
  if (!job) {
    jobDetails.innerHTML = '<div class="empty">เลือกงานเพื่อดูไฟล์และบันทึกการทำงาน</div>';
    return;
  }

  if (isCompactLayout()) {
    setJobsPanelCollapsed(true);
  }

  const previewItems = previewItemsForJob(job);
  let selectedPreviewKey = selectedPreviewByJob[job.id];
  if (!previewItems.some((item) => item.key === selectedPreviewKey)) {
    selectedPreviewKey = previewItems[0]?.key || null;
  }
  if (selectedPreviewKey) {
    selectedPreviewByJob[job.id] = selectedPreviewKey;
  }

  const selectedPreview = previewItems.find((item) => item.key === selectedPreviewKey) || previewItems[0] || null;
  const previewMarkup = previewItems.length
    ? `
      <div class="preview-shell">
        <div class="preview-stage">
          ${
            selectedPreview
              ? `<video class="preview-player" controls preload="metadata" src="/files/${encodeURI(selectedPreview.path)}"></video>`
              : '<div class="empty preview-empty">ยังไม่ได้เลือกตัวอย่างวิดีโอ</div>'
          }
        </div>
        <div class="preview-controls" role="tablist" aria-label="แหล่งตัวอย่างวิดีโอ">
          ${previewItems
            .map(
              (item) => `
                <button
                  class="secondary preview-toggle ${item.key === selectedPreviewKey ? "active" : ""}"
                  type="button"
                  data-preview-key="${escapeHtml(item.key)}"
                >
                  ${escapeHtml(item.label)}
                </button>
              `,
            )
            .join("")}
        </div>
        <div class="preview-meta">
          ${selectedPreview ? `${escapeHtml(selectedPreview.label)} · ${escapeHtml(selectedPreview.path.split("/").pop())}` : "ไม่มีแหล่งตัวอย่างวิดีโอ"}
        </div>
      </div>
    `
    : '<div class="empty">ไม่มีตัวอย่างวิดีโอสำหรับงานนี้</div>';

  const files = Object.entries(job.files || {});
  const fileLinks = files.length
    ? files
        .map(([label, path]) => {
          const name = path.split("/").pop();
          return `
            <a class="file-link" href="/files/${encodeURI(path)}" target="_blank">
              <span>${escapeHtml(label)}</span>
              <span>${escapeHtml(name)}</span>
            </a>
          `;
        })
        .join("")
    : '<div class="empty">ยังไม่มีไฟล์</div>';

  const log = (job.log || []).map(escapeHtml).join("\n");
  const progress = progressValue(job);
  const compatibilityMarkup = renderCompatibility(job.compatibility || {});
  const autopostMarkup = renderAutopostV2(job);
  const manualPostingSection = manualPostingMarkup(job);
  jobDetails.innerHTML = `
    <div class="meta">
      <strong>${escapeHtml(job.title || "ไม่มีชื่อ")}</strong><br />
      ${escapeHtml(job.uploader || "ไม่ทราบผู้เผยแพร่")} · ${formatDuration(job.duration)}<br />
      ยืนยันสิทธิ์แล้ว: ${job.rights_confirmed ? "ใช่" : "ไม่ใช่"}<br />
      สร้างเมื่อ ${formatTime(job.created_at)}
    </div>
    <div class="detail-progress">
      <div class="progress-row">
        <span>${escapeHtml(job.step)}</span>
        <strong>${progress}%</strong>
      </div>
      <div class="progress" aria-label="ความคืบหน้าของงาน">
        <div class="progress-fill ${job.status}" style="width:${progress}%"></div>
        </div>
      </div>
    </div>
    <button class="secondary full-width" type="button" data-open-folder="${escapeHtml(job.id)}">เปิดโฟลเดอร์</button>
    ${job.error ? `<p class="meta error-text">ข้อผิดพลาด: ${escapeHtml(job.error)}</p>` : ""}
    <h2 style="margin-top:16px">ตัวอย่าง</h2>
    ${previewMarkup}
    <h2 style="margin-top:16px">ไฟล์</h2>
    <div class="files">${fileLinks}</div>
    <h2 style="margin-top:16px">ความเข้ากันได้</h2>
    ${compatibilityMarkup}
    <h2 style="margin-top:16px">โพสต์อัตโนมัติ</h2>
    ${autopostMarkup}
    ${manualPostingSection}
    <h2 style="margin-top:16px">บันทึกการทำงาน</h2>
    <pre class="log">${log || "ยังไม่มีบันทึกการทำงาน"}</pre>
  `;

  const openButton = jobDetails.querySelector("[data-open-folder]");
  const previewSection = jobDetails.querySelector(".preview-shell")?.closest("div");
  const autopostSection = jobDetails.querySelector(".autopost-shell")?.closest("div");
  const manualSection = jobDetails.querySelector(".manual-shell")?.closest("div");
  const logsSection = jobDetails.querySelector(".log")?.closest("pre")?.parentElement;
  if (previewSection) previewSection.setAttribute("data-section", "preview");
  if (autopostSection) autopostSection.setAttribute("data-section", "autopost");
  if (manualSection) manualSection.setAttribute("data-section", "manual");
  if (logsSection) logsSection.setAttribute("data-section", "logs");

  const jumpLinks = document.createElement("div");
  jumpLinks.className = "detail-jump-links";
  jumpLinks.innerHTML = `
    <button class="secondary" type="button" data-jump-section="preview">Preview</button>
    <button class="secondary" type="button" data-jump-section="autopost">Autopost</button>
    <button class="secondary" type="button" data-jump-section="manual">Manual</button>
    <button class="secondary" type="button" data-jump-section="logs">Logs</button>
    <button class="secondary" type="button" data-copy-link="job">Copy Job Link</button>
    <button class="secondary" type="button" data-copy-link="manual">Copy Manual Link</button>
  `;
  openButton.insertAdjacentElement("beforebegin", jumpLinks);
  openButton.addEventListener("click", () => openFolder(job.id, openButton));

  jobDetails.querySelectorAll("[data-jump-section]").forEach((button) => {
    button.addEventListener("click", () => {
      const section = button.dataset.jumpSection || "";
      setSection(section);
      const target = jobDetails.querySelector(`[data-section="${section}"]`);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });
  jobDetails.querySelectorAll("[data-copy-link]").forEach((button) => {
    button.addEventListener("click", () => {
      const mode = button.dataset.copyLink || "job";
      const url = new URL(window.location.href);
      url.searchParams.set("job_id", job.id);
      if (mode === "manual") {
        url.searchParams.set("section", "manual");
      } else {
        url.searchParams.delete("section");
      }
      copyText(url.toString(), button, "คัดลอกแล้ว", "Copy Link");
    });
  });

  jobDetails.querySelectorAll("[data-preview-key]").forEach((button) => {
    button.addEventListener("click", () => {
      selectedPreviewByJob[job.id] = button.dataset.previewKey;
      renderDetails(latestJobs.find((item) => item.id === job.id));
    });
  });

  const autopostButton = jobDetails.querySelector("[data-autopost]");
  if (autopostButton) {
    autopostButton.addEventListener("click", () => {
      const modeInput = jobDetails.querySelector("[data-autopost-mode]");
      const languageInput = jobDetails.querySelector("[data-autopost-language]");
      const approvalInput = jobDetails.querySelector("[data-autopost-approval]");
      const platformInputs = jobDetails.querySelectorAll("[data-autopost-platform]:checked");
      const mode = modeInput ? modeInput.value : "dry";
      const language = languageInput ? languageInput.value : "en";
      const approval = approvalInput ? approvalInput.value.trim() : "";
      const platforms = platformInputs.length
        ? Array.from(platformInputs).map((item) => item.value)
        : ["tiktok", "reels", "shorts"];
      startAutopost(job.id, autopostButton, mode, language, platforms, approval);
    });
  }
  const pauseButton = jobDetails.querySelector("[data-autopost-pause]");
  if (pauseButton) {
    pauseButton.addEventListener("click", () => sendAutopostControl(job.id, "pause", pauseButton));
  }
  const resumeButton = jobDetails.querySelector("[data-autopost-resume]");
  if (resumeButton) {
    resumeButton.addEventListener("click", () => sendAutopostControl(job.id, "resume", resumeButton));
  }
  const retryButton = jobDetails.querySelector("[data-autopost-retry]");
  if (retryButton) {
    retryButton.addEventListener("click", () => sendAutopostControl(job.id, "retry", retryButton));
  }
  renderManualPosting(job).catch((error) => {
    console.error(error);
  });
  requestAnimationFrame(() => {
    scrollToRequestedSection();
  });
}

function renderCompatibility(compatibility) {
  const assets = Object.entries(compatibility || {});
  if (!assets.length) {
    return '<div class="empty">ยังไม่มีรายงานความเข้ากันได้</div>';
  }

  return `
    <div class="compat-list">
      ${assets
        .map(([assetKey, platforms]) => {
          const rows = Object.entries(platforms || {})
            .map(([platform, result]) => {
              const issues = Array.isArray(result?.issues) ? result.issues : [];
              const ok = Boolean(result?.ok);
              return `
                <div class="compat-row">
                  <div>
                    <strong>${escapeHtml(platform)}</strong>
                    ${issues.length ? `<div class="compat-issues">${escapeHtml(issues.join(" | "))}</div>` : ""}
                  </div>
                  <span class="compat-badge ${ok ? "ok" : "fail"}">${ok ? "ผ่าน" : "ไม่ผ่าน"}</span>
                </div>
              `;
            })
            .join("");
          return `
            <section class="compat-asset">
              <h3>${escapeHtml(assetKey)}</h3>
              ${rows || '<div class="empty">ยังไม่มีผลตรวจของแพลตฟอร์ม</div>'}
            </section>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderAutopost(job) {
  const canAutopost = job.status === "done" && Boolean(job.files?.exports_index);
  const status = job.autopost_status || "idle";
  const control = job.autopost_control || "active";
  const summary = job.autopost_report?.status ? `ผลรอบล่าสุด: ${job.autopost_report.status}` : "ยังไม่เคยรัน";
  if (!canAutopost) {
    return '<div class="empty">การโพสต์อัตโนมัติต้องใช้งานที่เสร็จแล้วและมี export package</div>';
  }
  return `
    <div class="autopost-shell">
      <div class="meta">${escapeHtml(summary)} · โหมดเริ่มต้น: dry-run</div>
      <label class="field">
        <span>โหมด</span>
        <select data-autopost-mode>
          <option value="dry" selected>ทดสอบการทำงาน</option>
          <option value="live">ใช้งานจริง (ต้องมี token)</option>
        </select>
      </label>
      <label class="field">
        <span>ภาษา</span>
        <select data-autopost-language>
          <option value="en" selected>อังกฤษ</option>
          <option value="th">ไทย</option>
        </select>
      </label>
      <label class="field">
        <span>คำยืนยันสำหรับโหมดจริง</span>
        <input data-autopost-approval type="text" placeholder="APPROVED" />
      </label>
      <div class="autopost-platforms">
        <label class="check"><input type="checkbox" data-autopost-platform="tiktok" value="tiktok" checked /><span>TikTok</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="reels" value="reels" checked /><span>Reels</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="shorts" value="shorts" checked /><span>Shorts</span></label>
      </div>
      <div class="meta">env สำหรับโหมดจริง: SOCIALAUTOPOST_[PLATFORM]_TOKEN + SOCIALAUTOPOST_[PLATFORM]_ENDPOINT</div>
      <div class="mobile-action-bar mobile-action-bar-autopost">
        <div class="mobile-action-bar-title">Autopost actions</div>
        <button class="secondary full-width" type="button" data-autopost="1" ${status === "running" ? "disabled" : ""}>
        ${status === "running" ? "กำลังโพสต์อัตโนมัติ..." : "เริ่มโพสต์อัตโนมัติ"}
      </button>
    </div>
  `;
}

function renderAutopostV2(job) {
  const canAutopost = job.status === "done" && Boolean(job.files?.exports_index);
  const status = job.autopost_status || "idle";
  const control = job.autopost_control || "active";
  const summary = job.autopost_report?.status ? `ผลรอบล่าสุด: ${job.autopost_report.status}` : "ยังไม่เคยรัน";
  if (!canAutopost) {
    return '<div class="empty">การโพสต์อัตโนมัติต้องใช้งานที่เสร็จแล้วและมี export package</div>';
  }
  return `
    <div class="autopost-shell">
      <div class="meta">${escapeHtml(summary)} · สถานะการควบคุม: ${escapeHtml(control)}</div>
      <label class="field">
        <span>โหมด</span>
        <select data-autopost-mode>
          <option value="dry" selected>ทดสอบการทำงาน</option>
          <option value="live">ใช้งานจริง (ต้องมี token)</option>
        </select>
      </label>
      <label class="field">
        <span>ภาษา</span>
        <select data-autopost-language>
          <option value="en" selected>อังกฤษ</option>
          <option value="th">ไทย</option>
        </select>
      </label>
      <div class="autopost-platforms">
        <label class="check"><input type="checkbox" data-autopost-platform="tiktok" value="tiktok" checked /><span>TikTok</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="reels" value="reels" checked /><span>Reels</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="shorts" value="shorts" checked /><span>Shorts</span></label>
      </div>
      <div class="meta">env สำหรับโหมดจริง: SOCIALAUTOPOST_[PLATFORM]_TOKEN + SOCIALAUTOPOST_[PLATFORM]_ENDPOINT</div>
      <div class="mobile-action-bar mobile-action-bar-autopost">
        <div class="mobile-action-bar-title">Autopost actions</div>
        <button class="secondary full-width" type="button" data-autopost="1" ${status === "running" ? "disabled" : ""}>
        ${status === "running" ? "กำลังโพสต์อัตโนมัติ..." : "เริ่มโพสต์อัตโนมัติ"}
      </button>
        <div class="autopost-actions">
        <button class="secondary" type="button" data-autopost-pause ${status !== "running" || control === "paused" ? "disabled" : ""}>หยุดชั่วคราว</button>
        <button class="secondary" type="button" data-autopost-resume ${control !== "paused" ? "disabled" : ""}>ทำงานต่อ</button>
        <button class="secondary" type="button" data-autopost-retry ${status === "running" ? "disabled" : ""}>ลองงานที่ล้มเหลวใหม่</button>
        </div>
      </div>
    </div>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderDiagnostics(data) {
  const whisper = data?.whisper || {};
  const ffmpeg = data?.ffmpeg || {};
  const cuda = data?.cuda || {};
  const libraries = Array.isArray(cuda.libraries) ? cuda.libraries : [];
  const candidates = Array.isArray(whisper.candidate_order) ? whisper.candidate_order : [];
  const dllPaths = Array.isArray(cuda.dll_search_paths) ? cuda.dll_search_paths : [];

  diagnosticsContent.innerHTML = `
    <div class="diagnostics-grid">
      <section class="diagnostics-card">
        <h3>Whisper</h3>
        <div class="diagnostics-list">
          <div><strong>Model:</strong> ${escapeHtml(whisper.model || "-")}</div>
          <div><strong>Requested device:</strong> ${escapeHtml(whisper.requested_device || "-")}</div>
          <div><strong>Requested compute:</strong> ${escapeHtml(whisper.requested_compute_type || "-")}</div>
          <div><strong>Candidate order:</strong> ${escapeHtml(
            candidates.map((item) => `${item.device}/${item.compute_type}`).join(" -> ") || "-",
          )}</div>
        </div>
      </section>
      <section class="diagnostics-card">
        <h3>FFmpeg</h3>
        <div class="diagnostics-list">
          <div><strong>Video encoder:</strong> ${escapeHtml(ffmpeg.video_encoder || "-")}</div>
          <div><strong>HW accel:</strong> ${escapeHtml((ffmpeg.hwaccel_args || []).join(" ") || "-")}</div>
          <div><strong>NVENC:</strong> ${yesNo(ffmpeg.nvenc_available)}</div>
        </div>
      </section>
      <section class="diagnostics-card">
        <h3>CUDA DLL</h3>
        <div class="diagnostics-list">
          <div><strong>All loaded:</strong> ${yesNo(cuda.all_loaded)}</div>
          ${libraries
            .map((item) => `<div><strong>${escapeHtml(item.name)}:</strong> ${yesNo(Boolean(item.loaded))}</div>`)
            .join("")}
        </div>
      </section>
      <section class="diagnostics-card">
        <h3>DLL search paths</h3>
        <pre class="log">${escapeJson(dllPaths)}</pre>
      </section>
    </div>
  `;
}

async function fetchDiagnostics() {
  diagnosticsPanel.classList.remove("hidden");
  diagnosticsContent.innerHTML = '<div class="empty">กำลังโหลดข้อมูล runtime...</div>';
  try {
    const response = await fetch("/api/diagnostics");
    const data = await response.json();
    if (!response.ok) {
      diagnosticsContent.innerHTML = `<div class="empty error-text">${escapeHtml(data.error || "โหลดข้อมูลไม่สำเร็จ")}</div>`;
      return;
    }
    renderDiagnostics(data);
  } catch (error) {
    console.error(error);
    diagnosticsContent.innerHTML = '<div class="empty error-text">โหลดข้อมูล runtime ไม่สำเร็จ</div>';
  }
}

async function submitUrlJob() {
  const payload = {
    url: urlInput.value.trim(),
    category: document.querySelector("#categoryInput").value,
    browser: browserInput.value,
    normalize: normalizeInput.checked,
    transcribe: transcribeInput.checked,
    highlights: highlightsInput.checked,
    highlight_length: Number(highlightLengthInput.value),
    rights_confirmed: rightsInput.checked,
  };

  const response = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return [response, await response.json(), payload];
}

async function submitFileJob() {
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("category", document.querySelector("#categoryInput").value);
  formData.append("normalize", normalizeInput.checked ? "true" : "false");
  formData.append("transcribe", transcribeInput.checked ? "true" : "false");
  formData.append("highlights", highlightsInput.checked ? "true" : "false");
  formData.append("highlight_length", highlightLengthInput.value);
  formData.append("rights_confirmed", rightsInput.checked ? "true" : "false");

  const response = await fetch("/api/jobs/upload", {
    method: "POST",
    body: formData,
  });
  return [
    response,
    await response.json(),
    {
      browser: browserInput.value,
      normalize: normalizeInput.checked,
      transcribe: transcribeInput.checked,
      highlights: highlightsInput.checked,
      highlight_length: highlightLengthInput.value,
      rights_confirmed: rightsInput.checked,
    },
  ];
}

async function openFolder(jobId, button) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "กำลังเปิด...";
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/open-folder`, {
      method: "POST",
    });
    const data = await response.json();
    if (!response.ok) {
      alert(data.error || "ไม่สามารถเปิดโฟลเดอร์ได้");
    }
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function startAutopost(jobId, button, mode = "dry", language = "en", platforms = ["tiktok", "reels", "shorts"], approval = "") {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "กำลังโพสต์อัตโนมัติ...";
  try {
    if (!platforms.length) {
      alert("กรุณาเลือกอย่างน้อยหนึ่งแพลตฟอร์ม");
      return;
    }
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/autopost`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Operator": currentOperator(),
      },
      body: JSON.stringify({
        dry_run: mode !== "live",
        language,
        platforms,
        operator: currentOperator(),
        approval,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      alert(data.error || "ไม่สามารถเริ่มโพสต์อัตโนมัติได้");
    }
    await fetchJobs();
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function sendAutopostControl(jobId, action, button) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = `${original}...`;
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/autopost/${action}`, {
      method: "POST",
      headers: {
        "X-Operator": currentOperator(),
      },
    });
    const data = await response.json();
    if (!response.ok) {
      alert(data.error || `ไม่สามารถสั่งงานโพสต์อัตโนมัติ: ${action}`);
    }
    await fetchJobs();
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

function manualPostingMarkup(job) {
  const clipItems = exportClipItemsForJob(job);
  if (!clipItems.length) {
    return "";
  }
  const selectedClip = selectedManualClipByJob[job.id] || String(clipItems[0].index);
  return `
    <h2 style="margin-top:16px">โพสต์ด้วยตนเอง</h2>
    <div class="policy-note manual-first">
      <strong>Manual-first:</strong> ใช้ส่วนนี้เป็นเส้นทางหลักสำหรับ TikTok และงานที่ยังต้องการคนตรวจคลิป คำบรรยาย และสิทธิ์ก่อนโพสต์จริง
    </div>
    <div class="manual-shell" data-manual-shell="1">
      <label class="field">
        <span>คลิปสำหรับโพสต์</span>
        <select data-manual-clip>
          ${clipItems
            .map(
              (item) => `
                <option value="${item.index}" ${String(item.index) === String(selectedClip) ? "selected" : ""}>
                  Export clip ${item.index.toString().padStart(2, "0")}
                </option>
              `,
            )
            .join("")}
        </select>
      </label>
      <label class="field">
        <span>ตัวเลือกคำบรรยาย</span>
        <select data-manual-caption>
          <option value="">กำลังโหลดตัวเลือก...</option>
        </select>
      </label>
      <div class="manual-links" data-manual-links>กำลังโหลดไฟล์...</div>
      <div class="mobile-action-bar">
        <div class="mobile-action-bar-title">Manual actions</div>
        <div class="manual-actions">
        <button class="secondary" type="button" data-manual-copy title="คัดลอกคำบรรยายตามที่แสดงในกล่องตัวอย่าง" aria-label="คัดลอกคำบรรยายตามที่แสดง">คัดลอกคำบรรยาย</button>
        <button class="secondary" type="button" data-manual-open title="เปิดวิดีโอคลิปที่เลือกในแท็บใหม่" aria-label="เปิดคลิปที่เลือก">เปิดคลิป</button>
        <button class="secondary" type="button" data-manual-copy-path title="คัดลอก path ของวิดีโอที่เลือก" aria-label="คัดลอก path ของวิดีโอที่เลือก">คัดลอก path วิดีโอ</button>
        <button class="secondary" type="button" data-manual-open-caption title="เปิดไฟล์คำบรรยายที่เลือกเมื่อเป็นตัวเลือกจากไฟล์" aria-label="เปิดไฟล์คำบรรยายที่เลือก">เปิดไฟล์คำบรรยาย</button>
        <button class="secondary" type="button" data-manual-open-folder title="เปิดโฟลเดอร์งานนี้ใน Explorer" aria-label="เปิดโฟลเดอร์งานนี้">เปิดโฟลเดอร์งาน</button>
        <button class="secondary" type="button" data-manual-copy-plain title="คัดลอกคำบรรยายแบบข้อความล้วน" aria-label="คัดลอกคำบรรยายแบบข้อความล้วน">คัดลอกคำบรรยายแบบข้อความล้วน</button>
      </div>
      <label class="field">
        <span>ตัวอย่างคำบรรยาย</span>
        <textarea class="manual-caption" data-manual-caption-text readonly>กำลังโหลดคำบรรยาย...</textarea>
      </label>
    </div>
  `;
}

async function manualCaptionOptionsForJob(job, clipIndex) {
  const clipItems = exportClipItemsForJob(job);
  const clip = clipItems.find((item) => item.index === Number(clipIndex)) || clipItems[0];
  const options = [];
  if (!clip) return options;
  if (clip.highlightCaptionPath) {
    options.push({
      key: `clip-${clip.index}`,
      label: `Clip ${clip.index.toString().padStart(2, "0")} draft`,
      type: "file",
      path: clip.highlightCaptionPath,
    });
  }
  if (clip.exportCaptionPath && clip.exportCaptionPath !== clip.highlightCaptionPath) {
    options.push({
      key: `export-${clip.index}`,
      label: `Clip ${clip.index.toString().padStart(2, "0")} export`,
      type: "file",
      path: clip.exportCaptionPath,
    });
  }
  if (job.files?.platform_captions) {
    try {
      const platformCaptions = await fetchJsonFile(job.files.platform_captions);
      [
        ["shorts", "YouTube Shorts"],
        ["reels", "Instagram Reels"],
        ["tiktok", "TikTok"],
      ].forEach(([platform, label]) => {
        const variants = platformCaptions?.[platform] || {};
        ["en", "th"].forEach((language) => {
          const text = variants?.[language];
          if (text) {
            options.push({
              key: `${platform}-${language}`,
              label: `${label} ${language.toUpperCase()}`,
              type: "inline",
              text,
            });
          }
        });
      });
    } catch (error) {
      console.error(error);
    }
  }
  return options;
}

function renderAutopostV2(job) {
  const canAutopost = job.status === "done" && Boolean(job.files?.exports_index);
  const status = job.autopost_status || "idle";
  const control = job.autopost_control || "active";
  const summary = job.autopost_report?.status ? `ผลรอบล่าสุด: ${job.autopost_report.status}` : "ยังไม่เคยรัน";
  if (!canAutopost) {
    return '<div class="empty">Autopost ใช้ได้เมื่อ job เสร็จแล้วและมี export package</div>';
  }
  return `
    <div class="autopost-shell">
      <div class="policy-note native-first">
        <strong>Native-first:</strong> ใช้ลำดับนี้สำหรับ production คือ <strong>Shorts native</strong> ก่อน, <strong>Reels native</strong> ถัดไป, และ <strong>TikTok manual-first</strong> จนกว่าจะพร้อม official approval
      </div>
      <div class="meta">${escapeHtml(summary)} · สถานะการควบคุม: ${escapeHtml(control)}</div>
      <label class="field">
        <span>โหมด</span>
        <select data-autopost-mode>
          <option value="dry" selected>Dry-run review</option>
          <option value="live">Live delivery (ต้องมี token/adapter พร้อม)</option>
        </select>
      </label>
      <label class="field">
        <span>ภาษา</span>
        <select data-autopost-language>
          <option value="en" selected>อังกฤษ</option>
          <option value="th">ไทย</option>
        </select>
      </label>
      <label class="field">
        <span>ลำดับแนะนำ</span>
        <input type="text" value="1) Shorts native  2) Reels native  3) TikTok manual-first" readonly />
      </label>
      <div class="autopost-platforms">
        <label class="check"><input type="checkbox" data-autopost-platform="shorts" value="shorts" checked /><span>YouTube Shorts (native-first)</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="reels" value="reels" checked /><span>Instagram Reels (native-next)</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="tiktok" value="tiktok" /><span>TikTok (manual-first / official-only later)</span></label>
      </div>
      <div class="meta">โหมดจริงควรใช้ native adapter ที่ผ่านการตรวจพร้อมแล้ว และใช้ไฟล์จาก export package เป็นหลัก</div>
      <button class="secondary full-width" type="button" data-autopost="1" ${status === "running" ? "disabled" : ""}>
        ${status === "running" ? "กำลังส่งงาน..." : "เริ่ม Autopost"}
      </button>
        <div class="autopost-actions">
        <button class="secondary" type="button" data-autopost-pause ${status !== "running" || control === "paused" ? "disabled" : ""}>หยุดชั่วคราว</button>
        <button class="secondary" type="button" data-autopost-resume ${control !== "paused" ? "disabled" : ""}>ทำงานต่อ</button>
        <button class="secondary" type="button" data-autopost-retry ${status === "running" ? "disabled" : ""}>ลองงานที่ล้มเหลวใหม่</button>
      </div>
    </div>
  `;
}

function renderAutopostV2(job) {
  const canAutopost = job.status === "done" && Boolean(job.files?.exports_index);
  const status = job.autopost_status || "idle";
  const control = job.autopost_control || "active";
  const summary = job.autopost_report?.status ? `ผลรอบล่าสุด: ${job.autopost_report.status}` : "ยังไม่เคยรัน";
  if (!canAutopost) {
    return '<div class="empty">Autopost ใช้ได้เมื่อ job เสร็จแล้วและมี export package</div>';
  }
  return `
    <div class="autopost-shell">
      <div class="policy-note native-first">
        <strong>Native-first:</strong> ใช้ลำดับนี้สำหรับ production คือ <strong>Shorts native</strong> ก่อน, <strong>Reels native</strong> ถัดไป, และ <strong>TikTok manual-first</strong> จนกว่าจะพร้อม official approval
      </div>
      <div class="meta">${escapeHtml(summary)} · สถานะการควบคุม: ${escapeHtml(control)}</div>
      <label class="field">
        <span>โหมด</span>
        <select data-autopost-mode>
          <option value="dry" selected>Dry-run review</option>
          <option value="live">Live delivery (ต้องมี token/adapter พร้อม)</option>
        </select>
      </label>
      <label class="field">
        <span>ภาษา</span>
        <select data-autopost-language>
          <option value="en" selected>อังกฤษ</option>
          <option value="th">ไทย</option>
        </select>
      </label>
      <label class="field">
        <span>ลำดับแนะนำ</span>
        <input type="text" value="1) Shorts native  2) Reels native  3) TikTok manual-first" readonly />
      </label>
      <div class="autopost-platforms">
        <label class="check"><input type="checkbox" data-autopost-platform="shorts" value="shorts" checked /><span>YouTube Shorts (native-first)</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="reels" value="reels" checked /><span>Instagram Reels (native-next)</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="tiktok" value="tiktok" /><span>TikTok (manual-first / official-only later)</span></label>
      </div>
      <div class="meta">โหมดจริงควรใช้ native adapter ที่ผ่านการตรวจพร้อมแล้ว และใช้ไฟล์จาก export package เป็นหลัก</div>
      <div class="mobile-action-bar mobile-action-bar-autopost">
        <div class="mobile-action-bar-title">Autopost actions</div>
        <button class="secondary full-width" type="button" data-autopost="1" ${status === "running" ? "disabled" : ""}>
          ${status === "running" ? "กำลังส่งงาน..." : "เริ่ม Autopost"}
        </button>
        <div class="autopost-actions">
          <button class="secondary" type="button" data-autopost-pause ${status !== "running" || control === "paused" ? "disabled" : ""}>หยุดชั่วคราว</button>
          <button class="secondary" type="button" data-autopost-resume ${control !== "paused" ? "disabled" : ""}>ทำงานต่อ</button>
          <button class="secondary" type="button" data-autopost-retry ${status === "running" ? "disabled" : ""}>ลองงานที่ล้มเหลวใหม่</button>
        </div>
      </div>
    </div>
  `;
}

function manualPostingMarkup(job) {
  const clipItems = exportClipItemsForJob(job);
  if (!clipItems.length) {
    return "";
  }
  const selectedClip = selectedManualClipByJob[job.id] || String(clipItems[0].index);
  return `
    <h2 style="margin-top:16px">โพสต์ด้วยตนเอง</h2>
    <div class="policy-note manual-first">
      <strong>Manual-first:</strong> ใช้ส่วนนี้เป็นเส้นทางหลักสำหรับ TikTok และงานที่ยังต้องการคนตรวจคลิป คำบรรยาย และสิทธิ์ก่อนโพสต์จริง
    </div>
    <div class="manual-shell" data-manual-shell="1">
      <label class="field">
        <span>คลิปสำหรับโพสต์</span>
        <select data-manual-clip>
          ${clipItems
            .map(
              (item) => `
                <option value="${item.index}" ${String(item.index) === String(selectedClip) ? "selected" : ""}>
                  Export clip ${item.index.toString().padStart(2, "0")}
                </option>
              `,
            )
            .join("")}
        </select>
      </label>
      <label class="field">
        <span>ตัวเลือกคำบรรยาย</span>
        <select data-manual-caption>
          <option value="">กำลังโหลดตัวเลือก...</option>
        </select>
      </label>
      <div class="manual-links" data-manual-links>กำลังโหลดไฟล์...</div>
      <div class="mobile-action-bar">
        <div class="mobile-action-bar-title">Manual actions</div>
        <div class="manual-actions">
          <button class="secondary" type="button" data-manual-copy title="คัดลอกคำบรรยายตามที่แสดงในกล่องตัวอย่าง" aria-label="คัดลอกคำบรรยายตามที่แสดง">คัดลอกคำบรรยาย</button>
          <button class="secondary" type="button" data-manual-open title="เปิดวิดีโอคลิปที่เลือกในแท็บใหม่" aria-label="เปิดคลิปที่เลือก">เปิดคลิป</button>
          <button class="secondary" type="button" data-manual-copy-path title="คัดลอก path ของวิดีโอที่เลือก" aria-label="คัดลอก path ของวิดีโอที่เลือก">คัดลอก path วิดีโอ</button>
          <button class="secondary" type="button" data-manual-open-caption title="เปิดไฟล์คำบรรยายที่เลือกเมื่อเป็นตัวเลือกจากไฟล์" aria-label="เปิดไฟล์คำบรรยายที่เลือก">เปิดไฟล์คำบรรยาย</button>
          <button class="secondary" type="button" data-manual-open-folder title="เปิดโฟลเดอร์งานนี้ใน Explorer" aria-label="เปิดโฟลเดอร์งานนี้">เปิดโฟลเดอร์งาน</button>
          <button class="secondary" type="button" data-manual-copy-plain title="คัดลอกคำบรรยายแบบข้อความล้วน" aria-label="คัดลอกคำบรรยายแบบข้อความล้วน">คัดลอกคำบรรยายแบบข้อความล้วน</button>
        </div>
      </div>
      <label class="field">
        <span>ตัวอย่างคำบรรยาย</span>
        <textarea class="manual-caption" data-manual-caption-text readonly>กำลังโหลดคำบรรยาย...</textarea>
      </label>
    </div>
  `;
}

jobForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = sourceMode() === "file" ? "กำลังอัปโหลด..." : "กำลังเริ่ม...";

  try {
    const [response, data, previous] = sourceMode() === "file" ? await submitFileJob() : await submitUrlJob();
    if (!response.ok) {
      alert(data.error || "ไม่สามารถสร้างงานได้");
      return;
    }
    selectedJobId = data.id;
    syncUrlState();
    jobForm.reset();
    browserInput.value = previous.browser;
    normalizeInput.checked = previous.normalize;
    transcribeInput.checked = previous.transcribe;
    highlightsInput.checked = previous.highlights;
    highlightLengthInput.value = String(previous.highlight_length || 15);
    rightsInput.checked = Boolean(previous.rights_confirmed);
    syncSourceMode();
    syncHighlightMode();
    await fetchJobs();
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "เริ่มงาน";
  }
});

document.querySelectorAll('input[name="sourceMode"]').forEach((input) => {
  input.addEventListener("change", syncSourceMode);
});
highlightsInput.addEventListener("change", syncHighlightMode);
compactLayoutQuery.addEventListener("change", syncCompactLayout);

refreshBtn.addEventListener("click", fetchJobs);
if (diagnosticsBtn) {
  diagnosticsBtn.addEventListener("click", fetchDiagnostics);
}
if (closeDiagnosticsBtn) {
  closeDiagnosticsBtn.addEventListener("click", () => diagnosticsPanel.classList.add("hidden"));
}

const savedOperator = localStorage.getItem(OPERATOR_STORAGE_KEY) || "";
if (operatorInput) {
  operatorInput.value = savedOperator;
  operatorInput.addEventListener("input", () => {
    localStorage.setItem(OPERATOR_STORAGE_KEY, operatorInput.value.trim());
  });
}

applyInitialUrlPrefill();
ensureJobsToggle();
syncCompactLayout();
urlInput.addEventListener("input", syncUrlState);
syncSourceMode();
syncHighlightMode();
fetchJobs();
setInterval(fetchJobs, 2500);
