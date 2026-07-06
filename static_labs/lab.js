const views = {
  record: document.querySelector("#record-view"),
  history: document.querySelector("#history-view"),
  detail: document.querySelector("#detail-view"),
};

const navLinks = document.querySelectorAll(".nav-link");
const recordButton = document.querySelector("#record-button");
const statusText = document.querySelector("#status-text");
const markerInput = document.querySelector("#marker-input");
const markerButton = document.querySelector("#marker-button");
const markerList = document.querySelector("#marker-list");
const queuePanel = document.querySelector("#queue-panel");
const queueList = document.querySelector("#queue-list");
const recordResults = document.querySelector("#record-results");
const breakdownOutput = document.querySelector("#breakdown-output");
const transcriptOutput = document.querySelector("#transcript-output");
const saveViewButton = document.querySelector("#save-view-button");
const openOutputsButton = document.querySelector("#open-outputs-button");
const searchInput = document.querySelector("#search-input");
const sessionsList = document.querySelector("#sessions-list");
const backHistoryButton = document.querySelector("#back-history-button");
const detailTitle = document.querySelector("#detail-title");
const detailDate = document.querySelector("#detail-date");
const detailBreakdown = document.querySelector("#detail-breakdown");
const detailTranscript = document.querySelector("#detail-transcript");
const ocrPanel = document.querySelector("#ocr-panel");
const detailOcr = document.querySelector("#detail-ocr");
const framesPanel = document.querySelector("#frames-panel");
const framesGrid = document.querySelector("#frames-grid");
const outputPaths = document.querySelector("#output-paths");
const exportButton = document.querySelector("#export-button");

let mediaRecorder = null;
let screenStream = null;
let micStream = null;
let mixedAudioContext = null;
let chunks = [];
let startedAt = 0;
let timerId = null;
let markers = [];
let lastSessionId = null;
let currentDetailId = null;
let searchTimer = null;
let activeJobIds = loadStoredJobs();
let jobStates = {};

function loadStoredJobs() {
  try {
    return JSON.parse(window.localStorage.getItem("activeLabJobIds") || "[]");
  } catch (error) {
    return [];
  }
}

function saveStoredJobs() {
  window.localStorage.setItem("activeLabJobIds", JSON.stringify(activeJobIds));
}

function showView(name) {
  Object.entries(views).forEach(([key, view]) => {
    view.classList.toggle("active", key === name);
  });
  navLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.view === name);
  });
  if (name === "history") {
    fetchLabs(searchInput.value.trim());
  }
}

function formatTime(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function setStatus(message) {
  statusText.textContent = message;
}

function setRecordingState(isRecording) {
  recordButton.classList.toggle("recording", isRecording);
  recordButton.setAttribute("aria-label", isRecording ? "Stop Lab Recording" : "Start Lab Recording");
  markerButton.disabled = !isRecording;
}

function startTimer() {
  startedAt = Date.now();
  setStatus("Recording... 0:00");
  timerId = window.setInterval(() => {
    const elapsed = Math.floor((Date.now() - startedAt) / 1000);
    setStatus(`Recording... ${formatTime(elapsed)}`);
  }, 1000);
}

function stopTimer() {
  if (timerId) {
    window.clearInterval(timerId);
    timerId = null;
  }
}

function preferredMimeType() {
  const types = [
    "video/webm;codecs=vp8,opus",
    "video/webm;codecs=vp9,opus",
    "video/webm",
  ];
  return types.find((type) => window.MediaRecorder && MediaRecorder.isTypeSupported(type)) || "";
}

async function buildCaptureStream() {
  screenStream = await navigator.mediaDevices.getDisplayMedia({
    video: {
      frameRate: { ideal: 15, max: 20 },
    },
    audio: true,
  });

  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
  } catch (error) {
    micStream = null;
  }

  const tracks = [...screenStream.getVideoTracks()];
  const audioTracks = [
    ...screenStream.getAudioTracks(),
    ...(micStream ? micStream.getAudioTracks() : []),
  ];

  if (audioTracks.length) {
    mixedAudioContext = new AudioContext();
    const destination = mixedAudioContext.createMediaStreamDestination();
    if (screenStream.getAudioTracks().length) {
      mixedAudioContext.createMediaStreamSource(screenStream).connect(destination);
    }
    if (micStream && micStream.getAudioTracks().length) {
      mixedAudioContext.createMediaStreamSource(micStream).connect(destination);
    }
    tracks.push(...destination.stream.getAudioTracks());
  }

  return new MediaStream(tracks);
}

async function startRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
    setStatus("Screen recording is not available in this browser");
    return;
  }

  try {
    chunks = [];
    markers = [];
    renderMarkers();
    const stream = await buildCaptureStream();
    const mimeType = preferredMimeType();
    mediaRecorder = new MediaRecorder(stream, {
      ...(mimeType ? { mimeType } : {}),
      videoBitsPerSecond: 1800000,
      audioBitsPerSecond: 96000,
    });

    screenStream.getVideoTracks()[0].addEventListener("ended", () => {
      if (mediaRecorder && mediaRecorder.state === "recording") {
        stopRecording();
      }
    });

    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size > 0) {
        chunks.push(event.data);
      }
    });

    mediaRecorder.addEventListener("stop", () => {
      cleanupStreams();
      uploadRecording(mimeType || "video/webm");
    });

    recordResults.classList.add("hidden");
    saveViewButton.classList.add("hidden");
    lastSessionId = null;
    mediaRecorder.start(5000);
    setRecordingState(true);
    startTimer();
  } catch (error) {
    cleanupStreams();
    setRecordingState(false);
    setStatus(error.name === "NotAllowedError" ? "Screen access was not allowed" : "Could not start lab recording");
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    stopTimer();
    setRecordingState(false);
    setStatus("Preparing upload...");
    recordButton.disabled = true;
    mediaRecorder.requestData();
    mediaRecorder.stop();
  }
}

function cleanupStreams() {
  [screenStream, micStream].forEach((stream) => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }
  });
  screenStream = null;
  micStream = null;
  if (mixedAudioContext) {
    mixedAudioContext.close().catch(() => undefined);
    mixedAudioContext = null;
  }
}

async function uploadRecording(mimeType) {
  const durationSeconds = Math.max(0, Math.round((Date.now() - startedAt) / 1000));
  const blob = new Blob(chunks, { type: mimeType });
  if (!blob.size) {
    setStatus("No lab recording was captured");
    recordButton.disabled = false;
    return;
  }

  const formData = new FormData();
  formData.append("recording", blob, mimeType.includes("mp4") ? "lab.mp4" : "lab.webm");
  formData.append("duration_seconds", String(durationSeconds));
  formData.append("markers", JSON.stringify(markers));

  try {
    setStatus(`Uploading ${formatTime(durationSeconds)} lab recording...`);
    const response = await fetch("/api/labs", {
      method: "POST",
      body: formData,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Lab upload failed");
    }

    addJob(data.job_id, {
      job_id: data.job_id,
      status: data.status || "queued",
      message: data.message || "Queued",
      duration_seconds: durationSeconds,
    });
    setStatus("Lab uploaded. You can start another recording.");
    pollJob(data.job_id);
  } catch (error) {
    setStatus(error.message || "Lab upload failed");
  } finally {
    chunks = [];
    recordButton.disabled = false;
  }
}

function addMarker() {
  if (!mediaRecorder || mediaRecorder.state !== "recording") {
    return;
  }
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
  const note = markerInput.value.trim() || "Marker";
  markers.push({ elapsed_seconds: elapsedSeconds, note });
  markerInput.value = "";
  renderMarkers();
}

function renderMarkers() {
  markerList.innerHTML = "";
  markers.forEach((marker) => {
    const item = document.createElement("div");
    item.className = "marker-item";
    item.innerHTML = "<strong></strong><span></span>";
    item.querySelector("strong").textContent = formatTime(marker.elapsed_seconds);
    item.querySelector("span").textContent = marker.note;
    markerList.appendChild(item);
  });
}

function addJob(jobId, initialState = {}) {
  if (!activeJobIds.includes(jobId)) {
    activeJobIds.push(jobId);
  }
  jobStates[jobId] = { ...(jobStates[jobId] || {}), ...initialState };
  saveStoredJobs();
  renderQueue();
}

function removeStoredJob(jobId) {
  activeJobIds = activeJobIds.filter((id) => id !== jobId);
  saveStoredJobs();
}

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/labs/jobs/${jobId}`);
    const job = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(job.error || "Could not check lab status");
    }

    jobStates[jobId] = job;
    renderQueue();

    if (job.status === "completed") {
      removeStoredJob(jobId);
      completeLab(job);
      return;
    }

    if (job.status === "failed") {
      removeStoredJob(jobId);
      setStatus(job.error || "Lab processing failed");
      return;
    }

    if (!mediaRecorder || mediaRecorder.state !== "recording") {
      setStatus("Ready for another lab");
    }
    window.setTimeout(() => pollJob(jobId), 5000);
  } catch (error) {
    jobStates[jobId] = {
      ...(jobStates[jobId] || {}),
      job_id: jobId,
      status: "checking",
      message: error.message || "Could not check lab status",
    };
    renderQueue();
    window.setTimeout(() => pollJob(jobId), 10000);
  }
}

function renderQueue() {
  const jobs = Object.values(jobStates).sort((a, b) => {
    return String(a.created_at || "").localeCompare(String(b.created_at || ""));
  });
  queuePanel.classList.toggle("hidden", jobs.length === 0);
  queueList.innerHTML = "";

  jobs.forEach((job) => {
    const item = document.createElement("div");
    item.className = "queue-item";
    const detail = `${job.message || job.status || "Processing"}${job.duration_seconds ? ` - ${formatTime(job.duration_seconds)}` : ""}`;
    item.innerHTML = `
      <div>
        <strong></strong>
        <span></span>
      </div>
    `;
    item.querySelector("strong").textContent = statusTitle(job);
    item.querySelector("span").textContent = detail;

    if (job.session_id) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = job.status === "completed" ? "View" : "Open";
      button.addEventListener("click", () => loadLab(job.session_id));
      item.appendChild(button);
    }

    queueList.appendChild(item);
  });
}

function statusTitle(job) {
  if (job.status === "queued") {
    return job.queue_position ? `Queued #${job.queue_position}` : "Queued";
  }
  if (job.status === "extracting") {
    return "Extracting Frames";
  }
  if (job.status === "transcribing") {
    return "Transcribing";
  }
  if (job.status === "reading") {
    return "Reading Screen";
  }
  if (job.status === "breaking_down") {
    return "Breaking Down";
  }
  if (job.status === "completed") {
    return "Complete";
  }
  if (job.status === "failed") {
    return "Failed";
  }
  return "Processing";
}

function completeLab(data) {
  lastSessionId = data.session_id;
  breakdownOutput.textContent = data.breakdown || "";
  transcriptOutput.textContent = data.transcript || "";
  recordResults.classList.remove("hidden");
  saveViewButton.classList.remove("hidden");
  setStatus("Ready");
}

async function fetchLabs(query = "") {
  sessionsList.innerHTML = '<div class="empty-state">Loading labs...</div>';
  const url = query ? `/api/labs?q=${encodeURIComponent(query)}` : "/api/labs";
  try {
    const response = await fetch(url);
    const sessions = await response.json();
    if (!response.ok) {
      throw new Error(sessions.error || "Could not load labs");
    }
    renderLabs(sessions);
  } catch (error) {
    sessionsList.innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

function renderLabs(sessions) {
  if (!sessions.length) {
    sessionsList.innerHTML = '<div class="empty-state">No labs found.</div>';
    return;
  }

  sessionsList.innerHTML = "";
  sessions.forEach((session) => {
    const card = document.createElement("button");
    card.className = "session-card";
    card.type = "button";
    card.innerHTML = `
      <h3></h3>
      <time></time>
      <p></p>
    `;
    card.querySelector("h3").textContent = session.title;
    card.querySelector("time").textContent = formatDate(session.created_at);
    const summary = session.breakdown || "";
    card.querySelector("p").textContent = summary.length > 120 ? `${summary.slice(0, 120)}...` : summary;
    card.addEventListener("click", () => loadLab(session.id));
    sessionsList.appendChild(card);
  });
}

async function loadLab(id) {
  try {
    const response = await fetch(`/api/labs/${id}`);
    const session = await response.json();
    if (!response.ok) {
      throw new Error(session.error || "Could not load lab");
    }
    currentDetailId = session.id;
    detailTitle.textContent = session.title;
    detailDate.textContent = formatDate(session.created_at);
    detailBreakdown.textContent = session.breakdown || "";
    detailTranscript.textContent = session.transcript || "";
    detailOcr.textContent = session.ocr_text || "";
    ocrPanel.classList.toggle("hidden", !session.ocr_text);
    renderFrames(session);
    renderOutputPaths(session);
    showView("detail");
  } catch (error) {
    sessionsList.innerHTML = `<div class="empty-state">${error.message}</div>`;
    showView("history");
  }
}

function renderFrames(session) {
  const frames = session.frames || [];
  framesPanel.classList.toggle("hidden", frames.length === 0);
  framesGrid.innerHTML = "";
  frames.forEach((_frame, index) => {
    const image = document.createElement("img");
    image.alt = `Screen frame ${index + 1}`;
    image.loading = "lazy";
    image.src = `/api/labs/${session.id}/frames/${index}`;
    framesGrid.appendChild(image);
  });
}

function renderOutputPaths(session) {
  const paths = [
    ["Recording", session.recording_path],
    ["Transcript", session.transcript_path],
    ["Breakdown", session.breakdown_path],
    ["Combined", session.combined_path],
    ["PDF", session.pdf_path],
  ].filter(([, path]) => path);

  if (!paths.length) {
    outputPaths.innerHTML = '<div class="empty-state">Files will appear after processing finishes.</div>';
    return;
  }

  outputPaths.innerHTML = "";
  paths.forEach(([label, path]) => {
    const row = document.createElement("div");
    row.className = "output-path";
    row.innerHTML = "<strong></strong><code></code>";
    row.querySelector("strong").textContent = label;
    row.querySelector("code").textContent = path;
    outputPaths.appendChild(row);
  });
}

async function openOutputsFolder() {
  try {
    const response = await fetch("/api/labs/outputs/open", { method: "POST" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Could not open outputs folder");
    }
    setStatus("Outputs folder opened");
  } catch (error) {
    setStatus(error.message || "Could not open outputs folder");
  }
}

navLinks.forEach((link) => {
  link.addEventListener("click", () => showView(link.dataset.view));
});

recordButton.addEventListener("click", () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    stopRecording();
  } else {
    startRecording();
  }
});

markerButton.addEventListener("click", addMarker);
markerInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    addMarker();
  }
});

saveViewButton.addEventListener("click", () => {
  if (lastSessionId) {
    loadLab(lastSessionId);
  }
});

searchInput.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    fetchLabs(searchInput.value.trim());
  }, 300);
});

backHistoryButton.addEventListener("click", () => showView("history"));
openOutputsButton.addEventListener("click", openOutputsFolder);

exportButton.addEventListener("click", () => {
  if (currentDetailId) {
    window.location.href = `/api/labs/${currentDetailId}/export`;
  }
});

window.addEventListener("beforeunload", (event) => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    event.preventDefault();
    event.returnValue = "";
  }
});

if (activeJobIds.length) {
  setStatus("Checking saved lab jobs...");
  activeJobIds.forEach((jobId) => {
    addJob(jobId, { job_id: jobId, status: "checking", message: "Checking status" });
    pollJob(jobId);
  });
}
