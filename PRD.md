# Resume Tailoring Workspace

## Product Requirements Document

| Field | Value |
| --- | --- |
| Status | MVP implemented locally |
| Version | 1.0 |
| Date | September 3, 2026 |
| Product | Self-hosted AI-assisted resume tailoring workspace |
| Initial platform | Local web application |

## 1. Product summary

Resume Tailoring Workspace is a private, self-hosted web application that opens with the user's verified resume already built in. After the user adds a job description, the product analyzes the complete resume and displays all AI recommendations inline across it. The user can then approve each suggestion, keep the current content, or provide another instruction.

The product converts the repository's existing conversational workflow into a visual review experience. It preserves the master resume as the source of truth, applies only explicit decisions to a tailored draft, and produces a validated one-page A4 PDF.

The first version is intentionally resume-only. Cover letters and broader job-application tracking are deferred until the resume workflow is reliable and pleasant to use.

## 2. Problem

The current workflow has strong accuracy and approval safeguards, but it happens inside a long text conversation. This creates avoidable friction:

- The user cannot see the complete resume and current progress at a glance.
- Current wording, AI suggestions, and approved wording can be difficult to distinguish.
- The relationship between a suggestion and the job description is not continuously visible.
- Returning to an interrupted review requires conversational context.
- PDF generation and validation happen after many decisions instead of feeling integrated with them.
- The user must remember commands or phrase decisions in text when a clear control would be faster.

Generic resume tools may provide a polished interface, but they often obscure the underlying source, over-automate decisions, or introduce claims that are not supported by the user's history.

## 3. Product vision

Create the simplest trustworthy interface for moving from a verified master resume to a job-specific resume: the resume is already there, AI proposes changes, the user remains in control, and the final document is visibly ready to submit.

## 4. Goals

### 4.1 Primary goals

1. Load and display the existing master resume without requiring an upload or manual setup on every use.
2. Generate job-specific suggestions grounded in verified resume content.
3. Show the complete set of AI suggestions across the resume before review begins.
4. Make every AI suggestion easy to understand, approve, reject, or redirect.
5. Apply only explicit user decisions to the tailored resume.
6. Show progress, job relevance, and document impact throughout the review.
7. Produce an exactly one-page A4 resume that passes factual, structural, and visual validation.
8. Keep resume and job-description data locally controlled.
9. Preserve work across browser refreshes and interrupted sessions.

### 4.2 Success definition

A user can launch the product, paste a job description, see every AI recommendation directly on the complete resume, review those recommendations in any order, and export a validated tailored resume without uploading an existing resume, editing LaTeX, remembering workflow commands, or wondering whether an AI change was applied automatically.

## 5. Non-goals for the MVP

The first release will not:

- Create or manage cover letters.
- Search job boards or submit applications.
- Track interviews, networking, or recruiting activity.
- Host resume data in a managed cloud service.
- Replace the master resume with a proprietary editor format.
- Automatically approve, reject, remove, or shorten resume content.
- Invent employers, titles, dates, responsibilities, technologies, metrics, or outcomes.
- Allow direct editing of locked historical fields.
- Offer a visual resume-template marketplace or unrestricted document design.
- Provide a native macOS, Windows, iOS, or Android application.
- Require Git or LaTeX knowledge for normal use.

## 6. Target user

### 6.1 Primary user

An individual job seeker who maintains a comprehensive verified resume and creates targeted versions for specific roles.

### 6.2 Primary jobs to be done

- Show me my current verified resume as soon as I open the product.
- Help me understand which parts of my resume matter for this job.
- Suggest stronger wording without changing facts.
- Let me approve a good suggestion with one action.
- Let me keep my original wording when I disagree.
- Let me ask for something different without leaving the review context.
- Show me how accepted decisions change the final resume.
- Tell me exactly what still needs attention before I can export.

## 7. Product principles

### 7.1 The resume is already there

The application loads `master/_resume.tex` automatically from the configured repository. The user should not repeatedly upload, paste, or reconstruct their resume.

### 7.2 AI proposes; the user decides

AI recommendations are previews. They do not change the tailored draft until the user explicitly approves a suggestion or provides an alternative decision.

### 7.3 Truth before keyword matching

Every factual claim must originate from active master-resume content or an explicit user confirmation. The product must not strengthen a claim merely because it better matches the job description.

### 7.4 Make the decision obvious

Every suggestion must clearly show:

- The current content
- The recommended action
- The proposed content, when applicable
- Why the suggestion helps for this job
- Which job requirement it addresses
- Whether accepting it changes, keeps, or removes content

### 7.5 Reversible actions

Every decision batch can be undone. Existing tailored variants cannot be overwritten without explicit confirmation and a visible change summary.

### 7.6 Local by default

The application runs on the user's machine, listens only on localhost by default, and stores application state locally.

### 7.7 Submission quality is part of the workflow

PDF building, validation, rendering, and visual review are required stages of the product rather than separate maintenance tasks.

## 8. Product structure

The product has two primary objects: the **Master Resume** and a **Tailoring Session**.

```text
Master Resume
├── Verified content from master/_resume.tex
├── Read-only resume view
└── Current master PDF preview

Tailoring Session
├── Company, role, and job description
├── Extracted job requirements
├── AI recommendations
├── Project selections
├── Explicit bullet decisions
├── Tailored resume draft
├── Decision history
└── Build, validation, and export status
```

### 8.1 Primary navigation

1. **My Resume** — View the built-in verified resume and its rendered PDF.
2. **Tailor for a Job** — Start a new tailoring session from a job description.
3. **Sessions** — Resume, inspect, or archive incomplete and completed sessions.
4. **Settings** — Configure repository location, document tools, AI integration, and optional remote access.

### 8.2 Tailoring stages

Each session moves through five visible stages:

1. Job
2. Suggestions
3. Page fit
4. Final review
5. Export

## 9. Core user journey

### 9.1 Open the product

1. The product locates the configured repository and reads the active master resume.
2. The home screen displays the rendered master resume, last build status, and available actions.
3. If the master cannot be parsed or built, the product explains the problem and does not silently fall back to stale content.
4. The primary action is **Tailor for a Job**.

### 9.2 Start a tailoring session

1. The user enters a company, role, and complete job description. A job URL is optional.
2. The product proposes a unique lowercase folder slug.
3. The product records the current master-resume hash and creates a complete working copy for the tailored session.
4. The product extracts job responsibilities, required qualifications, preferred qualifications, keywords, and eligibility constraints.
5. The user can inspect and correct the extracted requirements before suggestions are generated.

### 9.3 Review AI suggestions

1. The product analyzes the job description against verified resume content.
2. Before review begins, the product generates a complete recommendation set for Education, Relevant Experience, skills, and project selection.
3. The product displays the complete resume in its original section and entry order, with every available recommendation shown inline beside or immediately beneath the affected content.
4. The user can scroll through the whole resume, jump from the section outline, filter to unresolved suggestions, and review suggestions in any order.
5. Every bullet receives exactly one recommendation:
   - Keep
   - Rewrite
   - Remove
   - Ask for one missing fact
6. Every recommendation card contains the original content, proposed content when relevant, a short reason, and the matching job requirement.
7. The user selects one of three primary responses:
   - **Approve suggestion** — Apply the recommendation to the tailored draft.
   - **Keep current** — Reject the proposed change and retain the original content.
   - **Other…** — Edit the wording, request a different suggestion, remove the bullet, or provide a custom instruction.
8. The UI changes **Approve suggestion** to an action-specific confirmation where clarity is important, such as **Use rewrite**, **Keep bullet**, or **Remove bullet**.
9. Accepted decisions update the tailored draft and live preview. Unaccepted suggestions never affect the draft.
10. The user cannot complete the resume until every mandatory or included bullet has an explicit decision.
11. The user can undo the most recent decision batch.

The complete suggestion set is visible at once, but suggestions are not bulk-applied. Visibility does not count as approval.

### 9.4 Select projects

1. The Projects section of the full-resume view shows every verified project and its Include or Exclude recommendation together.
2. Each project receives one job-specific Include or Exclude recommendation with a short reason.
3. The user explicitly includes or excludes every project.
4. Only included projects display and require decisions for their bullet-level suggestions; excluded projects collapse into their accepted exclusion state.
5. Excluding a project affects only the tailored resume and never removes it from the master.

### 9.5 Fit the resume to one page

1. After all required decisions are complete, the product builds a temporary tailored PDF.
2. If the draft exceeds one A4 page, the product identifies specific fitting opportunities.
3. Every removal or rewrite still requires explicit approval.
4. The product prioritizes concision and removal of repetition before recommending smaller type or tighter layout.
5. The product never removes a verified work position and retains at least one substantive bullet for each position.

### 9.6 Final review and export

1. The product shows the final tailored resume and a concise summary of accepted changes.
2. The product runs structural, factual, page-size, text-extraction, hyperlink, and visual checks.
3. A failed check links back to the affected entry or bullet.
4. The user approves the final output location before an existing variant is overwritten.
5. The product exports the tailored source and `Morgan_Le_Resume.pdf` to the approved resume folder.

## 10. Interface requirements

### 10.1 My Resume screen

The default screen shows:

- The current rendered master resume
- The date and result of the most recent successful build
- Any source or build warnings
- A section outline for quick navigation
- A primary **Tailor for a Job** action
- A secondary **View source details** action for advanced inspection

The master resume is read-only in the MVP. Adding or changing source-of-truth content continues through an explicit, separate workflow.

### 10.2 Review workspace

The desktop layout uses three regions:

- **Left:** Resume sections, entries, progress, unresolved-decision counts, and suggestion filters.
- **Center:** The complete resume in source order with all recommendations displayed inline.
- **Right:** Relevant job requirements and the live tailored-resume preview.

The center region is the primary workflow. Entries may be collapsed after completion, but every unresolved suggestion remains reachable without advancing through a forced sequence. The user can collapse the job-requirement panel or enlarge the PDF preview. On smaller screens, the right region becomes a switchable panel rather than a permanently visible column.

An overview bar above the resume shows counts for All suggestions, Unresolved, Approved, Kept current, Needs confirmation, and Removed. Selecting a count filters or navigates the inline resume view without changing decisions.

### 10.3 Recommendation card

Each card must include:

1. Local bullet number and status
2. AI recommendation label
3. Current wording from the source
4. Suggested wording, if the recommendation is Rewrite
5. A short job-specific reason
6. The linked job requirement
7. Controls for Approve suggestion, Keep current, and Other…
8. A visible accepted state after the user decides

The card must never imply that suggested wording has already been applied.

Compact Keep recommendations may use a shorter card, but they must still be visible in the full-resume view and require an explicit decision.

### 10.4 Other… interaction

Selecting **Other…** opens a focused input area with these capabilities:

- Edit the suggested wording directly
- Ask for a shorter, clearer, or differently emphasized rewrite
- Provide a custom instruction in natural language
- Add or confirm a missing fact
- Remove the bullet when permitted
- Cancel without changing the decision

Generated alternatives remain suggestions and require approval.

### 10.5 Live preview

- The preview reflects accepted decisions only.
- Pending suggestions do not appear in the preview.
- The active entry is highlighted or scrolled into view when possible.
- Preview generation is debounced so rapid decisions do not trigger overlapping builds.
- The last valid preview remains available if a new build fails.

### 10.6 Status language

The interface uses these states consistently:

- Not reviewed
- Suggestion ready
- Decision required
- Accepted
- Kept current
- Removed
- Needs confirmation
- Stale source
- Build failed
- Validation failed
- Ready to export

## 11. Functional requirements

### 11.1 Built-in resume

- **BASE-01:** The product automatically reads `master/_resume.tex` from the configured repository.
- **BASE-02:** Only active, uncommented resume content is treated as verified.
- **BASE-03:** The product renders and displays the current master PDF without requiring an upload.
- **BASE-04:** The product clearly distinguishes the read-only master resume from tailored drafts.
- **BASE-05:** The product detects changes to the master and refreshes its parsed content and preview.
- **BASE-06:** Parse or build failures show actionable errors and never replace the last valid preview with an empty state.

### 11.2 Tailoring sessions

- **SES-01:** The user can create a session from a company, role, and job description.
- **SES-02:** The product proposes a unique slug and prevents accidental folder overwrite.
- **SES-03:** The session list shows company, role, updated time, current stage, and completion status.
- **SES-04:** The user can resume at the exact active entry and unresolved decision.
- **SES-05:** The product marks a session stale when the master hash changes.
- **SES-06:** A stale session requires reconciliation before new decisions can be saved.
- **SES-07:** The user can archive a session without deleting its resume artifacts.

### 11.3 Job analysis

- **JOB-01:** The product stores the complete job description used by the session.
- **JOB-02:** The product extracts responsibilities, required qualifications, preferred qualifications, keywords, and eligibility constraints.
- **JOB-03:** Extracted requirements remain traceable to the original job-description text.
- **JOB-04:** The product maps requirements to verified resume evidence and marks unsupported requirements.
- **JOB-05:** Material eligibility mismatches are surfaced rather than hidden through rewritten history.

### 11.4 AI recommendations and decisions

- **REC-01:** The product generates the complete initial recommendation set before the suggestion-review stage begins.
- **REC-02:** The complete resume displays all available recommendations inline at the same time.
- **REC-03:** The user can review suggestions in any order or filter to unresolved suggestions.
- **REC-04:** Every reviewed bullet receives exactly one current recommendation.
- **REC-05:** Rewrite suggestions preserve all factual boundaries of the verified source.
- **REC-06:** Suggestions include a concise rationale and linked job requirement.
- **REC-07:** Suggestions never modify the tailored draft before explicit approval.
- **REC-08:** The user can approve the suggestion, keep current wording, or choose Other….
- **REC-09:** Other… supports manual wording, custom instructions, alternate generation, removal, and fact confirmation.
- **REC-10:** New metrics, responsibilities, technologies, or outcomes require explicit confirmation.
- **REC-11:** Historical employer, title, school, and date fields remain locked.
- **REC-12:** One user action may decide multiple bullets, and all decisions from that action are saved atomically.
- **REC-13:** The user can undo the most recent decision batch.
- **REC-14:** The user may approve all recommendations within one entry only after a confirmation summarizing their effects.
- **REC-15:** The product does not provide a global one-click action that silently accepts the complete resume.

### 11.5 Resume rules

- **RES-01:** Education and work entries are reviewed before projects.
- **RES-02:** The contact header is excluded from bullet review.
- **RES-03:** Every verified work position remains represented.
- **RES-04:** Every verified work position retains at least one substantive bullet.
- **RES-05:** Every bullet in a mandatory or included entry receives an explicit decision.
- **RES-06:** Every project receives an explicit Include or Exclude decision.
- **RES-07:** Only included projects proceed to bullet review.
- **RES-08:** Project exclusion affects only the tailored version.
- **RES-09:** Tailored-session decisions do not change the master resume.
- **RES-10:** Appending accepted content to the master requires a separate explicit source-of-truth action.
- **RES-11:** The final tailored resume is exactly one A4 page.

### 11.6 Build, validation, and export

- **EXP-01:** Accepted decisions can be rendered as a tailored PDF preview.
- **EXP-02:** Validation checks page count, A4 dimensions, extractable text, hyperlinks, protected fields, unsupported numeric claims, and work-position coverage.
- **EXP-03:** Visual QA checks for clipping, overlap, broken glyphs, awkward page breaks, and orphaned headings.
- **EXP-04:** Failed checks provide plain-language explanations and link to the relevant content.
- **EXP-05:** Build intermediates and temporary renders are removed after validation.
- **EXP-06:** A build can overwrite only the artifacts belonging to the active tailored folder.
- **EXP-07:** Existing variants require a visible final change summary and explicit overwrite confirmation.
- **EXP-08:** Successful output uses the stable filename `Morgan_Le_Resume.pdf`.

### 11.7 Privacy and settings

- **SET-01:** The local server listens on localhost by default.
- **SET-02:** Resume and job content is not sent to a third party without a clearly disclosed, user-configured AI integration.
- **SET-03:** Secrets are never stored in session JSON, logs, PDFs, or version-controlled files.
- **SET-04:** Remote access is disabled by default.
- **SET-05:** The product shows the configured repository and session-data locations.
- **SET-06:** File operations are restricted to configured repository and temporary build paths.

## 12. Data and storage

### 12.1 Sources of truth

- `master/_resume.tex` remains the canonical verified resume source.
- A tailored resume is an independent snapshot created from the current master.
- Session state stores job inputs, recommendations, explicit decisions, confirmations, and artifact references.
- A generated PDF is an output and never becomes a factual source.

### 12.2 Minimum session record

A tailoring session contains:

- Stable session ID
- Company, role, URL, and job description
- Extracted job requirements
- Master-resume path and hash
- Target slug
- Current stage, section, entry, and bullet
- AI recommendations and their evidence links
- Project selections and bullet decisions
- Explicitly confirmed additional facts
- Atomic decision history
- Build and validation results
- Tailored source and PDF paths
- Created and updated timestamps

### 12.3 Storage direction

Session metadata remains in the existing gitignored `.resume/sessions/` area or its versioned successor. Tailored resume folders continue to contain only `_resume.tex` and `Morgan_Le_Resume.pdf`. Shared LaTeX files remain under `shared/latex/`.

## 13. AI and automation boundaries

- AI may analyze the job description, map requirements to evidence, rank content, and propose wording.
- AI output is always a suggestion until accepted.
- Deterministic code performs decision persistence, file writes, builds, and validation.
- The model receives only the context needed for the active session: its job description, verified resume entries, saved requirements, and pending revision requests.
- Every suggested factual claim is traceable to source content or a user-confirmed fact.
- Model failures do not corrupt saved decisions or the last valid preview.
- The MVP uses the active Codex task through registered workspace tools or the local bridge; the independent web server does not reuse credentials, call a model, or store an API key.

## 14. Non-functional requirements

### 14.1 Reliability

- Decision writes are atomic.
- Browser refreshes and server restarts do not lose accepted work.
- Interrupted builds leave the previous valid PDF intact.
- Corrupt or incompatible session state fails safely with recovery guidance.

### 14.2 Performance

- The built-in resume screen becomes interactive within two seconds on the target machine.
- Moving between already loaded entries feels immediate.
- Suggestion generation and PDF builds show progress and remain cancellable.
- Accepting a suggestion updates the text draft immediately; PDF preview generation may complete asynchronously.

### 14.3 Accessibility

- Every primary action is keyboard accessible.
- Status is never communicated by color alone.
- Text meets WCAG AA contrast targets.
- Focus returns predictably after approval, undo, or alternate generation.

### 14.4 Maintainability

- Existing parser, ledger, builder, and validator behavior is reused rather than duplicated.
- Session state has a versioned schema and migration path.
- Resume workflow rules remain testable without a browser.
- The frontend cannot directly modify resume source files.

### 14.5 Security

- The default deployment is accessible only from the host machine.
- User-provided slugs and filenames are validated against path traversal.
- Logs redact contact details, resume content, job descriptions, and credentials by default.
- Any future network-accessible deployment requires authentication and encrypted transport.

## 15. MVP acceptance criteria

The MVP is complete when the user can:

1. Launch the application locally with one documented command.
2. See the existing master resume and its PDF without uploading anything.
3. Create and resume a tailoring session from a job description.
4. See the complete resume with all initial AI recommendations displayed inline at once.
5. Navigate or filter those suggestions and review them in any order.
6. Approve a suggestion, keep current wording, or choose Other… for every bullet.
7. See only accepted decisions in the tailored draft and live preview.
8. Select every project for inclusion or exclusion.
9. Undo the latest decision batch without losing earlier work.
10. Complete explicit page-fitting decisions when necessary.
11. Receive actionable validation failures.
12. Export an exactly one-page A4 tailored resume.
13. Restart the product and recover the complete session state.
14. Complete the workflow without editing LaTeX manually.
15. Confirm that the master source remained unchanged throughout tailoring.

## 16. Success measures

Initial measurement remains local and optional.

- Median time from job-description entry to valid PDF
- Percentage of sessions resumed successfully after interruption
- Percentage of suggestions approved, kept current, or redirected through Other…
- Number of accepted decisions later undone
- Percentage of unsupported-claim warnings resolved before export
- Build and validation success rate
- Percentage of sessions completed without manual source editing
- User-rated confidence that the final resume is accurate and ready to submit

The product should not optimize for the number of AI rewrites or the percentage of suggestions approved.

## 17. Delivery phases

### Phase 0 — Foundation

- Confirm the AI model and authentication approach.
- Define the browser-facing session API and versioned state schema.
- Wrap the existing parser, ledger, builder, and validator behind a local service boundary.
- Add failure recovery and migration tests.

### Phase 1 — Built-in resume and sessions

- Local launcher
- My Resume screen and PDF preview
- Job-description intake
- Session creation, listing, resume, and stale-source handling
- Job-requirement extraction and review

### Phase 2 — AI suggestion workflow

- Complete-resume inline suggestion interface
- Full suggestion generation before review
- Section navigation and decision-status filters
- Grounded recommendation cards
- Approve suggestion, Keep current, and Other… interactions
- Project selection
- Atomic persistence and undo
- Accepted-change live preview

### Phase 3 — Page fit and export

- Interactive page-fitting decisions
- Final change summary
- Build and deterministic validation
- Visual QA and actionable failures
- Protected export and overwrite confirmation

### Phase 4 — Product hardening

- Backup and restore
- Improved accessibility and keyboard workflow
- Optional Docker packaging
- Optional authenticated private-network access
- Optional macOS packaging if installation or file integration justifies it

### Future — Outside the resume MVP

- Cover-letter creation
- Application and interview tracking
- Additional document formats or templates
- Multi-user or hosted deployment

## 18. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| AI suggestions introduce unsupported claims | Display source evidence and require confirmation before acceptance. |
| An approval control has an unexpected effect | Use action-specific labels and preview the resulting wording. |
| The UI bypasses workflow safeguards | Enforce rules in the local service and cover them with tests. |
| Master changes during a session | Store and verify the master hash; require reconciliation. |
| Page fitting becomes automatic deletion | Present explicit line-level choices and require approval. |
| Accepted changes are hard to distinguish from suggestions | Update the tailored draft only after decisions and use distinct visual states. |
| The local server is exposed accidentally | Bind to localhost and require explicit secure configuration for remote access. |
| Existing repository changes are overwritten | Scope writes to the active tailored folder and show a final change summary. |
| Model integration relies on unsupported authentication assumptions | Resolve and prototype the model adapter in Phase 0. |
| The UI becomes a second factual source | Keep the master file canonical and store only decisions and confirmed facts in sessions. |

## 19. MVP implementation decisions

1. Completed entries remain expanded and can be filtered by decision state, preserving the full-resume review model.
2. Suggestions come from the active Codex task through registered workspace tools or the local command-line bridge. The web server does not run a second model or require a second API key.
3. Job requirements arrive with the complete initial suggestion set and remain visible as evidence throughout review; separate requirement approval is deferred.
4. **Other…** combines common actions with free-form wording, fact confirmation, and a focused request for a new AI suggestion.
5. Accepted decisions update deterministic session state immediately and invalidate the prior PDF. The user starts a new preview build when ready, avoiding overlapping builds.
6. The MVP creates new workspace sessions and does not import existing tailored folders.
7. The MVP ships with a one-command local launcher. Docker and native packaging remain optional hardening work.

## 20. Recommended initial implementation direction

Build a local browser interface backed by a small local service. The service is the only layer allowed to read or write repository files and wraps the existing parser, session ledger, build script, and validator.

Start with three product surfaces:

1. A read-only **My Resume** screen showing the existing master resume.
2. A **Tailor for a Job** intake screen for the company, role, and job description.
3. A three-region **Suggestion Review** screen showing the complete resume with every recommendation inline, centered on Approve suggestion, Keep current, and Other….

Do not build cover-letter, tracking, public hosting, or native macOS features until the complete resume workflow has been tested successfully in the web interface.
