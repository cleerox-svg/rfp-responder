# Feature Design — Canadian Public Sector RFP Discovery
**Researched by:** Integration Specialist agent
**Date:** 2026-07-08

---

## What it does

Allows an Okta Pre-Sales SE to discover open Canadian public sector RFPs focused on Identity and AI security — surfaced automatically in NaughtRFP so they can import directly rather than hunting manually across procurement portals.

---

## Data Sources (Ranked)

| Source | Coverage | Access | Priority |
|---|---|---|---|
| **CanadaBuys** (`canadabuys.canada.ca`) | All federal tenders >$25K — SSC, TBS, CSE, DND, RCMP, Health Canada | Public, no auth. httpx GET to search URL | **MVP — Channel 1** |
| **Google Custom Search MCP** (`mcp__google__google-search_custom`) | Searches canadabuys.ca + merx.com + provincial portals simultaneously | Already in session — uses `sites` array filter | **MVP — Channel 2** |
| **GovBid.ca** | 2,411+ federal + provincial aggregated tenders | Public web | Fallback |
| **Alberta Purchasing Connection** (`vendor.purchasingconnection.ca`) | Alberta tenders — directly relevant to AHS-type deals | Public web | Provincial add-on |
| **BC Bid** (`bcbid.gov.bc.ca`) | BC provincial tenders | Public web | Provincial add-on |
| **MERX** (`merx.com`) | Federal + Ontario + some provincial | RSS feeds (category ID needed) | Post-hackathon |

**Key insight:** `mcp__google__google-search_custom` with `sites` parameter is the ideal MVP integration — it queries multiple procurement portals in one call with no scraper needed.

```json
{
  "q": "identity access management IAM cybersecurity tender RFP 2026",
  "sites": ["canadabuys.canada.ca", "merx.com", "vendor.purchasingconnection.ca", "bcbid.gov.bc.ca"]
}
```

---

## Keyword Groups

**Identity Core:** `identity access management`, `IAM`, `identity governance`, `IGA`, `privileged access management`, `PAM`, `single sign-on`, `SSO`, `multi-factor authentication`, `MFA`, `zero trust`, `ZTNA`, `federated identity`

**AI + Security:** `AI governance`, `AI security`, `artificial intelligence security`, `machine learning security`, `AI risk management`, `responsible AI`, `generative AI governance`

**Broad Cybersecurity:** `cybersecurity`, `information security`, `security operations`, `SIEM`, `cloud security`, `data protection`

**Relevant GSIN codes on CanadaBuys:** D301 (IT Software), D302 (IT Services), D304 (Cybersecurity), D305 (IT Consulting)

---

## UI Design

**New nav section: "Discover RFPs"** — top-level sidebar entry, not a widget.

**Result card:**
```
┌──────────────────────────────────────────────────────────────┐
│  [SOURCE: CanadaBuys / MERX / Alberta APC / BC Bid]          │
│                                                              │
│  Identity and Access Management Platform — Enterprise        │
│  Org:  Shared Services Canada                                │
│  #:    SSC-2026-RFP-0142                                     │
│                                                              │
│  Closing: 2026-08-15  (38 days remaining)  [RED if <7 days]  │
│  Posted:  2026-07-01   Est. Value: $2.4M                     │
│                                                              │
│  [IAM]  [SSO]  [Zero Trust]  [MFA]                          │
│                                                              │
│  [View on Portal ↗]      [Import into NaughtRFP →]          │
└──────────────────────────────────────────────────────────────┘
```

**Filters:** `All` | `Identity / IAM` | `Cybersecurity` | `AI Security` | `Federal` | `Provincial`

**Import flow:** Creates RFP project shell pre-filled with title, org, solicitation number, closing date, source URL. SE then uploads the actual tender documents (PDF/DOCX from the portal) to run the agent pipeline.

---

## Technical Approach (MVP)

No new dependencies. Reuses existing NaughtRFP infrastructure.

### Discovery module (`discovery.py`)

```python
# Two channels:
# 1. Google Custom Search MCP (via Claude tool call) — no scraper needed
# 2. httpx.get() to canadabuys.canada.ca with verify=False — direct fetch

# New env vars:
# DISCOVERY_ENABLED=true
# DISCOVERY_KEYWORDS=  (comma-separated override of defaults)
```

### New DB table

```sql
CREATE TABLE IF NOT EXISTS discovered_rfps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    source_url      TEXT,
    solicitation_no TEXT,
    title           TEXT NOT NULL,
    org_name        TEXT,
    gsin_code       TEXT,
    closing_date    TEXT,
    posted_date     TEXT,
    est_value       TEXT,
    relevance_score REAL DEFAULT 0,
    relevance_tags  TEXT,           -- JSON array
    status          TEXT DEFAULT 'new',  -- 'new', 'imported', 'dismissed'
    raw_data        TEXT,           -- JSON of all scraped fields
    fetched_at      TEXT DEFAULT (datetime('now')),
    rfp_id          INTEGER REFERENCES rfps(id)
);
```

### New API routes

| Method | Route | Description |
|---|---|---|
| GET | `/api/discover/run` | SSE stream — triggers fetch+score pipeline |
| GET | `/api/discover/results` | Returns cached discovery results |
| POST | `/api/discover/import/<id>` | Creates RFP shell from discovered result |
| POST | `/api/discover/dismiss/<id>` | Marks result as dismissed |

### Relevance scoring

Keyword-only for hackathon (no LLM call). Python function scores title + description against keyword groups, returns 0-10 + tags array. Claude Haiku upgrade post-hackathon.

---

## Implementation Plan

| Component | Agent | Est. time |
|---|---|---|
| `discovered_rfps` table + `db.py` methods | Data Engineer | 30 min |
| `discovery.py` — fetch + parse + deduplicate | Integration Specialist | 2-3 hrs |
| Flask routes + SSE streaming | Backend Engineer | 1.5 hrs |
| Relevance scoring (keyword) | AI Pipeline Engineer | 1 hr |
| Discover RFPs page — list view + cards | Frontend Engineer | 2-3 hrs |
| Import-to-RFP flow | Backend + Frontend | 1 hr |
| **Total (parallel)** | | **~3-4 hrs wall clock** |

---

## Design Decisions

1. **No auth/API keys required for MVP** — CanadaBuys is publicly accessible; Google Custom Search MCP already in session
2. **Reuse SSE streaming** — Discovery progress streams same way as agent pipeline — SE knows the pattern
3. **Graceful degradation** — if direct httpx fetch fails, fall back to search; if search returns nothing, surface manual portal link
4. **Import creates a shell, not a processed RFP** — SE downloads actual docs from portal and uploads to trigger pipeline; keeps existing processing unchanged
5. **Relevance scoring is keyword-only at MVP** — fast, no tokens, sufficient for filtering
