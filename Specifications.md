# Contract Reviewer Web App — Specification (v1, "start simple")

Status: **built, then narrowed.** §§1–11 below (the risk-review flow) were approved and
implemented as `webconfig`/`webreview`, and one real end-to-end run went through the web UI
(produced a correct `Incomplete` report when OpenAI's account ran out of credits mid-run —
not a defect, the intended failure-handling behavior). **As of 2026-09-23, §14 supersedes
§§1–11 for the web app**: the risk-review UI (upload's "Start review" button, the progress/
report/PDF-download views and routes, the `tasks.py` review task) was removed from
`webconfig`/`webreview` at the user's explicit request, leaving the web app summary-only
(§12). §§1–11 are kept below unchanged as the historical record of what was built and why —
they no longer describe the live web app, but the risk-review pipeline they describe
(`contract_reviewer/graph.py` and everything under §3) is untouched and still fully
reachable via the CLI (`review.py`). See `CLAUDE.md`'s dated 2026-09-23 entry and
`ARCHITECTURE.md` §7 for the full picture.

## 1. Objective

Wrap the existing `contract_reviewer` pipeline (see `ARCHITECTURE.md`) in a Django web app
with the smallest feature set that's actually usable:

1. Upload a contract (PDF or Word).
2. Run it through the same agent pipeline that the CLI already runs.
3. Show progress while it runs (this takes minutes, not seconds).
4. Display the finished review as a formatted web page.
5. Download the review as a PDF via a button.

No accounts, no multi-tenancy, no contract database browsing/search UI, no skill editing UI
in this version — see §9 for what's explicitly deferred and why.

## 2. User flow

```
1. User opens the app -> upload form (file picker + optional client role / perspective fields)
2. User submits -> file is saved, a Review is created with status=pending, a background
   job is enqueued -> user is redirected to a progress page
3. Progress page polls a status endpoint every few seconds -> shows a progress bar and the
   current stage name (e.g. "Independent verification (cycle 1)")
4. When the job finishes:
     - report_status = Completed or Provisional -> page auto-refreshes to show the
       rendered report, with a "Download PDF" button
     - report_status = Incomplete -> page shows the incomplete reason and whatever partial
       report exists (same as the CLI's Incomplete path -- never a bare failure page)
5. "Download PDF" -> serves the PDF generated at completion time
```

## 3. Reuse of the existing pipeline

Per `ARCHITECTURE.md`, the entire `contract_reviewer` package (`graph.py`, every
`nodes/*.py`, `schemas.py`, `prompts.py`, `models.py`, `skills.py`, `pdf_report.py`, the two
Jinja templates) is reused **unchanged**. The Django app is a thin shell around it:

- A background task builds the same initial `ReviewState` dict the CLI builds in `cli.py`
  (source path, client role/perspective, run ID, max_cycles) and calls `graph.invoke(...)`
  or `graph.stream(...)` (see §6 for why `stream` is preferred here).
- The only *required* code change inside `contract_reviewer/` is replacing
  `runtime.py`'s global tier-config (`set_tiers`/`get_tiers`) with something request/task-safe
  — e.g. tiers resolved once per task and passed through LangGraph's existing
  `config={"configurable": {...}}` dict instead of a module global. Everything else in
  `ARCHITECTURE.md`'s reuse table applies as documented there.
- **New, not yet built:** Word document support. Today `pdf_extract.py` only handles PDF.
  Add a small `contract_reviewer/docx_extract.py` (using `python-docx`) returning the same
  shape as `pdf_extract.extract_pdf()` (`{ok, text, pages, warnings, scanned_pages}` — pages
  can just be `[{page_no: 1, text: ...}]` for a single logical unit if `.docx` doesn't have a
  clean page concept), and a small dispatcher (`extract_document(path)`) that picks the
  extractor by file extension. `intake_node` calls the dispatcher instead of `extract_pdf`
  directly.

## 4. Data model

Adapts `Contracts Database Plan.md`, filling the gaps `ARCHITECTURE.md` §6/§7 already flagged
(verification ledger, run history, separate execution/report status). Field lists, not DDL —
Django migrations generate the actual schema.

| Model | Key fields | Notes |
|---|---|---|
| `Contract` | `title`, `contract_type`, `client_role`, `created_at` | One row per matter. `contract_type` is filled in from the routing record once classification runs, not chosen by the user at upload. |
| `ContractDocument` | `contract` FK, `version_number`, `original_filename`, `file_extension`, `file` (FileField), `file_hash_sha256`, `is_current`, `extraction_status`, `extraction_error` | Immutable once uploaded — a re-upload creates a new version row, never overwrites. Mirrors the plan's `contract_documents` table. |
| `Review` | `contract` FK, `document` FK, `run_id`, `client_perspective`, `research_date`, `max_cycles`, `execution_status`, `report_status`, `commercial_recommendation`, `correction_cycle`, `current_stage_label`, `progress_percent`, `report_markdown`, `report_context` (JSONField), `report_pdf` (FileField), `incomplete_reason`, `created_at`, `started_at`, `completed_at` | **`execution_status`** (pending/running/succeeded/failed) and **`report_status`** (Completed/Provisional/Incomplete) are separate fields — do not collapse them, per the workflow's explicit rule. `report_context` is stored so the PDF (or a re-styled HTML view) can be regenerated later without re-running the LLM pipeline. |
| `Finding` | `review` FK, `finding_id` (`F001`…), `severity`, `confidence`, `clause_reference`, `clause_text`, `trigger_scenario`, `consequence`, `legal_proposition`, `recommended_amendment`, `fallback_position`, `residual_risk`, `status` | Matches `schemas.Finding` field-for-field. |
| `Authority` | `review` FK, `authority_id` (`A001`…), `authority_type`, `title`, `citation`, `url`, `pinpoint`, `application_notes` | Matches `schemas.Authority`. |
| `VerificationRecord` | `finding` FK, `authority` FK, `proposition_checked`, `status` (Verified/Qualified/Unsupported/Unverified), `identity_check`, `text_check`, `attribution_check`, `proposition_check`, `treatment_check`, `application_check`, `caveats` | The verification ledger `Contracts Database Plan.md` didn't have and the handover flagged as gap #2 — one row per finding–authority–proposition, never deduped to one per authority. |
| `RunEvent` | `review` FK, `stage`, `role`, `tier`, `provider`, `model`, `effort_actual`, `occurred_at`, `detail` | Satisfies handover gap #3 (run/agent history). One row per `ModelAssignment` plus one per stage transition/error — this is what the progress bar and the final report's "Model / Role Assignments" table both read from. |

## 5. File upload

- Accepted types: `.pdf`, `.docx` (matching the stated requirement; `.doc` legacy format is
  out of scope, same as the original database plan).
- Validate extension + MIME type + a reasonable size cap (e.g. 20 MB) before saving.
- Compute SHA-256 on upload, same as the CLI's `pdf_extract.sha256_file`.
- Store the original file via Django's default `FileField`/`MEDIA_ROOT` for v1 (local disk).
  Object storage (S3-compatible) is a later, purely-configuration change via
  `django-storages` — don't build for it now.

## 6. Background execution and progress

**The review cannot run inside the request/response cycle** — a single run makes many
Flagship-tier + Tavily calls across multiple stages and reliably takes minutes. This is not
optional to design around.

**Recommended: `django-q2`**, using its Django-ORM broker (no Redis, no extra service to
run) rather than Celery. It gives a real task queue — retries, a monitorable task table,
survives the dev server autoreloader — while staying inside "start simple": one more
`INSTALLED_APP`, one more `manage.py qcluster` process, no new infrastructure.
**Alternative:** Celery + Redis, the more common production pattern and a natural upgrade if
this later needs multiple worker machines or task routing/priority — recommended as the
Phase 3 move if/when `django-q2` stops being enough, not as the v1 starting point.

**Progress tracking:** call `graph.stream(initial_state, config)` instead of `graph.invoke(...)`.
`stream()` yields the state after every completed node (superstep), which is exactly the
granularity needed to update `Review.current_stage_label` and `Review.progress_percent` as
the run proceeds — no LangGraph-internal changes needed. A fixed, human-readable label per
node name (`intake` → "Reading document", `classify` → "Classifying contract type", `review`
→ "Legal review (cycle N)", `verify`/`factual_check` → "Independent verification (cycle N)",
`reconcile` → "Reconciling findings", `assemble`/`write_report` → "Assembling report") plus a
simple weighted-stage percentage (correction cycles compress the remaining range
proportionally, since the total cycle count isn't known in advance) is enough for a v1
progress bar — no need for token-level or sub-stage granularity.

**Progress page mechanics:** the progress page polls `GET /reviews/<id>/status/` (returns
`{execution_status, current_stage_label, progress_percent}` as JSON) every 2–3 seconds via
plain `fetch()` and updates a CSS progress bar. No WebSockets/Django Channels needed for v1;
that's a reasonable later upgrade for push-based updates, not a requirement now.

## 7. Report display

- Store the pipeline's `final_markdown` output on `Review.report_markdown` verbatim (already
  produced by `nodes/report.py`, unchanged).
- Render it to HTML at display time with Python-Markdown (`markdown` package, `tables` and
  `fenced_code` extensions for the report's tables) inside a Django template.
- Style it with a dedicated stylesheet reusing the visual language already designed for the
  PDF template (`report.pdf.html.jinja`'s severity badges, status badge, table styling) so
  the web view and the downloaded PDF look like the same document, not two different products.
- The 8-section structure and validation already done by `write_report_node` (heading
  presence/order, no duplicate IDs, cross-references resolve) is a Markdown-file guarantee
  that carries over unchanged to what gets displayed — no extra validation needed here.

## 8. PDF download

- Generate the PDF once, at pipeline-completion time (same `pdf_report.render_pdf(report_context)`
  call the CLI already makes), and store the bytes on `Review.report_pdf` (FileField).
- `GET /reviews/<id>/download/pdf/` streams that stored file back with a
  `Content-Disposition: attachment` header — no regeneration on click, so the button is fast
  and the exact document that was produced during the run is what gets downloaded.
- If PDF generation failed at completion time (mirrors the CLI's existing behavior of
  logging a warning without downgrading `report_status`), the download button is simply
  hidden/disabled and the page explains the PDF isn't available, rather than a broken link.

## 9. Explicitly out of scope for v1 (and why)

| Deferred | Why |
|---|---|
| User accounts / auth | Single-user/local use for now; `TECHNICAL HANDOVER.md` already says add auth "before using the app with confidential contracts" through any exposed deployment — do this before anyone but you uses it, not before that. |
| Multi-tenancy / per-user contract lists | No `User` model relationship exists yet; every `Contract`/`Review` is globally visible. Fine for one person, not fine to share. |
| Contract list/search/history browsing UI | Only today's upload → progress → result flow. A "past reviews" list is a small, obvious follow-up once this works. |
| Editing skills (`Contract Skills/*.md`) from the web UI | Skills stay file-based and are still loaded verbatim by `skills.py`, same as the CLI. Moving them into the DB is a distinct, larger change (`ARCHITECTURE.md` §7, point 5). |
| Celery/Redis, WebSockets/Channels | Named above as the natural upgrades once `django-q2`/polling stop being enough — not needed to ship v1. |
| Re-running/editing a finding after the fact | The CLI doesn't support this either; `Finding.status` exists in the schema for future use but nothing in v1 writes to it after the run completes. |
| `.doc` (legacy binary Word format) | Matches the original database plan's stated scope; `.docx` and `.pdf` only. |

## 10. Suggested build order

1. Django project skeleton + the models in §4 + migrations.
2. Upload view + form (PDF/Word validation, hashing, `ContractDocument` creation) — no
   pipeline wiring yet, just prove upload/storage works.
3. `docx_extract.py` + the extension dispatcher (§3) — needed before wiring the pipeline in,
   since intake must handle both file types from day one per the stated requirement.
4. `django-q2` wired up; a task function that builds `ReviewState` and calls `graph.stream(...)`,
   writing `RunEvent` rows and updating `Review.current_stage_label`/`progress_percent` as it goes.
5. Progress page + status JSON endpoint + polling JS.
6. Report display page (Markdown → styled HTML) + PDF download view.
7. Wire the `runtime.py` tier-config fix (§3) before this goes anywhere near concurrent use —
   don't skip it just because it "works" with one review running at a time in dev.

## 11. Confirmed decisions

- **Database engine: SQLite.** Confirmed. Fine for local, single-user use; the trigger to
  move to Postgres is concurrent access (multiple simultaneous reviews, or once §6's
  background worker and the Django web process are routinely hitting the DB at the same
  time under real load), not a fixed timeline.
- **Hosting: deployed to PythonAnywhere, 2026-09-23.** The two constraints below (outbound
  internet, Always-on tasks) were exactly right and both required a paid plan — the account
  used is a paid Hacker-or-above plan, and the deployment is live at
  `https://ngwaichung.pythonanywhere.com/` with a first real production summary run already
  succeeded end-to-end. See `CLAUDE.md`'s "Production deployment (PythonAnywhere)" section
  for the concrete paths/commands/redeploy steps; kept below as the original reasoning for
  why a paid plan was necessary, not just a preference:
  - **Outbound internet access is restricted on PythonAnywhere's free/lower tiers** — only a
    whitelisted set of sites is reachable without a paid plan. The pipeline calls
    api.anthropic.com / api.openai.com / openrouter.ai / api.tavily.com directly, none of
    which are on the free whitelist, so a paid PythonAnywhere plan (their "Hacker" tier or
    above, which lifts the restriction) would be required — not just for running the
    website, but for the pipeline to reach any of its providers at all.
  - **A persistent `django-q2` cluster process needs PythonAnywhere's "Always-on task"
    feature**, which is also a paid-tier feature (their free/lower tiers only offer
    scheduled/cron-style tasks with a minimum interval, not a continuously-running worker
    process). This doesn't change the §6 recommendation — `django-q2` still applies, and
    still avoids needing a separate Redis service. In production this runs
    `manage.py qcluster` as an Always-on task; forgetting to set this up (or forgetting to
    restart it after a code change to `tasks.py`) reproduces the exact "stuck at pending"
    failure mode §13 was built to detect locally, just on the server.
  - **One real deployment-only issue neither point anticipated**: `requirements.txt` left
    `django` unpinned, so PythonAnywhere's `pip install` resolved the latest release (6.1.1)
    instead of the 5.2.17 this app was actually built and tested against — an untested
    major-version jump. Fixed by pinning `django==5.2.17`. Worth remembering for every other
    unpinned dependency in that file if a future redeploy ever behaves differently from local.

---

## 12. Addendum: Contract Summary in the web app

Status: **built and confirmed working with a real live run.** Implemented exactly as
planned below, with one small addition found necessary during implementation:
`contract_reviewer.summarize.run_summary()` gained an optional `on_stage` callback parameter
(called with `"extracting"` then `"summarizing"`) so `run_summary_task` can report the
two-stage progress described in §12.3 without duplicating the pipeline logic -- the CLI
ignores the parameter entirely. Verified twice: first structurally through the actual
running server using simulated task completion (no API cost), then for real -- a genuine
employment agreement uploaded through the browser, summarised successfully end-to-end
(`execution_status=succeeded`, PDF generated), correctly surfacing a real drafting detail
(the employee's name left blank in the executed schedule). Adds a "Summarise" path alongside
the existing risk-review path, reusing `contract_reviewer/summarize.py` (already built and
verified for the CLI -- see `summary.md`) the same way §3 reuses `graph.py` for review.

That live run also surfaced one new fidelity-check false positive, not yet fixed: the source
used `$3,200` (no `S` prefix) for a second figure after establishing `S$3,000` earlier; the
model normalised it to `S$3,200`, which is reasonable but broke the exact-prefix match in
`_fidelity_issues()`. See `summary.md` for the fix (compare digits only, ignore `S$`/`$`).

### 12.1 Objective

From the same upload page, let the user choose **Review** (existing flow) or **Summarise**
(new): upload → background task runs `contract_reviewer.summarize.run_summary()` → a
progress indicator → the finished summary displayed as a formatted web page → a **Download
PDF** button. Unlike the CLI's `summarise.py` (which writes a Word document), the web
version's download is a **PDF** — a new renderer, not the existing `docx_report.py`.

### 12.2 Reuse vs. new pieces

Reused as-is: `ContractUploadForm`, upload validation/hashing, `Contract`/`ContractDocument`
creation, the `django-q2` background-task mechanism, and the progress-polling JS pattern
already proven in `progress.html`. `contract_reviewer.summarize.run_summary()` itself is
reused unchanged — it already returns everything needed (`summary`, `fidelity_issues`,
`model_assignment`, `source_sha256`).

**Recommended: generalize `progress.html`** to take its status/report URLs as template
variables instead of hardcoding `webreview:status`/`webreview:report` for a `Review`, so the
exact same template serves both the review and summary progress pages rather than
duplicating it.

New pieces:

| New piece | Purpose |
|---|---|
| `Summary` model (`webreview/models.py`) | A **separate** model from `Review`, not a shared one with a `kind` discriminator — a summary has no findings/authorities/severity/`report_status`/correction cycle, so forcing it into `Review`'s shape would mean a table full of always-null review-only columns. Fields: `contract` FK, `document` FK, `run_id`, `execution_status` (pending/running/succeeded/failed — same states as `Review`, same meaning), `current_stage_label`, `progress_percent`, `summary_context` (JSONField — the `ContractSummary` data plus rendering context, stored the same way `Review.report_context` is, so the PDF can be regenerated later without re-running the LLM call), `summary_pdf` (FileField), `fidelity_issues` (JSONField list), `incomplete_reason`, `created_at`/`started_at`/`completed_at`. |
| `contract_reviewer/summary_pdf_report.py` (new, alongside `docx_report.py`) | `render_pdf(summary, context) -> bytes` — the same Jinja2 → `xhtml2pdf` approach as `pdf_report.py`, via a new `templates/summary.pdf.html.jinja` styled identically to `report.pdf.html.jinja` (navy headings, same table/badge language) so every PDF this app produces looks like one product. Renders the same sections `docx_report.py` already defines (Snapshot, Subject Matter, Obligations by Party, Payment Terms, Key Dates, Termination, Liability Snapshot, IP/Confidentiality, Notable/Unusual Terms, Missing Information, Data Fidelity Notices) — same content, different output format. |
| `webreview/templates/webreview/summary_report.html` | On-page HTML display. Renders directly from the stored `summary_context` dict via Django template tags (loops over `parties`, `obligations_by_party`, `key_dates`, etc.) — no Markdown intermediate step needed here, unlike the review report, since a `ContractSummary` is already structured data, not prose. |
| `webreview/tasks.py::run_summary_task(summary_id)` | Mirrors `run_review`'s structure but simpler: no `graph.stream()` loop (there's no graph — see `summary.md` §2), just two stage updates ("Reading document" during extraction, "Summarising" during the LLM call) around the single call to `run_summary()`. On success: render the PDF, save `summary_pdf`, set `execution_status="succeeded"`. On an unreadable/empty document: `execution_status="succeeded"` still (the task itself completed), but `incomplete_reason` set and no PDF — mirrors the review flow's execution-status-vs-content-status separation. |
| `webreview/views.py` | `summary_progress_view`, `summary_status_view` (JSON), `summary_report_view` (HTML), `summary_download_pdf_view` — one-to-one with the existing `Review` views, operating on `Summary` instead. |
| `webreview/urls.py` | `/summaries/<id>/`, `/summaries/<id>/status/`, `/summaries/<id>/report/`, `/summaries/<id>/download/pdf/`. |
| `upload.html` | A second submit button, `<button type="submit" name="action" value="summarise">Summarise</button>` alongside the existing `<button type="submit" name="action" value="review">Start review</button>` — one form, one upload view, branching on `request.POST.get("action")` after the shared `Contract`/`ContractDocument` creation, so upload validation/hashing logic is written exactly once. |

### 12.3 User flow

```
1. Same upload page as before, now with two buttons: "Start review" and "Summarise"
2. User picks Summarise -> same upload/validation/Contract+ContractDocument creation as
   the review path -> a Summary row is created (execution_status=pending) -> async_task
   enqueues run_summary_task -> redirect to the summary progress page
3. Progress page (the same generalized template as review) polls its status endpoint ->
   two stages only: "Reading document" then "Summarising" -> no correction-cycle concept
4. On completion -> redirect to the summary report page: Snapshot table, Subject Matter,
   Obligations by Party, Payment Terms, Key Dates, Termination, Liability Snapshot,
   IP/Confidentiality (if present), Notable/Unusual Terms, Missing Information, and any
   Data Fidelity Notices -- same sections as the CLI's Word output, same content, styled
   for the web. A "Download PDF" button sits at the top, same placement as the review page.
5. "Download PDF" -> serves the PDF generated at completion time (not regenerated on click,
   same reasoning as §8 for reviews)
```

### 12.4 Design decisions

- **PDF only on the web, not Word.** The CLI keeps producing `.docx` (already built); the
  web app produces PDF only, per the explicit ask. Both are rendered from the same
  `ContractSummary` + context, so adding a Word download to the web later (or a PDF option
  to the CLI) is a small, independent addition to either side, not a redesign.
- **Separate `Summary` model, not `Review` + a `kind` field.** Named explicitly here because
  it's the opposite of how `Contract`/`ContractDocument` are shared unchanged — those two
  really are identical concepts for both flows; `Review` and a contract summary are not.
- **Two-stage progress, not a percentage bar with many steps.** There's no multi-stage graph
  or correction loop to report on (`summary.md` §2); a simple "Reading document" →
  "Summarising" → done sequence is proportionate and honest about what's actually happening.
- **One upload form, two submit buttons**, not two separate upload pages — the upload
  mechanics are identical; only the downstream task differs. Say if you'd rather have two
  distinct pages/URLs instead (e.g. `/` for review, `/summarise/` for summary) — this is a
  cheap change either way, decide before building rather than after.

### 12.5 Suggested build order

1. `Summary` model + migration.
2. `summary_pdf_report.py` + `summary.pdf.html.jinja` — verify locally by rendering from a
   `ContractSummary` built from data already captured during the CLI's earlier verification
   runs (no new API cost, same technique used to iterate on `report.pdf.html.jinja` and
   `docx_report.py` earlier in this project).
3. `webreview/tasks.py::run_summary_task`.
4. Generalize `progress.html` (status/report URLs as template variables); views + URLs.
5. `summary_report.html` + the second upload button.
6. End-to-end run through the browser, on request (real API cost, confirm before running,
   same as every other paid test in this project).

---

## 13. Addendum: stall detection on the progress pages

Status: **built.** Prompted directly by the two real "it's not doing anything" incidents in
`CLAUDE.md`'s process-hygiene notes — both times the actual cause (no `qcluster` running) was
invisible from the progress page itself; the page just polled forever showing "Starting...".

**Design:** computed live from timestamps on every status poll, never stored, so a fix (e.g.
starting `qcluster`) is reflected on the very next poll with nothing to reset. Two distinct
cases, both surfaced as a warning banner rather than a hard failure (polling continues,
since either can resolve on its own):

- **Stuck `pending`**: never picked up by a worker at all. Threshold 30s — generous for a
  poll-based queue, but this is overwhelmingly the case that's actually occurred in practice.
- **Stuck `running`**: a worker claimed it but produced no progress update for far longer
  than that stage should take. Different thresholds per pipeline, since their normal
  durations are wildly different: 300s for review (Flagship-tier + Tavily stages can
  legitimately take minutes), 120s for the summariser (a single call, normally under a minute).

**New/changed pieces:**
- `Review`/`Summary` gained an `updated_at` field (`auto_now=True`) as the "last heard from"
  clock for the running case. **Caveat that cost real debugging time to get right**: Django
  does not refresh `auto_now` fields on `save(update_fields=[...])` unless the field is
  explicitly listed in `update_fields` — every progress-saving call in `tasks.py` needed
  `"updated_at"` added to its `update_fields` list, or the field would silently never update.
- `webreview/stall.py`: `check_stall(execution_status, created_at, updated_at, threshold) ->
  (stalled, reason)`, shared by both status views.
- `status_view`/`summary_status_view` JSON responses gained `stalled`/`stall_reason`.
- `progress.html`'s polling JS shows/hides an amber warning banner based on `data.stalled`,
  independent of the existing hard-failure (`execution_status == "failed"`) handling.

**Verified**: unit-level (all 5 branches: fresh pending, stale pending, stale running under
the summary threshold, not-stale running under the review threshold, never-stalled once
succeeded) and through a real HTTP request against the running server with a deliberately
backdated row, confirming the JSON and the rendered page both carry the warning correctly.

---

## 14. Addendum: risk-review functionality removed from the web app; logging added

Status: **built.** Explicit user request: *"I want to remove the review button and all
review functionality. I just want the web page to perform contract summaries. I also
[if] possible, come up with logging capabilities so that future troubleshooting is
smoother."* Scope is the web app only — `review.py` and `contract_reviewer/graph.py` (and
every `nodes/*.py`) are unaffected and still fully functional from the CLI; this section
only changes what `webconfig`/`webreview` expose.

### 14.1 What was removed

- `webreview/templates/webreview/upload.html`: the "Start review" button. The page now has a
  single "Summarise" submit button, and the `action` POST field the two buttons used to
  distinguish is gone — every upload creates a `Summary`.
- `webreview/views.py`: `progress_view`, `status_view`, `report_view`, `download_pdf_view`
  (all review-specific). `upload_view` no longer branches on `request.POST.get("action")`.
- `webreview/urls.py`: the four `reviews/<int:review_id>/...` routes.
- `webreview/tasks.py`: `run_review`, `_execute`, `_persist_results`, and the
  `_STAGE_LABELS`/`_STAGE_PROGRESS` maps. Only `run_summary_task`/`_execute_summary` remain.
- `webreview/templates/webreview/report.html`: deleted outright rather than left in place —
  with `download_pdf_view` gone, its `{% url 'webreview:download_pdf' ... %}` reference would
  raise `NoReverseMatch` if anything ever rendered it, and nothing does anymore.
- `webreview/forms.py`: the `client_perspective` field — it only ever fed `Review.
  client_perspective`; the summariser never read it.
- `webreview/stall.py`: the now-unused `RUNNING_STALL_SECONDS_REVIEW` threshold
  (`RUNNING_STALL_SECONDS_SUMMARY` is unaffected — the summary status check is all that's
  left calling `check_stall()`).

### 14.2 What was deliberately kept

- The `Review`, `Finding`, `Authority`, `VerificationRecord`, `RunEvent` Django models, their
  DB tables, and their `admin.py` registrations. No destructive migration was run — dropping
  them would have deleted the one real historical review row from before this change for no
  functional benefit, and keeping them means a future web review UI is additive (new views/
  URLs/templates against an already-correct schema), not a rebuild.
- `Q_CLUSTER`'s `timeout`/`retry` in `webconfig/settings.py` were trimmed from `3600`/`3700`
  to `600`/`700` — those values existed specifically because review runs (Flagship-tier +
  Tavily, correction cycles) could legitimately take 10+ minutes; with only the summariser
  left in the web app's task queue (normally well under a minute — see §12.4), the old
  timeout no longer matched anything the web app actually does.

### 14.3 Logging (new capability, same change)

Motivated directly by the repeated real "qcluster isn't running, the progress page looks
stalled" incidents (§13's motivation) — those were always diagnosable, but only by manually
querying `django_q.models.OrmQ`/`Success`/`Failure` via `manage.py shell`, with no log file
to just read. `webconfig/settings.py` gained a `LOGGING` dict (Django's `dictConfig` format,
`disable_existing_loggers: False`):

- A `RotatingFileHandler` writing to `logs/webreview.log` (5 MB × 5 backups), plus a
  `StreamHandler` so the same lines still show up on the console.
- Two logger entries: `webreview` (new — everything in `tasks.py`/`views.py`) and
  `contract_reviewer` (the engine's existing `logging.getLogger("contract_reviewer")`,
  previously only ever captured by the CLI's `logging_setup.configure_logging()` — the web
  app never called it, so engine-level log lines from a web-triggered summary run went
  nowhere before this change).
- Deliberately **additive only**: neither `"django"` nor Django's own `"console"` handler
  name is touched, so Django's default request logging and any future use of its own
  logging config is unaffected by this change.

`webreview/tasks.py` now logs: task start (with document filename), each `on_stage`
transition, extraction failure (`WARNING`), success, PDF-render failure, and any unhandled
exception (`logger.exception()`, full traceback). `webreview/views.py` logs: a received
upload (contract/document IDs, file size) and form-validation failures (`WARNING`, with the
field errors). `logs/` was added to `.gitignore`, consistent with `media/`/`db.sqlite3`.

**Verified**: `manage.py check` passes; a live run of `run_dev.py` confirmed the upload page
renders summary-only with no "Start review" button; an intentionally invalid form submission
(no file attached) produced a correctly formatted `WARNING` line in `logs/webreview.log`
(timestamp, level, logger name, message). A full paid summary run through the web UI (to see
the complete task-lifecycle log sequence end-to-end) was intentionally not performed as part
of this change, per the project's standing rule not to spend API budget without asking first.
