# Pragmatic Programmer Refactoring Guide

A practical checklist for applying principles from *The Pragmatic Programmer* (Hunt & Thomas) to an existing codebase, without changing its behavior. Treat this as a working document: copy it into your repo, check items off as you go, and adapt anything that doesn't fit your stack.

## Ground Rule: Behavior Must Not Change

Every item below is a *refactoring*, not a rewrite. Before touching code:

1. Confirm you have a test suite, or write characterization tests that capture current behavior (inputs → outputs) before changing anything.
2. Work in small, reversible steps. Commit after each one.
3. Run the full test suite after every change. If there's no suite, manually verify the specific behavior you touched.
4. Never combine a refactor with a feature change or bug fix in the same commit.
5. Keep a rollback path — feature branch, tags, or frequent commits — so any step can be undone in isolation.

## 1. DRY — Don't Repeat Yourself

- Find duplicated logic (not just duplicated text) and extract it into a single function, class, or module.
- Watch for duplicated *knowledge*: the same business rule expressed in code, config, and documentation that could drift out of sync.
- Replace copy-pasted blocks with a shared abstraction only when the duplication represents the same concept — don't force unrelated code together just because it looks similar today.

## 2. Orthogonality

- Identify components that are tangled together (changing one forces changes in another for unrelated reasons).
- Separate concerns: pull business logic out of UI code, pull I/O out of pure logic, isolate third-party library calls behind a thin wrapper.
- Aim for each module to have one reason to change.

## 3. Reversibility

- Avoid hard-coding decisions that are likely to change (database vendor, cloud provider, logging framework, currency, locale).
- Introduce configuration or abstraction layers so these decisions can be swapped later without a rewrite.

## 4. Tracer Bullets & Prototypes (for new work built on old code)

- When extending the codebase, build a thin end-to-end slice first to validate the approach before fully fleshing it out.
- Clearly label throwaway prototype code as such (and actually throw it away — don't let it become production code by accident).

## 5. Eliminate Effects Between Unrelated Things

- Remove global mutable state where possible; pass dependencies explicitly.
- Check for temporal coupling: does function B secretly depend on function A having run first? Make ordering explicit (parameters, return values) instead of implicit.

## 6. Estimate and Break Down Work

- Before starting a refactor, break it into steps small enough to estimate and reverse individually.
- Track "shotgun surgery" candidates — changes that currently require touching many files — as signals for a future consolidation.

## 7. Good Enough Software / No Gold-Plating

- Don't over-engineer the refactor. Fix what's actually causing pain (hard to test, hard to change, hard to understand) — don't add speculative flexibility for hypothetical future needs.

## 8. Knowledge Portfolio / Naming

- Improve names: variables, functions, and classes should describe *what* and *why*, not implementation detail.
- Remove misleading names, dead code, and commented-out blocks (rely on version control history instead of comments for old code).

## 9. Communicate Precisely — Comments and Documentation

- Comments should explain *why*, not *what* (the code should already say what).
- Delete stale comments and outdated documentation that no longer matches behavior.
- Add a comment only where the code's intent genuinely isn't obvious from the code itself.

## 10. Design by Contract / Defensive Coding

- Make assumptions explicit: add input validation, preconditions, and assertions where a function currently relies on "it just happens to always be called correctly."
- Fail fast — surface errors close to their source rather than letting bad data propagate silently.
- Don't over-validate: check what actually matters for correctness, not everything imaginable.

## 11. Dead Programs Tell No Lies — Error Handling

- Ensure errors are handled or explicitly propagated, never silently swallowed (empty catch blocks, ignored return codes).
- Standardize on one error-handling approach per language idiom (exceptions vs. result types) rather than mixing styles inconsistently.

## 12. Decoupling and Law of Demeter

- Look for chains like `a.getB().getC().doSomething()` — this signals excessive coupling to internal structure. Consider adding a method on `a` that hides the chain.
- Reduce the number of things any one module needs to know about.

## 13. Metaprogramming / Configuration

- Move hard-coded values (magic numbers, magic strings, environment-specific settings) into named constants or configuration.
- Only abstract into config what genuinely varies across environments or deployments — don't over-configure static values.

## 14. Automate Everything

- Ensure the build, test, and lint steps run with a single command.
- Add a linter/formatter if one doesn't exist, and apply it in a dedicated formatting-only commit (never mixed with logic changes).
- Set up (or verify) CI so tests run automatically on every change.

## 15. Ruthless Testing

- Add unit tests for any function you refactor that lacks coverage, before changing its internals.
- Add regression tests for any bug fixed along the way, so the old bug can't silently return.
- Test edge cases and boundary conditions, not just the happy path.

## 16. Refactor Early, Refactor Often (Boy Scout Rule)

- Leave every file you touch slightly cleaner than you found it — but keep the scope tight to the area you're already working in.
- Don't let "just this one file" turn into a repo-wide rewrite in one pass. Track broader concerns as separate follow-up items instead.

## 17. Broken Windows

- Fix small visible issues (inconsistent formatting, TODOs left for months, ignored warnings) promptly — they signal to the team that quality doesn't matter, and they accumulate.
- Treat compiler/linter warnings as things to resolve, not ignore.

## Suggested Workflow for Applying This to a Real Project

1. Pick one module or one pain point (e.g., "this file is impossible to test," "this class does five unrelated things").
2. Write or confirm characterization tests around it.
3. Apply the relevant items above, one small commit at a time.
4. Run tests after each commit.
5. Move to the next module.
6. Periodically revisit this checklist — treat it as a recurring review, not a one-time pass.

## Anti-Checklist — Things to Avoid

- Don't rename/restructure and change logic in the same commit.
- Don't refactor code you don't have tests for and can't manually verify.
- Don't introduce new dependencies or frameworks as part of a "refactor" — that's a separate decision.
- Don't chase 100% adherence to every principle above at once; prioritize by what's actually causing bugs or slowing the team down.
