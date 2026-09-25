# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Owner and house rules (read first)

Owner: Chris (Christopher Ng Wai Chung). Singapore-based investment trainer, adjunct law
lecturer at Temasek Polytechnic, admitted to the Singapore Bar (2018), CFA, former IT
governance and infrastructure professional. He is the legal domain expert on this project:
defer to him on the legal substance in `Workflow/SKILL.md` and `Contract Skills/*.md`, and
flag (don't silently change) anything in those files that looks legally wrong.

Reference files in `claude-context/` (copied from his personal setup; edit them there):

- @claude-context/profile-and-voice.md: bio, working style, brand voice.
- @claude-context/ANTI-AI-STYLE.md: pre-output filter for all prose. No em dashes.
- @claude-context/pragmatic-programmer-refactor-guide.md: rules for any code change.
- @claude-context/design.md: Tree of Prosperity visual brand.

If `@` imports don't expand in a session, read the relevant file before starting.

How they apply to this repo:

| Work | Apply | Notes |
|---|---|---|
| Replies to Chris, commit messages, new doc text | Voice + ANTI-AI-STYLE | Conclusion first, then reasoning. State assumptions. No em dashes in new text. Don't mass-rewrite existing docs (`ARCHITECTURE.md`, `Specifications.md`, this file) just to remove em dashes; that is churn. |
| User-facing web copy (`webreview/templates/`) and generated summary prose | Voice + ANTI-AI-STYLE, legal-writing rules | Changing what the summariser writes means changing `Contract Skills/Contract Summary.md` or `prompts.py`: ask Chris first, since those are runtime instructions. |
| Code changes | Refactor guide | Behaviour must not change in a refactor. There is no pytest suite, so write a characterisation check in `tests/` before refactoring untested code. Adding pytest or any new dependency is a separate decision: ask first. Never mix refactor and behaviour change in one commit. |
| Web UI and PDF styling | `design.md` | The live UI does not use the brand yet: `report.css` and the PDF Jinja templates use a navy `#1a2b4c` / Helvetica scheme. Don't restyle unless asked. If restyling, change `report.css` and `summary.pdf.html.jinja` together (they are meant to match), and note that xhtml2pdf cannot fetch Google Fonts: Fraunces/Inter need local TTFs via `@font-face`. |
| Explaining code or errors | Profile working style | Plain English, runnable commands, say what the error means and the immediate fix. |

Not relevant here (they live in his personal setup, not this repo): the StocksCafe trade-import
workflow and the Obsidian Second Brain vault.

## Project state

**Phase 1 (current): a working Python CLI.** `review.py` runs the full `Workflow/SKILL.md`
orchestration end-to-end with real agentic LLM calls (LangGraph + LangChain) and produces a
Markdown report (`Reviews/`) and a matching PDF (`Reports/`). This has been run successfully
end-to-end against real contract text, including the full correction-cycle loop.

**Phase 2 (current): a Django web app (`webconfig`/`webreview`), built per `Specifications.md`.**
Originally wrapped both the risk-review pipeline and the summariser; **as of 2026-09-23 the
web app is summary-only** (see the dated entry below) — upload a PDF/Word contract → a
`django-q2` background task runs `contract_reviewer.summarize.run_summary()` → a progress bar
polls a status endpoint → the finished summary renders as styled HTML with a PDF download
button. The risk-review pipeline (`graph.stream()`, the styled-report-with-PDF flow) is still
fully intact and reachable via the CLI (`review.py`) — only its web-app wiring was removed.
One real end-to-end review run went through the web UI before removal: it produced a correct
`Incomplete` report (OpenAI ran out of credits mid-run at the `classify` stage) — a billing
issue, not a code defect, and it confirmed the guard/Incomplete-path logic worked for real
under the web app, not just the CLI. `ARCHITECTURE.md` documents, module by module, what
`contract_reviewer/` code was reused unchanged vs. adapted; `Specifications.md` is the
feature spec this app was originally built against — **read both before making structural
changes** to either the engine package or the Django app, and read the dated entry below
before assuming §§1–11 of `Specifications.md` still describe the live web app.

**Current status (as of 2026-09-23):** `models.yaml` defaults to Anthropic (switched back
from OpenAI after OpenAI's credits ran out). The web app's risk-review UI has since been
removed (see below), so no further review runs are expected through the web UI — `review.py`
is still the way to run a risk review. The **summariser** has had a real, fully successful
web-UI run (see directly above) and is now the web app's only pipeline. Testing continues in
the next session; nothing is mid-run or left in an inconsistent state.

**`summarise.py` (new, separate program): a plain-English contract summariser.** Takes a
PDF/`.docx`/`.md` contract, runs the `Contract Skills/Contract Summary.md` skill (a `kind:
task` skill, deliberately excluded from the risk-review classifier) through one Balanced-tier
structured LLM call, and writes a formatted Word document to `Summary/`. Deliberately a plain
linear pipeline (`contract_reviewer/summarize.py`), not a LangGraph graph — no branching, no
correction loop, so no graph is needed (see `summary.md` §2). Verified end-to-end with real
API calls; a real deterministic-substring fidelity check (`_fidelity_issues()`) went through
three real false-positive bugs during verification (composite descriptive sentences,
PDF-extraction line-wraps, word-order paraphrasing) — all fixed by extracting concrete
money/date/duration tokens and normalizing whitespace before comparing, rather than checking
whole fields verbatim.

**Contract Summary is now also in the web app** (`Specifications.md` §12): a second
"Summarise" button on the upload page, alongside "Start review". Separate `Summary` Django
model (not `Review` + a discriminator — a summary has none of `Review`'s findings/
authorities/severity concepts), separate `webreview/tasks.py::run_summary_task` (two-stage
progress via `run_summary()`'s new `on_stage` callback, no graph), and a new
`contract_reviewer/summary_pdf_report.py` for the web's PDF download — the CLI's
`summarise.py` still produces Word via `docx_report.py`; both render from the same
`ContractSummary` data. `progress.html` was generalized (status/report URLs as template
variables) so both flows share it.

**First real, fully successful live run through the web UI happened here** (a real
employment agreement, "Sample Contract.pdf" — not a synthetic fixture): `execution_status`
`succeeded`, 100%, PDF generated, correctly identified an unusual real detail (the employee's
name left blank in the executed schedule). This is the first time anything in the web app has
gone all the way to a clean success against real content, not just structurally or with a
billing failure.

It also surfaced a **new, understood fidelity-check false-positive class**, not yet fixed
(deliberately left for the next session — see summary.md's fidelity-check history for the
three earlier ones already fixed): the source document uses `$3,200` (no `S` prefix) for a
second figure after already establishing `S$3,000` earlier; the model reasonably normalized
it to `S$3,200` for consistency, but `_fidelity_issues()`'s money regex requires the exact
`S?\$` prefix it extracted to appear in the source, so the normalization itself trips the
check. A currency-prefix-insensitive comparison (compare digits only, ignore `S$` vs `$`)
would fix this specific case. The same run also flagged two purely-descriptive `term_duration`
sentences (no fixed term stated, expressed in prose) — those are the already-known "whole-
string fallback" limitation for fields with no extractable money/date/duration token, not a
new bug.

**Progress pages now detect and surface a stalled run** (`Specifications.md` §13), prompted
directly by the two "it's not doing anything" incidents above: `Review`/`Summary` gained an
`updated_at` (`auto_now=True`) field, and `webreview/stall.py::check_stall()` computes live
(never stored) whether a row has been `pending` too long (no worker ever picked it up — the
actual cause both times so far) or `running` with no progress update for far longer than
that stage should take. Surfaced as an amber warning banner on the progress page, polling
continues (it's not a hard failure). **Real gotcha hit while building this**: Django does not
refresh an `auto_now` field on `save(update_fields=[...])` unless it's explicitly listed —
every progress-saving call in `tasks.py` needed `"updated_at"` added, or the whole feature
would have silently done nothing.

**(2026-09-23) Risk-review functionality removed from the web app; the web app is now
summary-only.** Explicit user request: "I want to remove the review button and all review
functionality. I just want the web page to perform contract summaries." Scope was the web
app only — `review.py`, `contract_reviewer/graph.py`, and every `nodes/*.py` are untouched
and still fully functional from the CLI. Removed: the "Start review" button (`upload.html`),
`progress_view`/`status_view`/`report_view`/`download_pdf_view` and the now-broken
`report.html` template that referenced them, the `reviews/...` URL routes, `run_review`/
`_execute`/`_persist_results` and the stage-label maps in `tasks.py`, the `client_perspective`
form field (review-only, never read by the summariser), and the now-unused
`RUNNING_STALL_SECONDS_REVIEW` threshold in `stall.py`. `upload_view` no longer branches on
an `action` POST field — every upload now creates a `Summary`. **Deliberately left in place,
dormant rather than dropped**: the `Review`/`Finding`/`Authority`/`VerificationRecord`/
`RunEvent` Django models, their DB tables (including the one real historical review row from
before removal), and their `admin.py` registrations — no destructive migration was run, so
re-adding a web review UI later is additive, not a rebuild. `Q_CLUSTER`'s `timeout`/`retry`
(`webconfig/settings.py`) were also trimmed from 3600/3700 to 600/700, since the only
remaining web pipeline (the summariser) never approaches review-length runtimes.

**Same change added logging** — directly motivated by the repeated "qcluster isn't running,
why does this look stalled" incidents documented above, which had no persistent log trail to
diagnose from. `webconfig/settings.py` gained a `LOGGING` dict: a rotating file handler
(`logs/webreview.log`, 5 MB × 5 backups) plus console output, wired to two logger names —
`webreview` (new) and `contract_reviewer` (the engine's existing logger, previously only
captured by the CLI's `logging_setup.configure_logging()`, never by the web app). It's
additive only — it does not touch Django's own `"django"`/`"console"` handler config, so
Django's default request logging is unaffected. `webreview/tasks.py` and `webreview/views.py`
now log upload receipt, form-validation failures, task start, each stage transition, success,
extraction failure, PDF-render failure, and unhandled exceptions (`logger.exception()`, full
traceback). `logs/` is gitignored, same as `media/`/`db.sqlite3`. Verified live: an
intentionally invalid upload produced a correctly formatted `WARNING` line in
`logs/webreview.log`.

**(2026-09-23) Deployed to PythonAnywhere — first real production run succeeded.** The
summary-only web app is now live at `https://ngwaichung.pythonanywhere.com/` (account
`NgWaiChung`, a paid Hacker-or-above plan — required, since the free tier's outbound-internet
whitelist doesn't include `api.anthropic.com` and it has no Always-on tasks). Full details in
a new **## Production deployment (PythonAnywhere)** section below; summary of what changed to
get there:
- `webconfig/settings.py`: `DEBUG`/`ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` became
  environment-driven (`DEBUG` now defaults to `False` — local dev sets `DEBUG=True` in
  `.env`), `STATIC_ROOT` added for `collectstatic`, and `SESSION_COOKIE_SECURE`/
  `CSRF_COOKIE_SECURE`/`SECURE_SSL_REDIRECT` are forced whenever `DEBUG` is off.
- `requirements.txt`: `django` was unpinned, so PythonAnywhere's first install silently
  resolved the latest **6.1.1** instead of the **5.2.17** this app is actually tested
  against — pinned to `django==5.2.17` to guarantee dev/prod parity.
- **Real, non-code PythonAnywhere quirk hit during setup**: a virtualenv built from
  `/usr/bin/python3.11` produced a broken standard-library copy (`ModuleNotFoundError: No
  module named '_posixsubprocess'`) even though bare `/usr/bin/python3.11` worked fine
  standalone — a broken 3.11 image on that account, not anything this project did. Worked
  around by using Python **3.12** for the production virtualenv instead; nothing in this
  codebase actually requires exactly 3.11 (that pin was only ever about local wheel
  availability — see Commands below).
- First real production run: a genuine employment agreement uploaded through the live URL,
  summarised successfully end-to-end, correctly surfacing the same blank-employee-name detail
  the local test run found — confirming the deployed app, not just the local one, produces
  correct output against real content.

**(2026-09-25) qcluster auto-recovery for local dev, plus a real process-kill mistake worth
recording.** The "qcluster isn't running" incident (documented above) recurred a third time
today: four stray `runserver` processes were running with no `qcluster` at all, leaving a
`Summary` stuck at `pending`. While cleaning up the stray processes, PowerShell's default
table formatting truncated a `CommandLine` column mid-string ("...manage.py..."), and a
process that was actually the venv-stub half of a running `qcluster` (the same cosmetic quirk
described above under `run_dev.py`) got killed by mistake, based on an assumption rather than
a confirmed command line. Lesson: always confirm a full, untruncated command line
(`Format-List`, or query by exact PID) before killing anything identified only by a truncated
table column.

The actual fix: `webreview/worker_health.py` plus a new `manage.py qcluster_local` command
(`webreview/management/commands/qcluster_local.py`), wired into `upload_view`. `qcluster_local`
is a thin wrapper around django-q2's own `qcluster` command that also writes a heartbeat file
(`.runs/qcluster.heartbeat`) every 10 seconds from a background thread. `upload_view` checks
that file's age before enqueuing a task: if it is missing or older than 25 seconds, it spawns
`qcluster_local` as a detached process itself, guarded by a short-lived lock file
(`.runs/qcluster_local.lock`) so two near-simultaneous uploads do not each spawn their own
worker. Verified end to end through the real HTTP path: `runserver` alone, no `qcluster`, a
real upload through curl, and the auto-spawned worker took the task all the way to `succeeded`
with no manual intervention.

Deliberately local-dev-only, gated on `settings.DEBUG`: in production, PythonAnywhere's
Always-on task already restarts `qcluster` if it dies (see "Production deployment" below), so
a second auto-spawn from inside a WSGI worker would just create a duplicate cluster.
`run_dev.py` now starts `qcluster_local` instead of plain `qcluster`, so a normal local
session always has a live heartbeat, and the auto-recovery only ever triggers for the genuine
"someone forgot, or it crashed" case, not routine use. Checked django-q2's own source before
building this: its built-in cluster-monitoring API (`Stat.get_all()`) stores heartbeats
through Django's cache framework, which defaults to `LocMemCache` in this project (private to
each process), so it could never see a `qcluster` process's liveness from inside `runserver`
without configuring a shared cache backend. The plain heartbeat file avoids that entirely, at
the cost of being custom rather than using the library's own mechanism.

**(2026-09-25) Nav bar added; upload moved from `/` to `/summarise/`.** The site now has three
sections, reachable from a nav bar in `base.html`: **Summarise** (the existing upload flow,
now at `/summarise/`; `/` redirects there so old links still work), **Full Stack Development**
(`/full-stack/`), and **Natural Language Processing** (`/nlp/`). The latter two are static
educational pages (`webreview/content.py` holds the data, rendered by `full_stack.html`/
`nlp.html`), written for teaching, not generated: Full Stack Development maps every real layer
this app has (frontend, Django, `contract_reviewer`'s domain logic, the Claude/LangChain call,
SQLite, `django-q2`, deployment config, logging) to its actual files, and Natural Language
Processing walks the four real steps `summarize.py` takes (text extraction, prompt
construction with the untrusted-`<source_document>` framing, structured extraction by the
language model, the deterministic fact-check), stating plainly what it deliberately does not
do (no separate tokenisation/NER stage; one LLM call replaces all of that). Keep both pages
accurate to the code they describe if either changes; they cite real file and function names.

Three distinct kinds of work happen in this repo — don't confuse them:

1. **Editing the specification files** (`Workflow/SKILL.md`, `Contract Skills/*.md`, the
   database plan) — these are the actual substantive instructions the pipeline executes at
   runtime (loaded verbatim by `contract_reviewer/skills.py`), not documentation to
   summarize into code. Read the specific file in full before changing review logic that
   depends on it.
2. **Running a review** — `.venv\Scripts\python.exe review.py <contract.pdf> [-v]` (see
   below). This costs real API money (Flagship-tier + Tavily calls across multiple stages).
3. **Changing the application code** — see `ARCHITECTURE.md` for the module map and what's
   safe to change without breaking the eventual Django port.

Read `TECHNICAL HANDOVER.md` for the original requirements this was built against, and
`ARCHITECTURE.md` for how the current implementation satisfies them and what's still open.

## Commands

```powershell
# One-time setup (Python 3.11 — 3.14 is too new for reliable wheel support on these deps)
py -3.11 -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt

# --- CLI (Phase 1) ---
.\.venv\Scripts\python.exe review.py "<contract.pdf>" [--client-role ...] [--perspective "..."] [-v]
.\.venv\Scripts\python.exe review.py "<contract.pdf>" --resume <run_id>   # resume a crashed run

# Manual checks (no automated test suite yet)
.\.venv\Scripts\python.exe tests\make_sample_pdf.py                       # build a synthetic PDF fixture
.\.venv\Scripts\python.exe tests\check_verifier_catches_bad_citation.py   # live API call, small cost
.\.venv\Scripts\python.exe tests\check_cheap_tiers_pipeline.py            # skips Flagship-tier stages

# --- Web app (Phase 2) ---
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe run_dev.py                    # RECOMMENDED: starts runserver + qcluster together, stops both on Ctrl+C
.\.venv\Scripts\python.exe run_dev.py --port 8001         # use a different port (e.g. to test alongside a session already on 8000)
.\.venv\Scripts\python.exe manage.py createsuperuser      # optional, for /admin/

# ...or run them separately, if you specifically want to watch one process's log on its own:
.\.venv\Scripts\python.exe manage.py runserver
.\.venv\Scripts\python.exe manage.py qcluster_local     # local dev: see "Auto-recovery" below. Plain `qcluster` still works, just without the heartbeat.

# --- Contract summariser (separate program, not part of the risk-review pipeline) ---
.\.venv\Scripts\python.exe summarise.py "<contract.pdf|.docx|.md>" [--client-role ...] [--tier balanced] [-v]
```

The web app has no automated tests either; verify by using the upload flow at `/` (summary
only — the review flow was removed 2026-09-23, see above) and watching
`webreview.tasks.run_summary_task` execute in the `qcluster` process's output, or in
`logs/webreview.log` (rotating file, also captures `contract_reviewer`'s own log lines —
check this first when troubleshooting instead of just the console).

**Run exactly one `runserver` and one `qcluster` at a time.** Multiple stray instances have
accumulated in past sessions (different terminals, different Python interpreters) with no
error since Django doesn't stop you from doing it. Only one process can actually bind port
8000 (check with `Get-NetTCPConnection -LocalPort 8000` in PowerShell); extra `runserver`s
are harmless clutter, but extra `qcluster`s risk confusing which worker log to watch. Before
starting either, check for existing ones: `Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like '*manage.py*' }`.
**These processes outlive a Claude Code session** — a `runserver`/`qcluster` started in an
earlier conversation can still be running (and bound to port 8000, serving stale code) when a
new session starts. Check for and kill stale ones *before* testing, not after — a stale
process silently serving old code while you test against it produces misleading results.
This has now happened twice in real sessions (both times: a `qcluster` was simply never
started, leaving an uploaded review/summary stuck at `pending` in the queue forever with no
error — check `django_q.models.OrmQ`/`Success`/`Failure` counts and the row's
`execution_status` first when "it's not doing anything" is reported, before assuming a code
bug). **At the end of a testing session, stop `runserver`/`qcluster` cleanly** rather than
leaving them running indefinitely — that's exactly how they go stale by the next session.

**`run_dev.py` (new) starts both together as one command**, precisely to stop this recurring.
Two real bugs were found and fixed while building and testing it, both worth knowing about
if you ever touch process-management code here again:
- Its port-availability check originally used a `connect()` test, which only detects an
  *active listener*. A port a process just died on can still refuse a *bind* (Windows
  TIME_WAIT) even though nothing is listening — `connect()` reported "free" while the actual
  `runserver` bind then failed. Fixed by testing with a real throwaway `bind()`, the same
  operation `runserver` itself performs, so it can't produce a false negative.
- Its cleanup originally used `Popen.terminate()`, which on Windows only signals the
  *direct* child — it does not cascade to grandchildren (django-q2 forks a sentinel, which
  forks workers), which were then silently orphaned rather than stopped. Fixed with
  `taskkill /T /F`, which kills the whole process tree; verified by force-killing the
  top-level process and confirming all 11 processes in a real running tree (launcher +
  runserver + qcluster + sentinel + 4 workers, each showing up as 2 PIDs due to a Windows
  venv-stub-relaunch quirk that's cosmetic, not a real duplicate) terminated with zero orphans.

Default model tiers live in `models.yaml` (currently all-Anthropic — switched from OpenAI
after OpenAI's credits ran out; see "Current status" above); override per-run with
`MODEL_TIER_<TIER>_PROVIDER`/`MODEL_TIER_<TIER>_MODEL` env vars without editing the file.
API keys come from `.env` (`ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY`,
`TAVILY_API_KEY`) — never log full key values, and ignore the other unrelated keys in that
file (Telegram, Finnhub, secret key belong to other projects on this machine).

## Production deployment (PythonAnywhere)

**Live at `https://ngwaichung.pythonanywhere.com/`** (account `NgWaiChung`, paid Hacker-or-
above plan — the free tier cannot run this app at all, see the dated entry above). Deployed
2026-09-23; first real summary run against a genuine contract succeeded end-to-end.

| Setting | Value |
|---|---|
| Project path | `/home/NgWaiChung/ContractSummary` (a `git clone` of this repo's `main` branch) |
| Virtualenv | `/home/NgWaiChung/.virtualenvs/contractsummary`, **Python 3.12** (not 3.11 — see the dated entry above for why) |
| Web app | Manual configuration, Python 3.12, WSGI file hand-edited to add the project path to `sys.path` and set `DJANGO_SETTINGS_MODULE=webconfig.settings` |
| Static files mapping (Web tab) | `/static/` → `.../ContractSummary/staticfiles` (after `collectstatic`); `/media/` → `.../ContractSummary/media` |
| Background worker | `manage.py qcluster` runs as a PythonAnywhere **Always-on task** (paid-tier feature) — command: `/home/NgWaiChung/.virtualenvs/contractsummary/bin/python /home/NgWaiChung/ContractSummary/manage.py qcluster`. **Without this, uploads sit at `pending` forever** — the exact local "qcluster isn't running" failure mode documented above, just on the server instead of a dev machine. |
| `.env` | Created manually on the server (never committed, same as local) — needs its own `SECRET_KEY` (don't reuse the local one), `DEBUG=False`, `ALLOWED_HOSTS=ngwaichung.pythonanywhere.com`, `CSRF_TRUSTED_ORIGINS=https://ngwaichung.pythonanywhere.com`, and `ANTHROPIC_API_KEY`. |

**To redeploy after a code change:**
```bash
# In a PythonAnywhere Bash console:
workon contractsummary
cd ~/ContractSummary
git pull
pip install -r requirements.txt          # only if requirements.txt changed
python manage.py migrate                 # only if a new migration was added
python manage.py collectstatic --noinput # only if static files changed
```
Then: **Web tab → Reload** (picks up code/settings changes for the request-serving process).
If `webreview/tasks.py` or anything it imports changed, also restart the qcluster Always-on
task from the **Tasks** tab — reloading the web app does **not** restart it, since it's a
separate long-running process.

## Repository layout

| Path | Role |
|---|---|
| `ARCHITECTURE.md` | Module-by-module reference and Django-reusability guide. Read before structural changes. |
| `Specifications.md` | The Django web app's feature spec (upload → progress → report → PDF download) — what `webconfig`/`webreview` were built against. |
| `TECHNICAL HANDOVER.md` | Original requirements/status document this implementation was built against. |
| `webconfig/` | Django project settings/URLs (SQLite, `django_q` ORM broker config, media settings). |
| `webreview/` | The Django app. Only summary-only code paths remain in `views.py`/`urls.py`/`tasks.py` (`run_summary_task` calls `contract_reviewer.summarize`) since 2026-09-23. `models.py` still defines `Contract`/`ContractDocument`/`Summary` (live) plus `Review`/`Finding`/`Authority`/`VerificationRecord`/`RunEvent` (dormant — no views/URLs reference them, kept for the one historical review row and to make a future web review UI additive rather than a rebuild). |
| `manage.py`, `db.sqlite3`, `media/`, `logs/` | Django entrypoint, dev database, uploaded contracts + generated PDFs, rotating app log (`logs/webreview.log`) — all local-disk, gitignored. |
| `run_dev.py` | Starts `runserver` + `qcluster_local` together (recommended way to start the web app locally); see the process-hygiene notes above for the two bugs fixed while building it. |
| `webreview/worker_health.py` | Heartbeat-file check for the qcluster auto-recovery feature (see the 2026-09-25 dated entry above). `ensure_worker_running()` is called from `upload_view`; dev-only, gated on `DEBUG`. |
| `webreview/management/commands/qcluster_local.py` | Local-dev `qcluster` wrapper that also writes the heartbeat file `worker_health.py` reads. Not used in production; PythonAnywhere's Always-on task runs plain `manage.py qcluster`. |
| `webreview/content.py` | Static content (as Python data, not prose baked into templates) for the Full Stack Development and Natural Language Processing pages. Keep it accurate to the file/function names it cites if the underlying code changes. |
| `Workflow/SKILL.md` | The orchestration spec — routing, roles, model tiers, verification rules, report structure. Loaded verbatim into prompts by `contract_reviewer/skills.py`; do not paraphrase its rules into code without checking the source. |
| `Contract Skills/*.md` | Skill files, loaded verbatim by `contract_reviewer/skills.py`. Frontmatter `kind: contract-type` (the four review skills: Sales/Purchase, Tenancy, Employment, General fallback) marks a skill the risk-review classifier can route to (`skills.load_routing_skills()`); `kind: task` (`Contract Summary.md`) marks a different job entirely, never shown to that classifier — it's driven directly by `contract_reviewer/summarize.py` instead (both `summarise.py` and the web app's "Summarise" button). Adding a new skill file to this folder without a `kind: task` frontmatter field defaults it to `contract-type` and puts it in front of the classifier. |
| `Contracts Database/Contracts Database Plan.md` | The proposed Phase 2 SQLite schema — see `ARCHITECTURE.md` §6 for how current state maps onto it. |
| `contract_reviewer/` | The application package — see `ARCHITECTURE.md` for the full module table. |
| `review.py` | Risk-review CLI entrypoint. |
| `summarise.py` | Contract-summariser CLI entrypoint (`summary.md` is its plan doc; `contract_reviewer/summarize.py` + `docx_report.py` are the actual pipeline/renderer). Separate program from `review.py` — no shared execution path beyond the common extraction/config/model-call utilities. |
| `models.yaml` | Efficient/Balanced/Flagship tier → provider/model config, shared by both `review.py` and `summarise.py`. |
| `Reviews/`, `Reports/`, `Summary/` | Generated Markdown/PDF/Word output, created on demand. |
| `.runs/` | Per-run checkpoints (LangGraph `SqliteSaver`) and JSON artifacts (routing record, findings, verification ledger, model assignments) for inspection and future DB import. |
| `tests/` | Manual verification scripts (no pytest suite) — see Commands above. |

## Hard rules the workflow enforces (do not weaken silently)

- **Routing is by substance, not filename or title.** Specialist skills take precedence over
  the general fallback; the fallback is used only after explicitly excluding all specialist
  routes. Mixed contracts may need multiple specialist skills.
- **Reviewer and verifier are separate agents, always.** `nodes/verify.py` builds its own
  fresh message list and its own model client — never derived from the reviewer's history.
  A single call role-playing both roles does not satisfy this.
- **Model assignment is by provider-neutral capability tier** (Efficient/Balanced/Flagship),
  resolved at runtime via `contract_reviewer/config.py` + `models.yaml`. Every LLM call
  records its *actual* provider/model/tier in a `ModelAssignment` — never invented or assumed.
- **Every substantive finding needs a real, independently verified Singapore authority**
  (Verified/Qualified/Unsupported/Unverified) — a citation alone is not sufficient, and
  `Unsupported`/`Unverified` items move to a separate "unverified concerns" register rather
  than being silently dropped or kept as confirmed.
- **Source documents are immutable evidence**, and contract text / search results are always
  framed as untrusted data in prompts, never as instructions (see `prompts.py`).
- **Report status, commercial recommendation, finding severity, and authority verification
  status are four separate fields** — never collapsed into one (`schemas.py`, `state.py`).
- The correction loop is bounded (`max_cycles`, default 2); an unresolved disagreement after
  the bound produces a **Provisional** report, never a silently-optimistic "Completed" one.
- The pipeline never modifies the original contract, contacts counterparties, signs,
  publishes, or files anything.

## Known simplifications in the Django app (don't "fix" without reading the reasoning first)

- `runtime.py`'s tier-config global is still a global. `webreview/tasks.py` calls
  `runtime.set_tiers()` once per task execution; this is safe under `django-q2`'s default
  multiprocessing worker model (separate OS processes don't share the global) but would need
  the proper `RunnableConfig`-based fix (see `ARCHITECTURE.md` §3) if workers ever become
  threaded instead of process-based.
- The `SqliteSaver` checkpoint DB (`.runs/checkpoints.sqlite`) is still shared/single-file —
  fine for one local user, a contention risk under real concurrent web use (`ARCHITECTURE.md` §7).
- No auth, no per-user contract lists — see `Specifications.md` §9 for the full deferred list
  and why each item is deferred, not forgotten.
