# NaughtRFP — AI-Powered RFP Responder

> **Hackathon submission — Okta Pre-Sales SE Team | Theme: Agentic AI | July 2026**

NaughtRFP is an autonomous, multi-agent platform that transforms how Solutions Engineers respond to Request for Proposals (RFPs). Instead of manually answering hundreds of security and technical requirements, nine specialised AI agents collaborate in real time to parse, analyse, research, answer, score, and review each requirement — all while building a growing knowledge base from every completed RFP.

---

## For Judges — Quick Start

**Requirements:** Python 3.11+, access to `llm.atko.ai` (Okta internal LiteLLM proxy)

### Mac / Linux (one command)
```bash
bash setup.sh
# Follow the prompt to add your key to .env, then:
source venv/bin/activate
python app.py
```

### Windows
```bash
# 1. Install dependencies
py -m pip install flask anthropic openpyxl python-docx pdfplumber

# 2. Configure credentials
copy .env.example .env
# Edit .env: set LITELLM_API_KEY=sk-your-key-here

# 3. Start
py app.py
```

Open `http://localhost:5000` in your browser.

**No UI configuration needed** — the app reads `.env` on startup and bootstraps all settings automatically. Go straight to uploading an RFP.

**Test RFP included:** `sample_rfp.csv` — a 34-requirement Identity Governance RFP ready to process. Upload it from the Dashboard to see all 9 agents run.

**Authentication note:** Okta OIDC authentication is implemented but **disabled by default** so you can access the app without an Okta account. The auth plumbing (login, callback, logout routes + Settings UI) is visible in `app.py` and the Settings page. Enable it via Settings → Okta Authentication if you want to test the auth flow.

**Knowledge base:** The app ships with 25 baseline Okta Q&A entries. To load the full 657-entry KB (SIG Core 2024 + Confluence compliance), run:
```bash
py seed_sig.py        # 615 entries from Okta_SIG_Core.xlsm
py seed_confluence.py # 15 entries from internal Confluence docs
```
The baseline KB is sufficient to demo the agent pipeline.

---

## Agent Team (Claude Code Sub-Agents)

This project uses a two-tier team of Claude Code sub-agents to manage the build. See [`docs/multiAgentDesign.md`](docs/multiAgentDesign.md) for the full design rationale and [`.claude/agents/`](.claude/agents/) for all agent definitions.

**Tier 1 — Strategic:** Product Owner · Architect · Project Manager

**Tier 2 — Implementation:** Backend Engineer · Frontend Engineer · Data Engineer · AI Pipeline Engineer · Integration Specialist

**First task sequence:** Spawn all 5 implementation agents in parallel for the assessment wave → Architect synthesizes → PM sequences → parallel implementation waves.

---

## Table of Contents

1. [The Problem](#the-problem)
2. [What It Does](#what-it-does)
3. [Agent Architecture](#agent-architecture)
4. [Key Features](#key-features)
5. [Knowledge Base](#knowledge-base)
6. [Technology Stack](#technology-stack)
7. [Setup & Running](#setup--running)
8. [Application Screens](#application-screens)
9. [API Reference](#api-reference)
10. [Performance](#performance)
11. [File Structure](#file-structure)

---

## The Problem

Enterprise RFPs for identity and governance platforms contain **50–300+ technical and security requirements** that need accurate, consistent vendor responses. For Okta Pre-Sales SEs:

- Each RFP takes **8–40 hours** to respond to manually
- Responses are inconsistent across team members
- Security questionnaires (SIG, vendor assessments) are repeated from scratch
- Demo preparation is disconnected from the RFP analysis
- Knowledge from past responses is siloed in individual documents

---

## What It Does

1. **Upload** a customer RFP in CSV, XLSX, DOCX, or PDF format
2. **Agents run autonomously** — parsing structure, categorising requirements, researching answers from a 640+ entry knowledge base and live Okta web sources, scoring fit/risk, and quality-checking every response
3. **Review** answers in the UI with confidence scores, source citations, and flagged items
4. **Export** back to the original file format with Vendor Response and Comments columns populated
5. **Ingest** completed RFPs into the knowledge base so every future RFP improves
6. **Generate demo plans** — AI-built, section-by-section demo scripts tied to what the customer actually asked about
7. **Demo Library** — confirmed demo plans stored for team reuse

---

## Agent Architecture

NaughtRFP uses **9 specialised agents** in a coordinated pipeline. Each agent has a defined role, tools it can call, and a live status feed visible in the UI.

```
Upload
  │
  ├─► Customer Agent     → Who issued this? Industry? RFP number? Scope?
  │
  ├─► Parser Agent       → What columns are requirements vs responses?
  │
  ├─► Analysis Agent     → Which Okta products apply? What's the risk level?
  │
  ├─► Research Agent ────┐  (bulk KB pre-fetch, then per-question if needed)
  │   └─ search_kb       │
  │   └─ search_web      │
  │                      │
  ├─► Answer Agent ◄─────┘  (parallel, 6 workers)
  │   └─ search_kb (tool)   Agentic loop: KB → web → answer OR flag
  │   └─ search_web (tool)
  │   └─ flag_for_review
  │
  ├─► Scoring Agent      → Overall fit/risk scores (1–5)
  │
  ├─► Review Agent       → QA pass; adds ⚠ notes to high-risk answers
  │
  ├─► KB Ingestion Agent → Adds answered Q&A to the knowledge base
  │
  ├─► KB Direct Ingestion Agent → Upload any CSV/XLSX/XLSM/DOCX/PDF directly into KB
  │
  └─► Demo Prep Agent    → Generates a demo plan from the RFP analysis
```

### Agent Details

| Agent | Model | Tools | Key Output |
|---|---|---|---|
| **Customer Agent** | 🪶 claude-haiku-4-5 | file read | customer_name, industry, rfp_number, scope_summary |
| **Parser Agent** | 🪶 claude-haiku-4-5 | openpyxl, csv | Structured requirement list, column mapping |
| **Analysis Agent** | ⚡ claude-sonnet-4-6 (batch) | — | Okta product mapping, refined categories, risk pre-scores |
| **Research Agent** | 🔧 local only | SQLite FTS5, httpx | Pre-fetched KB context for all questions |
| **Answer Agent** | ⚡ claude-sonnet-4-6 | search_kb, search_web, flag_for_review | Vendor response, confidence, fit/risk scores, citations |
| **Scoring Agent** | 🔧 aggregation | — | Overall fit score /5, risk score /5 |
| **Review Agent** | 🔧 rule-based | — | High-risk ⚠ warnings (stripped on export) |
| **KB Ingestion Agent** | 🔧 local only | SQLite FTS5 | New KB entries, deduplication |
| **KB Direct Ingestion Agent** | 🪶/⚡ Haiku (mode detect) + Sonnet (extract) | — | Direct file → KB: auto-detects structured/unstructured, deduplicates |
| **Demo Prep Agent** | ⚡ claude-sonnet-4-6 | — | Ordered demo sections with steps and talking points |

> ⚡ Sonnet — heavy reasoning & tool use · 🪶 Haiku — fast structured extraction · 🔧 Local — no LLM

### Agentic Tool Use

The Answer Agent implements a genuine **agentic loop** — it calls tools iteratively before producing a final answer:

```
User message (with pre-fetched KB context injected)
  │
  ├─ If KB context is sufficient → answer directly (1 API call)
  │
  ├─ If not → tool_call: search_knowledge_base(query)
  │   └─ Returns matching Q&A pairs from 640+ entry KB
  │   └─ Then: answer or call search_web
  │
  ├─ If still insufficient → tool_call: search_web(query)
  │   └─ Fetches trust.okta.com, docs.okta.com via DuckDuckGo + httpx
  │   └─ Claude summarises live content
  │   └─ Then: answer
  │
  └─ If confidence < 60% → tool_call: flag_for_review(reason)
      └─ Never hallucinates a response when uncertain
```

Response codes follow standard vendor RFP notation:
- **F** — Full Functionality (available out of the box)
- **P** — Partial Functionality
- **C** — Customisation Required
- **NE** — Not Currently Available (planned)
- **N** — Not Available

---

## Key Features

### Navigation
- **Collapsible vertical sidebar** — default open (240px), collapses to icon-only (64px). State persists in localStorage.
- 3D tactile nav buttons — raised at rest, lift on hover, sink on press, Okta blue gradient when active.
- **Circuit-N logo mark** — SVG logo representing the agent pipeline as connected nodes.

### Dashboard
- Grid of all uploaded RFPs with fit/risk scores and status
- **Multi-document upload** — drag multiple files at once; all become documents under one RFP project
- **Instant risk scan on upload** — rule-based pre-processing (no API call) detects Critical/High/Medium/Low requirement distribution and risk keywords (SLA, PIPEDA, FedRAMP, encryption, etc.) before agents run
- Priority breakdown bar (red/amber/blue/green) visible immediately after upload
- Customer identity auto-detected from file content

### RFP Detail View
- **Document list** — for multi-document RFPs, shows all files with status, counts, per-document Process/Export buttons, Add Document, and Export All as ZIP
- Click a document row to filter questions to just that document
- Live agent activity feed during processing (Server-Sent Events)
- **Preview panel** for pending RFPs showing requirement counts, categories, risk signals
- **Human Review banner** (amber, pulsing) — surfaces all flagged questions prominently
- **Inline edit for flagged questions** — response code picker, editable answer textarea, ✓ Approve as-is, ↺ Re-run AI on individual question
- **↺ Re-run Agents** — re-process any completed RFP with three modes: All Questions / Flagged Only / Unanswered + Flagged. Uses the current KB automatically — ideal after adding new data sources.
- Filter by category or "Needs Review"
- Per-question confidence bars, source citations (internal only — stripped from exports), Okta product tags
- Export to original CSV/XLSX/XLSM format with colour-coded response codes (macros preserved in .xlsm)

### Knowledge Base
- **657+ entries** across three sources: Okta SIG Core 2024 (615), internal Confluence compliance docs (15), hand-crafted baseline (25+)
- **Hybrid RRF search** — Reciprocal Rank Fusion combines FTS5 keyword results (BM25-equivalent) with per-keyword broadened results. Phrase match → prefix-AND → prefix-OR → LIKE fallback per pass. Handles single words, fragments, acronyms (DR, MFA, SoD, BCP), and full sentences
- **AI semantic search** — Claude matches by intent and context, not just keywords. Expands acronyms, finds related entries
- **BLUF card** — when AI search is on, Claude generates a 2-4 sentence Bottom Line Up Front synthesising all found entries, shown above results
- ⊕ Seed buttons: Okta Knowledge (baseline), SIG Core 2024, Confluence
- **⊕ Upload Document to KB** — drag and drop any CSV, XLSX, XLSM, DOCX, or PDF directly onto the KB page to extract Q&A pairs into the knowledge base without creating an RFP project. Structured files (clear Q/A columns) are inserted directly; unstructured files (free text, DOCX, PDF, single-column) use Claude Sonnet to extract pairs in batches. Multi-tab XLSX fully scanned with merged-cell resolution, DOCX and PDF tables extracted first with paragraph fallback. Exact-match deduplication prevents duplicate entries.
- Grows with every RFP ingestion

### Demo Prep — APEX / Command of the Message aligned
- **🎭 Demo Prep button** on any completed RFP
- Agent reads all answered requirements and generates a full **APEX Brief** (Okta's CoM-powered sales framework):
  - **Deal Mantra** — 1-2 sentence power statement in customer language
  - **Before Scenario** — current pain state with Negative Consequences
  - **After Scenario** — desired future state with Positive Business Outcomes (PBOs)
  - **Required Capabilities** — framed to favour Okta differentiators as objectively necessary
  - **Unique Differentiators** — why Okta specifically
- 4–6 ordered demo sections each mapping to a PBO and Required Capability
- Per-section: CoM-aligned talking points (Before → After language), demo steps, differentiators
- **Pre-Demo Discovery Questions** to validate the APEX brief before the call
- **✓ Confirm** to save to the Demo Library
- **Demo Library** — searchable catalogue of confirmed demo plans across all RFPs

### Agents Page
- Cards for all 9 agents with live descriptions, tools, inputs, outputs, and interactions
- Pipeline diagram (click any node for flyout detail)
- Built for hackathon judges to understand the agentic architecture

### Settings
- API key stored locally in SQLite (never hardcoded, never exported)
- LiteLLM proxy URL (Okta's internal `llm.atko.ai`)
- Web search toggle — disable for faster processing (KB alone handles most questions)
- Token usage tracker with LiteLLM spend query
- ⚡ Test Connection button

---

## Knowledge Base

The KB is the platform's institutional memory. It has three layers:

| Source | Entries | Content |
|---|---|---|
| **Okta SIG Core 2024** | 615 | Official Okta responses to Shared Assessments Standard Information Gathering questionnaire (v2024.02). Covers risk governance, third-party management, cryptography, vulnerability management, personnel security, identity & access, network, contingency planning, and more. |
| **Okta Baseline Knowledge** | 25 | Hand-crafted Q&A pairs for the most common RFP topics: DR/BCP, encryption, uptime SLA, data residency, PIPEDA, certifications, MFA, provisioning, access governance, SoD, integrations, PAM, AI. |
| **Past RFP responses** | Grows | Every completed RFP can be ingested — the KB learns from real customer interactions. |

### Web Search (Live Data)

When the KB doesn't have sufficient context, the Research Agent fetches live content:
- **DuckDuckGo** — site-restricted to `okta.com` and `trust.okta.com`
- **Direct page fetch** — topic-mapped Okta pages (e.g., compliance → `trust.okta.com/compliance`, IGA → `okta.com/products/identity-governance/`)
- **Page cache** — 1-hour in-memory cache prevents repeated fetches during a single RFP run
- **Claude summarisation** — raw web content is summarised before being injected into the answer context

---

## Technology Stack

| Component | Technology | Why |
|---|---|---|
| Backend | Python 3.14 + Flask | Lightweight, no build step needed |
| AI | claude-sonnet-4-6 (reasoning) + claude-haiku-4-5 (extraction) via Okta LiteLLM proxy (`llm.atko.ai`) | Right model for each agent — Sonnet for tool use and synthesis, Haiku for fast structured extraction |
| Database | SQLite + FTS5 | Zero-install, 0.1ms KB searches, thread-local connections |
| Frontend | Vanilla JS + HTML (no framework, no build) | Runs directly in Chrome, zero install for judges |
| Excel I/O | openpyxl | Read/write XLSX with colour-coded cells |
| HTTP | httpx | Async-capable, `verify=False` for Okta corporate SSL proxy |
| Parallelism | ThreadPoolExecutor (6 workers) | Processes 6 requirements simultaneously |

### Design Decisions

**No framework on the frontend** — judges can open the source and read it directly. No `node_modules`, no build step, no webpack config.

**SQLite over Postgres** — zero setup for judges, WAL mode for concurrent writes from 6 parallel agent threads, thread-local connections for performance.

**Pre-fetch KB context** — instead of making the Answer Agent call `search_knowledge_base` as a tool (extra API round trip), the Research Agent pre-fetches the top-3 KB matches for all questions in bulk before the parallel pool starts. This eliminates ~34 API round trips for a 34-question RFP.

**SIG as the KB seed** — Okta's pre-completed SIG Core 2024 questionnaire is machine-readable and contains official, approved Okta answers to 600+ security questions. Seeding from this gives the agents an authoritative foundation before any RFPs are processed.

---

## Setup & Running

### Requirements
- Python 3.14+
- `py` command (Python Launcher for Windows)
- Okta LiteLLM API key (`sk-...` from `llm.atko.ai/ui/api-keys/`)

### Install
```bash
py -m pip install flask anthropic openpyxl python-docx pdfplumber
```

### Run
```bash
cd rfp-responder
py app.py
```

Open `http://localhost:5000` in Chrome.

### First-time configuration
1. Go to **Settings**
2. Set **LiteLLM Proxy URL**: `https://llm.atko.ai`
3. Set **API Key**: your `sk-...` LiteLLM key
4. Click **Save Settings** → **⚡ Test Connection**
5. Go to **Knowledge Base** → click **⊕ Seed Okta Knowledge**

### Seed the SIG knowledge (one-time)
```bash
py seed_sig.py
```

This loads 615 entries from `Okta_SIG_Core.xlsm` into the KB.

---

## Application Screens

```
/ (Dashboard)
├── Upload zone (drag & drop CSV/XLSX)
├── RFP cards grid (fit score, risk score, priority bar, customer badge)
└── Click card → RFP Detail

/rfp-detail
├── Customer header (name, industry, RFP number, scope)
├── Preview panel (pending) → Run Agents button
├── Processing panel (live agent feed via SSE)
├── Questions view (answers, confidence, citations, flagged items)
├── 🎭 Demo Prep → generates demo plan
└── ↓ Export → downloads filled-in original file

/kb (Knowledge Base)
├── Search bar (FTS or ⚡ AI semantic)
├── Entry cards (question, answer, category, products, source)
└── ⊕ Seed Okta Knowledge button

/agents (Agent Architecture)
├── Pipeline diagram (clickable nodes)
└── 9 agent cards (click for flyout: role, tools, inputs, outputs, interactions)

/demos (Demo Library)
└── Cards of all confirmed demo plans

/discover (RFP Discovery)
├── Run Discovery button — 20 targeted queries: 12 public sector + 8 private sector
│   Public:  CanadaBuys, MERX, Alberta APC, BC Bid, Ontario, buyandsell.gc.ca
│   Private: rfpdb.com, rfpmart.com, biddingo.com, canadacontracts.ca
│   Sectors: financial services, healthcare, energy/utilities, telco, retail
├── Result cards with: source badge, title, org, solicitation #, description snippet,
│   days-remaining countdown (amber if <7 days, CLOSED if past), relevance tags,
│   sector tag (public / private / unknown)
├── Import → creates RFP project from discovered tender
├── Dismiss → removes card with animation
└── Filter bar (All / Federal / Provincial / IAM / Cybersecurity / Cloud)

/settings
├── API key, LiteLLM URL, web search toggle
├── ⚡ Test Connection
└── Token usage tracker
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/rfps` | List all RFPs |
| POST | `/api/rfp/upload` | Upload a CSV/XLSX RFP file |
| GET | `/api/rfp/<id>` | Get RFP with questions, agent logs |
| GET | `/api/rfp/<id>/process` | SSE stream — run agent pipeline |
| POST | `/api/rfp/<id>/export` | Export RFP with answers (returns file) |
| DELETE | `/api/rfp/<id>` | Delete RFP |
| GET | `/api/rfp/<id>/demo-prep` | SSE stream — generate demo plan |
| GET | `/api/rfp/<id>/demo-plan` | Get existing demo plan |
| POST | `/api/rfp/<id>/demo-plan/confirm` | Confirm demo plan → Demo Library |
| GET | `/api/demos` | List confirmed demo plans |
| GET | `/api/kb/search?q=<query>&ai=true` | Search knowledge base |
| POST | `/api/kb/ingest/<id>` | SSE stream — ingest RFP into KB |
| POST | `/api/kb/upload-document` | SSE stream — upload file directly to KB (CSV/XLSX/XLSM/DOCX/PDF) |
| POST | `/api/kb/seed` | Seed baseline Okta knowledge |
| POST | `/api/kb/seed-sig` | Seed from Okta SIG Core 2024 |
| GET | `/api/kb/stats` | KB entry counts by category |
| GET | `/api/settings` | Get current settings |
| POST | `/api/settings` | Save settings (API key, URLs, toggles) |
| POST | `/api/test-connection` | Test LiteLLM connection |
| GET | `/api/usage` | Token usage summary + LiteLLM spend |

---

## Performance

### Benchmarks (34-question IGA RFP, web search disabled)

| Metric | Value |
|---|---|
| KB search (FTS5) | 0.1ms per query |
| KB pre-fetch (all 34 questions) | ~3ms total |
| API call latency (LiteLLM) | 3–8s per call |
| Parallel workers | 6 |
| Questions per "round" | 6 simultaneous |
| Estimated total time (web off) | ~35–55 seconds |
| Estimated total time (web on) | ~60–90 seconds |

### Optimisations Applied

- **Thread-local SQLite connections** — one connection per thread, reused across operations
- **Covering indexes** — 9 indexes on hot query paths (questions, KB, rfps, token_usage, demo_plans)
- **SQLite PRAGMAs** — WAL mode, 32MB cache, NORMAL synchronous, memory temp store, 256MB mmap
- **KB bulk pre-fetch** — all KB lookups done in one pass before the parallel pool; matching context injected directly into the first API message (eliminates 1 tool round trip per question)
- **1-hour page cache** — Okta web pages cached in memory during a processing run
- **max_tokens=768** — sufficient for 2–4 sentence answers; faster generation
- **max_iterations=3** — pre-fetched context means fewer tool call cycles needed

---

## File Structure

```
rfp-responder/
├── app.py              Flask backend — routes, SSE, multi-doc, re-run, .env bootstrap
├── agents.py           All 9 agents + APEX/CoM demo prep + multi-tab XLSX/DOCX/PDF parser
├── db.py               SQLite wrapper — thread-local connections, FTS5, multi-doc
├── export_handler.py   Multi-sheet CSV/XLSX/XLSM export (VBA macros preserved)
├── seed_kb.py          25 hand-crafted Okta baseline Q&A pairs
├── seed_sig.py         Loads Okta_SIG_Core.xlsm → KB (615 entries)
├── seed_confluence.py  15 entries from Okta internal Confluence compliance docs
├── discovery.py        RFP discovery from external sources
├── relevance.py        Relevance scoring for discovered RFPs
├── sample_rfp.csv      34-requirement IGA RFP for testing
├── setup.sh            One-command Mac/Linux setup (venv + deps + .env)
├── .env.example        Credential template — copy to .env and fill in API key
├── SESSION_LOG.md      Full build session log — decisions, problems, prompts
├── CLAUDE.md           Claude Code project instructions
├── README.md           This file
├── docs/
│   ├── solution.md          Problem statement and scope
│   ├── prd.md               Full PRD with user stories
│   ├── multiAgentDesign.md  Multi-agent architecture design
│   ├── day3-build-plan.md   Build plan
│   └── feature-rfp-discovery.md  RFP discovery feature spec
├── templates/
│   └── index.html      Single-page app shell — collapsible sidebar, all pages
├── static/
│   ├── style.css       Okta dark navy theme with 3D depth token system
│   └── app.js          Full SPA — routing, agents, KB, APEX demo prep, multi-doc
├── uploads/            Uploaded RFP files (gitignored)
├── exports/            Generated export files (gitignored)
└── naughtrfp.db        SQLite database (gitignored)
```

---

## Agentic AI — Hackathon Theme

This project demonstrates agentic AI in three dimensions:

**1. Multi-agent coordination** — 9 specialised agents, each with a defined role, pass structured outputs to the next agent. No single agent tries to do everything.

**2. Genuine tool use** — the Answer Agent calls tools autonomously (`search_knowledge_base`, `search_web`, `flag_for_review`) and decides mid-loop whether to search more, use what it has, or refuse to answer. This is not scripted — the agent makes real-time decisions.

**3. Appropriate refusal** — the agent flags questions when confidence falls below 60% rather than hallucinating. In the Sony RFP test run, 11 of 34 questions were intelligently flagged with specific reasons (e.g., "AI agent lifecycle governance maturity should be verified by a Solutions Architect before committing to a Full response on a Critical requirement").

**4. Compounding knowledge** — each processed RFP makes the next one better. The knowledge base grows with every ingestion, and the Okta SIG Core 2024 provides an authoritative foundation of 615 approved security responses.

---

*Built by Claude Leroux, Okta Solutions Engineer — Canada Public Sector*
*NaughtRFP | July 2026 Hackathon*
