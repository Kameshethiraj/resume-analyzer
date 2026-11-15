const app = document.querySelector("#app");
const account = document.querySelector("#account");
const accountEmail = document.querySelector("#account-email");
const toast = document.querySelector("#toast");
let csrfToken = "";
let currentUser = null;
let activeInterview = null;
let toastTimer;

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (csrfToken && options.method && options.method !== "GET") headers.set("X-CSRF-Token", csrfToken);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const requestId = response.headers.get("X-Request-ID") || body.request_id;
    const reference = response.status >= 500 && requestId ? ` (reference: ${requestId})` : "";
    throw new Error(`${body.detail || "The request could not be completed."}${reference}`);
  }
  return body;
}

function notify(message) {
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 3600);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function setHeader() {
  account.hidden = !currentUser;
  accountEmail.textContent = currentUser?.email || "";
}

function showAuth(mode = "login", error = "") {
  activeInterview = null;
  app.innerHTML = `
    <section class="auth-wrap"><div class="auth-panel">
      <span class="eyebrow">Private workspace</span>
      <h1>${mode === "login" ? "Welcome back" : "Create your account"}</h1>
      <p class="subtle">${mode === "login" ? "Sign in to continue to your resumes and interviews." : "Your resumes and interview results stay in your account."}</p>
      <form id="auth-form">
        <div class="field"><label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" maxlength="254" required></div>
        <div class="field"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="${mode === "login" ? "current-password" : "new-password"}" minlength="8" maxlength="256" required></div>
        ${error ? `<p class="form-error" role="alert">${escapeHtml(error)}</p>` : ""}
        <button class="button button-primary" type="submit">${mode === "login" ? "Sign in" : "Create account"}</button>
      </form>
      <p class="auth-switch">${mode === "login" ? "New here?" : "Already have an account?"}
        <button class="text-button" id="auth-toggle" type="button">${mode === "login" ? "Create an account" : "Sign in"}</button>
      </p>
    </div></section>`;
  document.querySelector("#auth-toggle").addEventListener("click", () => showAuth(mode === "login" ? "register" : "login"));
  document.querySelector("#auth-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const credentials = { email: form.get("email"), password: form.get("password") };
    try {
      if (mode === "register") await api("/api/auth/register", { method: "POST", body: JSON.stringify(credentials) });
      const result = await api("/api/auth/login", { method: "POST", body: JSON.stringify(credentials) });
      currentUser = result;
      csrfToken = result.csrf_token;
      setHeader();
      await showDashboard();
    } catch (requestError) {
      showAuth(mode, requestError.message);
    }
  });
}

function statusLabel(status) {
  return `<span class="status status-${escapeHtml(status)}">${escapeHtml(status)}</span>`;
}

async function showDashboard() {
  activeInterview = null;
  const [resumes, interviews] = await Promise.all([api("/api/resumes"), api("/api/interviews")]);
  app.innerHTML = `
    <div class="page-head"><div><span class="eyebrow">Your workspace</span><h1>Good to see you</h1><p class="subtle">Manage your resumes and practice for your next interview.</p></div></div>
    <section class="section upload-strip"><div><strong>Add a resume</strong><p>Upload a text-based PDF up to 10 MB.</p></div>
      <form id="upload-form" class="upload-controls"><input id="resume-file" type="file" accept="application/pdf,.pdf" required aria-label="Choose a PDF resume"><button class="button button-primary" type="submit">Upload PDF</button></form>
    </section>
    <section class="section"><div class="section-head"><h2>Your resumes</h2><span class="muted">${resumes.length}</span></div>
      <div class="list">${resumes.length ? resumes.map((resume) => {
        const activeSessions = interviews.filter((interview) => interview.resume_id === resume.id && interview.status === "active");
        return `<div class="list-row">
          <div class="list-title">${escapeHtml(resume.original_filename)}</div><div class="list-meta">${new Date(resume.created_at).toLocaleDateString()} · ${resume.chunk_count} sections</div>
          <div class="row-actions">${statusLabel(resume.upload_status)}<button class="button button-quiet" data-resume="${escapeHtml(resume.id)}">Open</button>
            ${activeSessions.length ? `<button class="button button-secondary" data-close-resume="${escapeHtml(resume.id)}">Close ${activeSessions.length === 1 ? "session" : `sessions (${activeSessions.length})`}</button>` : ""}
            <button class="button button-danger" data-delete-resume="${escapeHtml(resume.id)}">Delete</button></div>
        </div>`;
      }).join("") : `<div class="empty">No resumes yet. Upload a PDF to get started.</div>`}</div>
    </section>
    <section class="section"><div class="section-head"><h2>Recent interviews</h2></div>
      <div class="list">${interviews.length ? interviews.slice(0, 6).map((interview) => `<div class="list-row">
        <div class="list-title">${escapeHtml(interview.resume_name)}</div><div class="list-meta">${new Date(interview.created_at).toLocaleDateString()} · ${escapeHtml(interview.status)}</div>
        <div class="row-actions"><button class="button button-quiet" data-results="${escapeHtml(interview.id)}">${interview.status === "active" ? "Continue" : "View results"}</button></div>
      </div>`).join("") : `<div class="empty">Your completed and active interviews will appear here.</div>`}</div>
    </section>`;
  document.querySelectorAll("[data-resume]").forEach((button) => button.addEventListener("click", () => showResume(button.dataset.resume)));
  document.querySelectorAll("[data-close-resume]").forEach((button) => button.addEventListener("click", () => closeResumeSessions(button.dataset.closeResume)));
  document.querySelectorAll("[data-delete-resume]").forEach((button) => button.addEventListener("click", () => deleteResume(button.dataset.deleteResume)));
  document.querySelectorAll("[data-results]").forEach((button) => button.addEventListener("click", () => openInterview(button.dataset.results)));
  document.querySelector("#upload-form").addEventListener("submit", uploadResume);
}

async function closeResumeSessions(resumeId) {
  try {
    const interviews = await api("/api/interviews");
    const activeSessions = interviews.filter((interview) => interview.resume_id === resumeId && interview.status === "active");
    if (!activeSessions.length) return showDashboard();
    const confirmation = activeSessions.length === 1
      ? "Close the active interview session for this resume?"
      : `Close all ${activeSessions.length} active interview sessions for this resume?`;
    if (!window.confirm(confirmation)) return;
    for (const interview of activeSessions) {
      await api(`/api/interviews/${interview.id}/end`, { method: "POST" });
    }
    notify(activeSessions.length === 1 ? "Interview session closed." : "Active interview sessions closed.");
    await showDashboard();
  } catch (error) { notify(error.message); }
}

async function deleteResume(resumeId) {
  const confirmed = window.confirm("Delete this resume and its interview history? This cannot be undone.");
  if (!confirmed) return;
  try {
    await api(`/api/resumes/${resumeId}`, { method: "DELETE" });
    notify("Resume deleted.");
    await showDashboard();
  } catch (error) { notify(error.message); }
}

async function uploadResume(event) {
  event.preventDefault();
  const file = document.querySelector("#resume-file").files[0];
  if (!file) return;
  const data = new FormData();
  data.append("file", file);
  try {
    await api("/api/resumes", { method: "POST", body: data });
    notify("Resume processed successfully.");
    await showDashboard();
  } catch (error) { notify(error.message); }
}

async function showResume(resumeId) {
  const [resume, interviews] = await Promise.all([api(`/api/resumes/${resumeId}`), api("/api/interviews")]);
  const related = interviews.filter((item) => item.resume_id === resumeId);
  app.innerHTML = `
    <a href="#" class="back-link" id="back-dashboard">← Dashboard</a>
    <div class="page-head"><div><span class="eyebrow">Resume details</span><h1>${escapeHtml(resume.original_filename)}</h1><p class="subtle">Uploaded ${new Date(resume.created_at).toLocaleDateString()}</p></div>
      <div class="row-actions"><a class="button button-secondary" href="/api/resumes/${escapeHtml(resume.id)}/download">Download PDF</a><button class="button button-primary" id="start-interview" ${resume.upload_status !== "completed" ? "disabled" : ""}>Start interview</button></div></div>
    <div class="detail-band"><span>Processing ${statusLabel(resume.upload_status)}</span><span><strong>${resume.chunk_count}</strong> resume sections indexed</span></div>
    <section class="section"><div class="section-head"><h2>Interview history</h2></div><div class="list">${related.length ? related.map((item) => `<div class="list-row"><div class="list-title">Interview</div><div class="list-meta">${new Date(item.created_at).toLocaleString()} · ${escapeHtml(item.status)}</div><div class="row-actions"><button class="button button-quiet" data-interview="${escapeHtml(item.id)}">${item.status === "active" ? "Continue" : "View results"}</button></div></div>`).join("") : `<div class="empty">No interviews for this resume yet.</div>`}</div></section>`;
  document.querySelector("#back-dashboard").addEventListener("click", (event) => { event.preventDefault(); showDashboard(); });
  document.querySelector("#start-interview").addEventListener("click", () => startInterview(resume.id));
  document.querySelectorAll("[data-interview]").forEach((button) => button.addEventListener("click", () => openInterview(button.dataset.interview)));
}

async function startInterview(resumeId) {
  try {
    const result = await api(`/api/interviews/start/${resumeId}`, { method: "POST" });
    activeInterview = result.id;
    renderInterview(result, null);
  } catch (error) { notify(error.message); }
}

async function openInterview(interviewId) {
  try {
    const result = await api(`/api/interviews/${interviewId}`);
    activeInterview = interviewId;
    if (result.status === "completed") return renderSummary(interviewId, result.summary);
    renderInterview({ id: interviewId, ...result.question }, null);
  } catch (error) { notify(error.message); }
}

function renderInterview(interview, feedback) {
  activeInterview = interview.id;
  let question = interview.question ?? interview;
  if (typeof question === "string") question = { ...interview, question };
  app.innerHTML = `
    <a href="#" class="back-link" id="back-dashboard">← Dashboard</a>
    <div class="page-head"><div><span class="eyebrow">Interview in progress</span><h1>Technical interview</h1><p class="subtle">Question ${question.sequence_number}${question.is_follow_up ? " · Follow-up" : ""}</p></div><button id="end-interview" class="button button-secondary" type="button">End interview</button></div>
    ${feedback ? feedbackMarkup(feedback) : ""}
    <section class="question-panel"><div class="question-number">QUESTION ${question.sequence_number}</div><p class="question-text">${escapeHtml(question.question)}</p>
      <form id="answer-form"><div class="field"><label for="answer">Your answer</label><textarea id="answer" maxlength="12000" placeholder="Write your response..." required></textarea></div>
        <div class="interview-actions"><button class="button button-primary" type="submit">Submit answer</button><button id="skip-question" class="button button-secondary" type="button">Skip question</button></div>
      </form>
    </section>`;
  document.querySelector("#back-dashboard").addEventListener("click", (event) => { event.preventDefault(); showDashboard(); });
  document.querySelector("#end-interview").addEventListener("click", finishInterview);
  document.querySelector("#answer-form").addEventListener("submit", submitAnswer);
  document.querySelector("#skip-question").addEventListener("click", skipQuestion);
}

function feedbackMarkup(evaluation) {
  if (!evaluation) return "";
  return `<section class="feedback"><div class="score">${evaluation.score}/10</div><p class="feedback-copy">${escapeHtml(evaluation.feedback)}</p><div class="feedback-grid"><div><h3>Strengths</h3><ul>${(evaluation.strengths || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>None recorded</li>"}</ul></div><div><h3>Areas to improve</h3><ul>${(evaluation.improvements || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>None recorded</li>"}</ul></div></div></section>`;
}

async function submitAnswer(event) {
  event.preventDefault();
  const answer = document.querySelector("#answer").value;
  try {
    const result = await api(`/api/interviews/${activeInterview}/answers`, { method: "POST", body: JSON.stringify({ answer }) });
    if (result.next_question) renderInterview({ id: activeInterview, ...result.next_question }, result.evaluation);
    else renderSummary(activeInterview, result.summary, result.evaluation);
  } catch (error) { notify(error.message); }
}

async function skipQuestion() {
  try {
    const result = await api(`/api/interviews/${activeInterview}/skip`, { method: "POST" });
    if (result.next_question) renderInterview({ id: activeInterview, ...result.next_question }, null);
    else renderSummary(activeInterview, result.summary);
  } catch (error) { notify(error.message); }
}

async function finishInterview() {
  try {
    const result = await api(`/api/interviews/${activeInterview}/end`, { method: "POST" });
    renderSummary(activeInterview, result.summary);
  } catch (error) { notify(error.message); }
}

function renderSummary(interviewId, summary, lastEvaluation = null) {
  activeInterview = null;
  const score = summary?.average_score;
  app.innerHTML = `
    <a href="#" class="back-link" id="back-dashboard">← Dashboard</a>
    <div class="page-head"><div><span class="eyebrow">Interview complete</span><h1>Your results</h1><p class="subtle">${summary?.answered_count || 0} answers evaluated</p></div></div>
    ${lastEvaluation ? feedbackMarkup(lastEvaluation) : ""}
    <div class="summary-band"><span class="summary-score">${score == null ? "—" : `${score}/10`}</span><span class="muted">Average score</span></div>
    <section class="section"><div class="section-head"><h2>Question review</h2></div><div class="list">${(summary?.questions || []).map((item) => `<article class="feedback"><div class="question-number">QUESTION ${item.sequence_number}${item.is_follow_up ? " · FOLLOW-UP" : ""}${item.skipped ? " · SKIPPED" : ""}</div><h3>${escapeHtml(item.question)}</h3>${item.answer ? `<p class="feedback-copy"><strong>Your answer:</strong> ${escapeHtml(item.answer)}</p>` : ""}${item.score != null ? `<div class="score">${item.score}/10</div><p class="feedback-copy">${escapeHtml(item.feedback)}</p><div class="feedback-grid"><div><h3>Strengths</h3><ul>${item.strengths.map((text) => `<li>${escapeHtml(text)}</li>`).join("")}</ul></div><div><h3>Areas to improve</h3><ul>${item.improvements.map((text) => `<li>${escapeHtml(text)}</li>`).join("")}</ul></div></div>` : ""}</article>`).join("") || `<div class="empty">No answers were recorded.</div>`}</div></section>
    <button class="button button-primary" id="return-dashboard">Back to dashboard</button>`;
  document.querySelector("#back-dashboard").addEventListener("click", (event) => { event.preventDefault(); showDashboard(); });
  document.querySelector("#return-dashboard").addEventListener("click", showDashboard);
}

document.querySelector("#logout-button").addEventListener("click", async () => {
  try { await api("/api/auth/logout", { method: "POST" }); } catch { /* Session may already have expired. */ }
  currentUser = null;
  csrfToken = "";
  setHeader();
  showAuth();
});

async function initialize() {
  try {
    currentUser = await api("/api/auth/me");
    csrfToken = currentUser.csrf_token;
    setHeader();
    await showDashboard();
  } catch {
    currentUser = null;
    csrfToken = "";
    setHeader();
    showAuth();
  }
}

initialize();