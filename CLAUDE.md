# NaughtRFP — Claude Code Instructions

## How to run
```bash
cd C:\Users\ClaudeLeroux\rfp-responder
py app.py          # starts Flask on http://localhost:5000
```

> **Important:** Use `py` not `python` on this machine. `python` maps to the Windows Store alias and fails. `py` uses the real Python 3.14 installation at `C:\Program Files\Python314\`.

Install dependencies (first time only):
```bash
py -m pip install flask anthropic openpyxl python-docx
```

Seed knowledge base (first time only):
```bash
py seed_sig.py         # 615 entries from Okta SIG Core 2024
py seed_confluence.py  # 15 entries from internal Confluence docs
```

Mac/Linux users:
```bash
bash setup.sh          # creates venv, installs deps, copies .env
source venv/bin/activate && python app.py
```

---

## Project context

**NaughtRFP** is an AI-powered RFP responder built for Okta Pre-Sales SEs. Hackathon POC — week of 2026-07-06. Theme: Agentic AI.

**Owner:** Claude Leroux, Okta Solutions Engineer, Canada Public Sector  
**LiteLLM proxy:** `https://llm.atko.ai` (Okta's internal LLM gateway)  
**Models:** `claude-sonnet-4-6` (reasoning/tool-use) · `claude-haiku-4-5` (fast extraction)

---

## Key files

| File | Purpose |
|---|---|
| `app.py` | Flask backend — all routes, SSE, multi-doc, re-run, .env bootstrap, Okta auth stubs |
| `agents.py` | All 9 agents, APEX/CoM demo prep, multi-tab XLSX parser, DOCX parser |
| `db.py` | SQLite wrapper — thread-local connections, FTS5, multi-doc tables |
| `export_handler.py` | Multi-sheet CSV/XLSX/XLSM export (VBA preserved with `keep_vba=True`) |
| `seed_kb.py` | 25 hand-crafted Okta baseline Q&A pairs |
| `seed_sig.py` | Loads `Okta_SIG_Core.xlsm` → KB (615 entries) |
| `seed_confluence.py` | 15 compliance/security entries from Okta Confluence |
| `discovery.py` | RFP discovery from external sources |
| `relevance.py` | Relevance scoring for discovered RFPs |
| `sample_rfp.csv` | 34-requirement IGA RFP for testing |
| `setup.sh` | One-command Mac/Linux setup |
| `templates/index.html` | Single-page app shell — collapsible sidebar, all pages |
| `static/style.css` | Okta dark navy theme with 3D CSS depth token system |
| `static/app.js` | Full SPA — routing, agent feed, APEX demo prep, KB, multi-doc |
| `.env.example` | Template for credentials — copy to `.env` |
| `SESSION_LOG.md` | Full build history for session continuity |

---

## Architecture rules

- **Always use `py`** not `python` to invoke Python on Windows
- **Always update `README.md`** after any non-trivial feature change
- **Work in small chunks** with a visible task list (`TaskCreate` / `TaskUpdate`)
- **Push to all three locations** after any commit: GitHub + `rfp-responder` folder (source) + `Desktop/Claude Code Projects/Hackathon Info` (use the Python sync snippet in SESSION_LOG.md)
- **SQLite is thread-safe** via thread-local connections with WAL mode. Don't add `check_same_thread=False` workarounds.
- **CSS depth tokens** are in `:root` — use `var(--depth-raised)`, `var(--depth-inset)`, `var(--card-grad)`. Never hardcode shadow values.
- **Model constants** are `_MODEL` and `_MODEL_FAST` in `agents.py` — never hardcode model strings elsewhere.

## SSL / Corporate proxy
Okta's corporate proxy does SSL inspection. All `httpx` clients must use `verify=False`. The `_make_client()` helper in `agents.py` handles this. For direct `httpx` calls elsewhere, always pass `verify=False`.

## Agent pipeline (9 agents)
```
Upload → Customer Agent (Haiku) → Parser Agent (Haiku) → Analysis Agent (Sonnet)
       → Research Agent (local: FTS5 bulk pre-fetch + httpx web search)
       → Answer Agent (Sonnet, 6 parallel workers, agentic tool loop)
       → Scoring Agent (local: aggregation) → Review Agent (local: rule-based)
       ↓ on demand:
       KB Ingestion Agent   (local: FTS5 dedup)     → Add to KB button
       Demo Prep Agent      (Sonnet, APEX/CoM)       → 🎭 Demo Prep button
```

## APEX / Command of the Message (Demo Prep)
- Demo Prep Agent generates a full APEX Brief: Mantra, Before/After Scenarios, PBOs, Required Capabilities, Unique Differentiators
- Each demo section maps to a PBO and Required Capability
- Talking points use CoM Before → After language
- Discovery questions help validate the brief pre-demo
- APEX is Okta's internal CoM + MEDDPICCC framework — see Confluence Presales AI Strike Team page

## File format support
Accepted: `.csv`, `.xlsx`, `.xls`, `.xlsm`, `.docx`

**Multi-tab XLSX/XLSM:**
- Parser iterates ALL sheets (skips nav tabs by name: cover, instruction, legend, etc.)
- Each question tagged with source sheet name: `"Sheet › Category"`
- `.xlsm` macro-enabled workbooks: macros detected, data read with `data_only=True`, exported with `keep_vba=True`

**DOCX:**
- `_parse_docx_rows()` in `agents.py` — tables first, paragraphs fallback, full-text last resort
- All table rows normalised to `{"requirement": text, "section": table_header}` regardless of original column names
- Scoring/rubric tables filtered by pattern (`Excellent Response`, `General Instructions`, etc.)
- `_parse_rfp` hard-wires `req_col="requirement"` for DOCX — don't rely on Claude column detection

## Re-run Agents
- `GET /api/rfp/<id>/rerun?mode=all|flagged|unanswered` — SSE stream
- Resets question statuses then re-runs the pipeline with current KB
- UI: ↺ Re-run button on completed RFP detail page

## Database
- Path: `naughtrfp.db` (gitignored)
- Thread-local connections via `db._get_con()`
- FTS5 multi-strategy search: phrase → prefix-AND → prefix-OR → LIKE fallback
- After changing question statuses, call `db.sync_rfp_counts(rfp_id)`
- Tables: settings, rfps, questions, knowledge_base, kb_search (FTS5), agent_logs, rfp_documents, demo_plans, token_usage, discovered_rfps

## Multi-document RFPs
- `rfp_documents` table: each file is a document under one RFP project
- `questions.document_id` links questions to source document
- Upload accepts `files` (plural) form field

## Okta Authentication (plumbing — disabled by default)
- Routes: `/auth/login`, `/auth/callback`, `/auth/logout`
- Full OIDC Authorization Code + PKCE flow
- Controlled by `okta_auth_enabled` setting (default: `false`)
- **Leave disabled** for demo/judge access

## LiteLLM-specific notes
- Model names: `claude-sonnet-4-6`, `claude-haiku-4-5` (no date suffixes on this proxy)
- Use Anthropic endpoint (`/v1/messages`) not OpenAI (`/v1/chat/completions`) — team key restriction
- Key format: `sk-...` (LiteLLM virtual key)

## Gitignore reminder
Never commit: `naughtrfp.db`, `uploads/`, `exports/`, `__pycache__/`, `.env`
