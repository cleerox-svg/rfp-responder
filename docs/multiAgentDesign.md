# NaughtRFP — Multi-Agent Architecture Design Document

**Version:** 1.0  
**Date:** 2026-07-07  
**Project:** NaughtRFP — AI-Powered RFP Responder for Okta Pre-Sales SEs  
**Codebase:** `agents.py`, `app.py` (Flask orchestration layer)  

---

## Table of Contents

1. [Problem and Motivation](#1-problem-and-motivation)
2. [Agent Roster](#2-agent-roster)
3. [Pipeline Diagram](#3-pipeline-diagram)
4. [Agentic Tool Use — The Answer Agent Loop](#4-agentic-tool-use--the-answer-agent-loop)
5. [Parallelism Design](#5-parallelism-design)
6. [Context Window Strategy](#6-context-window-strategy)
7. [Knowledge Base Architecture](#7-knowledge-base-architecture)
8. [Coordination Mechanism](#8-coordination-mechanism)
9. [Day 2 Design Seams](#9-day-2-design-seams)
10. [What Good Looks Like](#10-what-good-looks-like)

---

## 1. Problem and Motivation

### The Business Problem

Okta Pre-Sales Solutions Engineers spend 8–40 hours per RFP manually reading, assessing, and populating security and technical questionnaires. A typical security RFP contains 30–150 requirements spanning MFA, SSO, data residency, compliance certifications, incident response, and privileged access — each requiring a vendor response code (Full / Partial / Custom / Not Yet / Not Available) plus a written justification citing specific product capabilities.

Three structural problems compound this:

1. **Knowledge is siloed.** Each SE builds their own personal answer library. There is no shared institutional memory. The team's 615 Okta SIG Core pre-approved answers are not consistently used.
2. **Demo prep is disconnected.** After the RFP is done, the SE starts a demo plan from scratch without reference to what the customer actually asked about.
3. **Inconsistency creates risk.** Different SEs give different answers to the same question. High-risk questions (SLA commitments, data sovereignty, legal indemnification) are answered by individuals who may not have legal review visibility.

### Why Multi-Agent Rather Than Single-Agent

A single general-purpose agent handling a 34-question RFP end-to-end would face several hard constraints:

| Constraint | Single-agent failure mode | Multi-agent solution |
|---|---|---|
| Context window | All 34 questions + full KB + product knowledge saturates input context, degrading answer quality | Each Answer Agent worker handles one question at a time with only the relevant KB context |
| Hallucination risk | Without explicit tool calls, the model fills gaps from training data, producing plausible but unverifiable claims | The Answer Agent is constrained to a defined tool loop; if tools don't produce sufficient evidence, it must flag |
| Latency | Sequential answering of 34 questions takes 5–10 minutes at ~8s per API call | 6 parallel workers reduce wall-clock time by roughly 5x |
| Specialisation | A single agent must be instructed to simultaneously parse columns, identify risk, search the web, and write marketing copy — competing objectives degrade all of them | Each agent has one job and a system prompt calibrated for that job |
| Separation of concerns | A parsing error cascades into bad answers with no recovery point | Each agent writes to SQLite; failures in one stage are isolated and retryable |
| Compounding improvement | A single-pass system discards what it learned | The KB Ingestion Agent writes every good answer back to the KB, making future runs better |

The multi-agent design is not architectural ceremony — it is the mechanism by which the system avoids hallucination, runs at acceptable speed, and improves over time.

---

## 2. Agent Roster

The system contains nine specialised agents. Seven run in a linear pipeline for every RFP. Two are on-demand: KB Ingestion is triggered by the SE after review; Demo Prep is triggered by a UI button.

### Agent 1: Customer Detection Agent

| Attribute | Detail |
|---|---|
| **Class / function** | `detect_customer()` — standalone function called before the pipeline starts |
| **Model** | `claude-sonnet-4-6` |
| **Role** | Reads the raw file content and identifies the issuing organisation, industry, RFP reference number, scope, and estimated deployment scale |
| **Tools** | None — pure inference from file content sample |
| **Input** | File path (CSV/XLSX), filename; extracts up to 3,000 characters of raw content via `_sample_file_text()` |
| **Output** | Structured Python dict: `{customer_name, customer_short, rfp_number, project_name, industry, scope_summary, issuing_department, estimated_scale, confidence}` — written to `rfps.customer_info` (JSON) in SQLite |
| **Depends on** | File upload (pre-pipeline) |
| **Feeds into** | Demo Prep Agent (uses `customer_name`, `industry`, `scope_summary` to personalise demo plan) |
| **Failure mode** | Falls back to filename-derived values with confidence 0.2; never blocks the pipeline |

**Purpose:** Sets the context frame for everything downstream. The Demo Prep Agent uses this to produce a customer-named executive summary. The SE review UI displays it as a banner at the top of the RFP view.

---

### Agent 2: Parser Agent

| Attribute | Detail |
|---|---|
| **Class / method** | `AgentPipeline._parse_rfp()` |
| **Model** | `claude-sonnet-4-6` |
| **Role** | Identifies the semantic meaning of each column in the uploaded file — specifically which column contains requirements, which contains categories, which is for vendor responses — then extracts all valid requirement rows |
| **Tools** | None — pure inference from column headers and a 4-row sample |
| **Input** | Raw CSV/XLSX file; sends `headers_list` + `sample` (first 4 rows, max 120 chars per cell) to Claude |
| **Output** | JSON column mapping (`{requirement_column, category_column, priority_column, response_column, comments_column}`) + list of question dicts written to `questions` table in SQLite |
| **Depends on** | File I/O (openpyxl / csv.DictReader) |
| **Feeds into** | Analysis Agent (receives the question list); every subsequent agent works from questions written to SQLite by this agent |
| **Failure mode** | If AI column detection fails, falls back to the column with the highest total text length across the first 10 rows |

**Purpose:** RFPs have no standard column schema. Alberta Health Services, SaskPower, and a financial institution each have different spreadsheet structures. The Parser Agent makes the rest of the pipeline format-agnostic.

---

### Agent 3: Analysis Agent

| Attribute | Detail |
|---|---|
| **Class / method** | `AgentPipeline._analyze_questions()` |
| **Model** | `claude-sonnet-4-6` |
| **Role** | Reads all extracted requirements in a single batch and maps each to the relevant Okta product area(s) and a risk score |
| **Tools** | None — batch inference over the full question list |
| **Input** | Numbered list of all requirements (max 180 chars each), formatted as `[category] requirement_text` |
| **Output** | JSON array `[{index, okta_products, refined_category, risk_score}]` — merged back into the question dicts and written to `questions.okta_products`, `questions.category`, `questions.risk_score` in SQLite |
| **Depends on** | Parser Agent output |
| **Feeds into** | Research Agent (risk_score influences how urgently KB context is needed); Answer Agent (receives `okta_products` and `refined_category` as part of its prompt); Scoring Agent (reads `risk_score` from questions) |
| **Okta product options** | OIG, LCM, Workflows, SSO, MFA, Universal Directory, PAM, AI, Access Gateway, OIN |
| **Risk scoring** | 1 = low technical risk; 5 = legal/SLA/pricing commitment that requires legal review |

**Purpose:** Without this agent, every Answer Agent worker would have to infer product context from scratch for every question, burning tokens and introducing inconsistency. The Analysis Agent does it once for the whole RFP in a single LLM call, producing a product-tagged and risk-annotated question list that every downstream agent can use directly.

---

### Agent 4: Research Agent

| Attribute | Detail |
|---|---|
| **Class / method** | Part of `AgentPipeline.process_rfp()` — the KB pre-fetch block before the ThreadPoolExecutor starts |
| **Model** | None — this agent executes pure Python against SQLite FTS5; no LLM call |
| **Role** | Bulk pre-fetches the top 3 KB matches for every question before any Answer Agent worker starts |
| **Tools** | `db.search_knowledge_base(question_text[:150], limit=3)` — SQLite FTS5 multi-strategy search |
| **Input** | All question dicts from the Analysis Agent; queries the KB for each question's text |
| **Output** | `kb_cache: dict[question_id → list[kb_entries]]` — an in-memory Python dict passed directly into each Answer Agent worker via `pre_context` |
| **Depends on** | Analysis Agent output, SQLite knowledge base |
| **Feeds into** | All 6 Answer Agent workers (each receives its question's pre-fetched KB snippets at instantiation) |

**Purpose:** This is a deliberate performance optimisation. Without the pre-fetch, each of the 6 parallel Answer Agent workers would make its own `search_knowledge_base` tool call via the LLM, costing an extra API round-trip per question. With the pre-fetch, KB context is already in the worker's first message — the LLM reads it immediately and often does not need to call the KB tool at all. For a 34-question RFP with 6 workers, this eliminates up to 34 additional API calls.

---

### Agent 5: Answer Agent (x6 parallel workers)

| Attribute | Detail |
|---|---|
| **Class / method** | `AgentPipeline._research_and_answer()` — called once per question, runs in a `ThreadPoolExecutor` with 6 workers |
| **Model** | `claude-sonnet-4-6` |
| **Role** | Answers a single RFP requirement; the only agent with a genuine agentic tool-use loop |
| **Tools** | `search_knowledge_base` (SQLite FTS5), `search_web` (DuckDuckGo + targeted okta.com page fetcher), `flag_for_review` (writes flag to DB and terminates the loop) |
| **Input** | Single question dict (category, refined_category, priority, okta_products, question_text) + pre-loaded KB context injected as a JSON snippet in the first user message |
| **Output** | Structured JSON: `{response_code, answer, confidence, fit_score, risk_score, sources, okta_products}` — written to `questions` table in SQLite; or `{flagged: true, review_reason}` |
| **Depends on** | Research Agent pre-fetch (pre_context), SQLite KB (on-demand tool call), web search infrastructure |
| **Feeds into** | Scoring Agent (fit_score, risk_score aggregated across all answered questions); Review Agent (reads answers with high risk_score); export and SE review UI |
| **Max iterations** | 3 (hard limit enforced by the `for _ in range(3)` loop) |
| **max_tokens** | 768 |

This is the most architecturally significant agent and is described in full detail in Section 4.

---

### Agent 6: Scoring Agent

| Attribute | Detail |
|---|---|
| **Class / method** | Inline aggregation block in `AgentPipeline.process_rfp()` after the ThreadPoolExecutor completes |
| **Model** | None — pure Python arithmetic |
| **Role** | Computes the overall RFP fit score and risk score by averaging per-question scores across all answered questions |
| **Tools** | None |
| **Input** | `fit_scores` and `risk_scores` lists accumulated from Answer Agent results |
| **Output** | `avg_fit` and `avg_risk` (both 1–5 scale, rounded to 2dp) — written to `rfps.fit_score` and `rfps.risk_score` in SQLite; emitted as an SSE event to the UI |
| **Depends on** | Answer Agent outputs |
| **Feeds into** | RFP summary card in the UI; SE's go/no-go decision |

**Purpose:** Distils the per-question scoring into a deal-level signal. An SE can look at Fit: 4.2 / Risk: 3.8 and immediately understand whether this is a strong Okta fit with moderate commercial risk before reading a single answer.

---

### Agent 7: Review Agent

| Attribute | Detail |
|---|---|
| **Class / method** | `AgentPipeline._review_answers()` |
| **Model** | None — rule-based logic applied in Python |
| **Role** | Post-processes all answered questions; appends a human-visible high-risk warning note to any answered question with `risk_score >= 4` whose answer does not already contain legal/commercial language |
| **Tools** | None |
| **Input** | All answered questions for the RFP from SQLite |
| **Output** | Mutated `answer` text for high-risk questions (appends the warning note); written back to SQLite |
| **Depends on** | Answer Agent, Scoring Agent (risk scores must be set before Review Agent runs) |
| **Feeds into** | SE review UI (the warning note is visible inline); export (warning note is stripped on export by `export_handler`) |

**Purpose:** The Answer Agent scores risk but does not add warnings to the answer text. The Review Agent is the safety net that ensures an SE cannot accidentally approve a high-risk response without seeing an explicit flag. This separation means the business rule for what constitutes a high-risk warning can be changed in one place without touching the Answer Agent's prompting.

---

### Agent 8: KB Ingestion Agent (on-demand)

| Attribute | Detail |
|---|---|
| **Class** | `KnowledgeBaseAgent` |
| **Model** | None — pure Python; checks for duplicates and writes to SQLite |
| **Role** | After an SE completes review and approves a batch of answers, ingests all answered questions from that RFP into the shared knowledge base as new Q&A pairs |
| **Tools** | None — calls `db.search_knowledge_base()` for deduplication check, then `db.add_to_knowledge_base()` for each new entry |
| **Input** | `rfp_id` — reads all questions with `status="answered"` from SQLite |
| **Output** | New rows in the `knowledge_base` table; SSE event with ingestion count |
| **Depends on** | Completed RFP with at least one answered question |
| **Feeds into** | All future RFP runs (the pre-fetched KB context for future Answer Agent workers will include these entries) |
| **Trigger** | Manually triggered by the SE via the `/api/kb/ingest/{rfp_id}` endpoint; not part of the automatic pipeline |

**Purpose:** The mechanism for compounding improvement. Each approved RFP answer becomes a precedent that the next Answer Agent can find and reuse. An SE who answers a hard question about PIPEDA data residency once contributes that answer to every future team member running a similar RFP.

---

### Agent 9: Demo Prep Agent (on-demand)

| Attribute | Detail |
|---|---|
| **Class** | `DemoPrepAgent` |
| **Model** | `claude-sonnet-4-6` |
| **Role** | Generates a structured, customer-tailored demo plan from the completed RFP's answered requirements |
| **Tools** | None — single LLM call with a rich prompt |
| **Input** | Customer info (name, industry, scope from Customer Detection Agent), compact digest of all answered questions (id, category, requirement text, response_code, fit, risk, okta_products), flagged question count, optional customer-provided demo format |
| **Output** | JSON demo plan: `{executive_summary, total_minutes, sections:[{order, title, okta_products, priority, estimated_minutes, requirement_ids, demo_scenario, demo_steps, talking_points, differentiators}], questions_to_address, recommended_demo_env}` — written to `demo_plans` table in SQLite; plan_id returned |
| **Depends on** | Answer Agent outputs (must have at least one answered question) |
| **Feeds into** | Demo Library (SE can confirm plan to add it to the shared library); SE's demo preparation workflow |
| **Trigger** | Manually triggered by the SE via the UI "Generate Demo Plan" button; not part of the automatic pipeline |
| **max_tokens** | 8,000 — the largest output budget in the system, reflecting the structured richness of the plan |

**Purpose:** Closes the loop between RFP analysis and demo execution. Traditional demo prep starts from scratch. The Demo Prep Agent reads the exact requirements the customer asked about and maps them to ordered demo scenarios. The SE gets a ready-to-use script, not blank notes.

---

## 3. Pipeline Diagram

The following diagram shows the full execution flow from file upload to export.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  USER ACTION: Upload CSV/XLSX file(s)                                       │
│  Flask route: /api/rfp/upload                                               │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  QUICK SCAN (rule-based, no API)                                            │
│  - Parse columns, count priority levels                                     │
│  - Detect risky keywords (SLA, GDPR, FedRAMP, PIPEDA, etc.)                │
│  - Compute preliminary risk score                                           │
│  Output: risk_profile + upload_preview → SQLite rfps table                 │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  [0] CUSTOMER DETECTION AGENT                                               │
│  - Samples up to 3,000 chars of raw file content                           │
│  - Infers: customer name, industry, RFP number, scope, scale               │
│  - Single LLM call; JSON output                                             │
│  Output: rfps.customer_info (JSON blob)                                     │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  [1] PARSER AGENT                                                           │
│  - Sends column headers + 4-row sample to Claude                           │
│  - Identifies: requirement col, category col, priority col, response col   │
│  - Extracts all valid requirement rows (deduped, min 10 chars)             │
│  - Writes each requirement as a question row to SQLite                     │
│  Output: List[question dict], N questions in SQLite questions table        │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  [2] ANALYSIS AGENT                                                         │
│  - Sends all N requirements in one batch call                               │
│  - Maps each to Okta product area(s): OIG, LCM, SSO, MFA, PAM, etc.       │
│  - Assigns risk score 1–5 per requirement                                  │
│  - Refines category labels                                                  │
│  Output: okta_products + refined_category + risk_score → SQLite            │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  [3] RESEARCH AGENT (KB pre-fetch, no LLM)                                 │
│  - Iterates all N questions                                                 │
│  - Runs SQLite FTS5 search for each (question_text[:150], limit=3)         │
│  - Populates in-memory kb_cache: {question_id → [kb_entry, ...]}          │
│  Output: kb_cache dict passed directly to Answer Agent workers             │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  [4] ANSWER AGENT — ThreadPoolExecutor (6 parallel workers)                │
│                                                                             │
│   Worker 1    Worker 2    Worker 3    Worker 4    Worker 5    Worker 6     │
│   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐      │
│   │ Q[0] │   │ Q[1] │   │ Q[2] │   │ Q[3] │   │ Q[4] │   │ Q[5] │      │
│   └──────┘   └──────┘   └──────┘   └──────┘   └──────┘   └──────┘      │
│   Q[6] next  Q[7] next  ...                                               │
│                                                                             │
│   Each worker runs _research_and_answer():                                 │
│   1. Inject pre-fetched KB context into first message                      │
│   2. LLM call with tools: search_kb, search_web, flag_for_review          │
│   3. If tool_use → execute tool → append result → repeat (max 3 iters)   │
│   4. If end_turn → parse JSON answer → write to SQLite                    │
│   5. If flag_for_review → write flagged status → return                   │
│                                                                             │
│  Progress events → SSE event_queue → Flask /api/rfp/{id}/process stream  │
│  Output: answered/flagged questions written to SQLite questions table      │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  [5] SCORING AGENT (no LLM)                                                │
│  - avg_fit  = mean(fit_score  for all answered questions)                  │
│  - avg_risk = mean(risk_score for all answered questions)                  │
│  Output: rfps.fit_score, rfps.risk_score → SQLite                         │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  [6] REVIEW AGENT (rule-based, no LLM)                                     │
│  - For each answered question with risk_score >= 4:                        │
│    Append high-risk warning note to answer text                            │
│  Output: mutated answer text → SQLite                                      │
│  rfps.status = "complete"                                                   │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
        ┌───────────────────┐  ┌──────────────────────────────────────────┐
        │  SE REVIEW UI     │  │  PIPELINE COMPLETE EVENT (SSE)            │
        │  - Questions grid │  │  {rfp_id, fit_score, risk_score,          │
        │  - Human review   │  │   answered, flagged, total}               │
        │  - Inline edit    │  └──────────────────────────────────────────┘
        │  - Per-Q rerun    │
        └────────┬──────────┘
                 │
        ┌────────┴──────────────────────────────────────────────┐
        │                                                        │
        ▼                                                        ▼
┌──────────────────────────────┐           ┌────────────────────────────────┐
│  [7] KB INGESTION AGENT      │           │  [8] DEMO PREP AGENT           │
│  (on-demand, SE-triggered)   │           │  (on-demand, SE-triggered)     │
│                              │           │                                │
│  - Reads all answered Qs     │           │  - Reads answered Qs digest    │
│  - Dedup check vs KB         │           │  - Reads customer_info         │
│  - Writes new entries to     │           │  - Single LLM call, JSON plan  │
│    knowledge_base table      │           │  - {sections, steps, talking   │
│  - Compounds KB for future   │           │    points, differentiators}    │
│    RFP runs                  │           │  - Writes to demo_plans table  │
└──────────────────────────────┘           └──────────────────┬─────────────┘
                                                              │
                                                              ▼
                                           ┌────────────────────────────────┐
                                           │  DEMO LIBRARY                  │
                                           │  SE confirms plan → saved for  │
                                           │  team reuse                    │
                                           └────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXPORT                                                                     │
│  - Restores original CSV or XLSX structure                                 │
│  - Populates response code + vendor comments columns                       │
│  - Colour-codes response codes (green=F, yellow=P, orange=C, red=N)       │
│  - Strips internal citations and high-risk warning notes                   │
│  - Returns file to SE as download                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Agentic Tool Use — The Answer Agent Loop

The Answer Agent is the only agent in the system that runs a genuine agentic tool-use loop. Every other agent makes a single structured LLM call or runs purely in Python. The Answer Agent iterates — it can change direction mid-execution based on what tools return.

### Tools Available

| Tool name | Description | Backend implementation |
|---|---|---|
| `search_knowledge_base` | Search past RFP answers in the local KB | SQLite FTS5 multi-strategy search; returns up to 3 entries with question, answer, category |
| `search_web` | Search for current Okta information online | DuckDuckGo Instant Answer API (site-restricted to okta.com + trust.okta.com) + targeted page fetch + Claude summariser |
| `flag_for_review` | Flag this requirement for human review; terminates the answer loop | Writes flagged status and reason to SQLite; breaks the iteration loop |

### The Tool Loop — Step by Step

```
                   ┌──────────────────────────────────────────────┐
                   │  FIRST MESSAGE (assembled before LLM call)   │
                   │                                              │
                   │  System prompt:                              │
                   │  - OKTA_KNOWLEDGE constant (200 lines)       │
                   │  - Response code definitions (F/P/C/NE/N)    │
                   │  - Confidence threshold rules                │
                   │  - "Flag if <60% confident or legal/SLA"     │
                   │                                              │
                   │  User message:                               │
                   │  - Category, priority, okta_products         │
                   │  - Full requirement text                     │
                   │  - kb_hint: JSON array of 0-3 pre-fetched    │
                   │    KB entries (from Research Agent)          │
                   │  - Instruction: use KB hint if relevant,     │
                   │    else call search_knowledge_base           │
                   └──────────────────────┬───────────────────────┘
                                          │
                                          ▼
                   ┌──────────────────────────────────────────────┐
                   │  ITERATION 1 — LLM decides:                  │
                   └────┬───────────────────────────┬─────────────┘
                        │                           │
              ┌─────────▼──────────┐    ┌───────────▼──────────────┐
              │  stop_reason =     │    │  stop_reason = "tool_use" │
              │  "end_turn"        │    │  (at most 3 iterations)   │
              │                    │    └───────────┬───────────────┘
              │  Parse JSON from   │                │
              │  response text     │       ┌────────▼──────────────────────────┐
              │  → write to SQLite │       │  Which tool(s) called?            │
              │  → return answer   │       └──┬─────────────┬──────────────────┘
              └────────────────────┘          │             │
                                              │             │
               ┌──────────────────────────────▼──┐   ┌─────▼──────────────────────────┐
               │  search_knowledge_base           │   │  search_web                   │
               │                                 │   │                               │
               │  - Calls db.search_knowledge_   │   │  1. DuckDuckGo API query      │
               │    base(query, limit=3)          │   │     (site:okta.com)           │
               │  - Multi-strategy FTS5 search   │   │  2. Keyword-matched okta.com  │
               │  - Returns JSON array of hits   │   │     page fetched (1h cache)   │
               │  - "No results" if empty        │   │  3. Claude summarises to      │
               └──────────────────────────────┬──┘   │     3-5 bullet facts         │
                                              │      │  - Returns summary string     │
                                              │      └──────────────────┬────────────┘
                                              │                         │
                                              └────────────┬────────────┘
                                                           │
                       ┌───────────────────────────────────▼──────────────────────────┐
                       │  flag_for_review (terminates loop immediately)                │
                       │                                                               │
                       │  Triggered by the model when:                                │
                       │  - Confidence < 60%                                          │
                       │  - Requirement involves pricing, SLA, legal indemnification  │
                       │  - KB + web search both returned insufficient evidence       │
                       │  - Highly custom / environment-specific scenario             │
                       │                                                               │
                       │  Action: writes {status="flagged", needs_review=1,           │
                       │  review_reason=reason} to SQLite                             │
                       │  Loop exits; returns {flagged: True, review_reason}          │
                       └───────────────────────────────────────────────────────────────┘
```

### Decision Logic and Anti-Hallucination

The Answer Agent's system prompt contains an explicit evidence hierarchy:

1. **Pre-loaded KB context** — if the Research Agent found relevant KB entries and they are injected in the first message, the model is instructed to use them directly before calling any tool.
2. **search_knowledge_base** — if pre-loaded context is absent or insufficient, the model calls this tool to search for additional KB entries.
3. **search_web** — only called when the KB cannot support the answer. The web search is restricted to `okta.com` and `trust.okta.com`, preventing the model from citing non-authoritative sources.
4. **flag_for_review** — if neither KB nor web search produces sufficient evidence, or if the requirement contains pricing/SLA/legal language, the model calls this tool. It cannot proceed to produce a fabricated answer — calling `flag_for_review` terminates the loop.

The `flag_for_review` tool is the hallucination guard. The model does not have an option to say "I think" or "typically" and produce an unverified answer. Its only exit from insufficient evidence is to flag.

### Why max_iterations = 3

Three iterations is the maximum useful depth for a single-question answer:
- **Iteration 1:** LLM reads pre-loaded KB context, calls `search_knowledge_base` if needed
- **Iteration 2:** LLM reads KB results, calls `search_web` if still insufficient
- **Iteration 3:** LLM reads web results, either produces final JSON answer or calls `flag_for_review`

Four or more iterations would indicate the model is looping without converging — a pathological state that max_iterations = 3 prevents. The 768-token output budget also constrains answers to 2–4 sentences, preventing verbose, unverifiable elaboration.

---

## 5. Parallelism Design

### The ThreadPoolExecutor Pattern

```python
_ANSWER_WORKERS = 6

with ThreadPoolExecutor(max_workers=_ANSWER_WORKERS) as pool:
    futures = {pool.submit(_process_one, (i, q)): i
               for i, q in enumerate(questions)}
    for future in as_completed(futures):
        idx, q, result = future.result()
        # accumulate fit_scores, risk_scores
        # emit SSE progress event
```

All 34 questions are submitted to the pool at once. The executor maintains at most 6 active threads. Completed futures are processed as they arrive via `as_completed()`, allowing SSE progress events to fire continuously as answers complete rather than waiting for the full batch.

### Why 6 Workers

| Consideration | Detail |
|---|---|
| **API rate limits** | Okta's LiteLLM proxy enforces per-key RPM and TPM limits. At 6 workers, each Answer Agent worker makes 1–3 calls. 6 × 3 = 18 max concurrent calls, staying well within typical LiteLLM limits |
| **SQLite thread safety** | The `Database` class uses thread-local connections. Each worker gets its own connection, eliminating write contention |
| **Diminishing returns** | The bottleneck is API latency (~3–8s per call), not local compute. Beyond 8–10 workers, queuing at the API proxy negates the parallelism benefit |
| **Machine resources** | This is a developer laptop / hackathon laptop target. 6 threads is lightweight |

### Research Agent Pre-fetch — Why It Matters

Without the pre-fetch:
- Each Answer Agent worker's first action is to call `search_knowledge_base` via a tool call
- A tool call requires an LLM call (to let Claude invoke the tool) + a Python function call + another LLM call (to continue with the result)
- For 34 questions with ~80% KB hit rate: approximately 27 extra API calls

With the pre-fetch:
- The Research Agent runs a direct SQLite query for each question before the pool starts
- Each worker receives its KB context in the first user message — no tool call needed for KB in most cases
- The LLM reads the injected context, often resolves to `end_turn` in one call rather than three
- Estimated savings: 20–27 API calls eliminated; wall-clock reduction of roughly 60–90 seconds on a 34-question RFP

The pre-fetch is an example of optimising at the system level (batch the KB lookups once) rather than the agent level (each agent does its own lookup).

---

## 6. Context Window Strategy

Each agent is deliberately given the minimum context required to do its job. This is not just an efficiency decision — it is a quality decision. LLMs perform worse when the input context contains irrelevant information.

### Per-Agent Context Budget

| Agent | Input size | What is excluded | Why |
|---|---|---|---|
| Customer Detection | 3,000 chars of raw file content | Full question list | Customer info is readable from file headers and preamble, not from individual requirements |
| Parser | Column headers + 4-row sample (max 120 chars/cell) | All other rows | Column structure is determinable from a small sample; adding all rows would push beyond the useful window |
| Analysis | Full question list (max 180 chars/question) | KB, web content, customer info | Analysis is a classification task; adding KB context would bias the risk scoring |
| Answer Agent | Single question + pre-loaded KB snippets (max 250 chars each) + OKTA_KNOWLEDGE constant | Other questions, full KB, customer info | Limits hallucination surface to the specific topic; OKTA_KNOWLEDGE provides product facts as a grounding layer |
| Demo Prep | Compact question digest (max 150 chars/question, first 30 questions) + customer info | Individual answers, sources, review notes | Demo plan needs strategic shape, not verbatim answer text |

### Injected Context vs. Tool Context

The system uses two mechanisms for providing context to the Answer Agent:

**Injected context** (pre-fetched KB snippets): Written into the first user message as a JSON block. Counted against the input token budget but saves a full tool-call round trip. Used when the Research Agent found relevant KB entries.

**Tool-returned context** (on-demand KB search and web search): Returned as `tool_result` messages in subsequent turns. Each is capped at 300 chars for KB entries and 800 chars for web search summaries. This prevents a single verbose KB entry or noisy web page from consuming the majority of the answer agent's context budget.

### max_tokens = 768

The Answer Agent's output budget is 768 tokens — enough for a 2–4 sentence answer in the structured JSON format, with room for the confidence score, response code, product tags, and sources list. This hard cap prevents the model from producing verbose, un-reviewable answers that an SE would have to trim before submitting.

---

## 7. Knowledge Base Architecture

The knowledge base is the compounding differentiator of NaughtRFP. Unlike a one-shot AI tool that starts fresh every time, NaughtRFP's KB grows with every RFP processed.

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 3 — COMPOUNDING (grows over time)                       │
│                                                                 │
│  Past RFP ingestion: answered questions from completed RFPs    │
│  Ingested by KnowledgeBaseAgent after SE review and approval   │
│  Quality: vetted by a human SE before ingestion                │
│  Coverage: expands with every new customer / use case          │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────┐
│  LAYER 2 — HAND-CRAFTED BASELINE (~25 entries)                 │
│                                                                 │
│  Custom Q&A authored for common Okta RFP topics:               │
│  - Adaptive MFA and passwordless auth                          │
│  - 99.99% uptime SLA and trust portal                         │
│  - Data residency: US, EU, Canada (PIPEDA compliant)          │
│  - FedRAMP High, SOC 2 Type II, ISO 27001                     │
│  - Universal Directory, lifecycle management                   │
│  - Okta Integration Network (7,000+ apps)                     │
│  Quality: hand-authored, reviewed                              │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────┐
│  LAYER 1 — SIG CORE SEED (~615 entries)                        │
│                                                                 │
│  Okta's own SIG Core 2024 pre-approved security questionnaire  │
│  responses. Seeded from Okta_SIG_Core.xlsm at first run.      │
│  Categories: access control, authentication, encryption,       │
│  incident response, data handling, business continuity, etc.   │
│  Quality: Okta official; legally reviewed and approved         │
└─────────────────────────────────────────────────────────────────┘
```

### SQLite Schema

```sql
CREATE TABLE knowledge_base (
    id              INTEGER PRIMARY KEY,
    source_rfp_name TEXT,
    category        TEXT,
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    response_code   TEXT,
    okta_products   TEXT,         -- JSON array
    confidence      REAL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE kb_fts USING fts5(
    question, answer, category,
    content="knowledge_base",
    content_rowid="id"
);
```

### FTS5 Multi-Strategy Search

The KB search function uses a cascade of four strategies, falling through to the next when no results are found:

```
Strategy 1: FTS5 phrase match        "multi-factor authentication"
                    │ (no results)
                    ▼
Strategy 2: FTS5 prefix-AND match    multi* AND factor* AND authentication*
                    │ (no results)
                    ▼
Strategy 3: FTS5 prefix-OR match     multi* OR factor* OR authentication*
                    │ (no results)
                    ▼
Strategy 4: LIKE fallback            question LIKE '%authentication%'
                                     OR answer LIKE '%authentication%'
```

This cascade handles:
- Exact phrase matches (most common for seeded SIG Core entries)
- Variant forms and plurals (prefix wildcards)
- Broad topical queries where any one keyword is sufficient
- Legacy entries that may not be in the FTS5 index

### AI Semantic Search Layer

In addition to FTS5, the `/api/kb/search?ai=true` endpoint provides an AI-powered semantic search via `ai_search_knowledge_base()`:

1. Loads up to 60 KB entries (truncated summaries) into the prompt
2. Calls Claude with liberal matching rules: match acronyms (DR=disaster recovery, SoD=separation of duties), match by context and intent, not just exact keywords
3. Returns:
   - **Indices:** the 1–10 most relevant KB entries
   - **BLUF (Bottom Line Up Front):** a 2–4 sentence synthesis of Okta's position on the topic, military-style (most important fact first)
   - **Explanations:** why each matched entry is relevant

The BLUF is the key UX output — an SE searching for "data residency Canada" gets a direct synthesis, not a raw list of entries to read through.

---

## 8. Coordination Mechanism

The nine agents do not communicate via message queues or API calls to each other. They share state through two coordination channels:

### SQLite as Shared State

SQLite is the single source of truth for the entire pipeline. Every agent reads from and writes to specific tables:

| Agent | Reads from | Writes to |
|---|---|---|
| Customer Detection | File (raw bytes) | `rfps.customer_info` |
| Parser | File (structured) | `questions` (creates rows) |
| Analysis | `questions` | `questions.okta_products`, `.category`, `.risk_score` |
| Research | `questions`, `knowledge_base` | In-memory `kb_cache` only |
| Answer | `questions` (one row), `knowledge_base` (via tool) | `questions.answer`, `.response_code`, `.confidence`, `.fit_score`, `.risk_score`, `.status` |
| Scoring | `questions.fit_score`, `.risk_score` | `rfps.fit_score`, `rfps.risk_score` |
| Review | `questions.risk_score`, `.answer` | `questions.answer` (appends note) |
| KB Ingestion | `questions` (answered rows) | `knowledge_base`, `kb_fts` |
| Demo Prep | `questions`, `rfps.customer_info` | `demo_plans` |

SQLite is used in WAL (Write-Ahead Logging) mode with thread-local connections. This allows concurrent reads during the parallel Answer Agent phase without blocking, and allows writes from different workers to serialise without deadlock.

### SSE Event Queue as UI Feed

The second coordination channel is the SSE event queue — a Python `queue.Queue()` instance created per processing run and shared between the pipeline and the Flask streaming endpoint.

```python
event_q = queue.Queue()

# Flask creates queue, starts background thread with pipeline
threading.Thread(target=run, daemon=True).start()

# Flask streams events from the queue to the browser
def generate():
    while True:
        ev = event_q.get()
        if ev is None:   # sentinel — pipeline finished
            break
        yield f"data: {json.dumps(ev)}\n\n"
```

Every agent calls `self.emit()` before and after significant work. The emitted events are structured Python dicts:

```python
{
    "type":      "agent_start" | "agent_complete" | "agent_progress" | "processing_complete" | "error",
    "agent":     "Answer Agent",
    "message":   "[12/34] ✓ [F] Fit:4/5  Risk:2/5",
    "timestamp": 1720000000.0,
    "data":      {"current": 12, "total": 34}   # optional
}
```

The browser receives these events and renders them in the live agent activity feed — a real-time scrolling log showing which agent is running, what it found, and how many questions have been answered so far.

### Structured Python Dicts Between Agent Methods

Within the AgentPipeline class, agents pass data as Python dicts through method return values. There is no serialisation overhead between agents in the same pipeline run:

```
_parse_rfp()       → returns List[dict]  (question list)
_analyze_questions() → mutates List[dict] in-place (adds okta_products, risk_score)
kb_cache           → dict[int → List[dict]] (Research Agent output)
_research_and_answer() → returns dict (answer data or {flagged: True})
```

The question list never needs to be serialised and deserialised between agents because they run in the same Python process. SQLite is written after each agent completes, providing persistence for recovery and for the SE review UI, but the in-process pipeline uses direct Python object passing.

---

## 9. Day 2 Design Seams

The current system is a monolith — all agents run in the same Python process, share the same SQLite database, and communicate in-process. This is the right choice for a hackathon POC. But the agent boundaries are cleanly drawn, and the system would split naturally into independently deployable Claude Code sub-agents along the following seams:

### Sub-Agent 1: Ingestion Sub-Agent

**Owns:** Customer Detection Agent + Parser Agent  
**Trigger:** New file upload event  
**Input contract:** File path (CSV/XLSX), RFP project ID  
**Output contract:** Writes question rows to `questions` table; writes `rfps.customer_info`; emits `parse_complete` event with question count  
**Shared state reads:** None (file is the input)  
**Shared state writes:** `rfps.customer_info`, `questions` (creates rows)  
**Independent because:** This sub-agent only needs file I/O and LLM access. It does not need the KB, web search, or any other agent's output. A separate service could handle multi-format ingestion (adding PDF, Word, Google Sheets support) without touching the answer pipeline.

---

### Sub-Agent 2: Analysis Sub-Agent

**Owns:** Analysis Agent  
**Trigger:** `parse_complete` event (or polling for questions in `status="pending"`)  
**Input contract:** List of question IDs for an RFP project  
**Output contract:** Writes `okta_products`, `refined_category`, `risk_score` to `questions` table; emits `analysis_complete` event  
**Shared state reads:** `questions` (reads text)  
**Shared state writes:** `questions.okta_products`, `questions.category`, `questions.risk_score`  
**Independent because:** Classification of product areas and risk levels is a single-shot inference task with no dependencies on the KB or web. It could run on a cheaper model than the Answer Agent (e.g., Haiku for classification, Sonnet for answering).

---

### Sub-Agent 3: Answer Sub-Agent

**Owns:** Research Agent (pre-fetch) + Answer Agent (parallel workers)  
**Trigger:** `analysis_complete` event  
**Input contract:** List of question IDs; KB access credentials  
**Output contract:** Writes `answer`, `response_code`, `confidence`, `fit_score`, `risk_score`, `sources`, `status` to each question row; emits `answer_complete` events with progress  
**Shared state reads:** `questions.question_text`, `questions.okta_products`, `questions.category`, `knowledge_base`  
**Shared state writes:** `questions.answer`, `questions.status`, `questions.confidence`, etc.  
**Independent because:** This is the most compute-intensive and latency-sensitive sub-agent. Running it independently allows scaling the worker count independently of the rest of the pipeline. In a multi-tenant deployment, you could run 10 Answer Sub-Agents concurrently without affecting ingestion or analysis throughput.

---

### Sub-Agent 4: Quality Sub-Agent

**Owns:** Scoring Agent + Review Agent  
**Trigger:** `answer_complete` for all questions in the RFP (or a threshold percentage)  
**Input contract:** RFP ID  
**Output contract:** Writes `rfps.fit_score`, `rfps.risk_score`; appends high-risk warning notes to relevant answers; emits `quality_complete` event  
**Shared state reads:** `questions.fit_score`, `questions.risk_score`, `questions.answer`  
**Shared state writes:** `rfps.fit_score`, `rfps.risk_score`, `questions.answer` (warning notes)  
**Independent because:** Quality assessment is a post-processing pass. It can run after any subset of questions complete, making it suitable for incremental processing as answers come in rather than waiting for the full batch. It could also be extended to call Claude for deeper semantic review of high-risk answers.

---

### Sub-Agent 5: Knowledge Sub-Agent

**Owns:** KB Ingestion Agent + KB search (FTS5 + AI semantic)  
**Trigger:** SE-triggered ingestion request; direct KB search queries  
**Input contract:** RFP ID for ingestion; query string for search  
**Output contract:** Writes to `knowledge_base` and `kb_fts`; returns search results with optional BLUF  
**Shared state reads:** `questions` (answered rows for ingestion); `knowledge_base` (for search)  
**Shared state writes:** `knowledge_base`, `kb_fts`  
**Independent because:** The KB is a shared resource across all RFP projects. Extracting it as a sub-agent allows the KB to become a standalone service with its own API — other tools (email drafting, proposal writing) could query it without being part of the RFP pipeline.

---

### Sub-Agent 6: Demo Sub-Agent

**Owns:** Demo Prep Agent + Demo Library  
**Trigger:** SE-triggered demo plan request  
**Input contract:** RFP ID; optional customer_format string  
**Output contract:** Writes to `demo_plans`; returns plan_id; emits `demo_ready` event  
**Shared state reads:** `questions` (answered digest), `rfps.customer_info`  
**Shared state writes:** `demo_plans`  
**Independent because:** Demo preparation is entirely post-pipeline. It could run asynchronously — an SE could trigger it and come back an hour later to find the plan ready. It has no dependency on the answer pipeline being live.

---

### Day 2 Communication Protocol

When deployed as independent sub-agents, the coordination mechanism would shift from in-process Python dicts to:

- **Events:** A lightweight message queue (Redis Streams or a simple webhook) emitting typed events between sub-agents
- **Shared state:** The SQLite database promoted to PostgreSQL for multi-process write safety
- **SSE:** The Flask streaming layer reads from the same event queue, so the UI change is minimal — events now originate from multiple sub-agents rather than one pipeline class

The current SQLite schema is already the right shape for this migration — each sub-agent's read/write surface is well-defined and non-overlapping.

---

## 10. What Good Looks Like

### How NaughtRFP Demonstrates Agentic AI

**Multi-agent coordination:** Nine agents with distinct roles coordinate through structured data handoffs rather than a monolithic prompt. The Parser Agent's output is the Analysis Agent's input. The Research Agent's pre-fetch is the Answer Agent's context. The Answer Agent's approved output is the KB Ingestion Agent's raw material. Each agent has a single responsibility and clean handoff contracts.

**Genuine tool use:** The Answer Agent does not produce answers from memory. It executes a tool loop: search KB, evaluate results, search web if needed, evaluate again, and either produce a structured JSON answer with cited sources or call `flag_for_review`. The tool calls are real function calls that hit SQLite and the DuckDuckGo API — they are not simulated. The result of each tool call changes what the model does next.

**Appropriate refusal:** The `flag_for_review` tool is the system's refusal mechanism. When the model lacks sufficient evidence, or when the requirement touches pricing, SLA, or legal commitment, it calls `flag_for_review` instead of generating a plausible but unverifiable answer. This is explicit and observable — flagged questions appear in the Human Review view with a specific reason. The system never submits a guess.

**Compounding knowledge:** Every RFP processed improves the system for the next one. The KB Ingestion Agent writes human-approved answers back to the knowledge base. The first time an SE answers a PIPEDA data residency question, the next SE gets that answer pre-loaded. Over a year of use, the Answer Agent's pre-fetch hit rate trends toward 100% for common question types — the tool loop shortens, API costs drop, and answer quality improves simultaneously.

**Observable execution:** The SSE live feed makes the multi-agent behaviour visible. A judge watching the demo sees: Customer Agent identifying AHS, Parser Agent extracting 34 requirements, Analysis Agent mapping them to Okta products, Research Agent completing the KB pre-fetch, and then 6 parallel Answer Agent workers completing in overlapping order — each emitting a `[N/34] ✓ [F] Fit:4/5 Risk:2/5` or `[N/34] ⚑ Flagged: requires legal review` event in real time. This is not a progress bar over a batch script. It is agentic AI made legible.

### Metrics That Prove the System Works

| Metric | Target (POC) | Interpretation |
|---|---|---|
| Auto-answer rate | > 70% of requirements answered without human intervention | The KB seed and web search provide sufficient coverage for most standard security requirements |
| Flag precision | > 80% of flagged questions contain pricing, SLA, or legal language | The flag threshold is calibrated correctly; flags are meaningful, not noise |
| Pipeline wall-clock time | < 4 minutes for a 34-question RFP | 6 parallel workers at ~5s per question = ~30s of serial time; realistic API latency puts this at 2–4 minutes |
| KB hit rate | > 60% of questions find a pre-fetched KB match | The SIG Core seed is comprehensive enough that most security categories return a relevant entry |
| Export fidelity | 100% of source file structure preserved; internal notes stripped | The export_handler correctly distinguishes vendor-facing content from internal annotations |

---

*End of document. Total agents: 9. Pipeline agents: 7 (sequential). On-demand agents: 2 (KB Ingestion, Demo Prep). Parallel workers: 6 (Answer Agent). Shared state: SQLite + SSE event queue. Model: claude-sonnet-4-6 throughout.*
