# NaughtRFP — Solution Document

## Problem Statement

Okta Pre-Sales Solutions Engineers spend 8–40 hours per RFP manually reading, assessing, researching, and populating security and technical questionnaires — then preparing disconnected demo plans afterward. Responses are inconsistent across team members, knowledge from past RFPs is siloed, and demo preparation starts from scratch every time. This time cost directly limits how many deals an SE can run in parallel.

## Identity / Okta Connection

Two explicit angles:

1. **Content** — NaughtRFP is purpose-built for Okta's product portfolio. The knowledge base is seeded from Okta's own SIG Core 2024 responses (~615 pre-approved security answers) and hand-crafted Okta product Q&A. Every AI-generated answer is grounded in what Okta actually offers.
2. **Use case** — The end users are Okta Pre-Sales SEs. The platform directly accelerates Okta's sales motion by reducing the time cost of responding to identity and security RFPs. This is not an app that incidentally touches identity — it is an identity sales tool.

## Solution Description

NaughtRFP is a multi-agent AI platform that automates RFP response and demo preparation for Okta Pre-Sales SEs.

**What it does:**
- Accepts RFP uploads in CSV or XLSX format (single or multiple files per RFP project)
- Parses structure to identify requirement columns, question IDs, and response fields
- Assesses fit against Okta's product portfolio and scores overall fit and risk (1–5)
- Auto-answers as many requirements as possible from a layered knowledge base and live Okta web sources
- Flags requirements for human review when confidence falls below 60% (POC threshold; production target: 80–90%), when answers are legally sensitive, or when no credible source backs the response — never hallucinating
- Provides an SE review UI with inline editing, response code picker, and per-question re-run
- Exports the completed file in the original ingested format (CSV or XLSX) with vendor responses populated
- Generates a structured demo plan tied to what the customer actually asked about
- Stores confirmed demo plans in a team-accessible Demo Library
- Ingests completed RFPs back into the knowledge base so every future RFP improves

**What it does NOT do (POC scope):**
- Google Sheets or Google Docs ingestion
- Email draft generation
- SIG/certification file upload as KB sources
- Multi-tenancy or user authentication on the app itself

## Demo Scenario

**Audience:** Hackathon judges (Field CTO team, Okta SE leadership)

**3-minute flow:**
1. Upload a sample RFP CSV — show multi-column structure being parsed automatically
2. Watch the live agent activity feed — Customer → Parser → Analysis → Research → Answer agents running in real time, proving genuine agentic execution
3. Open the completed questions view — show answered requirements with confidence scores, source citations, and Okta product tags
4. Surface the Human Review banner — show 2–3 flagged questions with specific flag reasons, demonstrate inline editing and approval
5. Export the filled-in file — same format, response codes colour-coded
6. Kick off Demo Prep — show a generated demo plan with ordered sections, steps, and talking points

**The "wow" moment:** The live agent feed showing 9 agents collaborating in real time — this proves the system is agentic, not a batch script.

## Technical Approach

- **Backend:** Python + Flask (lightweight, no build step)
- **AI:** Claude Sonnet via Okta's internal LiteLLM proxy (`llm.atko.ai`)
- **Database:** SQLite with FTS5 full-text search (zero-install, thread-safe)
- **Frontend:** Vanilla JS + HTML (no framework, no build — judges can read the source directly)
- **Parallelism:** ThreadPoolExecutor (6 parallel Answer Agent workers)
- **File I/O:** openpyxl for XLSX read/write with colour-coded response codes

## Knowledge Base Layers

| Layer | Source | Entries |
|---|---|---|
| Seed | Okta SIG Core 2024 (official pre-approved security responses) | ~615 |
| Baseline | Hand-crafted Q&A — MFA, SSO, SLA, data residency, PIPEDA, certifications | ~25 |
| Compounding | Past completed RFPs ingested by SEs after each deal | Grows over time |
| Live fallback | DuckDuckGo search restricted to `okta.com` + `trust.okta.com` | On demand |

## Open Questions

- **Confidence threshold:** POC uses 60%. Production target is 80–90%. Exact production threshold should be validated against a real SE review sample before hardcoding.
- **File format edge cases:** XLSX files with merged cells or non-standard column layouts may require parser tuning per customer.
- **KB deduplication:** Ingesting multiple RFPs from the same customer could introduce duplicate entries — dedup strategy should be reviewed before scaling.
