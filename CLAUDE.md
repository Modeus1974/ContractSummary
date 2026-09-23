# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

**Phase 1 (current): a working Python CLI.** `review.py` runs the full `Workflow/SKILL.md`
orchestration end-to-end with real agentic LLM calls (LangGraph + LangChain) and produces a
Markdown report (`Reviews/`) and a matching PDF (`Reports/`). This has been run successfully
end-to-end against real contract text, including the full correction-cycle loop.

**Phase 2 (current): a Django web app (`webconfig`/`webreview`), built per `Specifications.md`.**
Upload a PDF/Word contract → a `django-q2` background task runs the same `contract_reviewer`
pipeline via `graph.stream()` → a progress bar polls a status endpoint → the finished report
renders as styled HTML with a PDF download button. Structurally verified, and one real
end-to-end run has gone through the actual web UI: it produced a correct `Incomplete` report
(OpenAI ran out of credits mid-run at the `classify` stage) — this was a billing issue, not a
code defect, and confirmed the guard/Incomplete-path logic works for real under the web app,
not just the CLI. `ARCHITECTURE.md` documents, module by module, what `contract_reviewer/`
code was reused unchanged vs. adapted; `Specifications.md` is the feature spec this app was
built against — **read both before making structural changes** to either the engine package
or the Django app.

**Current status (as of 2026-09-23):** `models.yaml` defaults to Anthropic (switched back
from OpenAI after OpenAI's credits ran out). No real *completed* risk-review has gone through
the web UI yet (the one real run hit `Incomplete` on OpenAI's credit exhaustion, before the
switch back). The **summariser** has now had a real, fully successful web-UI run (see
directly above) — that part of the app is confirmed working end-to-end with real content.
Testing continues in the next session; nothing is mid-run or left in an inconsistent state.

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
.\.venv\Scripts\python.exe manage.py qcluster

# --- Contract summariser (separate program, not part of the risk-review pipeline) ---
.\.venv\Scripts\python.exe summarise.py "<contract.pdf|.docx|.md>" [--client-role ...] [--tier balanced] [-v]
```

The web app has no automated tests either; verify by using the upload flow at `/` and
watching `webreview.tasks.run_review` execute in the `qcluster` process's output.

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

## Repository layout

| Path | Role |
|---|---|
| `ARCHITECTURE.md` | Module-by-module reference and Django-reusability guide. Read before structural changes. |
| `Specifications.md` | The Django web app's feature spec (upload → progress → report → PDF download) — what `webconfig`/`webreview` were built against. |
| `TECHNICAL HANDOVER.md` | Original requirements/status document this implementation was built against. |
| `webconfig/` | Django project settings/URLs (SQLite, `django_q` ORM broker config, media settings). |
| `webreview/` | The Django app: `models.py` (Contract/ContractDocument/Review/Finding/Authority/VerificationRecord/RunEvent, and the separate `Summary` model for the summariser), `tasks.py` (`run_review` calls `contract_reviewer.graph`; `run_summary_task` calls `contract_reviewer.summarize`), `views.py`/`urls.py`/`templates/`. |
| `manage.py`, `db.sqlite3`, `media/` | Django entrypoint, dev database, uploaded contracts + generated PDFs (all local-disk, gitignored). |
| `run_dev.py` | Starts `runserver` + `qcluster` together (recommended way to start the web app locally); see the process-hygiene notes above for the two bugs fixed while building it. |
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
