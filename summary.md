# Contract Summariser — Plan (v1, "start simple")

Status: **built.** Implemented as `summarise.py` / `contract_reviewer/summarize.py` /
`docx_report.py`, per the plan below with no changes to the approach. Verified end-to-end
with real API calls (Balanced-tier Claude Sonnet). One real bug found and fixed during
verification: the fidelity check in §6 originally did a naive whole-field substring match,
which produced false positives on (a) composite descriptive sentences with clause citations,
(b) PDF-extraction line-wraps splitting a phrase across a newline, and (c) the model
paraphrasing a duration in different word order. Fixed by extracting concrete money/date/
duration tokens from each field and normalizing whitespace before comparing, rather than
matching whole fields verbatim — see `CLAUDE.md`'s note on this program for the summary.
Since wired into the Django web app too (`Specifications.md` §12, PDF instead of Word for
that path) — §9's boundary did not hold long-term, superseded by a later request; the CLI
still produces Word, unchanged. Recommended choices below (tier default, ~5-item cap, §7
structure) were adopted as written; no changes were requested.

**Fourth fidelity-check false positive found (2026-09-23, via a real employment agreement
uploaded through the web app), not yet fixed:** the source used `$3,200` (no `S` prefix) for
a second monetary figure after already establishing `S$3,000` for the first; the model
normalised the second figure to `S$3,200` for consistency, which is a reasonable thing to do,
but `_fidelity_issues()`'s money regex (`S?\$\s?\d...`) extracts and compares the *whole*
matched token including whichever prefix the model wrote, so `"S$3,200"` doesn't literally
appear in a source that only has `"$3,200"`. **Fix for next session:** strip the optional `S`
prefix before comparing (compare on the digits, or normalize both sides to a bare `$digits`
form before the `in` check) — the currency is unambiguous from context in every case this
project handles (Singapore dollars), so the prefix is cosmetic, not a fact to verify.
Also seen in the same run: two purely-descriptive `term_duration` values (prose explaining
"no fixed term stated") correctly fell back to whole-string matching and correctly failed —
that's the already-documented "no extractable token" limitation working as designed, not a
new bug, and isn't something a regex fix can solve (there's no fact in free prose to extract).

Note on naming: this planning document is `summary.md` (project root). The program's
*output* files live in a new `Summary/` folder (capitalised, matching `Reviews/`/`Reports/`).
These are two different things — flagging it once so it's never ambiguous later.

## 1. Objective

A new standalone CLI, `summarise.py`, that takes a single contract file (PDF, Word `.docx`,
or Markdown `.md`), produces a plain-English descriptive summary using the
`Contract Skills/Contract Summary.md` skill created earlier, and writes a professionally
formatted Word document to `Summary/`. This is deliberately a separate, simpler program from
`review.py` — no risk ranking, no independent verification, no correction-cycle loop,
because that's not what a summary is for (see the skill file's own "how this differs from
the review skills" section).

## 2. Why this is a simple linear pipeline, not a LangGraph graph

`review.py`'s pipeline needs LangGraph because it has genuine branching (routing) and a
genuine cycle (reviewer ↔ verifier correction loop) that must be bounded and checkpointed.
Summarising one document with one skill is extract → summarise → (lightweight fidelity
check) → render → write — a straight line, no branching, no retries needed by design.
**Recommended: plain Python functions, no LangGraph.** Dragging in graph/checkpointer
machinery for a linear pipeline would be unjustified complexity for what it buys here.

## 3. Reuse from `contract_reviewer/` (per `ARCHITECTURE.md`'s existing reuse pattern)

| Existing piece | Reused how |
|---|---|
| `document_extract.py` / `pdf_extract.py` / `docx_extract.py` | Reused for PDF/`.docx` extraction. **New:** add `.md` support (trivial — read the file as text, wrap as a single logical page, same `{ok, text, pages, warnings, scanned_pages}` shape) and add `.md` to `SUPPORTED_EXTENSIONS`. |
| `skills.py` | Reused as-is to load `Contract Summary.md` verbatim (`kind: task`, already excluded from the risk-review classifier's catalog — this program is the reason that skill exists, and it's the only thing that loads it right now). |
| `config.py` / `runtime.py` / `models.py` | Reused as-is: same `.env`/`models.yaml` tier resolution, same `invoke_structured()` call-site, same `ModelAssignment` recording (real provider/model/tier, never invented). |
| `io_utils.py` | Reused pattern (`new_run_id()`, `safe_filename_stem()`, `write_artifact()`); add `SUMMARY_DIR` and `default_summary_path()` alongside the existing `REVIEWS_DIR`/`REPORTS_DIR` helpers. |
| `pdf_report.py` (as a pattern, not code) | The precedent for "render a structured result into a polished file format" — `docx_report.py` (new) plays the same role for Word that `pdf_report.py` plays for PDF. |

Nothing in the existing risk-review pipeline (`graph.py`, `nodes/*.py`) is touched or reused
directly — this program doesn't run a review, so there's no classify/verify/reconcile to reuse.

## 4. New pieces

| New file | Purpose |
|---|---|
| `summarise.py` | Thin CLI entrypoint (mirrors `review.py`): argument parsing, calls into the package, prints the result path/status. |
| `contract_reviewer/summarize.py` | The actual pipeline function: `run_summary(source_path, client_role=None, ...) -> dict`. Extract → build prompt → one structured LLM call → deterministic fidelity check → return everything needed to render. |
| `contract_reviewer/docx_report.py` | `render_docx(summary, context) -> bytes` using `python-docx` (already a project dependency, already used by `docx_extract.py`) — the Word-document equivalent of `pdf_report.py`. |
| `ContractSummary` (in `schemas.py`, alongside the existing pydantic models) | Structured output schema mirroring the skill file's own required sections one-to-one (see §5) — the LLM's output is captured as data, not free-form prose, the same discipline the review pipeline already uses for findings/authorities. |
| `build_summary_messages()` (in `prompts.py`, alongside the existing prompt builders) | Injects the full verbatim `Contract Summary.md` text plus the extracted contract text, framed as untrusted `<source_document>` data exactly like every other prompt builder already does. |

Small addition to existing files: `document_extract.py` gains `.md` support;
`io_utils.py` gains `SUMMARY_DIR`/`default_summary_path()`.

## 5. `ContractSummary` schema (maps directly to the skill file's sections)

- `contract_type: str`
- `parties: list[{name, role}]`
- `effective_date`, `term_duration`, `governing_law`, `dispute_resolution`, `key_monetary_value: str`
- `subject_matter_summary: str` (one paragraph)
- `obligations_by_party: list[{party: str, obligations: list[str]}]`
- `payment_terms: str`
- `key_dates: list[{date: str, description: str}]`
- `termination_and_exit: str`
- `liability_snapshot: str`
- `ip_confidentiality_data: str | None` (omit the section entirely if the skill found nothing to say)
- `notable_or_unusual_terms: list[str]` (the skill caps this at ~5 items — enforced by prompt instruction, not schema validation, since the model can't count reliably against a hard limit)
- `missing_information: list[str]`

Model tier: **Balanced** by default (`models.yaml`) — this is comprehension/extraction/
organisation work, not the complex legal reasoning Flagship is reserved for, matching the
tier philosophy already documented in `Workflow/SKILL.md`. No web-search tool bound (a
summary doesn't need primary-source verification — that's the review skills' job).

## 6. Fidelity check (Recommended, small addition)

Before rendering, run a deterministic check — reusing the exact pattern already in
`nodes/factual_check.py`'s `_substring_issues()` — confirming every monetary figure and date
the model wrote into `key_monetary_value`/`payment_terms`/`key_dates` actually appears
verbatim in the extracted source text. Any mismatch becomes a visible note in the output
document ("Data fidelity notice: the figure 'S$3,500' could not be matched verbatim in the
source text — verify against the original") rather than a silent possible hallucination in a
client-facing document. This is cheap (no extra LLM call) and directly prevents the one
failure mode that matters most for a document whose whole purpose is "trust this instead of
re-reading the contract."

## 7. Word document structure (`docx_report.py`)

Styled consistently with the existing PDF/web report's visual language (navy `#1a2b4c`
headings, clean sans-serif body) so all three output formats (Markdown, PDF, Word) read as
one product family:

1. **Header block**: "Contract Summary" title, source filename, date generated, client role
   if supplied, source SHA-256 (small print) — mirrors the review report's metadata section.
2. **Snapshot** — a table (Field | Detail), directly from the schema's top-level fields.
3. **Subject Matter and Purpose** — paragraph.
4. **Key Obligations by Party** — one subheading per party, bullet list under each.
5. **Payment Terms** — paragraph.
6. **Key Dates and Milestones** — a table (Date | Description), omitted if empty.
7. **Termination and Exit** — paragraph.
8. **Liability and Risk-Allocation Snapshot** — paragraph.
9. **IP, Confidentiality and Data** — paragraph, section omitted entirely if the model
   returned nothing (not every contract has this).
10. **Notable or Unusual Terms** — bullet list.
11. **Missing Information** — bullet list.
12. **Data fidelity notices**, if any (§6) — shown plainly, not buried.

Page numbers in the footer are a nice-to-have (`python-docx` supports it via a standard field
-code technique) — attempted during implementation, not a blocker if it proves fiddlier than
it's worth for v1.

## 8. CLI

```
python summarise.py <contract.pdf|.docx|.md>
  [--client-role ...]
  [--tier efficient|balanced|flagship]   # default: balanced
  [--output PATH]                         # override the default Summary/... path
  [-v]
```

Default output path: `Summary/<safe-contract-name>-<UTC-timestamp>-<run-id>.docx`, same
collision-avoidance convention as `Reviews/`/`Reports/`. Exit code non-zero only if
extraction failed outright (no contract text to summarise) — there's no `Incomplete`/
`Provisional`/`Completed` release-gate concept here; that's specific to the risk-review
workflow's Stage 4, not applicable to a descriptive summary.

## 9. What this deliberately does not do (matches the skill file's own boundary)

- No severity ranking, no Singapore statute/case citations, no independent verification —
  if that's actually what's needed, the answer is "run `review.py`," not "extend this."
- No correction cycles / no revision loop.
- Not wired into the Django web app in this pass — `webreview` still only exposes the
  risk-review pipeline. Say if/when you want a "Summarise" option added there too; it would
  reuse `contract_reviewer/summarize.py` the same way `webreview/tasks.py` reuses `graph.py`.

## 10. Open questions for you

- **`--tier` default of Balanced** — fine as the default, or would you rather Flagship for
  every summary regardless of cost? (Efficient is available too, but likely too weak for
  reliably organising a full contract's terms into the structured schema.)
- **Notable-or-unusual-terms cap of ~5** — matches the skill file as written; say if you want
  it uncapped or a different number.
- Anything else you want in/out of the Word document structure in §7 before implementation.

## 11. Suggested build order

1. `.md` support in `document_extract.py` (small, needed before anything else can be tested end to end).
2. `ContractSummary` schema + `build_summary_messages()`.
3. `contract_reviewer/summarize.py` (the pipeline function) — verify with a direct call
   against the existing `tests/fixtures/sample_tenancy.pdf`, one real (cheap, Balanced-tier)
   API call, before building anything else on top of it.
4. `docx_report.py` — verify by rendering from that same test call's output locally (no new
   API cost, same technique used to iterate on `pdf_report.py` earlier in this project).
5. `summarise.py` CLI wrapper + `Summary/` output path in `io_utils.py`.
6. End-to-end run against a real contract, on request (this costs a small amount of real
   API money — confirmed before running, same as every other paid test in this project).
