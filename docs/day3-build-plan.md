# NaughtRFP — Day 3 Build Plan
**Prepared:** 2026-07-08 (Day 2 wrap)
**Author:** Agent Architect synthesis from Backend Engineer, AI Pipeline Engineer, Frontend Engineer assessments
**Purpose:** Complete build instructions for Day 3 implementation using the defined agent team

---

## Context

The Day 2 agent team ran a parallel assessment wave across all five system layers. Three of the five implementation agents completed full code reviews. The Architect synthesized findings into a prioritized improvement plan. This document is the handoff for Day 3 — it contains every finding, every fix, every agent assignment, and the exact sequence to execute.

**Agent definitions:** `.claude/agents/strategic/` and `.claude/agents/implementation/`
**Design rationale:** `docs/multiAgentDesign.md`
**Spec:** `docs/solution.md`, `docs/prd.md`

---

## How to start Day 3

Paste this into a new session to kick off the build:

```
Read docs/day3-build-plan.md and docs/multiAgentDesign.md.
You are the orchestrator. Start with Wave 1:
spawn Backend Engineer, AI Pipeline Engineer, and Frontend Engineer
simultaneously — each with their Priority 1 task list and relevant
file content. Collect results, then proceed to Wave 2.
```

Switch Claude Code to **Auto mode** (permission selector, bottom-left) before starting — this allows agents to edit files without stopping for approval on every write.

---

## Agent Team Roster

| Tier | Agent | Definition File | Day 3 Role |
|---|---|---|---|
| Tier 1 | Product Owner | `.claude/agents/strategic/product-owner.md` | Scope arbiter — consult if a fix expands beyond its original boundary |
| Tier 1 | Architect | `.claude/agents/strategic/architect.md` | Cross-cutting decisions, Wave 2 synthesis |
| Tier 1 | Project Manager | `.claude/agents/strategic/project-manager.md` | Sequence Wave 2 tasks after Wave 1 lands |
| Tier 2 | Backend Engineer | `.claude/agents/implementation/backend-engineer.md` | `app.py`, `export_handler.py` — all P1 + QW backend fixes |
| Tier 2 | AI Pipeline Engineer | `.claude/agents/implementation/ai-pipeline-engineer.md` | `agents.py` — all P1 + QW pipeline fixes |
| Tier 2 | Frontend Engineer | `.claude/agents/implementation/frontend-engineer.md` | `app.js`, `index.html`, `style.css` — all P1 + QW frontend fixes |
| Tier 2 | Data Engineer | `.claude/agents/implementation/data-engineer.md` | `db.py` — escalation target for D-7 (KB FTS5 scope) if promoted |
| Tier 2 | Integration Specialist | `.claude/agents/implementation/integration-specialist.md` | On-call for auth/MCP questions from Backend or AI Pipeline |

---

## Priority 1 — Fix Today (Critical + High)
*These are correctness bugs and demo-critical issues. All must be resolved before any new features.*

### Backend Engineer — Priority 1 Tasks

**P1-1 · CRITICAL · `app.py:rerun_question_stream` — TypeError crash on multi-document RFPs**
- **File:** `app.py` ~line 679
- **Problem:** `rfp["filename"]` is `None` on project-style (multi-doc) RFPs. `os.path.join(..., None)` raises `TypeError` at runtime for any re-run triggered on a multi-document project.
- **Fix:** Add `doc = db.get_document(q.get("document_id"))` and resolve `filepath` from the document record. Fall back to `rfp["filename"]` only if `document_id` is absent.
- **Estimated time:** 20 minutes

**P1-8 · HIGH · `export_handler.py:_export_csv` — wrong-row silent data write**
- **File:** `export_handler.py` lines 116–125
- **Problem:** Iterates every value in every row to find the question text, instead of targeting the requirement column. Any cell whose first 120 chars match a question key will be used as the match anchor, silently writing the wrong answer into that row.
- **Fix:** Mirror `_export_xlsx`'s `req_col` detection logic — scan only the identified requirement column for the lookup key.
- **Estimated time:** 20 minutes

**P1-9 · HIGH · `export_handler.py:_build_lookup` — flagged questions produce blank rows in export**
- **File:** `export_handler.py` line 24
- **Problem:** Excludes questions with `status != "answered"` or empty `answer`. Flagged RFPs export a file indistinguishable from an unprocessed one.
- **Fix:** Include flagged questions in the lookup with sentinel response code `"FLAGGED"` and review-reason in the comments column.
- **Estimated time:** 20 minutes

**P1-15 · HIGH · `export_handler.py:_export_csv` — `fieldnames` read after iterator exhausted**
- **File:** `export_handler.py` lines 106–109
- **Problem:** `reader.fieldnames` accessed after `list(reader)` has consumed the iterator. Works in CPython today but is a fragile pattern that lint tools flag.
- **Fix:** Move `fieldnames = reader.fieldnames` to before `rows = list(reader)`.
- **Estimated time:** 10 minutes

---

### AI Pipeline Engineer — Priority 1 Tasks

**P1-2 · CRITICAL · `agents.py:_PAGE_CACHE` — unsynchronized dict mutation across 6 threads**
- **File:** `agents.py` module-level ~line 16
- **Problem:** `_PAGE_CACHE` is a plain `dict` mutated by `_fetch_page` from six concurrent Answer Agent threads without any lock. Under high I/O contention, concurrent writes can silently corrupt the dict in CPython.
- **Fix:** Wrap reads and writes in a `threading.Lock()` (one-liner acquire/release), or replace with `functools.lru_cache` on a single-argument pure function.
- **Estimated time:** 15 minutes

**P1-3 · CRITICAL · `agents.py:_research_and_answer` — silent exhaustion of tool loop with no diagnostic**
- **File:** `agents.py` ~lines 792–803
- **Problem:** When all 3 iterations exhaust via `stop_reason == "tool_use"` (model stuck in tool loop), exits with `flag_reason = None` and `final_text = None`. Falls into parse-error flag path silently — token cost incurred 3× with no diagnostic.
- **Fix:** Add a sentinel before the loop's natural exit: emit a distinct `review_reason` string like `"Max iterations reached — model did not produce end_turn response"` so stuck loops are distinguishable from genuine parse failures.
- **Estimated time:** 15 minutes

**P1-10 · HIGH · `agents.py:process_document` and `process_rfp` — missing `completed[0]` increment on error path**
- **File:** `agents.py` ~lines 525 (process_document) and ~411–415 (process_rfp)
- **Problem:** When a future raises an exception, `flagged` is incremented but `completed[0]` is not. For a 50-question RFP with one error, the counter shows `[48/50]` at the end, and `processing_complete` reports `answered + flagged < total`.
- **Fix:** Increment `completed[0]` in the `except` block in **both** `process_document` and `process_rfp` before `continue`.
- **Estimated time:** 15 minutes

**P1-12 · HIGH · `agents.py:_review_answers` — duplicate ⚠ warnings stacked on multi-doc RFPs**
- **File:** `agents.py` ~lines 820–828
- **Problem:** `_review_answers(rfp_id)` runs once per document in the multi-doc flow. Any high-risk question already tagged from a prior document gets the warning note appended again.
- **Fix:** Guard with a check: only append warning if `"⚠ This requirement"` is not already present in `answer`.
- **Estimated time:** 10 minutes

---

### Frontend Engineer — Priority 1 Tasks

**P1-4 · DEMO-CRITICAL · `app.js:filterQuestions` — bare `event.target` global reference**
- **File:** `app.js` ~line 792
- **Problem:** Uses `event.target` as an implicit global rather than a passed parameter. Works in Chrome today but can produce a `TypeError` in strict mode — a demo crash risk mid-filter.
- **Fix:** Pass event explicitly: `onclick="filterQuestions('${esc(c)}', event)"` and update function signature to `function filterQuestions(category, event = null)`.
- **Estimated time:** 10 minutes

**P1-5 · DEMO-CRITICAL · `style.css:.activity-feed` — feed capped at 200px, competes with agent rows**
- **File:** `static/style.css` ~line 596
- **Problem:** During a live demo the feed fills quickly and shows a tiny scroll box while agent rows above compete for vertical attention. The "wow moment" is undermined.
- **Fix:** Increase `max-height` to `260px` or add `flex-grow: 1` so the feed expands naturally, keeping agent rows pinned above it.
- **Estimated time:** 10 minutes

**P1-6 · DEMO-CRITICAL · `app.js:renderHome` — empty state gives no directional cue to upload zone**
- **File:** `app.js:renderHome`
- **Problem:** Empty state copy ("Upload an RFP file above to get started") appears below a generic icon with no visual arrow pointing to the upload zone. A judge starting cold won't connect the two.
- **Fix:** Add an `↑` SVG arrow cue above the empty state text and change copy to: `"Drop your first RFP above to begin"`.
- **Estimated time:** 15 minutes

**P1-14 · HIGH · `app.js:buildQuestionsView` — filter active class lost after `approveQuestion` re-renders**
- **File:** `app.js:buildQuestionsView` and `approveQuestion`
- **Problem:** After `approveQuestion` re-renders `questions-container`, the filter-button row is rebuilt but the `active` class for the previously selected filter is not reapplied.
- **Fix:** After re-rendering in `approveQuestion`, call `filterQuestions(state.filterCategory, null)` to reapply the current filter without resetting to `"all"`.
- **Estimated time:** 15 minutes

---

## Priority 2 — Quick Wins
*Run these in parallel with Wave 1. Each takes under 10 minutes. All Frontend unless noted.*

### Frontend Engineer — Quick Wins

| QW # | File | Finding | Fix |
|---|---|---|---|
| QW-1 | `app.js:demoLibCard` | `JSON.parse` on plain ISO date string throws — confirmed_at shows blank | Replace with `formatDate(d.confirmed_at)` directly |
| QW-2 | `style.css:.agent-msg` | `white-space:nowrap` clips meaningful agent status messages | Remove `white-space:nowrap`, add `overflow-wrap:break-word` |
| QW-3 | `style.css:.upload-icon` | `opacity:.4` makes upload icon barely visible | Change to `opacity:.65` |
| QW-4 | `index.html:page-home` | Generic subtitle reads as marketing copy | Change to `"Drop a customer RFP file above — 7 agents respond in under 90 seconds"` |
| QW-5 | `app.js:confirmDemoPlan` | No loading state on confirm — double-click risk | `btn.disabled = true; btn.textContent = '⟳ Saving…'` at top of function |
| QW-12 | `style.css:.review-banner` | 8% amber opacity too subtle — banner missed during fast demo scroll | Increase to `rgba(245,166,35,.13)`, add `border-left:3px solid var(--amber)` |
| QW-13 | `app.js:rfpCard` | Delete button at equal weight to primary action — accidental hit risk | `margin-left:auto` on delete button to right-align |
| QW-14 | `index.html:sidebar` | API dot has no tooltip in collapsed mode | Add `title="API Connected"` / `title="API Not Set"` to `.sidebar-api` container |
| QW-15 | `app.js:openRfp` | No loading skeleton between card click and render — card click feels dead | Show `⟳ Loading…` skeleton before `API.get` call |
| QW-16 | `app.js:renderAgents` | Model tier badge rendered as plain text at `.72rem` — disappears visually | Wrap in `<span class="badge badge-blue/badge-green/badge-muted">` chip |

### Backend Engineer — Quick Wins

| QW # | File | Finding | Fix |
|---|---|---|---|
| QW-6 | `app.py:rerun_question_stream` | Dead local imports of `json` and `AgentPipeline` inside thread function | Delete both — already in scope at module level |
| QW-7 | `app.py:auth_callback` | Raw JWT string stored as email in session | Use `tokens.get("email")` from userinfo or decode JWT payload |
| QW-8 | `app.py:get_usage` | Unnecessary inline `import httpx` (already module-level) and `import warnings` | Remove both local imports |
| QW-9 | `export_handler.py:_export_xlsx` | Silent `break` on missing `req_col` produces blank export with no error | Raise `ValueError("Could not identify requirement column")` before loop |

### AI Pipeline Engineer — Quick Wins

| QW # | File | Finding | Fix |
|---|---|---|---|
| QW-10 | `agents.py:_OKTA_PAGES` | `"certifications"` and `"compliance"` both map to same URL — duplicate | Remove `"certifications"` key |
| QW-11 | `agents.py:_research_and_answer` | `_record` only called on clean `end_turn` — token usage from flag/tool calls not recorded | Call `_record` after each `client.messages.create` unconditionally |

---

## Wave 2 — After Wave 1 Completes (Sequential)

These items depend on Wave 1 changes being in place first.

**AI Pipeline Engineer — Wave 2:**
- **P1-11 · HIGH · `agents.py:_WEB_SEARCH_ENABLED` global read mid-pool** — snapshot `web_enabled = _WEB_SEARCH_ENABLED` once per `process_rfp` call before `ThreadPoolExecutor` block and pass as parameter to `_research_and_answer`. Depends on `process_rfp` call signature being stable after P1-10 fix.

**Frontend Engineer — Wave 2:**
- **P1-7 · DEMO-CRITICAL · `app.js:buildErrorPanel` — raw Python exception shown to user** — truncate `err` at 120 chars in `buildErrorPanel`: `const display = err.length > 120 ? err.slice(0, 120) + '…' : err;`. Cleaner once AI Pipeline P1-3 emits a clean sentinel string rather than a raw exception.
- **P1-13 · HIGH · `app.js:renderHome` — no API key warning at upload zone** — add `badge-amber` inline hint below upload zone when `!state.apiKeySet`. Requires Backend to confirm `/api/settings` exposes `api_key_set` reliably (it does — confirm before implementing).

---

## Priority 3 — Deferred (Do Not Touch Today)

These items are real improvements but create regression risk on a demo codebase. Defer to post-hackathon.

| # | Finding | Reason for deferral |
|---|---|---|
| D-1 | Extract `_sse_response(event_q)` helper from 5 identical SSE blocks | Touches every streaming route — regression surface too wide before demo |
| D-2 | Extract `_run_in_sse_thread(event_q, fn)` from 5 SSE thread starters | Same as D-1 |
| D-3 | Extract `_recalculate_rfp_scores(rfp_id)` from duplicate score recalc | Low correctness risk; both paths currently work |
| D-4 | Silent fallback in `export_all_documents` — log + skip instead | Edge case; logging improvement only |
| D-5 | Empty zip returns 200 instead of 404 in `export_rfp` | Minor protocol correctness; not demo-observable |
| D-6 | Analysis Agent truncation check on 100+ question RFPs | Requires calibration; safe with log warning |
| D-7 | `ai_search_knowledge_base` fetches first 100 KB entries — 515 unreachable | Data Engineer coordination required for FTS5 scope; promote post-demo |
| D-8 | `_do_web_search` breaks on first keyword match — multi-topic queries fetch one page | Quality improvement; tolerable for demo |
| D-9 | KB dedup check uses 80 chars — common-prefix questions skipped | Data quality; single-line fix but low demo impact |
| D-10 | `_fetch_page` suppresses all warnings process-wide | Operational hygiene; no demo impact |
| D-11 | `_KB_QUERY_CHARS = 150` constant — inconsistent truncation between pre-fetch and inline search | Performance tuning; define constant later |
| D-12 | Shared `httpx.Client` across agents — no connection reuse | Performance improvement; not observable in demo run |

---

## Cross-Agent Dependencies

| Dependency | Source | Target | Notes |
|---|---|---|---|
| P1-7 (Frontend error truncation) depends on P1-3 (AI Pipeline sentinel message) | AI Pipeline Engineer | Frontend Engineer | Frontend should wait for P1-3 before implementing P1-7 — cleaner message from pipeline makes truncation copy more meaningful |
| P1-13 (Frontend API key badge) depends on Backend confirming /api/settings shape | Backend Engineer | Frontend Engineer | `api_key_set` field is already in the response (app.py line 141) — Backend should confirm before Frontend implements |
| P1-11 (AI Pipeline web search snapshot) depends on P1-10 (process_rfp error path fix) | AI Pipeline Engineer | AI Pipeline Engineer | Same function — do P1-10 first, then P1-11 in Wave 2 |
| D-7 (KB search scope) if promoted requires Data Engineer coordination | AI Pipeline Engineer | Data Engineer | `db.search_knowledge_base` interface must support `limit=` param reliably — confirm before AI Pipeline changes call site |

---

## Commit Strategy

After each wave completes:

```bash
# Wave 1
git add app.py export_handler.py agents.py static/app.js templates/index.html static/style.css
git commit -m "fix(wave1): correctness bugs + demo-critical UX — 15 P1 items + 16 quick wins

Backend: multi-doc rerun crash, CSV wrong-row write, flagged export blank rows,
  dead imports, auth session fix, export validation
Pipeline: PAGE_CACHE thread safety, tool loop sentinel, progress counter,
  duplicate review warnings, token recording, duplicate OKTA_PAGES entry
Frontend: filterQuestions global crash, activity-feed height, empty state arrow,
  filter persistence, review banner contrast, model tier badges, loading states"

# Wave 2
git add app.py agents.py static/app.js
git commit -m "fix(wave2): web search global snapshot, error truncation, API key badge"

git push
```

Then sync to rfp-responder:
```bash
cp app.py agents.py export_handler.py C:\Users\ClaudeLeroux\rfp-responder\
cp static/app.js static/style.css C:\Users\ClaudeLeroux\rfp-responder\static\
cp templates/index.html C:\Users\ClaudeLeroux\rfp-responder\templates\
```

---

## What the Agent as Judge Will See

After Day 3 implementation:
- 2 thread-safety/correctness crashes fixed (PAGE_CACHE, rerun TypeError)
- Export produces complete, accurate output for all RFP types including multi-doc and flagged-only
- Demo flow has no TypeError risk during filter, confirm, or error paths
- Agent cards display model tier badges as proper styled chips
- Empty state guides first-time users directly to the upload zone
- Human review banner has sufficient contrast to catch judge attention
- Loading states on all async actions eliminate the "dead button" impression

---

## Assessment Sources

All findings come from the Day 2 parallel assessment wave:
- **Backend Engineer** assessment of `app.py` + `export_handler.py` (108K tokens)
- **AI Pipeline Engineer** assessment of `agents.py` (109K tokens)
- **Frontend Engineer** assessment of `app.js` + `index.html` + `style.css` (152K tokens)
- **Architect** synthesis and prioritization

Assessment committed: 2026-07-08, Day 2 session
