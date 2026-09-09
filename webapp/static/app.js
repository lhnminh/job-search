const state = {
  master: null,
  session: null,
  filter: "all",
  otherTarget: null,
};

const views = {
  master: document.querySelector("#master-view"),
  sessions: document.querySelector("#sessions-view"),
  settings: document.querySelector("#settings-view"),
  review: document.querySelector("#review-view"),
};

const masterContent = document.querySelector("#resume-content");
const masterStatus = document.querySelector("#resume-status");
const masterSectionNav = document.querySelector("#section-nav");
const masterError = document.querySelector("#master-error");
const tailorPanel = document.querySelector("#tailor-panel");
const viewMasterPdf = document.querySelector("#view-master-pdf");
const masterPdfDialog = document.querySelector("#pdf-dialog");
const masterPdfFrame = document.querySelector("#master-pdf-frame");
const sourceDialog = document.querySelector("#source-dialog");
const description = document.querySelector("#job-description");
const descriptionCount = document.querySelector("#description-count");
const suggestionContent = document.querySelector("#suggestion-content");
const decisionOverview = document.querySelector("#decision-overview");
const reviewMessage = document.querySelector("#review-message");
const requirementsList = document.querySelector("#requirements-list");
const evidencePanel = document.querySelector("#evidence-panel");
const otherDialog = document.querySelector("#other-dialog");
const otherText = document.querySelector("#other-text");
const otherFact = document.querySelector("#other-fact");
const otherInstruction = document.querySelector("#other-instruction");
const toast = document.querySelector("#toast");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function groupedEntries(entries) {
  return entries.reduce((groups, entry) => {
    const existing = groups.find((group) => group.section === entry.section);
    if (existing) existing.entries.push(entry);
    else groups.push({ section: entry.section, entries: [entry] });
    return groups;
  }, []);
}

function sectionId(section, prefix = "section") {
  const slug = section.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `${prefix}-${slug}`;
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => { toast.hidden = true; }, 3200);
}

async function api(path, options = {}) {
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    headers["X-Resume-App"] = "local";
  }
  const response = await fetch(path, { ...options, headers });
  const payload = await response.json().catch(() => ({ message: "The local app returned an unreadable response." }));
  if (!response.ok || payload.status === "error") {
    const error = new Error(payload.message || "The request could not be completed.");
    error.status = response.status;
    throw error;
  }
  return payload;
}

function setView(name) {
  Object.entries(views).forEach(([key, element]) => { element.hidden = key !== name; });
  document.querySelector("#nav-resume").classList.toggle("is-active", name === "master");
  document.querySelector("#nav-sessions").classList.toggle("is-active", name === "sessions");
  document.querySelector("#nav-settings").classList.toggle("is-active", name === "settings");
  window.scrollTo({ top: 0, behavior: "auto" });
}

function entryBullets(entry, key = "text") {
  return entry.bullets.map((bullet) => `
    <li class="${bullet.is_metadata ? "is-metadata" : ""}">${escapeHtml(bullet[key])}</li>
  `).join("");
}

function renderMaster(master) {
  const groups = groupedEntries(master.entries);
  masterSectionNav.innerHTML = groups.map((group) => `
    <button class="section-link" type="button" data-master-section="${sectionId(group.section)}">
      <span>${escapeHtml(group.section)}</span><span class="section-count">${group.entries.length}</span>
    </button>
  `).join("");
  masterContent.innerHTML = groups.map((group) => `
    <section class="resume-section" id="${sectionId(group.section)}">
      <h3>${escapeHtml(group.section)}</h3>
      ${group.entries.map((entry) => `
        <article class="resume-entry">
          <div class="entry-line"><h4>${escapeHtml(entry.title)}</h4><span class="entry-date">${escapeHtml(entry.date)}</span></div>
          <p class="entry-subtitle">${escapeHtml(entry.subtitle)}</p>
          <ul class="bullet-list">${entryBullets(entry)}</ul>
        </article>
      `).join("")}
    </section>
  `).join("");
  masterStatus.classList.add("is-ready");
  const pdfDate = master.pdf.available
    ? new Date(master.pdf.updated_at * 1000).toLocaleString()
    : null;
  masterStatus.querySelector("span:last-child").textContent = master.pdf.available
    ? `${master.entry_count} verified entries · PDF built ${pdfDate}`
    : `${master.entry_count} verified entries · PDF unavailable`;
  viewMasterPdf.disabled = !master.pdf.available;
}

async function loadMaster() {
  try {
    state.master = await api("/api/master");
    renderMaster(state.master);
  } catch (error) {
    masterError.hidden = false;
    masterError.textContent = error.message;
    masterContent.innerHTML = "";
    masterStatus.querySelector("span:last-child").textContent = "Resume unavailable";
  }
}

function openTailorPanel() {
  setView("master");
  tailorPanel.classList.add("is-open");
  document.querySelector("#company").focus();
}

async function createSession(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = form.querySelector("button[type=submit]");
  const errorBox = document.querySelector("#job-error");
  errorBox.hidden = true;
  submit.disabled = true;
  submit.innerHTML = "Creating session…";
  try {
    const session = await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        company: document.querySelector("#company").value,
        role: document.querySelector("#role").value,
        job_url: document.querySelector("#job-url").value,
        job_description: description.value,
      }),
    });
    tailorPanel.classList.remove("is-open");
    form.reset();
    descriptionCount.textContent = "0 characters";
    showSession(session);
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  } finally {
    submit.disabled = false;
    submit.innerHTML = "Prepare suggestions <span aria-hidden=\"true\">→</span>";
  }
}

function suggestionMaps(session) {
  const suggestions = session.suggestions || { bullets: [], projects: [] };
  return {
    bullets: new Map(suggestions.bullets.map((item) => [`${item.entry_number}.${item.bullet_number}`, item])),
    projects: new Map(suggestions.projects.map((item) => [item.entry_number, item])),
    requirements: new Map(session.requirements.map((item) => [item.id, item])),
    revisions: new Map((session.revision_requests || [])
      .filter((item) => item.status === "pending")
      .map((item) => [`${item.entry_number}.${item.bullet_number}`, item])),
  };
}

function decisionStatus(decision, suggestion) {
  if (!decision) return suggestion?.action === "ask" ? "needs_confirmation" : "unresolved";
  if (decision.action === "keep") return "kept";
  if (decision.action === "remove") return "removed";
  return "accepted";
}

function actionLabel(action) {
  return { keep: "Keep recommended", rewrite: "Rewrite recommended", remove: "Remove recommended", ask: "More context needed" }[action] || "Suggestion";
}

function approvalLabel(action) {
  return { keep: "Keep bullet", rewrite: "Use rewrite", remove: "Remove bullet", ask: "Add context" }[action] || "Approve suggestion";
}

function acceptedLabel(decision) {
  if (!decision) return "";
  return { keep: "Kept current", rewrite: "Rewrite accepted", remove: "Removed" }[decision.action] || "Accepted";
}

function bulletCard(entry, bullet, maps) {
  const key = `${entry.entry_number}.${bullet.bullet_number}`;
  const suggestion = maps.bullets.get(key);
  if (!suggestion) {
    return `<li class="suggestion-item"><div class="source-bullet"><span class="bullet-number">${bullet.bullet_number}</span><p>${escapeHtml(bullet.source_text)}</p></div></li>`;
  }
  const status = decisionStatus(bullet.decision, suggestion);
  const revision = maps.revisions.get(key);
  const requirement = suggestion.requirement_id ? maps.requirements.get(suggestion.requirement_id) : null;
  const displayText = bullet.decision?.action === "rewrite" ? bullet.decision.accepted_text : suggestion.suggested_text;
  return `
    <li class="suggestion-item ${bullet.decision ? "is-decided" : ""} ${status === "removed" ? "is-removed" : ""}" data-suggestion-status="${status}" data-entry="${entry.entry_number}" data-bullet="${bullet.bullet_number}">
      <div class="source-bullet"><span class="bullet-number">${bullet.bullet_number}</span><p>${escapeHtml(bullet.source_text)}</p></div>
      <div class="suggestion-card action-${suggestion.action}">
        <div class="suggestion-label-row">
          <span class="suggestion-label">${escapeHtml(actionLabel(suggestion.action))}</span>
          ${bullet.decision ? `<span class="decision-state">${escapeHtml(acceptedLabel(bullet.decision))}</span>` : ""}
        </div>
        ${displayText ? `<p class="suggested-copy">${escapeHtml(displayText)}</p>` : ""}
        <p class="suggestion-reason">${escapeHtml(suggestion.reason)}</p>
        ${revision ? `<div class="revision-pending"><strong>New suggestion requested</strong>${escapeHtml(revision.instruction)}</div>` : ""}
        ${requirement ? `<button class="requirement-link" type="button" data-requirement="${escapeHtml(requirement.id)}">↗ ${escapeHtml(requirement.text)}</button>` : ""}
        <div class="suggestion-actions">
          <button class="mini-button primary" type="button" data-approve-bullet="${key}" ${revision ? "disabled" : ""}>${escapeHtml(revision ? "Waiting for revision" : approvalLabel(suggestion.action))}</button>
          <button class="mini-button" type="button" data-keep-bullet="${key}">Keep current</button>
          <button class="mini-button" type="button" data-other-bullet="${key}">Other…</button>
        </div>
      </div>
    </li>
  `;
}

function projectCard(entry, maps) {
  const suggestion = maps.projects.get(entry.entry_number);
  if (!suggestion) return "";
  const decision = entry.project_decision;
  const requirement = suggestion.requirement_id ? maps.requirements.get(suggestion.requirement_id) : null;
  const status = decision ? (decision.action === "exclude" ? "removed" : "accepted") : "unresolved";
  return `
    <div class="project-recommendation" data-suggestion-status="${status}" data-entry="${entry.entry_number}">
      <div class="project-recommendation-head">
        <strong>${escapeHtml(suggestion.action === "include" ? "Include recommended" : "Exclude recommended")}</strong>
        ${decision ? `<span class="decision-state">${escapeHtml(decision.action === "include" ? "Included" : "Excluded")}</span>` : ""}
      </div>
      <p>${escapeHtml(suggestion.reason)}</p>
      ${requirement ? `<button class="requirement-link" type="button" data-requirement="${escapeHtml(requirement.id)}">↗ ${escapeHtml(requirement.text)}</button>` : ""}
      <div class="project-actions">
        <button class="mini-button primary" type="button" data-project-action="${entry.entry_number}:${suggestion.action}">${escapeHtml(suggestion.action === "include" ? "Include project" : "Exclude project")}</button>
        <button class="mini-button" type="button" data-project-action="${entry.entry_number}:include">Include</button>
        <button class="mini-button" type="button" data-project-action="${entry.entry_number}:exclude">Exclude</button>
      </div>
    </div>
  `;
}

function renderSuggestionDocument(session) {
  const groups = groupedEntries(session.entries);
  const maps = suggestionMaps(session);
  suggestionContent.innerHTML = groups.map((group) => `
    <section class="suggestion-section" id="${sectionId(group.section, "review-section")}">
      <div class="suggestion-section-heading"><h3>${escapeHtml(group.section)}</h3><span>${group.entries.length} entries</span></div>
      ${group.entries.map((entry) => {
        const projectDecision = entry.project_decision?.action;
        const bulletsDecided = entry.bullets.filter((bullet) => bullet.decision).length;
        const gated = entry.is_project && projectDecision !== "include";
        return `
          <article class="suggestion-entry ${projectDecision === "exclude" ? "is-excluded" : ""}" data-entry-status="${projectDecision === "exclude" ? "removed" : "mixed"}">
            <header class="suggestion-entry-header">
              <div><h4>${escapeHtml(entry.title)}</h4><p>${escapeHtml(entry.subtitle)} · ${escapeHtml(entry.date)}</p></div>
              <div class="entry-progress-stack">
                <span class="entry-progress">${bulletsDecided} of ${entry.bullets.length} bullets decided</span>
                ${session.suggestions && !gated ? `<button class="mini-button" type="button" data-approve-entry="${entry.entry_number}">Use entry recommendations</button>` : ""}
              </div>
            </header>
            ${entry.is_project ? projectCard(entry, maps) : ""}
            ${gated ? `<p class="project-gate">Choose Include to review this project's bullet suggestions.</p>` : `<ol class="suggestion-list">${entry.bullets.map((bullet) => bulletCard(entry, bullet, maps)).join("")}</ol>`}
          </article>
        `;
      }).join("")}
    </section>
  `).join("");
  applyFilter();
}

function renderWaitingSession(session) {
  decisionOverview.hidden = true;
  reviewMessage.innerHTML = session.status === "stale" ? `
    <div class="analysis-waiting">
      <h3>Your master resume changed</h3>
      <p>This session is paused so older suggestions cannot be applied to the updated resume. Restart its analysis from the current master to continue.</p>
      <div class="waiting-actions"><button class="button button-primary" id="reconcile-session" type="button">Restart from current master</button></div>
    </div>
  ` : `
    <div class="analysis-waiting">
      <h3>Ready for grounded suggestions</h3>
      <p>This session is saved. Ask Codex to analyze it; the complete recommendation set will appear inline across your resume.</p>
      <div class="waiting-actions">
        <button class="button button-primary" id="copy-codex-request" type="button">Copy request for Codex</button>
        <button class="button button-quiet" id="waiting-refresh" type="button">Check for suggestions</button>
      </div>
    </div>
  `;
  requirementsList.innerHTML = `<p class="muted-panel-copy">Requirements will appear with the suggestions.</p>`;
  renderSuggestionDocument(session);
}

function renderStaleMessage() {
  reviewMessage.innerHTML = `
    <div class="analysis-waiting">
      <h3>Your master resume changed</h3>
      <p>This session is paused so older suggestions cannot be applied to the updated resume. Restart its analysis from the current master to continue.</p>
      <div class="waiting-actions"><button class="button button-primary" id="reconcile-session" type="button">Restart from current master</button></div>
    </div>
  `;
}

function renderPageFit(preview) {
  if (!preview || preview.report.pages <= 1) {
    reviewMessage.innerHTML = "";
    return;
  }
  const opportunities = preview.page_fit_opportunities || [];
  reviewMessage.innerHTML = `
    <div class="page-fit-alert">
      <h3>The current preview is ${preview.report.pages} pages</h3>
      <p>Revisit specific lines below. No content will be shortened or removed without your approval.</p>
      <div class="page-fit-links">
        ${opportunities.map((item) => `<button class="page-fit-link" type="button" data-jump-bullet="${item.entry_number}.${item.bullet_number}" title="${escapeHtml(item.reason)}">${escapeHtml(item.entry_title)} · bullet ${item.bullet_number}</button>`).join("")}
      </div>
    </div>
  `;
}

function renderOverview(session) {
  const counts = session.decision_counts;
  const chips = [
    ["all", "All", counts.all],
    ["unresolved", "Unresolved", counts.unresolved],
    ["accepted", "Approved", counts.accepted],
    ["kept", "Kept", counts.kept],
    ["needs_confirmation", "Needs context", counts.needs_confirmation],
    ["removed", "Removed", counts.removed],
  ];
  decisionOverview.hidden = false;
  decisionOverview.innerHTML = chips.map(([key, label, count]) => `
    <button class="filter-chip ${state.filter === key ? "is-active" : ""}" type="button" data-filter="${key}">${label}<span>${count}</span></button>
  `).join("");
}

function renderRequirements(session) {
  requirementsList.innerHTML = session.requirements.map((requirement) => `
    <article class="requirement-card ${requirement.eligibility_mismatch ? "is-mismatch" : ""}" id="requirement-${escapeHtml(requirement.id)}">
      <div class="requirement-status-row">
        <span>${escapeHtml(requirement.category)}</span>
        <strong>${requirement.supported ? `${requirement.evidence.length} evidence link${requirement.evidence.length === 1 ? "" : "s"}` : requirement.eligibility_mismatch ? "Eligibility mismatch" : "No direct evidence"}</strong>
      </div>
      <p>${escapeHtml(requirement.text)}</p>
      <blockquote>${escapeHtml(requirement.source_excerpt)}</blockquote>
    </article>
  `).join("");
}

function renderReviewNavigation(session) {
  const groups = groupedEntries(session.entries);
  document.querySelector("#review-section-nav").innerHTML = groups.map((group) => `
    <button class="section-link" type="button" data-review-section="${sectionId(group.section, "review-section")}">
      <span>${escapeHtml(group.section)}</span><span class="section-count">${group.entries.length}</span>
    </button>
  `).join("");
}

function updateReviewControls(session) {
  const hasSuggestions = Boolean(session.suggestions);
  const unresolved = session.decision_counts.unresolved;
  document.querySelector("#undo-button").disabled = !session.history.length;
  const previewReady = session.preview?.report?.pages === 1;
  document.querySelector("#build-preview").disabled = !hasSuggestions || session.status === "stale";
  document.querySelector("#export-button").disabled = !hasSuggestions || unresolved !== 0 || !previewReady || session.status === "stale";
  document.querySelector("#export-note").textContent = !hasSuggestions
    ? "Prepare suggestions before export."
    : unresolved
      ? `${unresolved} decision${unresolved === 1 ? "" : "s"} remaining before export.`
      : !previewReady
        ? "Build and review a one-page preview before export."
        : "All suggestions resolved. Ready for final export.";
}

function renderStages(session) {
  const stages = ["Job", "Preparing suggestions", "Page fit", "Final review", "Exported"];
  const activeStage = session.stage === "Reviewing suggestions" ? "Preparing suggestions" : session.stage;
  const activeIndex = Math.max(0, stages.indexOf(activeStage));
  document.querySelectorAll("#stage-list li").forEach((item, index) => {
    item.classList.toggle("is-active", index === activeIndex);
    item.classList.toggle("is-complete", index < activeIndex);
    if (index === activeIndex) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  });
}

function showSession(session) {
  const changedSession = state.session?.session_id !== session.session_id;
  state.session = session;
  if (changedSession) state.filter = "all";
  setView("review");
  document.querySelector("#review-role").textContent = session.job.role;
  document.querySelector("#review-company").textContent = session.job.company;
  const analysisStatus = document.querySelector("#analysis-status");
  analysisStatus.classList.toggle("is-ready", Boolean(session.suggestions) && session.status === "ready");
  analysisStatus.querySelector("span:last-child").textContent = session.status === "stale"
    ? "Master changed — reconciliation needed"
    : session.suggestions ? "All suggestions ready" : "Waiting for suggestions";
  renderStages(session);
  renderReviewNavigation(session);
  reviewMessage.innerHTML = "";
  if (session.status === "stale") {
    if (session.suggestions) {
      renderOverview(session);
      renderRequirements(session);
    } else {
      decisionOverview.hidden = true;
      requirementsList.innerHTML = `<p class="muted-panel-copy">Restart the session to prepare current requirements.</p>`;
    }
    renderSuggestionDocument(session);
    renderStaleMessage();
  } else if (!session.suggestions) {
    renderWaitingSession(session);
  } else {
    renderOverview(session);
    renderRequirements(session);
    renderSuggestionDocument(session);
    renderPageFit(session.preview);
  }
  updateReviewControls(session);
  if (changedSession && session.next_unresolved) {
    window.requestAnimationFrame(() => {
      const next = session.next_unresolved;
      const selector = next.kind === "bullet"
        ? `.suggestion-item[data-entry="${next.entry_number}"][data-bullet="${next.bullet_number}"]`
        : `.project-recommendation[data-entry="${next.entry_number}"]`;
      document.querySelector(selector)?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }
}

function applyFilter() {
  if (!state.session?.suggestions) return;
  document.querySelectorAll(".suggestion-item[data-suggestion-status]").forEach((item) => {
    item.hidden = state.filter !== "all" && item.dataset.suggestionStatus !== state.filter;
  });
  document.querySelectorAll(".project-recommendation[data-suggestion-status]").forEach((item) => {
    item.hidden = state.filter !== "all" && item.dataset.suggestionStatus !== state.filter;
  });
  document.querySelectorAll(".suggestion-entry").forEach((entry) => {
    if (state.filter === "all") { entry.hidden = false; return; }
    entry.hidden = !entry.querySelector(`[data-suggestion-status="${state.filter}"]:not([hidden])`);
  });
  document.querySelectorAll(".suggestion-section").forEach((section) => {
    section.hidden = !section.querySelector(".suggestion-entry:not([hidden])");
  });
}

async function reloadCurrentSession() {
  if (!state.session) return;
  try {
    const session = await api(`/api/sessions/${state.session.session_id}`);
    showSession(session);
    if (!session.suggestions) showToast("Suggestions are not ready yet.");
  } catch (error) {
    showToast(error.message);
  }
}

async function saveDecisions(body) {
  try {
    const session = await api(`/api/sessions/${state.session.session_id}/decisions`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    showSession(session);
    showToast("Decision saved.");
  } catch (error) {
    showToast(error.message);
  }
}

function findBulletSuggestion(key) {
  return state.session.suggestions.bullets.find((item) => `${item.entry_number}.${item.bullet_number}` === key);
}

function handleSuggestionAction(event) {
  const approve = event.target.closest("[data-approve-bullet]");
  const keep = event.target.closest("[data-keep-bullet]");
  const other = event.target.closest("[data-other-bullet]");
  const project = event.target.closest("[data-project-action]");
  const approveEntry = event.target.closest("[data-approve-entry]");
  const requirement = event.target.closest("[data-requirement]");
  if (requirement) {
    document.querySelector('[data-panel="requirements-panel"]').click();
    evidencePanel.classList.add("is-open");
    document.querySelector("#toggle-evidence").setAttribute("aria-expanded", "true");
    document.querySelector(`#requirement-${CSS.escape(requirement.dataset.requirement)}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  if (project) {
    const [entryNumber, action] = project.dataset.projectAction.split(":");
    saveDecisions({ project_decisions: [{ entry_number: Number(entryNumber), action }] });
    return;
  }
  if (approveEntry) {
    const entryNumber = Number(approveEntry.dataset.approveEntry);
    const entry = state.session.entries.find((item) => item.entry_number === entryNumber);
    const suggestions = state.session.suggestions.bullets.filter(
      (item) => item.entry_number === entryNumber,
    );
    const decisions = suggestions
      .filter((item) => item.action !== "ask")
      .map((item) => ({
        entry_number: item.entry_number,
        bullet_number: item.bullet_number,
        action: item.action,
        accepted_text: item.action === "rewrite" ? item.suggested_text : undefined,
      }));
    const contextNeeded = suggestions.length - decisions.length;
    const message = `Apply ${decisions.length} recommendations for ${entry.title}?${contextNeeded ? `\n\n${contextNeeded} item${contextNeeded === 1 ? "" : "s"} needing context will remain unresolved.` : ""}`;
    if (decisions.length && window.confirm(message)) {
      saveDecisions({ bullet_decisions: decisions });
    }
    return;
  }
  const key = approve?.dataset.approveBullet || keep?.dataset.keepBullet || other?.dataset.otherBullet;
  if (!key) return;
  const [entryNumber, bulletNumber] = key.split(".").map(Number);
  const suggestion = findBulletSuggestion(key);
  if (keep) {
    saveDecisions({ bullet_decisions: [{ entry_number: entryNumber, bullet_number: bulletNumber, action: "keep" }] });
  } else if (other || suggestion.action === "ask") {
    const entry = state.session.entries.find((item) => item.entry_number === entryNumber);
    const bullet = entry.bullets.find((item) => item.bullet_number === bulletNumber);
    state.otherTarget = { entryNumber, bulletNumber, requiresFact: suggestion.action === "ask" };
    otherText.value = suggestion.suggested_text || bullet.source_text;
    otherFact.value = "";
    otherInstruction.value = "";
    otherDialog.showModal();
    otherText.focus();
  } else {
    saveDecisions({
      bullet_decisions: [{
        entry_number: entryNumber,
        bullet_number: bulletNumber,
        action: suggestion.action,
        accepted_text: suggestion.action === "rewrite" ? suggestion.suggested_text : undefined,
      }],
    });
  }
}

async function undoLastDecision() {
  try {
    const session = await api(`/api/sessions/${state.session.session_id}/undo`, { method: "POST", body: "{}" });
    showSession(session);
    showToast("Last decision undone.");
  } catch (error) { showToast(error.message); }
}

async function buildPreview() {
  const button = document.querySelector("#build-preview");
  button.disabled = true;
  button.textContent = "Building…";
  try {
    const preview = await api(`/api/sessions/${state.session.session_id}/preview`, { method: "POST", body: "{}" });
    state.session.preview = preview;
    state.session.stage = preview.report.pages === 1 ? "Final review" : "Page fit";
    updateReviewControls(state.session);
    renderStages(state.session);
    renderPageFit(preview);
    document.querySelector('[data-panel="preview-panel"]').click();
    evidencePanel.classList.add("is-open");
    document.querySelector("#toggle-evidence").setAttribute("aria-expanded", "true");
    document.querySelector("#preview-empty").hidden = true;
    const frame = document.querySelector("#tailored-pdf-frame");
    frame.hidden = false;
    frame.src = `${preview.url}?v=${Date.now()}`;
    showToast(`Preview built: ${preview.report.pages} page${preview.report.pages === 1 ? "" : "s"}.`);
  } catch (error) { showToast(error.message); }
  finally { button.disabled = false; button.textContent = "Build preview"; }
}

async function exportResume(overwrite = false) {
  const button = document.querySelector("#export-button");
  button.disabled = true;
  button.innerHTML = "Exporting…";
  try {
    if (!overwrite) {
      const counts = state.session.decision_counts;
      const approved = counts.accepted + counts.kept;
      const confirmed = window.confirm(`Export ${state.session.job.role} at ${state.session.job.company}?\n\n${approved} approved or kept · ${counts.removed} removed\nTarget: ${state.session.target_slug}/Morgan_Le_Resume.pdf`);
      if (!confirmed) return;
    }
    const result = await api(`/api/sessions/${state.session.session_id}/export`, {
      method: "POST",
      body: JSON.stringify({ overwrite }),
    });
    state.session.export = result;
    state.session.stage = "Exported";
    renderStages(state.session);
    showToast(`Resume exported to ${result.pdf}.`);
    document.querySelector("#export-note").textContent = `Exported successfully · ${result.report.pages} A4 page`;
  } catch (error) {
    if (!overwrite && error.message.includes("already exists") && window.confirm(`${error.message}\n\nOverwrite only this tailored resume's source and PDF?`)) {
      return exportResume(true);
    }
    showToast(error.message);
  } finally {
    button.disabled = state.session?.decision_counts.unresolved !== 0 || state.session?.preview?.report?.pages !== 1;
    button.innerHTML = "Export tailored resume <span aria-hidden=\"true\">→</span>";
  }
}

async function loadSessions() {
  setView("sessions");
  const list = document.querySelector("#sessions-list");
  list.innerHTML = `<div class="empty-sessions">Loading sessions…</div>`;
  try {
    const payload = await api("/api/sessions");
    if (!payload.sessions.length) {
      list.innerHTML = `<div class="empty-sessions"><h2>No tailoring sessions yet</h2><p>Start from your built-in resume when you find a role.</p></div>`;
      return;
    }
    list.innerHTML = payload.sessions.map((session) => {
      const total = session.decision_counts.all || 1;
      const completed = total - session.decision_counts.unresolved;
      const percent = Math.max(0, Math.min(100, Math.round((completed / total) * 100)));
      return `
        <article class="session-card">
          <div><p class="eyebrow">${escapeHtml(session.job.company)}</p><h2>${escapeHtml(session.job.role)}</h2><p>${escapeHtml(session.stage)} · ${session.has_suggestions ? `${session.decision_counts.unresolved} decisions remaining` : "Waiting for suggestions"}</p></div>
          <div class="session-progress"><span style="width:${percent}%"></span></div>
          <div class="session-meta"><span>${escapeHtml(session.status)}</span><span>${new Date(session.updated_at).toLocaleDateString()}</span></div>
          <div class="card-actions">
            <button class="button button-quiet" type="button" data-open-session="${escapeHtml(session.session_id)}">Open session</button>
            <button class="mini-button danger" type="button" data-archive-session="${escapeHtml(session.session_id)}">Archive</button>
          </div>
        </article>
      `;
    }).join("");
  } catch (error) {
    list.innerHTML = `<div class="empty-sessions"><h2>Sessions unavailable</h2><p>${escapeHtml(error.message)}</p></div>`;
  }
}

async function loadSettings() {
  setView("settings");
  const target = document.querySelector("#settings-content");
  try {
    const settings = await api("/api/settings");
    target.innerHTML = `
      <section class="settings-card">
        <h2>Local workspace</h2>
        <div class="setting-row"><span>Repository</span><code>${escapeHtml(settings.repository)}</code></div>
        <div class="setting-row"><span>Session data</span><code>${escapeHtml(settings.session_data)}</code></div>
        <div class="setting-row"><span>Network</span><strong>${escapeHtml(settings.network)}</strong></div>
      </section>
      <section class="settings-card">
        <h2>Document workflow</h2>
        <div class="setting-row"><span>AI suggestions</span><strong>${escapeHtml(settings.ai_mode)}</strong></div>
        <div class="setting-row"><span>PDF compiler</span><span class="check-value">${settings.tectonic ? "Ready" : "Missing"}</span></div>
        <div class="setting-row"><span>PDF renderer</span><span class="check-value">${settings.pdf_renderer ? "Ready" : "Missing"}</span></div>
      </section>
    `;
  } catch (error) {
    target.innerHTML = `<div class="empty-sessions"><h2>Settings unavailable</h2><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function copyCodexRequest() {
  const request = `Use the resume workspace tools to read session ${state.session.session_id}, analyze the complete job description against every verified resume bullet, and submit one grounded suggestion for every bullet plus an Include or Exclude suggestion for every project.`;
  navigator.clipboard.writeText(request)
    .then(() => showToast("Request copied. Paste it into this Codex task."))
    .catch(() => showToast(request));
}

function copyRevisionRequest(request) {
  const prompt = `Use the resume workspace tools to read session ${state.session.session_id}. Fulfill pending revision request ${request.id}: ${request.instruction}. Submit a grounded replacement suggestion only for that request without inventing facts.`;
  navigator.clipboard.writeText(prompt)
    .then(() => showToast("Revision request saved and copied for Codex."))
    .catch(() => showToast("Revision request saved. Ask Codex to fulfill the pending request."));
}

function registerWebMcpTools() {
  const context = document.modelContext;
  if (!context?.registerTool) return;
  const register = (tool) => {
    try { Promise.resolve(context.registerTool(tool)).catch(() => {}); } catch { /* unsupported preview */ }
  };
  register({
    name: "read_resume_tailoring_context",
    title: "Read resume tailoring context",
    description: "Read the complete verified resume and job description for a saved local tailoring session before generating suggestions.",
    inputSchema: {
      type: "object",
      properties: { session_id: { type: "string", pattern: "^[a-z0-9][a-z0-9-]{0,79}$" } },
      required: ["session_id"],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true, untrustedContentHint: true },
    async execute(input) {
      return api(`/api/sessions/${encodeURIComponent(input.session_id)}/context`);
    },
  });
  register({
    name: "submit_resume_suggestions",
    title: "Submit complete resume suggestions",
    description: "Validate and save one complete grounded suggestion set for every resume bullet and project in a local tailoring session.",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string", pattern: "^[a-z0-9][a-z0-9-]{0,79}$" },
        requirements: { type: "array", items: { type: "object", properties: { id: { type: "string" }, text: { type: "string" }, category: { type: "string", enum: ["responsibility", "required", "preferred", "keyword", "eligibility"] }, source_excerpt: { type: "string" } }, required: ["id", "text", "category", "source_excerpt"], additionalProperties: false } },
        bullet_suggestions: { type: "array", items: { type: "object", properties: { entry_number: { type: "integer" }, bullet_number: { type: "integer" }, action: { type: "string", enum: ["keep", "rewrite", "remove", "ask"] }, suggested_text: { type: ["string", "null"] }, reason: { type: "string" }, requirement_id: { type: ["string", "null"] } }, required: ["entry_number", "bullet_number", "action", "reason"], additionalProperties: false } },
        project_suggestions: { type: "array", items: { type: "object", properties: { entry_number: { type: "integer" }, action: { type: "string", enum: ["include", "exclude"] }, reason: { type: "string" }, requirement_id: { type: ["string", "null"] } }, required: ["entry_number", "action", "reason"], additionalProperties: false } },
      },
      required: ["session_id", "requirements", "bullet_suggestions", "project_suggestions"],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: false, untrustedContentHint: false },
    async execute(input) {
      const session = await api(`/api/sessions/${encodeURIComponent(input.session_id)}/analysis`, {
        method: "POST",
        body: JSON.stringify(input),
      });
      if (state.session?.session_id === input.session_id) showSession(session);
      return { session_id: session.session_id, status: "suggestions_ready", suggestion_count: session.decision_counts.all };
    },
  });
  register({
    name: "submit_resume_suggestion_revision",
    title: "Submit one revised resume suggestion",
    description: "Fulfill a pending user-requested revision for one resume bullet in a local tailoring session.",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string", pattern: "^[a-z0-9][a-z0-9-]{0,79}$" },
        request_id: { type: "string" },
        suggestion: {
          type: "object",
          properties: {
            action: { type: "string", enum: ["keep", "rewrite", "remove", "ask"] },
            suggested_text: { type: ["string", "null"] },
            reason: { type: "string" },
            requirement_id: { type: ["string", "null"] },
          },
          required: ["action", "reason"],
          additionalProperties: false,
        },
      },
      required: ["session_id", "request_id", "suggestion"],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: false, untrustedContentHint: false },
    async execute(input) {
      const session = await api(`/api/sessions/${encodeURIComponent(input.session_id)}/revision`, {
        method: "POST",
        body: JSON.stringify(input),
      });
      if (state.session?.session_id === input.session_id) showSession(session);
      return { session_id: session.session_id, request_id: input.request_id, status: "revision_ready" };
    },
  });
}

masterSectionNav.addEventListener("click", (event) => {
  const button = event.target.closest("[data-master-section]");
  if (button) document.querySelector(`#${button.dataset.masterSection}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
});
document.querySelector("#review-section-nav").addEventListener("click", (event) => {
  const button = event.target.closest("[data-review-section]");
  if (button) document.querySelector(`#${button.dataset.reviewSection}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
});
document.querySelector("#job-form").addEventListener("submit", createSession);
document.querySelector("#open-tailor").addEventListener("click", openTailorPanel);
document.querySelector("#sessions-new").addEventListener("click", openTailorPanel);
document.querySelector("#nav-resume").addEventListener("click", () => setView("master"));
document.querySelector("#brand-home").addEventListener("click", () => setView("master"));
document.querySelector("#nav-sessions").addEventListener("click", loadSessions);
document.querySelector("#nav-settings").addEventListener("click", loadSettings);
document.querySelector("#review-back").addEventListener("click", () => setView("master"));
document.querySelector("#refresh-button").addEventListener("click", reloadCurrentSession);
document.querySelector("#undo-button").addEventListener("click", undoLastDecision);
document.querySelector("#build-preview").addEventListener("click", buildPreview);
document.querySelector("#toggle-evidence").addEventListener("click", () => {
  const open = evidencePanel.classList.toggle("is-open");
  document.querySelector("#toggle-evidence").setAttribute("aria-expanded", String(open));
});
document.querySelector("#export-button").addEventListener("click", () => exportResume(false));
description.addEventListener("input", () => { descriptionCount.textContent = `${description.value.length.toLocaleString()} characters`; });

document.querySelector("#sessions-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-open-session]");
  const archive = event.target.closest("[data-archive-session]");
  if (button) {
    try { showSession(await api(`/api/sessions/${button.dataset.openSession}`)); }
    catch (error) { showToast(error.message); }
  }
  if (archive && window.confirm("Archive this session? Its exported resume will remain untouched.")) {
    try {
      await api(`/api/sessions/${archive.dataset.archiveSession}/archive`, { method: "POST", body: "{}" });
      showToast("Session archived.");
      loadSessions();
    } catch (error) { showToast(error.message); }
  }
});

suggestionContent.addEventListener("click", handleSuggestionAction);
reviewMessage.addEventListener("click", (event) => {
  if (event.target.closest("#copy-codex-request")) copyCodexRequest();
  if (event.target.closest("#waiting-refresh")) reloadCurrentSession();
  if (event.target.closest("#reconcile-session") && window.confirm("Restart this session from the updated master? Existing suggestions and decisions in this session will be cleared.")) {
    api(`/api/sessions/${state.session.session_id}/reconcile`, { method: "POST", body: "{}" })
      .then(showSession)
      .then(() => showToast("Session restarted from the current master."))
      .catch((error) => showToast(error.message));
  }
  const jump = event.target.closest("[data-jump-bullet]");
  if (jump) {
    state.filter = "all";
    renderOverview(state.session);
    applyFilter();
    const [entryNumber, bulletNumber] = jump.dataset.jumpBullet.split(".");
    document.querySelector(`.suggestion-item[data-entry="${entryNumber}"][data-bullet="${bulletNumber}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }
});
decisionOverview.addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  state.filter = button.dataset.filter;
  renderOverview(state.session);
  applyFilter();
});

document.querySelectorAll(".evidence-tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".evidence-tab").forEach((tab) => tab.classList.toggle("is-active", tab === button));
    document.querySelectorAll(".evidence-content").forEach((panel) => { panel.hidden = panel.id !== button.dataset.panel; });
  });
});

document.querySelector("#other-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const action = event.submitter?.value;
  if (action === "cancel") { otherDialog.close(); return; }
  if (!state.otherTarget) return;
  const acceptedText = otherText.value.trim();
  const confirmedFact = otherFact.value.trim();
  const revisionInstruction = otherInstruction.value.trim();
  document.querySelector("#other-error").hidden = true;
  if (action === "rewrite" && !acceptedText) {
    document.querySelector("#other-error").textContent = "Enter the wording you want to use.";
    document.querySelector("#other-error").hidden = false;
    return;
  }
  if (action === "rewrite" && state.otherTarget.requiresFact && !confirmedFact) {
    document.querySelector("#other-error").textContent = "Confirm the missing fact or metric before accepting this rewrite.";
    document.querySelector("#other-error").hidden = false;
    return;
  }
  if (action === "request" && !revisionInstruction) {
    document.querySelector("#other-error").textContent = "Describe what you want the next suggestion to do differently.";
    document.querySelector("#other-error").hidden = false;
    return;
  }
  const target = state.otherTarget;
  otherDialog.close();
  if (action === "request") {
    try {
      const session = await api(`/api/sessions/${state.session.session_id}/revision-request`, {
        method: "POST",
        body: JSON.stringify({
          entry_number: target.entryNumber,
          bullet_number: target.bulletNumber,
          instruction: revisionInstruction,
        }),
      });
      showSession(session);
      const request = [...session.revision_requests].reverse().find(
        (item) => item.entry_number === target.entryNumber && item.bullet_number === target.bulletNumber && item.status === "pending",
      );
      if (request) copyRevisionRequest(request);
    } catch (error) {
      showToast(error.message);
    }
    state.otherTarget = null;
    return;
  }
  saveDecisions({
    bullet_decisions: [{ entry_number: target.entryNumber, bullet_number: target.bulletNumber, action, accepted_text: action === "rewrite" ? acceptedText : undefined }],
    confirmed_facts: confirmedFact ? [confirmedFact] : [],
  });
  state.otherTarget = null;
});

viewMasterPdf.addEventListener("click", () => { masterPdfFrame.src = "/api/master/pdf"; masterPdfDialog.showModal(); });
document.querySelector("#close-pdf").addEventListener("click", () => masterPdfDialog.close());
masterPdfDialog.addEventListener("click", (event) => { if (event.target === masterPdfDialog) masterPdfDialog.close(); });
document.querySelector("#view-source-details").addEventListener("click", () => {
  const master = state.master;
  document.querySelector("#source-details").innerHTML = master ? `
    <div><span>Source</span><code>master/_resume.tex</code></div>
    <div><span>Mode</span><strong>Read-only</strong></div>
    <div><span>Verified entries</span><strong>${master.entry_count}</strong></div>
    <div><span>Source fingerprint</span><code>${escapeHtml(master.sha256)}</code></div>
    <div><span>PDF</span><strong>${master.pdf.available ? "Available" : "Unavailable"}</strong></div>
  ` : `<p>Master resume details are unavailable.</p>`;
  sourceDialog.showModal();
});
document.querySelector("#close-source").addEventListener("click", () => sourceDialog.close());
sourceDialog.addEventListener("click", (event) => { if (event.target === sourceDialog) sourceDialog.close(); });

registerWebMcpTools();
loadMaster();
