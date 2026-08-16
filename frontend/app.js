"use strict";

const $ = (id) => document.getElementById(id);
const api = (path, opts) => fetch(path, opts).then((r) => r.json());

let stream = null;

// ---- Tabs ----------------------------------------------------------
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document
      .querySelectorAll(".tab-content")
      .forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    $("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "progress") loadProgress();
  });
});

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
  const text = $("dict-sentence").textContent.trim();
  if (!text || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.9;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
});

$("dict-check").addEventListener("click", async () => {
  const expected = $("dict-sentence").textContent.trim();
  const typed = $("dict-typed").value.trim();
  const form = new FormData();
  form.append("expected", expected);
  if (studentId()) form.append("student_id", studentId());
  try {
    if (typed) {
      form.append("recognized_text", typed);
    } else {
      form.append("image", await captureBlob(), "page.jpg");
    }
    const res = await fetch("/api/dictation/check", { method: "POST", body: form }).then((r) => r.json());
    renderDictation(res);
  } catch (err) {
    showError($("dict-result"), err.message);
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
  try {
    if (typed) {
      form.append("recognized_text", typed);
    } else {
      form.append("image", await captureBlob(), "page.jpg");
    }
    const res = await fetch("/api/homework/check", { method: "POST", body: form }).then((r) => r.json());
    renderHomework(res);
  } catch (err) {
    showError($("hw-result"), err.message);
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
    ${r.mistake ? `<div class="callout bad">❌ ${escapeHtml(r.mistake)}</div>` : ""}
    ${r.hint ? `<div class="callout hint">💡 ${escapeHtml(r.hint)}</div>` : ""}
    ${r.explanation ? `<div class="callout ${cls}">${escapeHtml(r.explanation)}</div>` : ""}
    ${r.next_step ? `<div class="muted">Next: ${escapeHtml(r.next_step)}</div>` : ""}`;
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
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}

let tmRecognizer = null;
let tmListening = false;

function initTeachMeMic() {
  const btn = $("tm-record");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    btn.disabled = true;
    $("tm-rec-status").textContent = "Voice not supported — type your explanation.";
    return;
  }
  btn.addEventListener("click", () => {
    if (tmListening) {
      if (tmRecognizer) tmRecognizer.stop();
      return;
    }
    const r = new SR();
    tmRecognizer = r;
    r.lang = "en-US";
    r.interimResults = true;
    r.continuous = true;
    let base = $("tm-explanation").value ? $("tm-explanation").value.trim() + " " : "";
    r.onstart = () => {
      tmListening = true;
      btn.textContent = "⏹ Stop";
      $("tm-rec-status").textContent = "Listening…";
    };
    r.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) base += t + " ";
        else interim += t;
      }
      $("tm-explanation").value = (base + interim).trim();
    };
    r.onerror = (e) => {
      $("tm-rec-status").textContent = "Mic error: " + e.error;
    };
    r.onend = () => {
      tmListening = false;
      btn.textContent = "🎤 Explain out loud";
      $("tm-rec-status").textContent = "Tap, then talk";
    };
    r.start();
  });
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
    showError($("tm-result"), err.message);
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
    ${r.feedback ? `<div class="callout ${good ? "good" : "hint"}">${escapeHtml(r.feedback)}</div>` : ""}`;
}

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
  const health = await api("/api/health").catch(() => ({ ai_mode: "?" }));
  $("ai-badge").textContent = "AI: " + (health.ai_mode || "?");
  initTeachMeMic();
  await loadTutorModes();
  await loadStudents();
})();
