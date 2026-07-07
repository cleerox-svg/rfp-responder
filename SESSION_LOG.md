# NaughtRFP — Build Session Log
**Session date:** 2026-07-06 → 2026-07-07  
**Participants:** Claude Leroux (Okta SE, Canada Public Sector) + Claude Code  
**Hackathon theme:** Agentic AI  
**Purpose of this doc:** Feed into a new Claude session for assessment, continuation, or code review

---

## What was built (chronological)

### 1. Initial scaffold
- Flask + SQLite + openpyxl stack chosen (zero-install beyond `py -m pip install flask anthropic openpyxl`)
- `py` command required — `python` maps to Windows Store alias on this corporate machine
- LiteLLM proxy at `https://llm.atko.ai` for all Claude API calls (Okta internal)
- SSL `verify=False` required — Okta corporate proxy does HTTPS inspection
- API key format: `sk-...` (LiteLLM virtual key, not raw Anthropic key)
- Model: `claude-sonnet-4-6` (no date suffix on this proxy)

### 2. Core agent pipeline (first working version)
Seven agents in sequence, communicating via SSE stream to the frontend:
1. **Parser Agent** — detects CSV/XLSX column structure using Claude
2. **Analysis Agent** — batch maps requirements to Okta products + risk scores
3. **Research Agent** — searches knowledge base via SQLite FTS5
4. **Answer Agent** — agentic loop with `search_knowledge_base`, `search_web`, `flag_for_review` tools
5. **Scoring Agent** — aggregates fit/risk scores
6. **Review Agent** — QA pass, adds ⚠ to high-risk answers
7. **KB Ingestion Agent** — adds answered Q&A to searchable KB

### 3. Knowledge base seeded
- 25 hand-crafted Okta baseline Q&A (`seed_kb.py`)
- 615 entries from Okta SIG Core 2024 (`seed_sig.py` reads `Okta_SIG_Core.xlsm` from Desktop)
- Total KB: 642 entries across 8 categories
- Multi-strategy FTS search: phrase → prefix-AND → prefix-OR → LIKE fallback
  - Handles: single words, fragments, acronyms (DR, MFA, SoD, BCP, PIPEDA), full sentences

### 4. Web search integration
- DuckDuckGo API (free, no key) + direct Okta page fetch (`trust.okta.com`, `docs.okta.com`)
- 1-hour in-process page cache (`_PAGE_CACHE`)
- Claude summarises raw web content before injecting into answer context
- Trust portal status API requires auth — fetched via HTML scraping instead
- Web search can be toggled off in Settings for faster processing

### 5. Performance optimisations
- Thread-local SQLite connections (WAL mode, one connection per thread, reused)
- 9 covering indexes on hot query paths
- SQLite PRAGMAs: 32MB cache, NORMAL synchronous, memory temp store, 256MB mmap
- **KB bulk pre-fetch**: all KB lookups done in one pass before parallel pool — eliminates 1 tool round-trip per question
- **6 parallel workers** (ThreadPoolExecutor) for the answer loop
- max_tokens reduced 1024→768, max_iterations 4→3
- KB search: 3.6ms → 0.1ms per query after indexes

### 6. UI — Okta dark theme + 3D depth system
- Dark navy: `#07111E` background, `#007DC1` Okta blue accent
- CSS custom property depth tokens in `:root`:
  - `--depth-raised` / `--depth-raised-hover` — cards, panels, buttons at rest/hover
  - `--depth-inset` / `--depth-inset-focus` — inputs (wells)
  - `--card-grad` — subtle top-highlight gradient on all cards
  - `--glow-blue` — active/selected glow
- All interactive elements: lift on hover (-2/-3px translateY), sink on press (+2px), inset shadow on inputs
- **Collapsible left sidebar** replacing top nav:
  - 240px open / 64px collapsed (icon-only)
  - State persists in localStorage
  - 3D tactile nav buttons — same depth system as sidebar
- **Circuit-N SVG logo**: inline SVG, 4 node dots + 3 circuit traces forming letter N with centre crossover dot

### 7. Additional agents added
8. **Customer Agent** — reads file content, extracts: customer_name, industry, rfp_number, scope_summary, estimated_scale
9. **Demo Prep Agent** — reads all answered requirements, generates ordered demo plan (4–6 sections, steps, talking points, differentiators, environment setup)

### 8. Feature: Instant risk scan on upload
- No API call — rule-based keyword + priority column scan
- Shows: risk level badge (🔴/🟡/🟢), priority bar, category chips, risk keywords
- Runs before agents, visible immediately after upload

### 9. Feature: Human review workflow for flagged questions
- Flagged cards auto-expand
- Inline edit form: response code picker (F/P/C/NE/N as 3D buttons), answer textarea
- **✓ Approve as-is** — saves without requiring text edit (only response code required)
- **↺ Re-run AI** — streams the Answer Agent on just that one question, pre-populates form

### 10. Feature: Demo Library
- Confirmed demo plans stored in `demo_plans` table
- Top-level **Demo Library** nav page — all confirmed plans across all RFPs
- Click card → full demo plan view with timeline, expandable sections

### 11. Feature: KB AI search with BLUF
- When AI search toggled: single Claude call returns both relevance indices AND a BLUF
- **BLUF card** (Bottom Line Up Front) shown above results — 2-4 sentence synthesis in military style
- AI search prompt explicitly handles acronyms, fragments, context

### 12. Feature: Token usage tracker
- `token_usage` table — records per-agent API call tokens
- `/api/usage` endpoint — queries LiteLLM `/key/info` for real spend + local token counts
- Shown in Settings with per-RFP breakdown

### 13. Feature: Multi-document RFPs
- `rfp_documents` table — multiple files under one RFP project
- `questions.document_id` — links questions to source document
- Upload zone accepts multiple files (HTML `multiple` attribute)
- Document list in RFP detail: per-doc status, process, export, delete, rename
- **Export All as ZIP** — `zipfile` (stdlib, no pip) creates archive of all completed docs
- `db.sync_rfp_counts(rfp_id)` aggregates counts across all documents
- `AgentPipeline.process_document(rfp_id, doc_id, filepath)` — processes one document

---

## Key technical decisions and why

| Decision | Reason |
|---|---|
| `py` not `python` | Corporate Windows: `python` → Windows Store alias, `py` → real Python 3.14 |
| `verify=False` in httpx | Okta corporate SSL inspection intercepts HTTPS, certifi doesn't trust corp CA |
| LiteLLM OpenAI endpoint blocked | Team key only has Claude access via Anthropic endpoint (`/v1/messages`), not `/v1/chat/completions` |
| SQLite thread-local connections | Multiple threads from ThreadPoolExecutor need isolated connections; WAL handles concurrent reads |
| KB bulk pre-fetch pattern | Eliminates 1 tool-call round-trip per question = ~34 fewer API calls for a 34-question RFP |
| FTS5 multi-strategy search | FTS5 exact match fails on fragments/acronyms; prefix-AND/OR fallback + LIKE catches everything |
| `zipfile` for Export All | stdlib, zero pip install, works on corporate device |
| Inline SVG logo | No image file, no CDN, renders at any size, hackable |
| Vanilla JS SPA (no React) | No build step, no node_modules, judges can read source directly |

---

## Problems encountered and solutions

| Problem | Solution |
|---|---|
| `python` not on PATH | Use `py` launcher throughout |
| `pip` not on PATH | Use `py -m pip install` |
| SSL `CERTIFICATE_VERIFY_FAILED` | `verify=False` in all httpx calls, wrapped in `_make_client()` helper |
| LiteLLM 401 on `gpt-5-search-api` | Team key restricted to Claude via Anthropic endpoint; used DuckDuckGo + httpx instead |
| Demo prep JSON truncated | max_tokens 3000→8000, prompt compacted to stay under limit |
| `_extract_json` failing on markdown fences | Strip ` ``` ` before parsing; try whole string, then regex fallback |
| SQLite index before table definition | Moved all `CREATE INDEX` to after all `CREATE TABLE` in executescript |
| `document_id` column missing at index creation | Added to questions CREATE TABLE; ALTER TABLE migration for existing DBs |
| FTS search returning irrelevant results | Multi-strategy: phrase → prefix-AND → prefix-OR → LIKE |
| Agent processes slow (~10+ min) | Parallel workers (6), pre-fetch KB, reduce max_tokens/iterations |

---

## Current state of the app (2026-07-07)

### Running
```bash
cd C:\Users\ClaudeLeroux\rfp-responder
py app.py
# → http://localhost:5000
```

### DB state
- 2 RFPs processed (sony_rfp: 23 answered, 11 flagged)
- 642 KB entries (25 baseline + 615 SIG + 2 from RFP ingestion)
- 0 confirmed demo plans

### Settings configured
- LiteLLM URL: `https://llm.atko.ai`
- API key: set (sk-... LiteLLM virtual key)
- Web search: enabled

### Files in repo (to be committed)
```
app.py, agents.py, db.py, export_handler.py
seed_kb.py, seed_sig.py, sample_rfp.csv
templates/index.html, static/style.css, static/app.js
README.md, CLAUDE.md, .gitignore
```
NOT committed: `naughtrfp.db`, `uploads/`, `exports/`, `__pycache__/`

---

## Features in progress / planned

| Feature | Status | Notes |
|---|---|---|
| Salesforce MCP integration | Planned | After customer detected, query SFDC for active opportunity |
| Highspot/Seismic integration | Planned | Sales enablement content for KB |
| Google Drive sync button | Partial | Folder ID in settings, MCP tools available in session |
| Okta OIDC authentication | Plumbing added by user | `app.py` has auth routes, disabled by default |
| `.env` file support | Added by user | `_load_dotenv()` in `app.py`, `.env.example` referenced in README |

---

## Codebase assessment prompts for a new session

If feeding this into a new Claude session, useful questions to ask:

1. **Code review**: "Review agents.py for correctness, efficiency, and error handling. Focus on the agentic loop in `_research_and_answer` and the parallel processing in `process_rfp`."

2. **Performance audit**: "Profile the RFP processing pipeline. Where are the remaining bottlenecks beyond the 6-worker parallel answer loop?"

3. **Security review**: "Review app.py for security issues. Note: `verify=False` is intentional for the corporate proxy environment."

4. **Feature continuation**: "Continue building NaughtRFP. The next priority is [X]. See SESSION_LOG.md for full context."

5. **Demo prep**: "Help prepare a hackathon demo script for NaughtRFP. The audience is Okta leadership. Theme is Agentic AI."
