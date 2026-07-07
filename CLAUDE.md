# NaughtRFP — Claude Code Instructions

## How to run
```bash
cd C:\Users\ClaudeLeroux\rfp-responder
py app.py          # starts Flask on http://localhost:5000
```

> **Important:** Use `py` not `python` on this machine. `python` maps to the Windows Store alias and fails. `py` uses the real Python 3.14 installation at `C:\Program Files\Python314\`.

Install dependencies (first time only):
```bash
py -m pip install flask anthropic openpyxl
```

Seed knowledge base (first time only):
```bash
py seed_sig.py     # loads 615 entries from Okta SIG Core 2024
```

---

## Project context

**NaughtRFP** is an AI-powered RFP responder built for Okta Pre-Sales SEs. Hackathon POC — week of 2026-07-06. Theme: Agentic AI.

**Owner:** Claude Leroux, Okta Solutions Engineer, Canada Public Sector  
**LiteLLM proxy:** `https://llm.atko.ai` (Okta's internal LLM gateway)  
**Models:** `claude-sonnet-4-6` (reasoning/tool-use agents) · `claude-haiku-4-5` (lightweight extraction agents)

---

## Key files

| File | Purpose |
|---|---|
| `app.py` | Flask backend — all routes, SSE streaming, Okta auth stubs |
| `agents.py` | All 9 agent classes, tools, web search, KB search |
| `db.py` | SQLite wrapper — thread-local connections, FTS5 |
| `export_handler.py` | CSV/XLSX export with colour-coded response codes |
| `seed_kb.py` | 25 hand-crafted Okta baseline Q&A pairs |
| `seed_sig.py` | Loads `Okta_SIG_Core.xlsm` → KB (615 entries) |
| `sample_rfp.csv` | 34-requirement IGA RFP for testing |
| `templates/index.html` | Single-page app shell |
| `static/style.css` | Okta dark navy theme with 3D depth system |
| `static/app.js` | Full SPA — routing, agent feed, KB, demo prep |
| `.env.example` | Template for judge/local credentials — copy to `.env` |
| `SESSION_LOG.md` | Full build session log — decisions, problems, prompts |
| `docs/solution.md` | Problem statement and scope (hackathon Day 1 spec) |
| `docs/prd.md` | Full PRD with 34 user stories (hackathon Day 1 spec) |
| `docs/multiAgentDesign.md` | Multi-agent architecture design document (817 lines) |

---

## Architecture rules

- **Always use `py`** not `python` to invoke Python
- **Always update `README.md`** after any non-trivial feature change (agents, routes, performance, new UI screens)
- **Work in small chunks** with a visible task list (`TaskCreate` / `TaskUpdate`)
- **SQLite is thread-safe** — the DB uses thread-local connections with WAL mode. Don't add `check_same_thread=False` workarounds.
- **CSS depth tokens** are defined in `:root` — use `var(--depth-raised)`, `var(--depth-inset)`, `var(--card-grad)` etc. Don't hardcode shadow values.
- **Model constants** are `_MODEL` and `_MODEL_FAST` in `agents.py` — never hardcode model strings elsewhere.
  - `_MODEL = "claude-sonnet-4-6"` — Analysis Agent, Answer Agent, Demo Prep Agent, AI KB Search
  - `_MODEL_FAST = "claude-haiku-4-5"` — Customer Agent, Parser Agent, Web Summarizer

## SSL / Corporate proxy
Okta's corporate proxy does SSL inspection. All `httpx` clients must use `verify=False`. The `_make_client()` helper in `agents.py` handles this for Claude API calls. For direct `httpx` calls elsewhere, always pass `verify=False`.

## Agent pipeline (9 agents)
```
Upload → Customer Agent (Haiku) → Parser Agent (Haiku) → Analysis Agent (Sonnet)
       → Research Agent (local — FTS5 + httpx, no LLM)
       → Answer Agent (Sonnet, 6 parallel workers, agentic tool loop)
       → Scoring Agent (local — aggregation) → Review Agent (local — rule-based)
       ↓ on demand:
       KB Ingestion Agent   (local — FTS5 dedup, → Add to KB button)
       Demo Prep Agent      (Sonnet, → 🎭 Demo Prep button)
```

## Okta Authentication (plumbing — disabled by default)
- Routes: `/auth/login`, `/auth/callback`, `/auth/logout` in `app.py`
- Full OIDC Authorization Code + PKCE flow
- Controlled by `okta_auth_enabled` setting (default: `false`)
- Configure via Settings UI: Okta Domain, Client ID, Redirect URI
- **Leave disabled** for judge/demo access — no Okta account required

## Environment / .env bootstrap
- Copy `.env.example` to `.env` and fill in `LITELLM_API_KEY`
- App reads `.env` on startup via `_load_dotenv()` + `_env_bootstrap()` in `app.py`
- Supported vars: `LITELLM_API_KEY`, `LITELLM_BASE_URL`, `OKTA_DOMAIN`, `OKTA_CLIENT_ID`, `OKTA_REDIRECT_URI`
- `.env` is gitignored — never commit it

## Database
- Path: `naughtrfp.db` (gitignored)
- Thread-local connections via `db._get_con()`
- FTS5 on `knowledge_base` — use `db.search_knowledge_base(query)` which runs multi-strategy search (phrase → prefix-AND → prefix-OR → LIKE fallback)
- After changing question statuses, call `db.sync_rfp_counts(rfp_id)` to update header scores

## Multi-document RFPs
- `rfp_documents` table: each uploaded file is a document record under one RFP project
- `questions.document_id` links questions to their source document
- `db.sync_rfp_counts(rfp_id)` aggregates counts across all documents
- Upload endpoint accepts `files` (plural) form field for batch upload

## LiteLLM-specific notes
- Model names on this proxy: `claude-sonnet-4-6`, `claude-haiku-4-5` (no date suffixes)
- OpenAI endpoint (`/v1/chat/completions`) has team model restrictions — use Anthropic endpoint (`/v1/messages`) via the `anthropic` SDK
- Key format: `sk-...` (LiteLLM virtual key, not a raw Anthropic key)

## Gitignore reminder
These are already in `.gitignore` — never commit them:
- `naughtrfp.db`
- `uploads/`
- `exports/`
- `__pycache__/`
- `.env`
