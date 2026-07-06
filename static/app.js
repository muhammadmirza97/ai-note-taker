const views = {
  auth: document.querySelector("#auth-view"),
  dashboard: document.querySelector("#dashboard-view"),
  capture: document.querySelector("#capture-view"),
  detail: document.querySelector("#detail-view"),
};

const navLinks = document.querySelectorAll(".nav-link");
const authForm = document.querySelector("#auth-form");
const authTitle = document.querySelector("#auth-title");
const authEmail = document.querySelector("#auth-email");
const authPassword = document.querySelector("#auth-password");
const authMessage = document.querySelector("#auth-message");
const authSubmitButton = document.querySelector("#auth-submit-button");
const authModeButton = document.querySelector("#auth-mode-button");
const passwordResetButton = document.querySelector("#password-reset-button");
const logoutButton = document.querySelector("#logout-button");
const dashboardRecordButton = document.querySelector("#dashboard-record-button");
const recordButton = document.querySelector("#record-button");
const pauseButton = document.querySelector("#pause-button");
const stopButton = document.querySelector("#stop-button");
const recordingTimer = document.querySelector("#recording-timer");
const recordingState = document.querySelector("#recording-state");
const levelBar = document.querySelector("#level-bar");
const statusText = document.querySelector("#status-text");
const processingPanel = document.querySelector("#processing-panel");
const queueList = document.querySelector("#queue-list");
const recordResults = document.querySelector("#record-results");
const summaryOutput = document.querySelector("#summary-output");
const transcriptOutput = document.querySelector("#transcript-output");
const saveViewButton = document.querySelector("#save-view-button");
const openOutputsButton = document.querySelector("#open-outputs-button");
const searchInput = document.querySelector("#search-input");
const dateFilter = document.querySelector("#date-filter");
const sessionsList = document.querySelector("#sessions-list");
const dashboardInsight = document.querySelector("#dashboard-insight");
const recommendationsList = document.querySelector("#recommendations-list");
const fileInput = document.querySelector("#file-input");
const uploadDropzone = document.querySelector("#upload-dropzone");
const uploadMessage = document.querySelector("#upload-message");
const backHistoryButton = document.querySelector("#back-history-button");
const detailTitle = document.querySelector("#detail-title");
const detailDate = document.querySelector("#detail-date");
const overviewExportButton = document.querySelector("#overview-export-button");
const overviewDate = document.querySelector("#overview-date");
const overviewSource = document.querySelector("#overview-source");
const overviewDuration = document.querySelector("#overview-duration");
const overviewStatus = document.querySelector("#overview-status");
const overviewSummary = document.querySelector("#overview-summary");
const overviewWeakTopics = document.querySelector("#overview-weak-topics");
const overviewRecommendations = document.querySelector("#overview-recommendations");
const detailSummary = document.querySelector("#detail-summary");
const detailTranscript = document.querySelector("#detail-transcript");
const detailKeyPoints = document.querySelector("#detail-key-points");
const detailTerms = document.querySelector("#detail-terms");
const detailQuiz = document.querySelector("#detail-quiz");
const transcriptSearch = document.querySelector("#transcript-search");
const outputPaths = document.querySelector("#output-paths");
const toggleAnswersButton = document.querySelector("#toggle-answers-button");
const tabButtons = document.querySelectorAll(".tab-button");
const chatSuggestions = document.querySelector("#chat-suggestions");
const chatMessages = document.querySelector("#chat-messages");
const chatForm = document.querySelector("#chat-form");
const chatInput = document.querySelector("#chat-input");
const clearChatButton = document.querySelector("#clear-chat-button");
const createFlashcardsButton = document.querySelector("#create-flashcards-button");
const regenerateFlashcardsButton = document.querySelector("#regenerate-flashcards-button");
const flashcardEmpty = document.querySelector("#flashcard-empty");
const flashcardStudy = document.querySelector("#flashcard-study");
const flashcardProgress = document.querySelector("#flashcard-progress");
const flashcardCard = document.querySelector("#flashcard-card");
const flashcardSideLabel = document.querySelector("#flashcard-side-label");
const flashcardContent = document.querySelector("#flashcard-content");
const prevFlashcardButton = document.querySelector("#prev-flashcard-button");
const nextFlashcardButton = document.querySelector("#next-flashcard-button");
const gotItButton = document.querySelector("#got-it-button");
const notYetButton = document.querySelector("#not-yet-button");
const deleteFlashcardButton = document.querySelector("#delete-flashcard-button");
const quizPracticeBanner = document.querySelector("#quiz-practice-banner");
const quizForm = document.querySelector("#quiz-form");
const submitQuizButton = document.querySelector("#submit-quiz-button");
const tryAgainButton = document.querySelector("#try-again-button");
const quizResult = document.querySelector("#quiz-result");
const quizAttempts = document.querySelector("#quiz-attempts");
const createMindMapButton = document.querySelector("#create-mind-map-button");
const downloadMindMapButton = document.querySelector("#download-mind-map-button");
const mindMapEmpty = document.querySelector("#mind-map-empty");
const mindMapShell = document.querySelector("#mind-map-shell");
const mindMapSvg = document.querySelector("#mind-map-svg");
const mindMapActions = document.querySelector("#mind-map-actions");
const generateVideoScriptButton = document.querySelector("#generate-video-script-button");
const generatePodcastScriptButton = document.querySelector("#generate-podcast-script-button");
const podcastStyleSelect = document.querySelector("#podcast-style-select");
const videoScriptOutput = document.querySelector("#video-script-output");
const podcastScriptOutput = document.querySelector("#podcast-script-output");
const exportIncludeTranscript = document.querySelector("#export-include-transcript");
const exportIncludeQuiz = document.querySelector("#export-include-quiz");
const exportIncludeFlashcards = document.querySelector("#export-include-flashcards");
const exportIncludeMindMap = document.querySelector("#export-include-mind-map");

const RECOVERY_DB_NAME = "lecture-notes-recovery";
const RECOVERY_DB_VERSION = 1;
const RECOVERY_INTERVAL_MS = 10000;
const SUPPORTED_EXTENSIONS = [".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".aac", ".mov", ".txt", ".md", ".markdown"];

let mediaRecorder = null;
let chunks = [];
let startedAt = 0;
let elapsedBeforePause = 0;
let timerId = null;
let levelAnimationId = null;
let audioContext = null;
let analyser = null;
let lastSessionId = null;
let currentDetailId = null;
let currentSession = null;
let searchTimer = null;
let activeJobIds = loadStoredJobs();
let jobStates = {};
let currentRecording = null;
let chunkSequence = 0;
let chunkSaveQueue = Promise.resolve();
let stopRequested = false;
let recoveryUploadStarted = false;
let answersVisible = false;
let chatSuggestionValues = [];
let flashcards = [];
let flashcardIndex = 0;
let flashcardShowingBack = false;
let quizQuestions = [];
let quizAnswers = {};
let mindMap = null;
let selectedMindMapNodeId = "";
let authMode = "login";
let signedInUser = null;

function getCookie(name) {
  return document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${name}=`))
    ?.slice(name.length + 1) || "";
}

const nativeFetch = window.fetch.bind(window);
window.fetch = (input, init = {}) => {
  const headers = new Headers(init.headers || {});
  const csrfToken = getCookie("lecture_notes_csrf");
  if (csrfToken && !headers.has("X-CSRF-Token")) {
    headers.set("X-CSRF-Token", decodeURIComponent(csrfToken));
  }
  return nativeFetch(input, { ...init, headers }).then((response) => {
    if (response.status === 401 && !String(input).includes("/api/auth/")) {
      showSignedOut("Please sign in again before continuing.");
    }
    return response;
  });
};

function loadStoredJobs() {
  const legacyJobId = window.localStorage.getItem("activeLectureJobId");
  let jobs = [];
  try {
    jobs = JSON.parse(window.localStorage.getItem("activeLectureJobIds") || "[]");
  } catch (error) {
    jobs = [];
  }
  if (legacyJobId && !jobs.includes(legacyJobId)) {
    jobs.push(legacyJobId);
  }
  window.localStorage.removeItem("activeLectureJobId");
  return jobs.filter((jobId) => !String(jobId).startsWith("recovery-"));
}

function saveStoredJobs() {
  window.localStorage.setItem("activeLectureJobIds", JSON.stringify(activeJobIds));
}

function openRecoveryDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(RECOVERY_DB_NAME, RECOVERY_DB_VERSION);
    request.addEventListener("upgradeneeded", () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("recordings")) {
        db.createObjectStore("recordings", { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains("chunks")) {
        const store = db.createObjectStore("chunks", { keyPath: ["recordingId", "sequence"] });
        store.createIndex("recordingId", "recordingId", { unique: false });
      }
    });
    request.addEventListener("success", () => resolve(request.result));
    request.addEventListener("error", () => reject(request.error));
  });
}

function requestToPromise(request) {
  return new Promise((resolve, reject) => {
    request.addEventListener("success", () => resolve(request.result));
    request.addEventListener("error", () => reject(request.error));
  });
}

function transactionDone(transaction) {
  return new Promise((resolve, reject) => {
    transaction.addEventListener("complete", resolve);
    transaction.addEventListener("error", () => reject(transaction.error));
    transaction.addEventListener("abort", () => reject(transaction.error));
  });
}

async function putRecoveryRecording(recording) {
  const db = await openRecoveryDb();
  const tx = db.transaction("recordings", "readwrite");
  tx.objectStore("recordings").put(recording);
  await transactionDone(tx);
  db.close();
}

async function updateRecoveryRecording(id, updates) {
  const db = await openRecoveryDb();
  const readTx = db.transaction("recordings", "readonly");
  const recording = await requestToPromise(readTx.objectStore("recordings").get(id));
  if (recording) {
    const writeTx = db.transaction("recordings", "readwrite");
    writeTx.objectStore("recordings").put({ ...recording, ...updates });
    await transactionDone(writeTx);
  }
  db.close();
}

async function putRecoveryChunk(recordingId, sequence, blob) {
  const db = await openRecoveryDb();
  const tx = db.transaction("chunks", "readwrite");
  tx.objectStore("chunks").put({ recordingId, sequence, blob, size: blob.size, savedAt: Date.now() });
  await transactionDone(tx);
  db.close();
}

async function getRecoveryRecordings() {
  const db = await openRecoveryDb();
  const tx = db.transaction("recordings", "readonly");
  const recordings = await requestToPromise(tx.objectStore("recordings").getAll());
  db.close();
  return recordings;
}

async function getRecoveryChunks(recordingId) {
  const db = await openRecoveryDb();
  const tx = db.transaction("chunks", "readonly");
  const index = tx.objectStore("chunks").index("recordingId");
  const chunksForRecording = await requestToPromise(index.getAll(recordingId));
  db.close();
  return chunksForRecording.sort((a, b) => a.sequence - b.sequence);
}

async function deleteRecoveryRecording(recordingId) {
  const db = await openRecoveryDb();
  const readTx = db.transaction("chunks", "readonly");
  const chunksForRecording = await requestToPromise(readTx.objectStore("chunks").index("recordingId").getAll(recordingId));
  const tx = db.transaction(["recordings", "chunks"], "readwrite");
  tx.objectStore("recordings").delete(recordingId);
  const chunkStore = tx.objectStore("chunks");
  chunksForRecording.forEach((chunk) => {
    chunkStore.delete([chunk.recordingId, chunk.sequence]);
  });
  await transactionDone(tx);
  db.close();
}

function createRecordingId() {
  if (window.crypto && window.crypto.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `recording-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function setAuthMode(mode) {
  authMode = mode;
  const isSignup = mode === "signup";
  const isReset = mode === "reset";
  authTitle.textContent = isSignup ? "Create your account" : isReset ? "Reset password" : "Welcome back";
  authSubmitButton.textContent = isSignup ? "Create account" : isReset ? "Update password" : "Sign in";
  authPassword.autocomplete = isSignup || isReset ? "new-password" : "current-password";
  authModeButton.textContent = isSignup ? "I already have an account" : "Create your account";
  passwordResetButton.classList.toggle("hidden", isReset);
  authMessage.textContent = "";
  authMessage.classList.remove("error");
}

function showSignedOut(message = "") {
  signedInUser = null;
  logoutButton.classList.add("hidden");
  navLinks.forEach((link) => link.disabled = true);
  showView("auth");
  if (message) {
    authMessage.textContent = message;
    authMessage.classList.add("error");
  }
}

function showSignedIn(user) {
  signedInUser = user;
  logoutButton.classList.remove("hidden");
  navLinks.forEach((link) => link.disabled = false);
  showView("dashboard");
}

async function initAuth() {
  setAuthMode("login");
  try {
    const response = await fetch("/api/auth/me");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "");
    }
    showSignedIn(data.user);
    if (activeJobIds.length) {
      setStatus("Checking saved processing jobs.", 1);
      activeJobIds.forEach((jobId) => {
        addJob(jobId, { job_id: jobId, status: "checking", message: "Checking status." });
        pollJob(jobId);
      });
    }
    recoverSavedRecordings();
  } catch (error) {
    showSignedOut("");
  }
}

async function submitAuth(event) {
  event.preventDefault();
  const email = authEmail.value.trim();
  const password = authPassword.value;
  if (!email) {
    authMessage.textContent = "Enter your email address.";
    authMessage.classList.add("error");
    return;
  }
  if (password.length < 8) {
    authMessage.textContent = "That password is too short - use at least 8 characters.";
    authMessage.classList.add("error");
    return;
  }

  authSubmitButton.disabled = true;
  authMessage.textContent = authMode === "reset" ? "Updating your password..." : "Signing you in...";
  authMessage.classList.remove("error");
  try {
    const endpoint = authMode === "signup" ? "/api/auth/signup" : authMode === "reset" ? "/api/auth/reset-password" : "/api/auth/login";
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "That did not work. Please try again.");
    }
    if (authMode === "reset") {
      authMessage.textContent = "Password updated. Sign in with the new password.";
      setAuthMode("login");
      return;
    }
    showSignedIn(data.user);
    if (data.claimed_lectures) {
      setStatus(`Imported ${data.claimed_lectures} existing lecture${data.claimed_lectures === 1 ? "" : "s"} into your account.`, 0);
    }
  } catch (error) {
    authMessage.textContent = error.message || "That did not work. Please try again.";
    authMessage.classList.add("error");
  } finally {
    authSubmitButton.disabled = false;
  }
}

async function logout() {
  await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined);
  showSignedOut("");
}

function showView(name) {
  Object.entries(views).forEach(([key, view]) => {
    view.classList.toggle("active", key === name);
  });
  navLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.view === name);
  });
  if (name === "dashboard") {
    fetchSessions();
    fetchRecommendations();
  }
}

function showTab(name) {
  tabButtons.forEach((button) => button.classList.toggle("active", button.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${name}`);
  });
}

function setStatus(message, step = 0) {
  statusText.textContent = message;
  processingPanel.classList.remove("hidden");
  document.querySelectorAll(".step").forEach((item) => {
    item.classList.toggle("active", Number(item.dataset.step) === Number(step));
  });
}

function setUploadMessage(message, isError = false) {
  uploadMessage.textContent = message;
  uploadMessage.classList.toggle("error", isError);
}

function formatTime(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function elapsedRecordingSeconds() {
  if (!startedAt) {
    return Math.round(elapsedBeforePause / 1000);
  }
  return Math.round((elapsedBeforePause + Date.now() - startedAt) / 1000);
}

function startTimer() {
  startedAt = Date.now();
  timerId = window.setInterval(() => {
    recordingTimer.textContent = formatTime(elapsedRecordingSeconds());
  }, 500);
}

function pauseTimer() {
  if (startedAt) {
    elapsedBeforePause += Date.now() - startedAt;
  }
  startedAt = 0;
  if (timerId) {
    window.clearInterval(timerId);
    timerId = null;
  }
  recordingTimer.textContent = formatTime(Math.round(elapsedBeforePause / 1000));
}

function stopTimer() {
  pauseTimer();
  elapsedBeforePause = 0;
}

function setRecordingControls(state) {
  const isRecording = state === "recording";
  const isPaused = state === "paused";
  recordButton.classList.toggle("recording", isRecording);
  recordButton.classList.toggle("paused", isPaused);
  recordButton.disabled = isRecording || isPaused;
  pauseButton.disabled = !(isRecording || isPaused);
  pauseButton.textContent = isPaused ? "Resume" : "Pause";
  stopButton.disabled = !(isRecording || isPaused);
  recordingState.textContent = state === "idle" ? "Ready" : state === "paused" ? "Paused" : "Recording";
}

function preferredMimeType() {
  const types = ["audio/webm;codecs=opus", "audio/webm", "audio/wav"];
  return types.find((type) => window.MediaRecorder && MediaRecorder.isTypeSupported(type)) || "";
}

function startLevelMeter(stream) {
  try {
    audioContext = new AudioContext();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    const draw = () => {
      analyser.getByteFrequencyData(data);
      const average = data.reduce((sum, value) => sum + value, 0) / data.length;
      levelBar.style.width = `${Math.min(100, Math.round((average / 160) * 100))}%`;
      levelAnimationId = window.requestAnimationFrame(draw);
    };
    draw();
  } catch (error) {
    levelBar.style.width = "0%";
  }
}

function stopLevelMeter() {
  if (levelAnimationId) {
    window.cancelAnimationFrame(levelAnimationId);
    levelAnimationId = null;
  }
  if (audioContext) {
    audioContext.close().catch(() => undefined);
    audioContext = null;
  }
  analyser = null;
  levelBar.style.width = "0%";
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    chunks = [];
    const mimeType = preferredMimeType();
    const recordingId = createRecordingId();
    startedAt = Date.now();
    elapsedBeforePause = 0;
    chunkSequence = 0;
    chunkSaveQueue = Promise.resolve();
    stopRequested = false;
    recoveryUploadStarted = false;
    currentRecording = {
      id: recordingId,
      mimeType: mimeType || "audio/webm",
      startedAt,
      status: "recording",
    };
    await putRecoveryRecording(currentRecording);

    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size > 0) {
        const sequence = chunkSequence;
        chunkSequence += 1;
        chunks.push(event.data);
        chunkSaveQueue = chunkSaveQueue.then(() => putRecoveryChunk(recordingId, sequence, event.data));
      }
    });
    mediaRecorder.addEventListener("error", () => handleRecorderFailure(stream));
    mediaRecorder.addEventListener("stop", async () => {
      stream.getTracks().forEach((track) => track.stop());
      stopLevelMeter();
      await chunkSaveQueue.catch(() => undefined);
      if (stopRequested || !recoveryUploadStarted) {
        uploadSavedRecording(recordingId, stopRequested ? "normal" : "recovered");
      }
    });

    recordResults.classList.add("hidden");
    saveViewButton.classList.add("hidden");
    lastSessionId = null;
    mediaRecorder.start(RECOVERY_INTERVAL_MS);
    setRecordingControls("recording");
    startTimer();
    startLevelMeter(stream);
    setStatus("Recording your lecture.", 1);
  } catch (error) {
    recordingState.textContent = "Please allow microphone access";
  }
}

function pauseOrResumeRecording() {
  if (!mediaRecorder) {
    return;
  }
  if (mediaRecorder.state === "recording") {
    mediaRecorder.pause();
    pauseTimer();
    setRecordingControls("paused");
    setStatus("Recording paused.", 1);
    return;
  }
  if (mediaRecorder.state === "paused") {
    mediaRecorder.resume();
    startTimer();
    setRecordingControls("recording");
    setStatus("Recording your lecture.", 1);
  }
}

function stopRecording() {
  if (mediaRecorder && (mediaRecorder.state === "recording" || mediaRecorder.state === "paused")) {
    stopRequested = true;
    stopTimer();
    setRecordingControls("idle");
    setStatus("Uploading your recording.", 1);
    recordButton.disabled = true;
    mediaRecorder.requestData();
    mediaRecorder.stop();
  }
}

function handleRecorderFailure(stream) {
  if (recoveryUploadStarted) {
    return;
  }
  recoveryUploadStarted = true;
  stopTimer();
  setRecordingControls("idle");
  setStatus("Recorder stopped unexpectedly. Saving captured audio.", 1);
  stream.getTracks().forEach((track) => track.stop());
  stopLevelMeter();
  if (currentRecording) {
    updateRecoveryRecording(currentRecording.id, {
      status: "interrupted",
      endedAt: Date.now(),
    }).finally(() => uploadSavedRecording(currentRecording.id, "recovered"));
  }
}

async function uploadSavedRecording(recordingId, reason = "normal") {
  const recordings = await getRecoveryRecordings();
  const recording = recordings.find((item) => item.id === recordingId);
  const savedChunks = await getRecoveryChunks(recordingId);
  const blobParts = savedChunks.length ? savedChunks.map((chunk) => chunk.blob) : chunks;
  const mimeType = recording?.mimeType || "audio/webm";
  const endedAt = Date.now();
  const durationSeconds = Math.max(
    0,
    Math.round(((recording?.endedAt || endedAt) - (recording?.startedAt || endedAt)) / 1000),
  );
  const blob = new Blob(blobParts, { type: mimeType });
  if (!blob.size) {
    setStatus("No audio was captured before recording stopped.", 0);
    recordButton.disabled = false;
    return;
  }

  const formData = new FormData();
  formData.append("audio", blob, mimeType.includes("wav") ? "lecture.wav" : "lecture.webm");
  formData.append("duration_seconds", String(durationSeconds));

  try {
    const prefix = reason === "recovered" ? "Uploading recovered recording." : "Uploading your recording.";
    setStatus(prefix, 1);
    await updateRecoveryRecording(recordingId, { status: "uploading", endedAt });
    const response = await fetch("/api/transcribe", { method: "POST", body: formData });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Upload failed. Please try again.");
    }
    await deleteRecoveryRecording(recordingId);
    if (data.job_id) {
      addJob(data.job_id, {
        job_id: data.job_id,
        status: data.status || "queued",
        message: data.message || "Waiting for its turn.",
        duration_seconds: durationSeconds,
        step: data.step || 1,
        source_type: "recorded",
      });
      setStatus("Recording uploaded. You can start the next recording.", 1);
      pollJob(data.job_id);
      return;
    }
    completeRecording(data);
  } catch (error) {
    await updateRecoveryRecording(recordingId, {
      status: "recoverable",
      endedAt,
      error: error.message || "Upload failed",
    }).catch(() => undefined);
    jobStates[`recovery-${recordingId}`] = {
      job_id: `recovery-${recordingId}`,
      status: "recoverable",
      message: "Saved locally. Upload when ready.",
      duration_seconds: durationSeconds,
      recording_id: recordingId,
    };
    renderQueue();
    setStatus(error.message || "Upload failed. Recording saved locally.", 1);
  } finally {
    currentRecording = null;
    chunks = [];
    recordButton.disabled = false;
  }
}

async function recoverSavedRecordings() {
  try {
    const recordings = await getRecoveryRecordings();
    recordings.forEach((recording) => {
      jobStates[`recovery-${recording.id}`] = {
        job_id: `recovery-${recording.id}`,
        status: "recoverable",
        message: "Saved locally after an interrupted recording.",
        duration_seconds: Math.max(0, Math.round(((recording.endedAt || Date.now()) - recording.startedAt) / 1000)),
        recording_id: recording.id,
      };
    });
    if (recordings.length) {
      renderQueue();
      setStatus("Recovered an interrupted recording. Upload it from the queue.", 1);
    }
  } catch (error) {
    setStatus("Could not check local recording recovery.", 0);
  }
}

function fileLooksSupported(file) {
  const name = file.name.toLowerCase();
  return file.type.startsWith("audio/") || file.type.startsWith("video/") || file.type.startsWith("text/") || SUPPORTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

async function uploadLectureFile(file) {
  if (!file) {
    return;
  }
  if (!fileLooksSupported(file)) {
    setUploadMessage("That file type is not ready in this version yet. Try audio, video, or plain text.", true);
    return;
  }

  const formData = new FormData();
  formData.append("file", file, file.name);
  formData.append("title", file.name.replace(/\.[^.]+$/, ""));

  try {
    setUploadMessage("Uploading your file.");
    setStatus("Uploading your file.", 1);
    const response = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Upload failed. Please try another file.");
    }
    addJob(data.job_id, {
      job_id: data.job_id,
      status: data.status || "queued",
      message: data.message || "Waiting for its turn.",
      step: data.step || 1,
    });
    setUploadMessage("Upload accepted. Notes will appear when processing finishes.");
    pollJob(data.job_id);
  } catch (error) {
    setUploadMessage(error.message || "Upload failed. Please try again.", true);
    setStatus(error.message || "Upload failed. Please try again.", 1);
  } finally {
    fileInput.value = "";
  }
}

function addJob(jobId, initialState = {}) {
  if (!activeJobIds.includes(jobId)) {
    activeJobIds.push(jobId);
  }
  jobStates[jobId] = { ...(jobStates[jobId] || {}), ...initialState };
  if (!String(jobId).startsWith("recovery-")) {
    saveStoredJobs();
  }
  renderQueue();
}

function removeStoredJob(jobId) {
  activeJobIds = activeJobIds.filter((id) => id !== jobId);
  saveStoredJobs();
}

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    const job = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(job.error || "Could not check processing status.");
    }
    jobStates[jobId] = job;
    renderQueue();
    setStatus(job.message || friendlyStatus(job.status), job.step || statusStep(job.status));

    if (job.status === "completed") {
      removeStoredJob(jobId);
      completeRecording(job);
      fetchSessions();
      return;
    }
    if (job.status === "failed") {
      removeStoredJob(jobId);
      setStatus(job.error || "Something went wrong. Please try again.", 0);
      return;
    }
    window.setTimeout(() => pollJob(jobId), 5000);
  } catch (error) {
    jobStates[jobId] = {
      ...(jobStates[jobId] || {}),
      job_id: jobId,
      status: "checking",
      message: error.message || "Checking processing status.",
    };
    renderQueue();
    window.setTimeout(() => pollJob(jobId), 10000);
  }
}

function statusStep(status) {
  if (status === "transcribing") {
    return 2;
  }
  if (status === "generating" || status === "summarising") {
    return 3;
  }
  return 1;
}

function friendlyStatus(status) {
  if (status === "queued") return "Waiting for its turn.";
  if (status === "transcribing") return "Listening to your lecture.";
  if (status === "generating" || status === "summarising") return "Turning your lecture into study notes.";
  if (status === "completed") return "Your study notes are ready.";
  if (status === "failed") return "Something went wrong.";
  if (status === "recoverable") return "Saved locally. Upload when ready.";
  return "Working on your lecture.";
}

function renderQueue() {
  const jobs = Object.values(jobStates).sort((a, b) => String(a.created_at || "").localeCompare(String(b.created_at || "")));
  processingPanel.classList.toggle("hidden", jobs.length === 0);
  queueList.innerHTML = "";

  jobs.forEach((job) => {
    const item = document.createElement("div");
    item.className = "queue-item";
    const detail = `${job.message || friendlyStatus(job.status)}${job.duration_seconds ? ` - ${formatTime(job.duration_seconds)}` : ""}`;
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
      button.className = "secondary-button";
      button.textContent = job.status === "completed" ? "Open" : "View";
      button.addEventListener("click", () => loadSession(job.session_id));
      item.appendChild(button);
    }
    if (job.status === "recoverable" && job.recording_id) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button";
      button.textContent = "Upload";
      button.addEventListener("click", () => uploadSavedRecording(job.recording_id, "recovered"));
      item.appendChild(button);
    }
    queueList.appendChild(item);
  });
}

function statusTitle(job) {
  if (job.status === "queued") return job.queue_position ? `Queued #${job.queue_position}` : "Queued";
  if (job.status === "transcribing") return "Transcribing";
  if (job.status === "generating" || job.status === "summarising") return "Generating notes";
  if (job.status === "completed") return "Ready";
  if (job.status === "failed") return "Needs retry";
  if (job.status === "recoverable") return "Recovered recording";
  return "Processing";
}

function completeRecording(data) {
  lastSessionId = data.session_id;
  summaryOutput.textContent = data.short_summary || data.detailed_summary || data.summary || "";
  transcriptOutput.textContent = data.transcript || "";
  recordResults.classList.remove("hidden");
  saveViewButton.classList.remove("hidden");
  setStatus("Your study notes are ready.", 3);
}

async function fetchSessions() {
  sessionsList.innerHTML = '<div class="empty-state">Loading lectures...</div>';
  const params = new URLSearchParams();
  const query = searchInput.value.trim();
  if (query) params.set("q", query);
  if (dateFilter.value && dateFilter.value !== "all") params.set("date", dateFilter.value);
  const url = params.toString() ? `/api/sessions?${params}` : "/api/sessions";
  try {
    const response = await fetch(url);
    const sessions = await response.json();
    if (!response.ok) {
      throw new Error(sessions.error || "Could not load your lectures.");
    }
    renderSessions(sessions);
  } catch (error) {
    sessionsList.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  }
}

function renderSessions(sessions) {
  if (!sessions.length) {
    sessionsList.innerHTML = `
      <div class="empty-state">
        <h2>No lectures yet</h2>
        <p>Record a lecture or upload a file, and your study notes will appear here.</p>
        <div class="empty-actions">
          <button id="empty-record-button" class="primary-button" type="button">Record a lecture</button>
          <button id="empty-upload-button" class="secondary-button" type="button">Upload a file</button>
        </div>
      </div>
    `;
    document.querySelector("#empty-record-button").addEventListener("click", () => showView("capture"));
    document.querySelector("#empty-upload-button").addEventListener("click", () => {
      showView("capture");
      fileInput.click();
    });
    return;
  }

  sessionsList.innerHTML = "";
  sessions.forEach((session) => {
    const card = document.createElement("button");
    card.className = "session-card";
    card.type = "button";
    const statusClass = session.status === "failed" ? "status-pill failed" : "status-pill";
    card.innerHTML = `
      <div class="session-meta">
        <span></span>
        <span></span>
      </div>
      <h3></h3>
      <p></p>
      <span class="${statusClass}"></span>
    `;
    const meta = card.querySelectorAll(".session-meta span");
    meta[0].textContent = formatDate(session.created_at);
    meta[1].textContent = sourceLabel(session.source_type);
    card.querySelector("h3").textContent = session.title;
    card.querySelector("p").textContent = previewText(session.summary || session.error_message || "Transcript saved. Notes may still be generating.");
    card.querySelector(".status-pill").textContent = statusLabel(session.status);
    card.addEventListener("click", () => loadSession(session.id));
    sessionsList.appendChild(card);
  });
}

async function loadSession(id) {
  try {
    const response = await fetch(`/api/sessions/${id}`);
    const session = await response.json();
    if (!response.ok) {
      throw new Error(session.error || "Could not load that lecture.");
    }
    currentDetailId = session.id;
    currentSession = session;
    renderSessionDetail(session);
    showView("detail");
    showTab("overview");
  } catch (error) {
    sessionsList.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    showView("dashboard");
  }
}

function renderSessionDetail(session) {
  detailTitle.textContent = session.title;
  detailDate.textContent = formatDate(session.created_at);
  overviewDate.textContent = formatDate(session.created_at);
  overviewSource.textContent = sourceLabel(session.source_type);
  overviewDuration.textContent = session.duration_seconds ? formatTime(Number(session.duration_seconds)) : "Not timed";
  overviewStatus.textContent = statusLabel(session.status);
  overviewSummary.textContent = session.short_summary || session.detailed_summary || session.summary || "Notes are still being generated.";
  detailSummary.textContent = summaryText(session);
  detailTranscript.textContent = session.transcript || "";
  renderKeyPoints(session.key_point_citations || [], session.key_points || "None mentioned.");
  detailTerms.textContent = session.terms || "None mentioned.";
  detailQuiz.innerHTML = renderQuiz(session.quiz || "None mentioned.");
  detailQuiz.classList.toggle("answers-hidden", !answersVisible);
  toggleAnswersButton.textContent = answersVisible ? "Hide answers" : "Reveal answers";
  renderWeakTopics(session.weak_topics || []);
  renderOutputPaths(session);
  mindMap = session.mind_map || null;
  renderMindMap();
  videoScriptOutput.textContent = session.video_script || "";
  podcastScriptOutput.textContent = session.podcast_script || "";
  podcastStyleSelect.value = session.podcast_style || "two_voice";
  loadChat();
  loadFlashcards();
  loadQuiz();
  renderOverviewRecommendations();
}

function summaryText(session) {
  const parts = [];
  if (session.short_summary) {
    parts.push(`## Short Summary\n\n${session.short_summary}`);
  }
  parts.push(`## Detailed Notes\n\n${session.detailed_summary || session.summary || "Notes are still being generated."}`);
  return parts.join("\n\n");
}

function renderQuiz(text) {
  return escapeHtml(text).replace(/(^|\n)(\s*Answer:[^\n]*)/g, '$1<span class="answer-line">$2</span>');
}

function renderOutputPaths(session) {
  const paths = [
    ["Transcript", session.transcript_path],
    ["Markdown", session.combined_path],
    ["PDF", session.pdf_path],
    ["Summary", session.summary_path],
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

function renderKeyPoints(citations, fallbackText) {
  detailKeyPoints.innerHTML = "";
  if (citations.length) {
    citations.forEach((item) => {
      const row = document.createElement("div");
      row.className = "key-point-row";
      const text = document.createElement("span");
      text.textContent = item.text;
      row.appendChild(text);
      if (item.source) {
        row.appendChild(createCitationChip(item.source));
      }
      detailKeyPoints.appendChild(row);
    });
    return;
  }
  detailKeyPoints.textContent = fallbackText;
}

function createCitationChip(source) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "source-chip";
  button.textContent = source.label || "Source";
  button.addEventListener("click", () => jumpToTranscript(source.seconds, source.label));
  return button;
}

function jumpToTranscript(seconds, label) {
  showTab("transcript");
  const transcript = currentSession?.transcript || "";
  detailTranscript.innerHTML = renderTranscriptWithHighlight(transcript, label);
  const mark = detailTranscript.querySelector(".jump-highlight");
  if (mark) {
    mark.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => mark.classList.remove("jump-highlight"), 2200);
  }
}

function renderTranscriptWithHighlight(text, label) {
  const escaped = escapeHtml(text);
  if (!label) {
    return escaped;
  }
  const safeLabel = escapeRegex(`[${label}]`);
  return escaped.replace(new RegExp(safeLabel), `<mark class="transcript-mark jump-highlight">[${escapeHtml(label)}]</mark>`);
}

function renderMindMap() {
  mindMapEmpty.classList.toggle("hidden", !!mindMap);
  mindMapShell.classList.toggle("hidden", !mindMap);
  mindMapSvg.innerHTML = "";
  mindMapActions.innerHTML = "";
  if (!mindMap) {
    return;
  }
  const nodes = flattenMindMap(mindMap);
  const positioned = layoutMindMap(nodes);
  positioned.links.forEach((link) => {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", link.from.x);
    line.setAttribute("y1", link.from.y);
    line.setAttribute("x2", link.to.x);
    line.setAttribute("y2", link.to.y);
    line.setAttribute("class", "mind-map-link");
    mindMapSvg.appendChild(line);
  });
  positioned.nodes.forEach((item) => {
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("class", `mind-map-node ${item.node.id === selectedMindMapNodeId ? "selected" : ""}`);
    group.setAttribute("transform", `translate(${item.x}, ${item.y})`);
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", -70);
    rect.setAttribute("y", -22);
    rect.setAttribute("width", 140);
    rect.setAttribute("height", 44);
    rect.setAttribute("rx", 7);
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("dominant-baseline", "middle");
    text.textContent = item.node.label;
    group.appendChild(rect);
    group.appendChild(text);
    group.addEventListener("click", () => {
      selectedMindMapNodeId = item.node.id;
      renderMindMapActions(item.node);
      renderMindMap();
      if (item.node.source) {
        jumpToTranscript(item.node.source.seconds, item.node.source.label);
      }
    });
    mindMapSvg.appendChild(group);
  });
  if (selectedMindMapNodeId) {
    const node = nodes.find((item) => item.id === selectedMindMapNodeId);
    if (node) renderMindMapActions(node);
  }
}

function flattenMindMap(root) {
  const nodes = [];
  function visit(node, depth = 0, parent = null, index = 0) {
    nodes.push({ ...node, depth, parent, index });
    (node.children || []).forEach((child, childIndex) => visit(child, depth + 1, node.id, childIndex));
  }
  visit(root);
  return nodes;
}

function layoutMindMap(nodes) {
  const byDepth = {};
  nodes.forEach((node) => {
    byDepth[node.depth] = byDepth[node.depth] || [];
    byDepth[node.depth].push(node);
  });
  const positionedNodes = [];
  Object.entries(byDepth).forEach(([depthValue, group]) => {
    const depth = Number(depthValue);
    const y = 70 + depth * 150;
    group.forEach((node, index) => {
      const x = 100 + ((index + 1) * 760) / (group.length + 1);
      positionedNodes.push({ node, x, y });
    });
  });
  const lookup = Object.fromEntries(positionedNodes.map((item) => [item.node.id, item]));
  const links = positionedNodes
    .filter((item) => item.node.parent && lookup[item.node.parent])
    .map((item) => ({ from: lookup[item.node.parent], to: item }));
  return { nodes: positionedNodes, links };
}

function renderMindMapActions(node) {
  mindMapActions.innerHTML = "";
  const label = document.createElement("span");
  label.className = "inline-message";
  label.textContent = `Selected: ${node.label}`;
  const rename = document.createElement("button");
  rename.className = "secondary-button";
  rename.type = "button";
  rename.textContent = "Rename";
  rename.addEventListener("click", () => renameMindMapNode(node.id, node.label));
  const del = document.createElement("button");
  del.className = "secondary-button danger";
  del.type = "button";
  del.textContent = "Delete";
  del.addEventListener("click", () => deleteMindMapNode(node.id));
  mindMapActions.append(label, rename, del);
}

async function createMindMap() {
  if (!currentDetailId) return;
  createMindMapButton.disabled = true;
  mindMapEmpty.textContent = "Drawing your mind map...";
  try {
    const response = await fetch(`/api/sessions/${currentDetailId}/mind-map`, { method: "POST" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Could not create the mind map.");
    mindMap = data.mind_map;
    currentSession.mind_map = mindMap;
    renderMindMap();
  } catch (error) {
    mindMapEmpty.textContent = error.message || "Could not create the mind map. Please try again.";
  } finally {
    createMindMapButton.disabled = false;
  }
}

async function renameMindMapNode(nodeId, currentLabel) {
  const label = window.prompt("Rename this mind map node", currentLabel);
  if (!label) return;
  const response = await fetch(`/api/sessions/${currentDetailId}/mind-map/nodes/${encodeURIComponent(nodeId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  });
  const data = await response.json().catch(() => ({}));
  if (response.ok) {
    mindMap = data.mind_map;
    currentSession.mind_map = mindMap;
    renderMindMap();
  }
}

async function deleteMindMapNode(nodeId) {
  if (!window.confirm("Delete this mind map node?")) return;
  const response = await fetch(`/api/sessions/${currentDetailId}/mind-map/nodes/${encodeURIComponent(nodeId)}`, { method: "DELETE" });
  const data = await response.json().catch(() => ({}));
  if (response.ok) {
    mindMap = data.mind_map;
    selectedMindMapNodeId = "";
    renderMindMap();
  }
}

function downloadMindMapSvg() {
  if (!mindMap) return;
  const svg = mindMapSvg.cloneNode(true);
  svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const blob = new Blob([svg.outerHTML], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "mind-map.svg";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function generateVideoScript() {
  if (!currentDetailId) return;
  generateVideoScriptButton.disabled = true;
  videoScriptOutput.textContent = "Writing your video script...";
  try {
    const response = await fetch(`/api/sessions/${currentDetailId}/video-script`, { method: "POST" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Could not write the video script.");
    videoScriptOutput.textContent = data.video_script || "";
  } catch (error) {
    videoScriptOutput.textContent = error.message || "Could not write the video script. Please try again.";
  } finally {
    generateVideoScriptButton.disabled = false;
  }
}

async function generatePodcastScript() {
  if (!currentDetailId) return;
  generatePodcastScriptButton.disabled = true;
  podcastScriptOutput.textContent = "Writing your podcast script...";
  try {
    const response = await fetch(`/api/sessions/${currentDetailId}/podcast-script`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ style: podcastStyleSelect.value }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Could not write the podcast script.");
    podcastScriptOutput.textContent = data.podcast_script || "";
  } catch (error) {
    podcastScriptOutput.textContent = error.message || "Could not write the podcast script. Please try again.";
  } finally {
    generatePodcastScriptButton.disabled = false;
  }
}

async function fetchRecommendations() {
  try {
    const response = await fetch("/api/recommendations");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Could not load recommendations.");
    }
    dashboardInsight.textContent = data.weak_topics?.length
      ? `Topics to review: ${data.weak_topics.slice(0, 3).join(", ")}`
      : "Take a quiz and I'll show you what to focus on.";
    renderRecommendations(recommendationsList, data.recommendations || []);
  } catch (error) {
    dashboardInsight.textContent = "Study recommendations will appear after your first quiz.";
    recommendationsList.innerHTML = "";
  }
}

function renderOverviewRecommendations() {
  if (!currentSession) {
    return;
  }
  const weak = currentSession.weak_topics || [];
  const recommendations = weak.length
    ? [
        {
          session_id: currentSession.id,
          title: currentSession.title,
          action: "practice_topic",
          topic: weak[0].topic,
          reason: `Let's strengthen ${weak[0].topic}.`,
        },
      ]
    : [
        {
          session_id: currentSession.id,
          title: currentSession.title,
          action: "quiz",
          topic: "",
          reason: "Try the quiz to find what needs review.",
        },
      ];
  renderRecommendations(overviewRecommendations, recommendations);
}

function renderRecommendations(container, recommendations) {
  if (!recommendations.length) {
    container.innerHTML = '<div class="empty-state">No study nudges yet. Take a quiz and I will guide you.</div>';
    return;
  }
  container.innerHTML = "";
  recommendations.slice(0, 5).forEach((item) => {
    const card = document.createElement("div");
    card.className = "recommendation-card";
    card.innerHTML = `
      <div>
        <strong></strong>
        <span></span>
      </div>
      <button class="secondary-button" type="button">Start</button>
    `;
    card.querySelector("strong").textContent = item.topic || item.title;
    card.querySelector("span").textContent = item.reason || "A gentle next step.";
    card.querySelector("button").addEventListener("click", () => actOnRecommendation(item));
    container.appendChild(card);
  });
}

function actOnRecommendation(item) {
  const openAction = () => {
    if (item.action === "practice_topic") {
      showTab("quiz");
      loadPracticeQuiz(item.topic);
    } else if (item.action === "flashcards") {
      showTab("flashcards");
    } else if (item.action === "summary") {
      showTab("summary");
    } else {
      showTab("quiz");
    }
  };
  if (currentSession && Number(currentSession.id) === Number(item.session_id)) {
    openAction();
  } else {
    loadSession(item.session_id).then(openAction);
  }
}

function renderWeakTopics(topics) {
  if (!topics.length) {
    overviewWeakTopics.innerHTML = '<div class="empty-state">Take a quiz and I will show you what to focus on.</div>';
    return;
  }
  overviewWeakTopics.innerHTML = "";
  topics.forEach((topic) => {
    const item = document.createElement("div");
    item.className = "topic-chip";
    item.innerHTML = `
      <strong></strong>
      <span></span>
      <div class="section-actions">
        <button class="secondary-button" type="button">Practice this topic</button>
        <button class="secondary-button" type="button">Ask about this</button>
      </div>
    `;
    item.querySelector("strong").textContent = topic.topic;
    item.querySelector("span").textContent = topic.reason || "Let's strengthen this.";
    const buttons = item.querySelectorAll("button");
    buttons[0].addEventListener("click", () => {
      showTab("quiz");
      loadPracticeQuiz(topic.topic);
    });
    buttons[1].addEventListener("click", () => {
      showTab("ask");
      chatInput.value = `Explain ${topic.topic} more simply`;
      chatInput.focus();
    });
    overviewWeakTopics.appendChild(item);
  });
}

async function loadChat() {
  if (!currentDetailId) return;
  try {
    const response = await fetch(`/api/sessions/${currentDetailId}/chat`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Could not load conversation.");
    chatSuggestionValues = data.suggestions || [];
    renderChatSuggestions();
    renderChatMessages(data.messages || []);
  } catch (error) {
    chatMessages.innerHTML = '<div class="empty-state">Conversation will appear here when you ask a question.</div>';
  }
}

function renderChatSuggestions() {
  chatSuggestions.innerHTML = "";
  chatSuggestionValues.forEach((suggestion) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = suggestion;
    button.addEventListener("click", () => {
      chatInput.value = suggestion;
      chatInput.focus();
    });
    chatSuggestions.appendChild(button);
  });
}

function renderChatMessages(messages) {
  if (!messages.length) {
    chatMessages.innerHTML = '<div class="empty-state">Try a suggestion above or ask your own question.</div>';
    return;
  }
  chatMessages.innerHTML = "";
  messages.forEach((message) => {
    const item = document.createElement("div");
    item.className = `chat-message ${message.role === "user" ? "user" : "assistant"}`;
    if (message.role === "assistant") {
      item.innerHTML = linkifyCitations(message.content);
      item.querySelectorAll(".source-chip").forEach((chip) => {
        chip.addEventListener("click", () => jumpToTranscript(Number(chip.dataset.seconds || 0), chip.dataset.label));
      });
    } else {
      item.textContent = message.content;
    }
    chatMessages.appendChild(item);
  });
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function submitChat(event) {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message || !currentDetailId) return;
  chatInput.value = "";
  const loading = document.createElement("div");
  loading.className = "chat-message assistant";
  loading.textContent = "Thinking about this lecture...";
  chatMessages.appendChild(loading);
  try {
    const response = await fetch(`/api/sessions/${currentDetailId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "I couldn't answer that just now.");
    renderChatMessages(data.messages || []);
  } catch (error) {
    loading.textContent = error.message || "I couldn't answer that just now. Please try again.";
  }
}

async function clearChat() {
  if (!currentDetailId) return;
  await fetch(`/api/sessions/${currentDetailId}/chat`, { method: "DELETE" }).catch(() => undefined);
  renderChatMessages([]);
}

async function loadFlashcards() {
  if (!currentDetailId) return;
  try {
    const response = await fetch(`/api/sessions/${currentDetailId}/flashcards`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Could not load flashcards.");
    flashcards = data.flashcards || [];
    flashcardIndex = 0;
    flashcardShowingBack = false;
    renderFlashcards();
  } catch (error) {
    flashcards = [];
    renderFlashcards();
  }
}

function renderFlashcards() {
  flashcardEmpty.classList.toggle("hidden", flashcards.length > 0);
  flashcardStudy.classList.toggle("hidden", flashcards.length === 0);
  if (!flashcards.length) return;
  flashcardIndex = Math.max(0, Math.min(flashcardIndex, flashcards.length - 1));
  const card = flashcards[flashcardIndex];
  const notYetCount = flashcards.filter((item) => item.status === "not_yet").length;
  flashcardProgress.textContent = `Card ${flashcardIndex + 1} of ${flashcards.length} - ${notYetCount} marked Not yet`;
  flashcardSideLabel.textContent = flashcardShowingBack ? "Back" : "Front";
  flashcardContent.textContent = flashcardShowingBack ? card.back : card.front;
}

async function createFlashcards(regenerate = false) {
  if (!currentDetailId) return;
  if (regenerate && flashcards.length && !window.confirm("Regenerate flashcards? This replaces your current cards.")) {
    return;
  }
  createFlashcardsButton.disabled = true;
  regenerateFlashcardsButton.disabled = true;
  flashcardEmpty.textContent = "Creating flashcards from this lecture...";
  try {
    const response = await fetch(`/api/sessions/${currentDetailId}/flashcards`, { method: "POST" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Could not create flashcards.");
    flashcards = data.flashcards || [];
    currentSession.weak_topics = data.weak_topics || currentSession.weak_topics || [];
    renderWeakTopics(currentSession.weak_topics);
    renderFlashcards();
  } catch (error) {
    flashcardEmpty.textContent = error.message || "Could not create flashcards. Please try again.";
  } finally {
    createFlashcardsButton.disabled = false;
    regenerateFlashcardsButton.disabled = false;
  }
}

async function gradeFlashcard(statusValue) {
  const card = flashcards[flashcardIndex];
  if (!card) return;
  await fetch(`/api/flashcards/${card.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: statusValue }),
  }).catch(() => undefined);
  card.status = statusValue;
  flashcardShowingBack = false;
  flashcardIndex = Math.min(flashcardIndex + 1, flashcards.length - 1);
  renderFlashcards();
}

async function deleteCurrentFlashcard() {
  const card = flashcards[flashcardIndex];
  if (!card) return;
  await fetch(`/api/flashcards/${card.id}`, { method: "DELETE" }).catch(() => undefined);
  flashcards = flashcards.filter((item) => item.id !== card.id);
  flashcardShowingBack = false;
  renderFlashcards();
}

async function loadQuiz() {
  if (!currentDetailId) return;
  quizPracticeBanner.textContent = "";
  try {
    const response = await fetch(`/api/sessions/${currentDetailId}/quiz`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Could not load quiz.");
    quizQuestions = data.questions || [];
    quizAnswers = {};
    renderInteractiveQuiz();
    renderAttempts(data.attempts || []);
  } catch (error) {
    quizForm.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "Could not load quiz.")}</div>`;
  }
}

async function loadPracticeQuiz(topic) {
  if (!currentDetailId) return;
  quizPracticeBanner.textContent = topic ? `Practice quiz for ${topic}` : "";
  try {
    const response = await fetch(`/api/sessions/${currentDetailId}/quiz/practice?topic=${encodeURIComponent(topic || "")}`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Could not make a practice quiz.");
    quizQuestions = data.questions || [];
    quizAnswers = {};
    renderInteractiveQuiz();
  } catch (error) {
    quizPracticeBanner.textContent = error.message || "Could not make a practice quiz.";
  }
}

function renderInteractiveQuiz() {
  quizResult.innerHTML = "";
  if (!quizQuestions.length) {
    quizForm.innerHTML = '<div class="empty-state">Generate a quiz to start testing yourself.</div>';
    return;
  }
  quizForm.innerHTML = "";
  quizQuestions.forEach((question, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "quiz-question";
    wrapper.innerHTML = `
      <fieldset>
        <legend></legend>
        <label class="quiz-option"><input type="radio" name="${question.id}" value="A"> <span></span></label>
        <label class="quiz-option"><input type="radio" name="${question.id}" value="B"> <span></span></label>
        <label class="quiz-option"><input type="radio" name="${question.id}" value="C"> <span></span></label>
        <label class="quiz-option"><input type="radio" name="${question.id}" value="D"> <span></span></label>
      </fieldset>
    `;
    wrapper.querySelector("legend").textContent = `${index + 1}. ${question.question}`;
    wrapper.querySelectorAll(".quiz-option").forEach((label) => {
      const input = label.querySelector("input");
      label.querySelector("span").textContent = `${input.value}. ${question.options[input.value]}`;
      input.addEventListener("change", () => {
        quizAnswers[question.id] = input.value;
      });
    });
    quizForm.appendChild(wrapper);
  });
}

async function submitQuiz() {
  if (!currentDetailId || !quizQuestions.length) return;
  try {
    const response = await fetch(`/api/sessions/${currentDetailId}/quiz/attempts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers: quizAnswers }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Could not score quiz.");
    renderQuizResult(data.attempt);
    renderAttempts(data.attempts || []);
    currentSession.weak_topics = data.weak_topics || [];
    renderWeakTopics(currentSession.weak_topics);
    renderOverviewRecommendations();
    fetchRecommendations();
  } catch (error) {
    quizResult.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "Could not score quiz.")}</div>`;
  }
}

function renderQuizResult(attempt) {
  if (!attempt) return;
  const review = currentSession?.weak_topics?.[0]?.topic || "the questions you missed";
  quizResult.innerHTML = `
    <div class="quiz-feedback">
      <strong>Nice work - ${attempt.score}/${attempt.total} (${attempt.percent}%).</strong>
      <p>Next, review ${escapeHtml(review)}.</p>
    </div>
  `;
  (attempt.results || []).forEach((item) => {
    const div = document.createElement("div");
    div.className = "quiz-feedback";
    div.textContent = `${item.is_correct ? "Correct" : "Review"}: ${item.question} Your answer: ${item.selected_answer || "none"}. Correct answer: ${item.correct_answer}. ${item.explanation}`;
    quizResult.appendChild(div);
  });
}

function renderAttempts(attempts) {
  if (!attempts.length) {
    quizAttempts.innerHTML = '<div class="empty-state">No attempts yet. Take the quiz when you are ready.</div>';
    return;
  }
  quizAttempts.innerHTML = "";
  attempts.forEach((attempt, index) => {
    const item = document.createElement("div");
    item.className = "attempt-card";
    item.innerHTML = "<strong></strong><span></span>";
    item.querySelector("strong").textContent = `Attempt ${attempts.length - index} - ${attempt.score}/${attempt.total}`;
    item.querySelector("span").textContent = `${formatDate(attempt.created_at)} - ${attempt.percent}%`;
    quizAttempts.appendChild(item);
  });
}

async function regenerate(kind) {
  if (!currentDetailId) {
    return;
  }
  const button = document.querySelector(`[data-regenerate="${kind}"]`);
  const originalText = button?.textContent;
  if (button) {
    button.disabled = true;
    button.textContent = "Regenerating...";
  }
  try {
    setStatus("Regenerating that section.", 3);
    const response = await fetch(`/api/sessions/${currentDetailId}/generate/${kind}`, { method: "POST" });
    const session = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(session.error || "Could not regenerate that section.");
    }
    currentSession = session;
    renderSessionDetail(session);
    setStatus("Updated your study notes.", 3);
  } catch (error) {
    setStatus(error.message || "Could not regenerate that section.", 0);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

function exportSession(format) {
  if (!currentDetailId) {
    return;
  }
  const params = new URLSearchParams({
    format,
    include_transcript: String(exportIncludeTranscript.checked),
    include_quiz: String(exportIncludeQuiz.checked),
    include_flashcards: String(exportIncludeFlashcards.checked),
    include_mind_map: String(exportIncludeMindMap.checked),
  });
  window.location.href = `/api/sessions/${currentDetailId}/export?${params.toString()}`;
}

function copyTextFrom(id) {
  const element = document.querySelector(`#${id}`);
  if (!element) {
    return;
  }
  navigator.clipboard.writeText(element.innerText || element.textContent || "").then(
    () => setStatus("Copied.", 0),
    () => setStatus("Could not copy that text.", 0),
  );
}

function downloadTextFrom(id, filename) {
  const element = document.querySelector(`#${id}`);
  if (!element) {
    return;
  }
  const blob = new Blob([element.innerText || element.textContent || ""], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function searchTranscript(term) {
  const text = currentSession?.transcript || detailTranscript.textContent || "";
  if (!term.trim()) {
    detailTranscript.textContent = text;
    return;
  }
  const escapedTerm = escapeRegex(term.trim());
  const pattern = new RegExp(`(${escapedTerm})`, "gi");
  detailTranscript.innerHTML = escapeHtml(text).replace(pattern, '<mark class="transcript-mark">$1</mark>');
}

async function openOutputsFolder() {
  try {
    const response = await fetch("/api/outputs/open", { method: "POST" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Could not open outputs folder.");
    }
    setStatus("Outputs folder opened.", 0);
  } catch (error) {
    setStatus(error.message || "Could not open outputs folder.", 0);
  }
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value || "";
  }
  return date.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sourceLabel(value) {
  const label = String(value || "recorded").replace(/_/g, " ");
  return label.replace(/\b\w/g, (char) => char.toUpperCase());
}

function statusLabel(value) {
  if (value === "processing" || value === "transcribing") return "Transcribing";
  if (value === "generating") return "Generating notes";
  if (value === "failed") return "Needs retry";
  return "Ready";
}

function previewText(text) {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  return value.length > 130 ? `${value.slice(0, 130)}...` : value;
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function linkifyCitations(text) {
  return escapeHtml(text).replace(/\b(\d{1,2}:\d{2}(?::\d{2})?)\b/g, (match) => {
    return `<button class="source-chip" type="button" data-label="${match}" data-seconds="${timestampToSeconds(match)}">${match}</button>`;
  });
}

function timestampToSeconds(value) {
  const parts = value.split(":").map((part) => Number(part));
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return 0;
}

navLinks.forEach((link) => {
  link.addEventListener("click", () => showView(link.dataset.view));
});

authForm.addEventListener("submit", submitAuth);
authModeButton.addEventListener("click", () => setAuthMode(authMode === "signup" ? "login" : "signup"));
passwordResetButton.addEventListener("click", () => setAuthMode("reset"));
logoutButton.addEventListener("click", logout);

tabButtons.forEach((button) => {
  button.addEventListener("click", () => showTab(button.dataset.tab));
});

document.querySelectorAll("[data-tab-jump]").forEach((button) => {
  button.addEventListener("click", () => showTab(button.dataset.tabJump));
});

recordButton.addEventListener("click", startRecording);
pauseButton.addEventListener("click", pauseOrResumeRecording);
stopButton.addEventListener("click", stopRecording);
dashboardRecordButton.addEventListener("click", () => showView("capture"));
saveViewButton.addEventListener("click", () => {
  if (lastSessionId) {
    loadSession(lastSessionId);
  }
});

searchInput.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(fetchSessions, 300);
});
dateFilter.addEventListener("change", fetchSessions);
backHistoryButton.addEventListener("click", () => showView("dashboard"));
openOutputsButton.addEventListener("click", openOutputsFolder);
overviewExportButton.addEventListener("click", () => showTab("export"));
fileInput.addEventListener("change", () => uploadLectureFile(fileInput.files[0]));

["dragenter", "dragover"].forEach((eventName) => {
  uploadDropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadDropzone.classList.add("drag-over");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  uploadDropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadDropzone.classList.remove("drag-over");
  });
});

uploadDropzone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  uploadLectureFile(file);
});

document.querySelectorAll("[data-copy-target]").forEach((button) => {
  button.addEventListener("click", () => copyTextFrom(button.dataset.copyTarget));
});

document.querySelectorAll("[data-download-target]").forEach((button) => {
  button.addEventListener("click", () => downloadTextFrom(button.dataset.downloadTarget, button.dataset.downloadName || "notes.txt"));
});

document.querySelectorAll("[data-export-format]").forEach((button) => {
  button.addEventListener("click", () => exportSession(button.dataset.exportFormat));
});

document.querySelectorAll("[data-regenerate]").forEach((button) => {
  button.addEventListener("click", () => regenerate(button.dataset.regenerate));
});

toggleAnswersButton.addEventListener("click", () => {
  answersVisible = !answersVisible;
  detailQuiz.classList.toggle("answers-hidden", !answersVisible);
  toggleAnswersButton.textContent = answersVisible ? "Hide answers" : "Reveal answers";
});

transcriptSearch.addEventListener("input", () => searchTranscript(transcriptSearch.value));
chatForm.addEventListener("submit", submitChat);
clearChatButton.addEventListener("click", clearChat);
createFlashcardsButton.addEventListener("click", () => createFlashcards(false));
regenerateFlashcardsButton.addEventListener("click", () => createFlashcards(true));
flashcardCard.addEventListener("click", () => {
  flashcardShowingBack = !flashcardShowingBack;
  renderFlashcards();
});
prevFlashcardButton.addEventListener("click", () => {
  flashcardIndex = Math.max(0, flashcardIndex - 1);
  flashcardShowingBack = false;
  renderFlashcards();
});
nextFlashcardButton.addEventListener("click", () => {
  flashcardIndex = Math.min(flashcards.length - 1, flashcardIndex + 1);
  flashcardShowingBack = false;
  renderFlashcards();
});
gotItButton.addEventListener("click", () => gradeFlashcard("got_it"));
notYetButton.addEventListener("click", () => gradeFlashcard("not_yet"));
deleteFlashcardButton.addEventListener("click", deleteCurrentFlashcard);
submitQuizButton.addEventListener("click", submitQuiz);
tryAgainButton.addEventListener("click", () => {
  quizAnswers = {};
  renderInteractiveQuiz();
});
createMindMapButton.addEventListener("click", createMindMap);
downloadMindMapButton.addEventListener("click", downloadMindMapSvg);
generateVideoScriptButton.addEventListener("click", generateVideoScript);
generatePodcastScriptButton.addEventListener("click", generatePodcastScript);

window.addEventListener("beforeunload", (event) => {
  if (mediaRecorder && (mediaRecorder.state === "recording" || mediaRecorder.state === "paused")) {
    try {
      mediaRecorder.requestData();
    } catch (error) {
      // Best-effort flush before the browser decides whether to leave.
    }
    event.preventDefault();
    event.returnValue = "";
  }
});

setRecordingControls("idle");
initAuth();
