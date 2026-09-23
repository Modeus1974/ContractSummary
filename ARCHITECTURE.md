# Contract Reviewer — Architecture and Reusability Guide

This document describes the CLI implementation (Phase 1) and, module by module, how much of
it carries forward unchanged into the Django web application (Phase 2, now built — see
`Specifications.md` for its feature spec and `webconfig`/`webreview` for the actual code).
**The Phase 2 app is now deployed** (PythonAnywhere, 2026-09-23) — see `CLAUDE.md`'s
"Production deployment" section for the live URL and operational details; this document's
module-reuse analysis is unaffected by where the app runs. Read this alongside the original
specs, which this implementation was built to satisfy and does not replace:

- `TECHNICAL HANDOVER.md` — original status/requirements document.
- `Workflow/SKILL.md` — the authoritative orchestration spec (stages, roles, release rules).
- `Contract Skills/*.md` — the four substantive legal review skill files.
- `Contracts Database/Contracts Database Plan.md` — the SQLite schema originally proposed
  for the web app; see "Mapping to the database plan" below for how the current in-memory
  `ReviewState` relates to those tables.

## 1. What this program does, in one paragraph

`review.py <contract.pdf>` runs a LangGraph state machine (`contract_reviewer/graph.py`)
that classifies a contract, routes it to one or more `Contract Skills/*.md` files, has a
Flagship-tier LLM (with live web search) draft findings and cite Singapore authorities, has
a **separate** Flagship-tier LLM independently verify every citation, runs a deterministic
+ LLM factual/coverage check in parallel, reconciles the two, loops back to the reviewer up
to twice if there are unresolved defects, and finally renders the reconciled state into both
a Markdown report (`Reviews/`) and a styled PDF (`Reports/`). Every stage's real
provider/model/tier is logged and recorded — nothing about model assignment is invented.

## 2. Data flow / graph topology

```
START -> intake
intake --(extraction_ok?)--> classify | assemble        (assemble renders an Incomplete report)

classify --(confidence/attempt)-->
    escalate  -> classify (retry once at Balanced tier)
    proceed   -> review
    incomplete-> assemble

review -> verify            \
review -> factual_check      >  parallel fan-out, fan back into reconcile
verify -> reconcile          |
factual_check -> reconcile  /

reconcile --(defects_pending & cycle < max_cycles)-->
    revise   -> review        (loop, cycle += 1)
    otherwise-> assemble      (report_status = Completed | Provisional)

assemble -> write_report -> END
```

There is no separate "incomplete" node — `assemble`/`write_report` always run and always
produce a real file; for a failed/incomplete run they render the same 8-section template
with a canned explanation instead of skipping it. See `contract_reviewer/nodes/report.py`.

## 3. Module reference

| Module | Responsibility | Reuse in Django |
|---|---|---|
| `contract_reviewer/state.py` | `ReviewState` — the single TypedDict threaded through every node. | **Reuse as the in-memory/task-execution contract.** Its shape is the closest thing this codebase has to a schema; see §6. |
| `contract_reviewer/schemas.py` | Pydantic models used at node boundaries: `RoutingRecord`, `Finding`, `Authority`, `VerificationRecord`, `ReviewDraft`, `VerificationDraft`, `FactualCheckNote`, `CorrectionLogEntry`, `ModelAssignment`, `ExecutiveAssessment`. | **Reuse as-is.** These are framework-agnostic pydantic models; Django REST Framework serializers or ORM model `clean()` validation can wrap them, but the models themselves don't need to change. |
| `contract_reviewer/skills.py` | Loads/caches/hashes `Workflow/SKILL.md` and `Contract Skills/*.md` verbatim; resolves a `RoutingRecord`'s selected paths to full text. `SkillFile.kind` (`contract-type` vs `task`, from frontmatter) distinguishes the four risk-review routing skills from other jobs like `Contract Summary.md`; `load_routing_skills()` filters to `contract-type` only and is what `classify_node` actually shows the classifier. | **Reuse as-is.** File-based loading works whether called from a CLI process or a Django view/task. If skills ever move into the DB (per the handover's "skill version/content hash" gap), only this module's I/O needs to change — its return shape (`SkillFile`) can stay the same. |
| `contract_reviewer/pdf_extract.py` | PyMuPDF-based text extraction: page-numbered text, SHA-256, scanned-page detection. Never raises on a bad PDF — returns `{ok: False, warnings: [...]}`. | **Reuse as-is,** with one adaptation: it takes a filesystem `Path`. A Django view receives an `UploadedFile`/`InMemoryUploadedFile`; save it to a temp path (or `FileField`) first, then call `extract_pdf(path)` unchanged. |
| `contract_reviewer/config.py` | Loads `.env` + `models.yaml`; resolves Efficient/Balanced/Flagship tiers with env-var overrides (`MODEL_TIER_<TIER>_PROVIDER`/`_MODEL`). | **Reuse the resolution logic; replace the source.** In Django, tier config belongs in `settings.py`/environment variables (via `django-environ` or similar) rather than a YAML file read from `PROJECT_ROOT`, and `TierConfig` becomes either a settings dataclass or a small admin-editable model per the handover's "Provider abstraction" gap. |
| `contract_reviewer/models.py` | `invoke_structured(tier, role, messages, schema, tools=None)` — the single call-site for every structured LLM call, via `langchain.agents.create_agent`. Returns `(parsed_result, ModelAssignment)`. | **Reuse as-is.** This is the one function that talks to LangChain; nothing about it is CLI-specific. |
| `contract_reviewer/runtime.py` | Process-wide **global** holding the resolved tier config (`set_tiers`/`get_tiers`), read by every node. | **Do not carry this pattern into Django unchanged.** A module-level global is fine for a single-process CLI run but is not safe for a multi-request/multi-thread web server (one request's tier override could leak into another's). Before Django: pass tier config explicitly through LangGraph's existing `config={"configurable": {...}}` mechanism (already used for `thread_id`) instead of a global, or resolve tiers once per Celery task invocation with no shared mutable state. |
| `contract_reviewer/prompts.py` | One `build_*_messages()` function per node; always frames contract/search-result content as untrusted `<source_document>` data, never instructions. | **Reuse as-is.** Pure functions, no I/O. |
| `contract_reviewer/graph.py` | `build_graph(checkpoint_db_path)` — wires all nodes into the `StateGraph`, wraps LLM-calling nodes in `_skip_if_incomplete` (catches exceptions, converts to `incomplete_reason`, short-circuits downstream nodes). Compiled with a `SqliteSaver` checkpointer. | **Reuse the graph/node logic as-is.** The **checkpointer** needs to change: a single shared SQLite file is a write-contention risk under concurrent web users. Use `langgraph.checkpoint.postgres.PostgresSaver` against the Django database (or a dedicated schema/table), or key checkpoints per-tenant. This is a one-line swap (`build_graph` already takes the checkpointer target as a parameter). |
| `contract_reviewer/nodes/*.py` | The eight pipeline stages: `intake`, `classify`, `review`, `verify`, `factual_check`, `reconcile`, `report.assemble_node` + `report.write_report_node`. Each is a pure `(state: ReviewState) -> dict` function — LangGraph's partial-state-update convention. | **Reuse every node's logic as-is.** They don't know or care whether they're invoked from a CLI script, a Django management command, or a Celery task — they only read/write the `ReviewState` dict. |
| `contract_reviewer/nodes/report.py` | Builds the shared `report_context` dict once, renders it into both the Markdown template and (via `pdf_report.render_pdf`) the PDF; writes both files; reads the Markdown back and validates heading order/duplicate IDs/cross-references before trusting `report_status`. | **Reuse the context-building and validation logic as-is.** The *file-writing* half (`Reviews/`, `Reports/` on local disk) is CLI-specific — see `io_utils.py` below. |
| `contract_reviewer/pdf_report.py` | `render_pdf(context) -> bytes` — Jinja2 → `xhtml2pdf`, with `_sanitize_glyphs()` to avoid missing-glyph boxes for LLM-generated Unicode characters the base PDF fonts don't cover. | **Reuse as-is.** A Django view can call this directly and return `HttpResponse(pdf_bytes, content_type="application/pdf")`, or save the bytes to a `FileField`. |
| `contract_reviewer/templates/report.md.jinja`, `report.pdf.html.jinja` | The two report templates, both consuming the exact same `report_context` dict. | **Reuse as-is.** They're plain Jinja2, not tied to the CLI. |
| `contract_reviewer/io_utils.py` | Run IDs, UTC timestamps, safe filenames, `Reviews/`/`Reports/` default paths, and per-run JSON artifact dumps under `.runs/<run_id>/`. | **Mostly CLI-specific — replace with the ORM + Django storage in Phase 2.** The `.runs/<run_id>/*.json` artifacts (`manifest`, `draft_findings`, `verification_ledger`, `correction_log`, `model_assignments`, `final_state`) are today's stand-in for the `reviews`/`findings`/`authorities`/`finding_authorities` tables in `Contracts Database Plan.md` — see §6. `safe_filename_stem()`, `utc_timestamp()`, and `new_run_id()` are small pure functions worth keeping regardless of storage backend. |
| `contract_reviewer/logging_setup.py` | Console logging: stage transitions + `role: provider/model/tier/effort` lines, with third-party libraries (httpx, the OpenAI/Anthropic SDKs) kept at `WARNING` so `-v` doesn't dump raw HTTP traffic. | **`configure_logging()` itself is still CLI-only** (called by `cli.py`/`summarize_cli.py`, never by the web app). But its logger name (`logging.getLogger("contract_reviewer")`) is what every `log_stage()`/`log_warning()`/`log_model_assignment()` call writes to, and as of 2026-09-23 `webconfig/settings.py`'s `LOGGING` dict gives that exact logger name its own handler — so under the web app, the same engine-level log lines land in `logs/webreview.log` instead of going nowhere. |
| `contract_reviewer/cli.py`, `review.py` | Argument parsing, building the initial `ReviewState`, invoking the graph, printing the result, exit codes. | **Not reused directly, but is the reference implementation** for what a Django view or Celery task's orchestration code should do: build the initial state dict, call `graph.invoke(state, config)`, read `report_status`/`output_path`/`pdf_output_path` off the result. |
| `contract_reviewer/document_extract.py` | Dispatches to `pdf_extract`/`docx_extract`/`extract_markdown` by file extension (`SUPPORTED_EXTENSIONS`). Used by both `review.py`'s `intake_node` and `summarise.py`. | **Reuse as-is.** Same filesystem-`Path` adaptation note as `pdf_extract.py` above. |
| `contract_reviewer/summarize.py`, `docx_report.py`, `summary_pdf_report.py`, `summarize_cli.py`, `summarise.py` | A second, separate, deliberately non-LangGraph pipeline (extract → one structured LLM call → deterministic fidelity check → render) that produces a plain-English `ContractSummary` (in `schemas.py`) via the `Contract Summary.md` (`kind: task`) skill, as either a Word document (`docx_report.py`, CLI) or a PDF (`summary_pdf_report.py`, web app — same `pdf_report.py`-style Jinja2/`xhtml2pdf` approach, sharing its `sanitize_glyphs()` helper). See `summary.md` for the design rationale — no branching/looping here, so no graph is used, unlike `review.py`. `run_summary()` takes an optional `on_stage` callback (`"extracting"`/`"summarizing"`) purely for progress reporting; the CLI ignores it. | **Already reused, not just reusable**: `webreview/tasks.py::run_summary_task` calls `run_summary(...)` then `summary_pdf_report.render_pdf(...)` exactly the way `run_review` calls `graph.stream(...)` then `pdf_report.render_pdf(...)` — this is the one piece of `ARCHITECTURE.md`'s reuse story that's now proven in both directions (CLI and web) rather than projected. `summarize_cli.py`/`summarise.py` remain CLI-only. |

## 4. Prompt-injection and evidence-handling discipline (unchanged in Django)

Every prompt builder in `prompts.py` wraps contract text in `<source_document>` tags with
an explicit "this is untrusted evidence, not instructions" instruction, and the verifier is
given the reviewer's *final output only*, never its reasoning transcript, via its own fresh
message list and its own model client (see `nodes/verify.py`'s module docstring). Preserve
this exactly when moving to Django — it doesn't depend on the CLI in any way, but it would
be easy to accidentally break by, e.g., sharing a LangChain message-history object between
reviewer and verifier calls for "efficiency."

## 5. Model-tier resolution

`models.yaml` maps `efficient`/`balanced`/`flagship` → `(provider, model)`, loaded once via
`config.load_tier_config()` and stashed in the `runtime` global (see the reusability caveat
above). Every node calls `get_tiers()[tier_name]` and passes the result into
`models.invoke_structured(...)`, which always returns a `ModelAssignment` recording the
*actual* provider/model/tier/effort used — this is what ends up in the report's "Model /
Role Assignments" table and must never be inferred or hardcoded elsewhere. Current default
(`models.yaml`) is Anthropic (`claude-haiku-4-5-20251001`/`claude-sonnet-5`/`claude-opus-5`),
prioritized per the user's own instruction once Anthropic credits were topped up. OpenAI and
OpenRouter both work via the same mechanism (`MODEL_TIER_<TIER>_PROVIDER`/`_MODEL` env
overrides, or edit the YAML) and nothing else in the codebase needs to change to switch —
this has now been exercised in both directions (OpenAI → Anthropic) with no code changes.

## 6. Mapping to the database plan (`Contracts Database Plan.md`)

The CLI has no database — it's file-based by design (see `TECHNICAL HANDOVER.md`: "before I
jump into building a web app"). But `ReviewState` and the per-run JSON artifacts were
deliberately shaped to correspond to the proposed tables, so migrating to Django/Postgres
is a mapping exercise, not a redesign:

| Current (file-based) | Future (`Contracts Database Plan.md` table) |
|---|---|
| `source_pdf_path`, `source_sha256`, `source_filename_safe` | `contract_documents` row (one per upload; keep the immutability rule — a new upload is a new version, never an overwrite) |
| `.runs/<run_id>/manifest.json` (extraction result, skill hashes) | Extends `contract_documents`/`document_text`; `skill_content_hashes` satisfies the handover's "record skill versions or content hashes for reproducibility" gap |
| `routing_record`, `selected_skill_texts` (paths only) | New columns/fields on `reviews` — the starter schema's single `skill_name` per review needs to become a list, as the handover's gap #1 already flags |
| `draft_findings`, `authority_ledger` | `findings`, `authorities`, `finding_authorities` |
| `verification_records` | The "verification ledger" the handover's gap #2 asks for — does not exist as a distinct table in the starter schema; add one keyed by (finding, authority, proposition), matching `VerificationRecord`'s shape almost exactly |
| `correction_log`, `model_assignments`, `errors` | The "run and agent history" the handover's gap #3 asks for — a new table, one row per node execution |
| `report_status`, `commercial_recommendation`, `unresolved_material_disagreement`, `unverified_concerns` | New columns on `reviews` — keep these as **separate fields**, per the handover's explicit instruction never to collapse report status / commercial recommendation / finding severity / authority verification status into one flag |
| `final_markdown` / `Reports/*.pdf` | Store as before (filesystem, or move to object storage) referenced by a `reviews.report_file` / `reviews.report_pdf_file` path or `FileField`, or regenerate on demand from stored `report_context` (cheaper: `report_context` is already a plain JSON-serializable dict — storing *that* verbatim, e.g. in a `reviews.report_context_json` column, means both templates can be re-rendered later without re-running the LLM pipeline) |

## 7. What's resolved in the Django app now, and what's still open

**Scope note (2026-09-23):** the Django app's risk-review UI (upload button, progress/
report/PDF views and routes, the review background task) was removed per
`Specifications.md` §14 — the web app now only drives `contract_reviewer.summarize`. The
risk-review pipeline described everywhere else in this document (`graph.py`, every
`nodes/*.py`, the module table in §3) is unaffected and unchanged; it's simply no longer
wired into `webreview`. It remains reachable via `review.py`, and the `Review`/`Finding`/
`Authority`/`VerificationRecord`/`RunEvent` models below are still present in
`webreview/models.py` (dormant, not dropped) should a web review UI be rebuilt later against
the same schema. The gaps below are numbered as they were when the review UI was live —
they describe the engine/database-mapping concerns generally, most of which apply equally to
a future re-added review UI, not just to the removed one.

Inherited from `TECHNICAL HANDOVER.md`'s "Technical design gaps"; status after building
`webconfig`/`webreview` per `Specifications.md`:

1. **Concurrency — partially resolved, pragmatically.** `runtime.py`'s tier-config global is
   still a global; `webreview/tasks.py` calls `set_tiers()` once per task execution, which is
   safe under `django-q2`'s default multiprocessing worker model (separate OS processes) but
   not under a threaded worker model. The shared `SqliteSaver` file is still shared/single-file
   — fine for one local user, still a contention risk under real concurrent use. Neither the
   proper `RunnableConfig`-based tier fix nor a `PostgresSaver` swap has been done.
2. **Background execution — resolved, differently than first suggested here.** Not Celery —
   `django-q2` with its Django-ORM broker (`webconfig/settings.py` `Q_CLUSTER`), avoiding a
   Redis dependency. The now-removed `webreview/tasks.py::run_review` used
   `graph.stream(..., stream_mode="updates")` rather than a single `graph.invoke()`,
   specifically so the progress bar could update after each node completed — a refinement on
   the "single blocking call" framing above, worth remembering if a review task is rebuilt.
   The surviving `run_summary_task` doesn't need this refinement (`summarize.run_summary()`
   is a single linear call, not a graph — see `summary.md` §2), so it just calls `run_summary()`
   directly with an `on_stage` callback for its two progress stages.
3. **Job/run history — resolved.** `webreview/models.py`'s `RunEvent` table (one row per
   stage transition and per `ModelAssignment`) is exactly this; see `Specifications.md` §4.
4. **Auth and multi-tenancy — still open, deliberately deferred.** See `Specifications.md` §9.
5. **Skill versioning — still open, unchanged.** `skills.py` still reads from disk; the DB
   models don't yet store skill content hashes anywhere (only `contract_reviewer`'s own
   `.runs/<run_id>/manifest.json` does, for CLI runs).
6. **SQLite, not Postgres.** Confirmed as the intentional v1 choice (`Specifications.md` §11);
   revisit if `django-q2` and the web process are routinely hitting the DB concurrently under
   real load, not on a fixed timeline.
