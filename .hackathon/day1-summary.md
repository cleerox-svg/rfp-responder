# Day 1 Handoff — NaughtRFP

**Prepared for:** Day 2 agent architecture build  
**Participant:** Claude Leroux, Okta Solutions Engineer, Canada Public Sector  
**Repo:** https://github.com/ofctoV27/claudeleroux_hackathon  
**App location (local test):** `C:\Users\ClaudeLeroux\rfp-responder\`

---

## What was built today

NaughtRFP is a fully working AI-powered RFP responder for Okta Pre-Sales SEs. The application was pre-built before the hackathon and migrated into the repo today. The spec was written from scratch through a grill-me interrogation session and committed before the code — satisfying the Day 1 spec-first evaluation criterion.

### Git commit sequence (spec before code — evaluation criterion met)
```
41b9078 docs: add judge quick-start, .env.example, and env var bootstrap
b6a1204 feat: add Okta OIDC auth plumbing (disabled for judging)
329d541 feat: add NaughtRFP application code
7484d57 spec: add solution.md and prd.md before any code  ← spec first
4c88460 Initial commit — hackathon repo setup
```

---

## Spec artefacts

- `docs/solution.md` — problem statement, identity angle, demo scenario, scope boundaries, open questions
- `docs/prd.md` — 34 user stories, implementation decisions, out of scope, further notes

Do not re-read these unless Day 2 context requires it — they are the committed source of truth.

---

## What the application does

9-agent pipeline that processes RFP files (CSV/XLSX) and:
1. Identifies customer, industry, RFP scope (Customer Agent)
2. Parses column structure — requirement IDs, response fields (Parser Agent)
3. Tags Okta products, assesses risk per requirement (Analysis Agent)
4. Pre-fetches KB context for all questions in bulk (Research Agent)
5. Auto-answers requirements in parallel — 6 workers (Answer Agent, agentic tool loop)
6. Scores overall fit/risk 1–5 (Scoring Agent)
7. QA pass, flags high-risk answers with ⚠ notes (Review Agent)
8. On demand: ingests completed RFP into KB (KB Ingestion Agent)
9. On demand: generates structured demo plan (Demo Prep Agent)

### Key technical facts for Day 2 architecture design
- **Backend:** Python 3.14 + Flask, `app.py` (routes/SSE) + `agents.py` (all 9 agents)
- **AI:** `claude-sonnet-4-6` via Okta LiteLLM proxy (`https://llm.atko.ai`) — constant `_MODEL` in `agents.py`
- **DB:** SQLite + FTS5, thread-local connections, WAL mode — `db.py`
- **Parallelism:** `ThreadPoolExecutor(6)` for Answer Agent workers
- **Frontend:** Vanilla JS SPA — `static/app.js` + `templates/index.html`
- **Export:** `export_handler.py` — colour-coded XLSX/CSV
- **KB:** 640+ entries (SIG Core 2024 seed + hand-crafted baseline + past RFP ingestion)
- **Live feed:** Server-Sent Events stream agent status to UI during processing

### Okta auth plumbing (added Day 1)
- Settings UI: Okta Domain, Client ID, Redirect URI, Enable toggle
- Backend routes: `/auth/login`, `/auth/callback`, `/auth/logout` — OIDC Authorization Code + PKCE
- **Auth is disabled by default** (`okta_auth_enabled=false`) — judges access app unauthenticated
- Routes live in `app.py` after the settings block

### Judge setup
- `.env.example` committed — judges copy to `.env`, fill in `LITELLM_API_KEY`
- App reads `.env` on startup via `_load_dotenv()` + `_env_bootstrap()` in `app.py`
- README has "For Judges" section at the top with 5-step quick-start
- `sample_rfp.csv` — 34-requirement IGA RFP included for test processing

---

## Scope decisions locked in Day 1

**In scope (POC):**
- CSV / XLSX upload (single or multi-document per RFP project)
- 9-agent pipeline with live SSE feed
- Human review of flagged items (confidence < 60% POC threshold; 80–90% production target)
- Export in original format with colour-coded response codes
- Demo Prep → Demo Library
- KB ingestion loop (compounding knowledge)

**Out of scope (POC):**
- Google Sheets / Docs ingestion
- Email draft generation
- SIG/cert file upload as KB sources
- Auth enforcement (plumbing exists, disabled)

---

## Identity / Okta connection (judging criterion)
Two angles established and documented:
1. **Content** — KB seeded from Okta's own SIG Core 2024 (~615 approved security responses)
2. **Use case** — purpose-built for Okta Pre-Sales SE sales motion; directly reduces deal cycle friction

---

## Day 2 focus: Agent Architecture Design

The primary Day 2 deliverable is `docs/multiAgentDesign.md` and agent definition files in `.claude/agents/`.

The natural seams in the existing application where it would split into independent parallel agents:
- **Ingestion / parsing** — file upload, column detection, customer identification (independent of KB)
- **Research / answering** — KB pre-fetch + parallel Answer Agent workers (already parallelised internally)
- **Scoring / review** — post-answer aggregation (depends on answers, independent of each other)
- **Demo prep** — entirely independent of the RFP answer pipeline; triggered on demand
- **KB ingestion** — entirely independent; triggered on demand after export

These are the seams to interrogate with `/design-agents` on Day 2.

---

## Suggested skills for Day 2

- `/start-day` — run first, before anything else. Loads Day 2 coaching context.
- `/design-agents` — primary Day 2 skill. Interrogates the architecture and produces `docs/multiAgentDesign.md` + agent definition files. Invoke immediately after start-day orients you.
- `/to-issues` — after design is done, use to break the design into independently-grabbable implementation tasks.
- `/wrap-day` — run at end of Day 2 to commit, tag `day2-complete`, and push.

---

## Repo state at Day 1 wrap
- Remote: `https://github.com/ofctoV27/claudeleroux_hackathon.git`
- Branch: `master`
- All changes pushed
- `.env` is gitignored — not in repo (contains API key)
- `naughtrfp.db`, `uploads/`, `exports/` are gitignored — not in repo
