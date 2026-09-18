"use strict";

const $ = (id) => document.getElementById(id);

// Every request is time-bounded so a stalled backend never freezes a button.
const REQUEST_TIMEOUT_MS = 35000;
function fetchT(path, opts = {}, ms = REQUEST_TIMEOUT_MS) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  return fetch(path, { ...opts, signal: ctrl.signal }).finally(() =>
    clearTimeout(timer)
  );
}
const api = (path, opts) => fetchT(path, opts).then((r) => r.json());

// Show instant feedback on a button while an async action runs.
function busy(btn, label) {
  if (!btn) return () => {};
  const text = btn.textContent;
  const wasDisabled = btn.disabled;
  btn.disabled = true;
  btn.textContent = label;
  return () => {
    btn.disabled = wasDisabled;
    btn.textContent = text;
  };
}

// Render a child-safe subset of markdown (**bold**, line breaks) with HTML escaped.
function renderMarkdown(s) {
  return escapeHtml(String(s == null ? "" : s))
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/\n/g, "<br>");
}

// Friendly text for the common timeout/abort case.
function errMsg(err) {
  return err && err.name === "AbortError"
    ? "That took too long — please try again."
    : (err && err.message) || "Something went wrong — please try again.";
}

let stream = null;

// ---- Tabs ----------------------------------------------------------
const CAMERA_TABS = new Set(["dictation", "homework"]); // only these use the webcam

function syncCameraPanel(tab) {
  const panel = $("camera-panel");
  if (!panel) return;
  const show = CAMERA_TABS.has(tab);
  panel.hidden = !show;
  if (!show && stream) stopCamera(); // release the webcam on tabs that don't use it
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document
      .querySelectorAll(".tab-content")
      .forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    $("tab-" + btn.dataset.tab).classList.add("active");
    syncCameraPanel(btn.dataset.tab);
    if (btn.dataset.tab === "progress") loadProgress();
  });
});

syncCameraPanel(activeTab() || "dictation"); // set initial visibility for the default tab

// ---- Camera --------------------------------------------------------
async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true });
    $("video").srcObject = stream;
    $("cam-status").textContent = "Camera on";
    $("start-cam").textContent = "🛑 Stop camera";
  } catch (err) {
    $("cam-status").textContent = "Camera blocked: " + err.message;
  }
}

function stopCamera() {
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null;
  $("video").srcObject = null;
  $("cam-status").textContent = "Camera off";
  $("start-cam").textContent = "🎥 Start camera";
}

$("start-cam").addEventListener("click", () => {
  if (stream) stopCamera();
  else startCamera();
});

function captureBlob() {
  return new Promise((resolve, reject) => {
    if (!stream) return reject(new Error("Camera is off. Press “Start camera”."));
    const video = $("video");
    const canvas = $("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("capture failed"))), "image/jpeg", 0.9);
  });
}

// ---- Students ------------------------------------------------------
let studentsById = {};

async function loadStudents() {
  const list = await api("/api/students");
  const sel = $("student");
  sel.innerHTML = "";
  if (list.length === 0) {
    await api("/api/students", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Child 1", grade_level: 3 }),
    });
    return loadStudents();
  }
  studentsById = {};
  list.forEach((s) => {
    studentsById[s.id] = s;
    const o = document.createElement("option");
    o.value = s.id;
    o.textContent = `${s.name} (Gr ${s.grade_level})`;
    sel.appendChild(o);
  });
  applyStudentTutorPref(studentsById[studentId()]);
}

$("student").addEventListener("change", () => {
  applyStudentTutorPref(studentsById[studentId()]);
});

function applyStudentTutorPref(student) {
  if (!student) return;
  const sel = $("tutor-mode");
  const want = student.tutor_mode;
  const available = Array.from(sel.options).map((o) => o.value);
  if (want && want !== "auto" && available.includes(want)) sel.value = want;
}

$("add-student").addEventListener("click", async () => {
  const name = prompt("Child's name?");
  if (!name) return;
  const grade = parseInt(prompt("Grade level? (1-8)", "3") || "3", 10);
  await api("/api/students", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, grade_level: grade }),
  });
  loadStudents();
});

const studentId = () => parseInt($("student").value, 10) || null;

// ---- Tutor mode toggle ---------------------------------------------
const TUTOR_KEY = "tutorMode";

async function loadTutorModes() {
  const sel = $("tutor-mode");
  let data;
  try {
    data = await api("/api/tutor/modes");
  } catch {
    data = { default: "auto", modes: [] };
  }
  const modes =
    data.modes && data.modes.length
      ? data.modes
      : [{ name: "auto", label: "Default" }];
  const saved = localStorage.getItem(TUTOR_KEY);
  const available = modes.map((m) => m.name);
  const initial = available.includes(saved) ? saved : data.default;
  sel.innerHTML = "";
  modes.forEach((m) => {
    const o = document.createElement("option");
    o.value = m.name;
    o.textContent = m.label;
    if (m.name === initial) o.selected = true;
    sel.appendChild(o);
  });
  $("tutor-mode-hint").textContent = modes.length > 1 ? "(homework)" : "";
}

function currentTutorMode() {
  const sel = $("tutor-mode");
  return (sel && sel.value) || "auto";
}

$("tutor-mode").addEventListener("change", () => {
  const mode = currentTutorMode();
  localStorage.setItem(TUTOR_KEY, mode);
  const id = studentId();
  if (id) {
    api(`/api/students/${id}/tutor-mode`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tutor_mode: mode }),
    })
      .then((s) => {
        if (s && s.id) studentsById[s.id] = s;
      })
      .catch(() => {});
  }
});

// ---- Dictation -----------------------------------------------------
$("new-sentence").addEventListener("click", async () => {
  const level = $("dict-level").value;
  const data = await api(`/api/dictation/new?level=${level}`);
  $("dict-sentence").textContent = data.sentence;
});

$("read-sentence").addEventListener("click", () => {
  speak($("dict-sentence").textContent.trim());
});

$("dict-check").addEventListener("click", async () => {
  const expected = $("dict-sentence").textContent.trim();
  const typed = $("dict-typed").value.trim();
  const form = new FormData();
  form.append("expected", expected);
  if (studentId()) form.append("student_id", studentId());
  const restore = busy($("dict-check"), "⏳ Checking…");
  try {
    if (typed) {
      form.append("recognized_text", typed);
    } else {
      form.append("image", await captureBlob(), "page.jpg");
    }
    const res = await fetchT("/api/dictation/check", { method: "POST", body: form }).then((r) => r.json());
    renderDictation(res);
  } catch (err) {
    showError($("dict-result"), errMsg(err));
  } finally {
    restore();
  }
});

function scoreClass(pct) {
  return pct >= 85 ? "score-good" : pct >= 60 ? "score-mid" : "score-bad";
}

function renderDictation(r) {
  const el = $("dict-result");
  el.hidden = false;
  const pct = (r.overall_score / 10) * 100;
  const chips = [
    ["Correct", r.correct_words, false],
    ["Missing", r.missing_words, r.missing_words > 0],
    ["Spelling", r.misspelled_words, r.misspelled_words > 0],
    ["Caps", r.capitalization_errors, r.capitalization_errors > 0],
    ["Punctuation", r.punctuation_errors, r.punctuation_errors > 0],
  ]
    .map(([k, v, bad]) => `<span class="chip ${bad ? "err" : ""}">${k}: ${v}</span>`)
    .join("");
  const mistakes = (r.mistakes || [])
    .map((m) => {
      if (m.type === "missing") return `<li>Missing word: <b>${m.expected}</b></li>`;
      if (m.type === "extra") return `<li>Extra word: <b>${m.got}</b></li>`;
      if (m.type === "capitalization")
        return `<li>Capitalization: wrote <b>${m.got}</b>, expected <b>${m.expected}</b></li>`;
      return `<li>Spelling: wrote <b>${m.got}</b>, expected <b>${m.expected}</b></li>`;
    })
    .join("");
  el.innerHTML = `
    <div class="scorecard">
      <div class="score-big ${scoreClass(pct)}">${r.overall_score}/10</div>
      <div>
        <div>Spelling ${r.spelling_score}/10 · Accuracy ${r.accuracy}%</div>
        <div class="muted tiny">You wrote: “${escapeHtml(r.recognized)}”</div>
      </div>
    </div>
    <div class="metrics">${chips}</div>
    ${mistakes ? `<ul class="mistakes">${mistakes}</ul>` : ""}
    <div class="callout ${pct >= 85 ? "good" : "hint"}">${escapeHtml(r.feedback)}</div>`;
}

// ---- Homework ------------------------------------------------------
$("hw-check").addEventListener("click", async () => {
  const form = new FormData();
  form.append("question", $("hw-question").value.trim());
  form.append("topic", $("hw-topic").value.trim() || "homework");
  form.append("tutor_mode", currentTutorMode());
  if (studentId()) form.append("student_id", studentId());
  const typed = $("hw-typed").value.trim();
  const restore = busy($("hw-check"), "⏳ Checking…");
  try {
    if (typed) {
      form.append("recognized_text", typed);
    } else {
      form.append("image", await captureBlob(), "page.jpg");
    }
    const res = await fetchT("/api/homework/check", { method: "POST", body: form }).then((r) => r.json());
    renderHomework(res);
  } catch (err) {
    showError($("hw-result"), errMsg(err));
  } finally {
    restore();
  }
});

function renderHomework(r) {
  const el = $("hw-result");
  el.hidden = false;
  const cls = r.is_correct ? "good" : "bad";
  el.innerHTML = `
    <div class="scorecard">
      <div class="score-big ${r.is_correct ? "score-good" : "score-mid"}">${r.score}/10</div>
      <div>
        <div><b>${escapeHtml(r.verdict || (r.is_correct ? "Correct!" : "Let's fix it"))}</b>${r.tutor_mode ? ` <span class="chip">via ${escapeHtml(r.tutor_mode)}</span>` : ""}</div>
        <div class="muted tiny">Read from page: “${escapeHtml(r.recognized)}”</div>
      </div>
    </div>
    ${r.mistake ? `<div class="callout bad">❌ ${renderMarkdown(r.mistake)}</div>` : ""}
    ${r.hint ? `<div class="callout hint">💡 ${renderMarkdown(r.hint)}</div>` : ""}
    ${r.explanation ? `<div class="callout ${cls}">${renderMarkdown(r.explanation)}</div>` : ""}
    ${r.next_step ? `<div class="muted">Next: ${renderMarkdown(r.next_step)}</div>` : ""}`;
}

// ---- Teach Me ------------------------------------------------------
function studentGrade() {
  const sel = $("student");
  const opt = sel.options[sel.selectedIndex];
  const m = opt && /Gr (\d+)/.exec(opt.textContent);
  return m ? parseInt(m[1], 10) : 3;
}

function speak(text) {
  if (!text || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.95;
  // Mute the voice-command mic while the app talks, so it doesn't hear itself.
  VOICE.suppress = true;
  clearTimeout(VOICE._suppressTimer);
  VOICE._suppressTimer = setTimeout(() => (VOICE.suppress = false), 12000);
  const release = () => {
    clearTimeout(VOICE._suppressTimer);
    VOICE.suppress = false;
  };
  u.onend = release;
  u.onerror = release;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}

// ---- Voice control (hands-free commands + spoken input) ------------
const VOICE = {
  rec: null,
  on: false,
  wantOn: false,
  suppress: false, // true while the app is speaking (avoid self-hearing)
  _suppressTimer: null,
  supported: !!(window.SpeechRecognition || window.webkitSpeechRecognition),
};

function switchTab(name) {
  const btn = document.querySelector('.tab[data-tab="' + name + '"]');
  if (btn) btn.click();
}
function activeTab() {
  const b = document.querySelector(".tab.active");
  return b ? b.dataset.tab : null;
}
function setDictLevel(word) {
  const map = { one: "1", two: "2", three: "3", "1": "1", "2": "2", "3": "3" };
  const sel = $("dict-level");
  if (sel && map[word]) sel.value = map[word];
}

const VOICE_HELP =
  "Ask me anything: “teach me the 2 times table” · “what is cut copy paste” · “explain fractions”. " +
  "Commands: “dictation” · “homework” · “teach me” · “ask” · “progress” · “new sentence” · " +
  "“read it” · “level two” · “start/stop camera” · “check” · “send”.";

function flashVoice(msg) {
  const s = $("voice-status");
  if (s) s.textContent = msg;
}
// Open a real popover so the help can't be clobbered by live voice-status text.
function showVoiceHelp() {
  const ov = $("help-overlay");
  if (ov) ov.hidden = false;
}
function hideVoiceHelp() {
  const ov = $("help-overlay");
  if (ov) ov.hidden = true;
}
function initHelpPopover() {
  const ov = $("help-overlay");
  if (!ov) return;
  $("help-close").addEventListener("click", hideVoiceHelp);
  ov.addEventListener("click", (e) => { if (e.target === ov) hideVoiceHelp(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !ov.hidden) hideVoiceHelp();
  });
  ov.querySelectorAll(".help-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      hideVoiceHelp();
      if (chip.dataset.ask) askTutor(chip.dataset.ask);
      else if (chip.dataset.say) runVoiceCommand(chip.dataset.say);
    });
  });
}

// Commands are matched EXACTLY (after lowercasing + trimming punctuation) so a
// long spoken answer never accidentally triggers an action.
function runVoiceCommand(t) {
  if (["dictation", "go to dictation", "open dictation", "dictation tab"].includes(t)) { switchTab("dictation"); return "Dictation"; }
  if (["homework", "go to homework", "open homework", "homework tab"].includes(t)) { switchTab("homework"); return "Homework"; }
  if (['teach me', 'teachme', 'go to teach me', 'open teach me'].includes(t)) { switchTab('teachme'); return 'Teach Me'; }
  if (['ask', 'ask the tutor', 'go to ask', 'questions'].includes(t)) { switchTab('ask'); return 'Ask'; }
  if (["progress", "show progress", "go to progress", "my progress"].includes(t)) { switchTab("progress"); return "Progress"; }
  if (["help", "what can i say", "voice help", "commands"].includes(t)) { showVoiceHelp(); return "Help"; }

  if (["start camera", "turn on camera", "camera on", "open camera"].includes(t)) { startCamera(); return "Camera on"; }
  if (["stop camera", "turn off camera", "camera off", "close camera"].includes(t)) { stopCamera(); return "Camera off"; }

  if (["new sentence", "next sentence", "another sentence", "give me a sentence"].includes(t)) { switchTab("dictation"); $("new-sentence").click(); return "New sentence"; }
  if (["read it", "read the sentence", "read again", "say it again", "repeat", "repeat it"].includes(t)) { switchTab("dictation"); $("read-sentence").click(); return "Reading"; }
  const lvl = t.match(/^level (one|two|three|[123])$/);
  if (lvl) { switchTab("dictation"); setDictLevel(lvl[1]); return "Level " + lvl[1]; }
  if (["check my writing", "check writing", "check the writing"].includes(t)) { switchTab("dictation"); $("dict-check").click(); return "Checking writing"; }

  if (["check my answer", "check answer", "check the answer", "check homework"].includes(t)) { switchTab("homework"); $("hw-check").click(); return "Checking answer"; }

  if (["send", "send it", "send answer", "submit", "done explaining"].includes(t)) { if (activeTab() === "teachme") { $("tm-send").click(); return "Sent"; } }
  if (["start over", "reset", "clear", "new conversation"].includes(t)) { if (activeTab() === "teachme") { $("tm-restart").click(); return "Reset"; } }

  if (["check", "check it", "check please", "check now", "check my work"].includes(t)) {
    const tab = activeTab();
    if (tab === "dictation") { $("dict-check").click(); return "Checking writing"; }
    if (tab === "homework") { $("hw-check").click(); return "Checking answer"; }
    if (tab === "teachme") { $("tm-send").click(); return "Sent"; }
  }
  return null;
}

function routeVoiceContent(text) {
  const tab = activeTab();
  let target = null;
  if (tab === "dictation") target = $("dict-typed");
  else if (tab === "homework") target = $("hw-typed");
  else if (tab === "teachme") target = $("tm-explanation");
  if (!target) return false;
  const details = target.closest("details");
  if (details && !details.open) details.open = true; // reveal “Type instead”
  target.value = (target.value ? target.value.trim() + " " : "") + text;
  return true;
}

function handleVoicePhrase(raw) {
  const t = raw.toLowerCase().replace(/[.?!,]+$/g, "").trim();
  if (!t) return;
  const cmd = runVoiceCommand(t);
  if (cmd) { flashVoice("✓ " + cmd); return; }
  const topic = extractAskTopic(t);
  if (topic) { flashVoice("🗣️ Asking: " + topic); askTutor(topic); return; }
  if (routeVoiceContent(raw.trim())) flashVoice("📝 " + raw.trim().slice(0, 48));
}

function onVoiceResult(e) {
  if (VOICE.suppress) return;
  let interim = "";
  for (let i = e.resultIndex; i < e.results.length; i++) {
    const res = e.results[i];
    if (res.isFinal) handleVoicePhrase(res[0].transcript);
    else interim += res[0].transcript;
  }
  if (interim) flashVoice("… " + interim.trim());
}

function voiceUpdateUI() {
  const b = $("voice-toggle");
  if (b) {
    b.textContent = VOICE.on ? "🎙️ Listening — stop" : "🎙️ Voice off";
    b.classList.toggle("listening", VOICE.on);
  }
  const tm = $("tm-record");
  if (tm) tm.textContent = VOICE.on ? "⏹ Stop listening" : "🎤 Explain out loud";
  const trs = $("tm-rec-status");
  if (trs) trs.textContent = VOICE.on ? "Listening…" : "Tap, then talk";
}

function voiceStart() {
  if (!VOICE.supported || VOICE.wantOn) return;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const r = new SR();
  VOICE.rec = r;
  r.lang = "en-US";
  r.interimResults = true;
  r.continuous = true;
  r.onstart = () => { VOICE.on = true; voiceUpdateUI(); flashVoice(VOICE_HELP); };
  r.onresult = onVoiceResult;
  r.onerror = (e) => { if (e.error !== "no-speech") flashVoice("Mic: " + e.error); };
  r.onend = () => {
    VOICE.on = false;
    voiceUpdateUI();
    if (VOICE.wantOn) { try { r.start(); } catch (_) {} } // stay continuous
  };
  VOICE.wantOn = true;
  try { r.start(); } catch (_) {}
}

function voiceStop() {
  VOICE.wantOn = false;
  if (VOICE.rec) { try { VOICE.rec.stop(); } catch (_) {} }
  VOICE.on = false;
  voiceUpdateUI();
  flashVoice("");
}

function voiceToggle() {
  if (VOICE.wantOn) voiceStop();
  else voiceStart();
}

function initVoiceControl() {
  const b = $("voice-toggle");
  const help = $("voice-help");
  const tm = $("tm-record");
  if (!VOICE.supported) {
    if (b) { b.disabled = true; b.textContent = "🎙️ not supported"; }
    if (tm) tm.disabled = true;
    if ($("tm-rec-status")) $("tm-rec-status").textContent = "Voice needs Chrome/Edge — type instead.";
    flashVoice("Voice commands need Chrome or Edge.");
    return;
  }
  if (b) b.addEventListener("click", voiceToggle);
  if (help) help.addEventListener("click", showVoiceHelp);
  // “Explain out loud” shares the same engine and focuses the Teach Me tab.
  if (tm) tm.addEventListener("click", () => { switchTab("teachme"); voiceToggle(); });
  voiceUpdateUI();
}

let tmTurns = [];
let tmDone = false;

function renderTranscript() {
  const el = $("tm-transcript");
  el.hidden = tmTurns.length === 0;
  el.innerHTML = tmTurns
    .map(
      (t) =>
        `<div class="bubble ${t.speaker}">${t.speaker === "tutor" ? "🧑‍🏫" : "🧒"} ${escapeHtml(t.text)}</div>`
    )
    .join("");
  el.scrollTop = el.scrollHeight;
}

async function sendTeachMeTurn() {
  if (tmDone) return;
  const childText = $("tm-explanation").value.trim();
  if (!childText) {
    showError($("tm-result"), "Talk or type your explanation first.");
    return;
  }
  tmTurns.push({ speaker: "child", text: childText });
  renderTranscript();
  $("tm-explanation").value = "";
  const payload = {
    question: $("tm-question").value.trim(),
    answer: $("tm-answer").value.trim(),
    grade_level: studentGrade(),
    tutor_mode: currentTutorMode(),
    student_id: studentId(),
    turns: tmTurns,
  };
  const restore = busy($("tm-send"), "⏳ Thinking…");
  try {
    const r = await api("/api/tutor/teachme/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const tutorMsg = r.followup || r.feedback || "";
    if (tutorMsg) {
      tmTurns.push({ speaker: "tutor", text: tutorMsg });
      renderTranscript();
      speak(tutorMsg);
    }
    if (r.done) {
      tmDone = true;
      renderTeachMeFinal(r);
    }
  } catch (err) {
    showError($("tm-result"), errMsg(err));
  } finally {
    restore();
  }
}

$("tm-send").addEventListener("click", sendTeachMeTurn);

$("tm-restart").addEventListener("click", () => {
  tmTurns = [];
  tmDone = false;
  renderTranscript();
  $("tm-result").hidden = true;
  $("tm-explanation").value = "";
});

function renderTeachMeFinal(r) {
  const el = $("tm-result");
  el.hidden = false;
  const good = r.understands;
  el.innerHTML = `
    <div class="scorecard">
      <div class="score-big ${good ? "score-good" : "score-mid"}">${r.score}/10</div>
      <div>
        <div><b>${good ? "You've got it! 🎉" : "Good effort — keep practicing"}</b>${r.tutor_mode ? ` <span class="chip">via ${escapeHtml(r.tutor_mode)}</span>` : ""}</div>
        <div class="muted tiny">Confirmed after ${r.turn_count} turn(s)</div>
      </div>
    </div>
    ${r.feedback ? `<div class="callout ${good ? "good" : "hint"}">${renderMarkdown(r.feedback)}</div>` : ""}`;
}

// ---- Ask the tutor -------------------------------------------------
function extractAskTopic(t) {
  const m = t.match(
    /^(?:teach me|explain|tell me about|what is|what's|what are|how do i|how do|how does|how to|why is|why does|why do)\s+(.+)$/
  );
  return m ? m[1].replace(/^about\s+/, "").trim() : null;
}

async function askTutor(topic) {
  topic = (topic || "").trim();
  if (!topic) return;
  switchTab("ask");
  $("ask-question").value = topic;
  const el = $("ask-result");
  el.hidden = false;
  el.innerHTML = `
    <div class="scorecard">
      <div><b>🗣️ ${escapeHtml(topic)}</b> <span class="chip" id="ask-mode">…</span></div>
    </div>
    <div class="callout good" id="ask-text"><span class="caret">▍</span></div>`;
  const textEl = $("ask-text");
  const restore = busy($("ask-btn"), "🗣️ Thinking…");
  try {
    const res = await fetchT("/api/tutor/explain/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic,
        grade_level: studentGrade(),
        tutor_mode: currentTutorMode(),
      }),
    });
    if (!res.ok || !res.body) throw new Error("HTTP " + res.status);
    const mode = res.headers.get("X-Tutor-Mode") || "";
    const modeEl = $("ask-mode");
    if (modeEl) modeEl.textContent = mode ? "via " + mode : "";
    // Render tokens as they arrive so the answer appears instantly, word by word.
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let full = "";
    let started = false;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      if (!started) { textEl.textContent = ""; started = true; }
      full += decoder.decode(value, { stream: true });
      textEl.textContent = full;
    }
    full = full.trim();
    textEl.innerHTML = renderMarkdown(full) || "…";
    if (mode === "mock") {
      el.insertAdjacentHTML(
        "beforeend",
        `<div class="muted tiny">Demo answer — choose a real Tutor (Cloud/Cluster) above for a full explanation.</div>`
      );
    }
    speak(full);
  } catch (err) {
    showError(el, errMsg(err));
  } finally {
    restore();
  }
}

$("ask-btn").addEventListener("click", () => askTutor($("ask-question").value));
$("ask-question").addEventListener("keydown", (e) => {
  if (e.key === "Enter") askTutor($("ask-question").value);
});

// ---- Progress ------------------------------------------------------
$("refresh-progress").addEventListener("click", loadProgress);

async function loadProgress() {
  const id = studentId();
  if (!id) return;
  const p = await api(`/api/students/${id}/progress`);
  const rows = (p.topics || [])
    .map(
      (t) =>
        `<tr><td>${escapeHtml(t.topic)}</td><td>${t.average}%</td><td>${t.attempts}</td></tr>`
    )
    .join("");
  $("progress-view").innerHTML = `
    <p>Total attempts: <b>${p.total_attempts}</b></p>
    <table class="metrics-table">
      <tr><th align="left">Topic</th><th>Average</th><th>Tries</th></tr>
      ${rows || `<tr><td colspan="3" class="muted">No attempts yet.</td></tr>`}
    </table>
    <div class="callout hint">🧠 ${escapeHtml(p.recommendation || "")}</div>`;
}

// ---- Helpers -------------------------------------------------------
function showError(el, msg) {
  el.hidden = false;
  el.innerHTML = `<div class="callout bad">⚠️ ${escapeHtml(msg)}</div>`;
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// ---- Init ----------------------------------------------------------
(async function init() {
  // Don't block first paint on the health probe — fill the badge when it returns.
  api("/api/health")
    .then((h) => { $("ai-badge").textContent = "AI: " + (h.ai_mode || "?"); })
    .catch(() => { $("ai-badge").textContent = "AI: ?"; });
  initVoiceControl();
  initHelpPopover();
  await loadTutorModes();
  await loadStudents();
})();
