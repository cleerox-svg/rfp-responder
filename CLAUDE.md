# NaughtRFP — Claude Code Instructions

## How to run (local dev)

```bash
cd C:\Users\ClaudeLeroux\rfp-responder
py app.py          # starts Flask on http://localhost:5000
```

> **Important:** Use `py` not `python` on this machine. `python` maps to the Windows Store alias and fails. `py` uses the real Python 3.14 installation at `C:\Program Files\Python314\`.

Install dependencies (first time only):
```bash
py -m pip install flask anthropic openpyxl python-docx pdfplumber gunicorn
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

## Deployment

**Live URL:** https://rfp.naughtid.com
**Platform:** AWS EC2 t3.medium (Ubuntu 24.04) — `us-east-1`
**Elastic IP:** 100.56.213.110
**Stack:** Docker Compose — Gunicorn (gthread, 2 workers × 8 threads) + Nginx (Alpine)
**TLS:** Let's Encrypt via Certbot — cert at `/etc/letsencrypt/live/rfp.naughtid.com/`
**Data:** Docker named volume `naughtrfp_data` → `/data/` (SQLite DB + uploads + exports)
**Key pair:** `naughtIDRFP_Keypair.pem` at `C:\Users\ClaudeLeroux\Desktop\Claude Code Projects\NaughtRFP_Keystore\`

### SSH access
```bash
ssh -i "C:\Users\ClaudeLeroux\Desktop\Claude Code Projects\NaughtRFP_Keystore\naughtIDRFP_Keypair.pem" ubuntu@100.56.213.110
cd ~/rfp-responder/rfp-responder
```

### Container management
```bash
docker compose ps                   # check status
docker compose logs -f app          # live app logs
docker compose restart app          # restart after .env change
docker compose down && docker compose up -d  # full restart
```

### CI/CD — GitHub Actions
Every `git push origin master` auto-deploys via `.github/workflows/deploy.yml`:
1. SSH into EC2 → `git pull`
2. `docker compose build --no-cache app`
3. `docker compose up -d --no-deps app`
4. Health check via `curl http://localhost/api/kb/stats`

**Required GitHub secrets:** `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`
Monitor runs: https://github.com/cleerox-svg/rfp-responder/actions

### Git workflow rule
**Push to GitHub only** — `git push origin master`. Do NOT sync to local Desktop folders.
GitHub is the single source of truth. The CI/CD pipeline handles deployment automatically.

### Deployment reference
Full step-by-step guide (Route 53, Certbot, operations, troubleshooting): `DEPLOY.md`

---

## Key files

| File | Purpose |
|---|---|
| `app.py` | Flask backend — all routes, SSE, multi-doc, re-run, .env bootstrap, Okta auth stubs |
| `agents.py` | All 9 agents + KBDirectIngestionAgent, APEX/CoM demo prep, PDF/XLSX/DOCX parsers, hybrid RRF search |
| `db.py` | SQLite wrapper — thread-local connections, FTS5, KB sources management |
| `export_handler.py` | Multi-sheet CSV/XLSX/XLSM export (VBA preserved, EXPORTS_DIR env var) |
| `Dockerfile` | python:3.11-slim + gunicorn, data at /data/ |
| `docker-compose.yml` | app + nginx services, naughtrfp_data volume, /etc/letsencrypt mount |
| `nginx.conf` | HTTPS reverse proxy — SSE buffering off, 310s timeout on streaming routes |
| `deploy/aws-setup.sh` | One-shot EC2 provisioning script |
| `DEPLOY.md` | Full AWS deployment guide |
| `.github/workflows/deploy.yml` | GitHub Actions auto-deploy on push to master |
| `seed_kb.py` | 25 hand-crafted Okta baseline Q&A pairs |
| `seed_sig.py` | Loads `Okta_SIG_Core.xlsm` → KB (615 entries) |
| `seed_confluence.py` | 15 compliance/security entries from Okta Confluence |
| `discovery.py` | RFP discovery from external sources |
| `relevance.py` | Relevance scoring for discovered RFPs |
| `sample_rfp.csv` | 34-requirement IGA RFP for testing |
| `setup.sh` | One-command Mac/Linux setup |
| `templates/index.html` | Single-page app shell — collapsible sidebar, all pages |
| `static/style.css` | Okta dark navy theme with 3D CSS depth token system |
| `static/app.js` | Full SPA — routing, agent feed, APEX demo prep, KB sources panel, multi-doc |
| `.env.example` | Template for credentials — copy to `.env` |
| `SESSION_LOG.md` | Full build history for session continuity |

---

## Architecture rules

- **Always use `py`** not `python` to invoke Python on Windows
- **Always update `README.md`** after any non-trivial feature change
- **Work in small chunks** with a visible task list (`TaskCreate` / `TaskUpdate`)
- **Push to GitHub only** — `git push origin master`. No local folder syncs.
- **SQLite is thread-safe** via thread-local connections with WAL mode. Don't add `check_same_thread=False` workarounds.
- **CSS depth tokens** are in `:root` — use `var(--depth-raised)`, `var(--depth-inset)`, `var(--card-grad)`. Never hardcode shadow values.
- **Model constants** are `_MODEL` and `_MODEL_FAST` in `agents.py` — never hardcode model strings elsewhere.

## SSL / Corporate proxy
Okta's corporate proxy does SSL inspection. All `httpx` clients must use `verify=False`. The `_make_client()` helper in `agents.py` handles this. For direct `httpx` calls elsewhere, always pass `verify=False`.

## Agent pipeline (9 + 1 agents)
```
Upload → Customer Agent (Haiku) → Parser Agent (Haiku) → Analysis Agent (Sonnet)
       → Research Agent (local: FTS5 hybrid RRF pre-fetch + httpx web search)
       → Answer Agent (Sonnet, 6 parallel workers, agentic tool loop)
       → Scoring Agent (local: aggregation) → Review Agent (local: rule-based)
       ↓ on demand:
       KB Ingestion Agent        (local: FTS5 dedup)     → Add to KB button
       KB Direct Ingestion Agent (Haiku+Sonnet)          → Upload to KB button
       Demo Prep Agent           (Sonnet, APEX/CoM)      → 🎭 Demo Prep button
```

## APEX / Command of the Message (Demo Prep)
- Demo Prep Agent generates a full APEX Brief: Mantra, Before/After Scenarios, PBOs, Required Capabilities, Unique Differentiators
- Each demo section maps to a PBO and Required Capability
- Talking points use CoM Before → After language
- Discovery questions help validate the brief pre-demo
- APEX is Okta's internal CoM + MEDDPICCC framework — see Confluence Presales AI Strike Team page

## File format support
Accepted: `.csv`, `.xlsx`, `.xls`, `.xlsm`, `.docx`, `.pdf`

**Multi-tab XLSX/XLSM:**
- Parser iterates ALL sheets (skips nav tabs by name: cover, instruction, legend, etc.)
- Each question tagged with source sheet name: `"Sheet › Category"`
- `.xlsm` macro-enabled workbooks: macros detected, data read with `data_only=True`, exported with `keep_vba=True`
- Merged cells resolved via `ws.merged_cells.ranges` — anchor value propagated to all cells in range

**DOCX:**
- `_parse_docx_rows()` in `agents.py` — tables first, paragraphs fallback, full-text last resort
- All table rows normalised to `{"requirement": text, "section": table_header}`
- Scoring/rubric tables filtered by pattern

**PDF:**
- `_parse_pdf_rows()` in `agents.py` — requires `pdfplumber`
- Tables first, text paragraph fallback per page
- Graceful empty return if pdfplumber not installed

## Knowledge Base
- **Hybrid RRF search:** FTS5 (BM25) + per-keyword broadened pass, fused via Reciprocal Rank Fusion (k=60)
- **KB Sources panel:** `/kb` page shows source documents with entry counts, type badges, filter/delete/re-seed
- **FTS5 delete safety:** `delete_kb_source()` in `db.py` cleans `kb_search` rowids before deleting from `knowledge_base` — no triggers exist, manual cleanup required
- **Direct upload:** `POST /api/kb/upload-document` — any CSV/XLSX/XLSM/DOCX/PDF ingested directly without creating an RFP

## Re-run Agents
- `GET /api/rfp/<id>/rerun?mode=all|flagged|unanswered` — SSE stream
- Resets question statuses then re-runs the pipeline with current KB
- UI: ↺ Re-run button on completed RFP detail page

## Database
- **Local dev path:** `naughtrfp.db` (gitignored)
- **Production path:** `/data/naughtrfp.db` (Docker volume, set via `DATABASE_PATH` env var)
- Thread-local connections via `db._get_con()`
- FTS5 multi-strategy search: phrase → prefix-AND → prefix-OR → LIKE fallback
- After changing question statuses, call `db.sync_rfp_counts(rfp_id)`
- Tables: settings, rfps, questions, knowledge_base, kb_search (FTS5), agent_logs, rfp_documents, demo_plans, token_usage, discovered_rfps

## Environment variables (production)
| Var | Default | Purpose |
|---|---|---|
| `DATABASE_PATH` | `naughtrfp.db` | SQLite file path |
| `UPLOAD_FOLDER` | `uploads` | Uploaded RFP files |
| `EXPORTS_DIR` | `exports` | Generated export files |
| `PORT` | `5000` | Flask/Gunicorn port |
| `FLASK_DEBUG` | `false` | Debug mode |
| `FLASK_HOST` | `0.0.0.0` | Bind address |
| `LITELLM_API_KEY` | — | API key (set in .env) |
| `LITELLM_BASE_URL` | — | LiteLLM or Anthropic URL |
| `FLASK_SECRET_KEY` | — | Session secret (set in .env) |

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
- Outside Okta VPN: use `LITELLM_BASE_URL=https://api.anthropic.com` with a personal Anthropic key

## Gitignore reminder
Never commit: `naughtrfp.db`, `uploads/`, `exports/`, `__pycache__/`, `.env`
