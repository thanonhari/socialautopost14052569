const jobsList = document.querySelector("#jobsList");
const jobDetails = document.querySelector("#jobDetails");
const jobForm = document.querySelector("#jobForm");
const refreshBtn = document.querySelector("#refreshBtn");
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
const OPERATOR_STORAGE_KEY = "socialautopost.operator";

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

function statusText(status) {
  return {
    queued: "Queued",
    running: "Running",
    done: "Done",
    failed: "Failed",
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
  if (key === "source_video") return "Source video";
  if (key === "normalized_video") return "Normalized video";
  const match = key.match(/^highlight_clip_(\d+)$/);
  if (match) return `Highlight ${match[1]}`;
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

async function fetchJobs() {
  const response = await fetch("/api/jobs");
  latestJobs = await response.json();
  renderJobs();
  if (selectedJobId) {
    const current = latestJobs.find((job) => job.id === selectedJobId);
    renderDetails(current);
  }
}

function renderJobs() {
  if (!latestJobs.length) {
    jobsList.innerHTML = '<div class="empty">No jobs yet.</div>';
    return;
  }

  jobsList.innerHTML = latestJobs
    .map((job) => {
      const title = escapeHtml(job.title || job.url);
      const source = job.source_type === "file" ? "local file" : "url";
      const progress = progressValue(job);
      return `
        <article class="job-card ${job.id === selectedJobId ? "active" : ""}" data-id="${job.id}">
          <div class="job-head">
            <div class="job-title">${title}</div>
            <span class="badge ${job.status}">${statusText(job.status)}</span>
          </div>
          <div class="progress" aria-label="Job progress">
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
      renderJobs();
      renderDetails(latestJobs.find((job) => job.id === selectedJobId));
    });
  });
}

function renderDetails(job) {
  if (!job) {
    jobDetails.innerHTML = '<div class="empty">Select a job to view files and logs.</div>';
    return;
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
              : '<div class="empty preview-empty">No preview selected.</div>'
          }
        </div>
        <div class="preview-controls" role="tablist" aria-label="Preview sources">
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
          ${selectedPreview ? `${escapeHtml(selectedPreview.label)} · ${escapeHtml(selectedPreview.path.split("/").pop())}` : "No preview source"}
        </div>
      </div>
    `
    : '<div class="empty">No video preview available for this job.</div>';

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
    : '<div class="empty">No files yet.</div>';

  const log = (job.log || []).map(escapeHtml).join("\n");
  const progress = progressValue(job);
  const compatibilityMarkup = renderCompatibility(job.compatibility || {});
  const autopostMarkup = renderAutopostV2(job);
  jobDetails.innerHTML = `
    <div class="meta">
      <strong>${escapeHtml(job.title || "Untitled")}</strong><br />
      ${escapeHtml(job.uploader || "unknown")} · ${formatDuration(job.duration)}<br />
      Rights confirmed: ${job.rights_confirmed ? "yes" : "no"}<br />
      Created ${formatTime(job.created_at)}
    </div>
    <div class="detail-progress">
      <div class="progress-row">
        <span>${escapeHtml(job.step)}</span>
        <strong>${progress}%</strong>
      </div>
      <div class="progress" aria-label="Job progress">
        <div class="progress-fill ${job.status}" style="width:${progress}%"></div>
      </div>
    </div>
    <button class="secondary full-width" type="button" data-open-folder="${escapeHtml(job.id)}">Open folder</button>
    ${job.error ? `<p class="meta error-text">Error: ${escapeHtml(job.error)}</p>` : ""}
    <h2 style="margin-top:16px">Preview</h2>
    ${previewMarkup}
    <h2 style="margin-top:16px">Files</h2>
    <div class="files">${fileLinks}</div>
    <h2 style="margin-top:16px">Compatibility</h2>
    ${compatibilityMarkup}
    <h2 style="margin-top:16px">Autopost</h2>
    ${autopostMarkup}
    <h2 style="margin-top:16px">Log</h2>
    <pre class="log">${log || "No logs yet."}</pre>
  `;

  const openButton = jobDetails.querySelector("[data-open-folder]");
  openButton.addEventListener("click", () => openFolder(job.id, openButton));

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
}

function renderCompatibility(compatibility) {
  const assets = Object.entries(compatibility || {});
  if (!assets.length) {
    return '<div class="empty">No compatibility report yet.</div>';
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
                  <span class="compat-badge ${ok ? "ok" : "fail"}">${ok ? "Pass" : "Fail"}</span>
                </div>
              `;
            })
            .join("");
          return `
            <section class="compat-asset">
              <h3>${escapeHtml(assetKey)}</h3>
              ${rows || '<div class="empty">No platform checks.</div>'}
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
  const summary = job.autopost_report?.status ? `Last run: ${job.autopost_report.status}` : "No run yet.";
  if (!canAutopost) {
    return '<div class="empty">Autopost requires completed job with export package.</div>';
  }
  return `
    <div class="autopost-shell">
      <div class="meta">${escapeHtml(summary)} · Mode: dry-run default</div>
      <label class="field">
        <span>Mode</span>
        <select data-autopost-mode>
          <option value="dry" selected>Dry run</option>
          <option value="live">Live (requires tokens)</option>
        </select>
      </label>
      <label class="field">
        <span>Language</span>
        <select data-autopost-language>
          <option value="en" selected>English</option>
          <option value="th">Thai</option>
        </select>
      </label>
      <label class="field">
        <span>Live approval</span>
        <input data-autopost-approval type="text" placeholder="APPROVED" />
      </label>
      <div class="autopost-platforms">
        <label class="check"><input type="checkbox" data-autopost-platform="tiktok" value="tiktok" checked /><span>TikTok</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="reels" value="reels" checked /><span>Reels</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="shorts" value="shorts" checked /><span>Shorts</span></label>
      </div>
      <div class="meta">Live mode env: SOCIALAUTOPOST_[PLATFORM]_TOKEN + SOCIALAUTOPOST_[PLATFORM]_ENDPOINT</div>
      <button class="secondary full-width" type="button" data-autopost="1" ${status === "running" ? "disabled" : ""}>
        ${status === "running" ? "Autopost running..." : "Start autopost"}
      </button>
    </div>
  `;
}

function renderAutopostV2(job) {
  const canAutopost = job.status === "done" && Boolean(job.files?.exports_index);
  const status = job.autopost_status || "idle";
  const control = job.autopost_control || "active";
  const summary = job.autopost_report?.status ? `Last run: ${job.autopost_report.status}` : "No run yet.";
  if (!canAutopost) {
    return '<div class="empty">Autopost requires completed job with export package.</div>';
  }
  return `
    <div class="autopost-shell">
      <div class="meta">${escapeHtml(summary)} · Control: ${escapeHtml(control)}</div>
      <label class="field">
        <span>Mode</span>
        <select data-autopost-mode>
          <option value="dry" selected>Dry run</option>
          <option value="live">Live (requires tokens)</option>
        </select>
      </label>
      <label class="field">
        <span>Language</span>
        <select data-autopost-language>
          <option value="en" selected>English</option>
          <option value="th">Thai</option>
        </select>
      </label>
      <div class="autopost-platforms">
        <label class="check"><input type="checkbox" data-autopost-platform="tiktok" value="tiktok" checked /><span>TikTok</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="reels" value="reels" checked /><span>Reels</span></label>
        <label class="check"><input type="checkbox" data-autopost-platform="shorts" value="shorts" checked /><span>Shorts</span></label>
      </div>
      <div class="meta">Live mode env: SOCIALAUTOPOST_[PLATFORM]_TOKEN + SOCIALAUTOPOST_[PLATFORM]_ENDPOINT</div>
      <button class="secondary full-width" type="button" data-autopost="1" ${status === "running" ? "disabled" : ""}>
        ${status === "running" ? "Autopost running..." : "Start autopost"}
      </button>
      <div class="autopost-actions">
        <button class="secondary" type="button" data-autopost-pause ${status !== "running" || control === "paused" ? "disabled" : ""}>Pause</button>
        <button class="secondary" type="button" data-autopost-resume ${control !== "paused" ? "disabled" : ""}>Resume</button>
        <button class="secondary" type="button" data-autopost-retry ${status === "running" ? "disabled" : ""}>Retry failed</button>
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
  button.textContent = "Opening...";
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/open-folder`, {
      method: "POST",
    });
    const data = await response.json();
    if (!response.ok) {
      alert(data.error || "Could not open folder");
    }
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function startAutopost(jobId, button, mode = "dry", language = "en", platforms = ["tiktok", "reels", "shorts"], approval = "") {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Autopost running...";
  try {
    if (!platforms.length) {
      alert("Choose at least one platform");
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
      alert(data.error || "Could not start autopost");
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
      alert(data.error || `Could not ${action} autopost`);
    }
    await fetchJobs();
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

jobForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = sourceMode() === "file" ? "Uploading..." : "Starting...";

  try {
    const [response, data, previous] = sourceMode() === "file" ? await submitFileJob() : await submitUrlJob();
    if (!response.ok) {
      alert(data.error || "Could not create job");
      return;
    }
    selectedJobId = data.id;
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
    submitBtn.textContent = "Start job";
  }
});

document.querySelectorAll('input[name="sourceMode"]').forEach((input) => {
  input.addEventListener("change", syncSourceMode);
});
highlightsInput.addEventListener("change", syncHighlightMode);

refreshBtn.addEventListener("click", fetchJobs);

const savedOperator = localStorage.getItem(OPERATOR_STORAGE_KEY) || "";
if (operatorInput) {
  operatorInput.value = savedOperator;
  operatorInput.addEventListener("input", () => {
    localStorage.setItem(OPERATOR_STORAGE_KEY, operatorInput.value.trim());
  });
}

syncSourceMode();
syncHighlightMode();
fetchJobs();
setInterval(fetchJobs, 2500);
