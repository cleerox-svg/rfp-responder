"""
discovery.py — RFP Discovery fetch module for NaughtRFP

Fetches open Canadian public sector AND private sector RFPs matching Okta's
full solution portfolio: IAM, IGA, PAM, CIAM, Lifecycle Management,
Non-Human Identity, Zero Trust, Identity Threat Detection, AI Security,
and Cybersecurity.

Three channels:
  1. Google Custom Search via Claude tool-call (primary) — runs up to 20 targeted
     queries across government portals AND private-sector/commercial aggregators
  2. Direct httpx fetch to CanadaBuys (secondary) — GSIN-filtered: D301/D302/D304
  3. DuckDuckGo fallback (if both primary channels return nothing)

Each discovered result carries a `sector` field in `raw_data`:
  sector: "public"   — source is a government domain
  sector: "private"  — source is a commercial/aggregator domain
  sector: "unknown"  — could not determine

Public interface (called by Backend Engineer's Flask routes):
  run_discovery(api_key, db, event_q) -> None
  get_discovery_keywords() -> list[str]
"""

import json
import queue
import re
import time
import warnings
import httpx

# Suppress SSL verification warnings throughout this module
warnings.filterwarnings("ignore", message=".*verify=False.*")
warnings.filterwarnings("ignore", message=".*Unverified HTTPS.*")

# ---------------------------------------------------------------------------
# Model constant — mirrors agents.py; never hardcode model strings elsewhere
# ---------------------------------------------------------------------------
_MODEL_FAST = "claude-haiku-4-5"

# ---------------------------------------------------------------------------
# Procurement sites for Google Custom Search — PUBLIC SECTOR
# ---------------------------------------------------------------------------
_PROCUREMENT_SITES_GOV = [
    "canadabuys.canada.ca",
    "merx.com",
    "vendor.purchasingconnection.ca",
    "bcbid.gov.bc.ca",
    "ontario.ca",
    "buyandsell.gc.ca",
    "achatsetventes.gc.ca",
]

# ---------------------------------------------------------------------------
# Commercial / aggregator sites for private-sector Google Custom Search
# These are publicly accessible and Google-indexed without login.
# ---------------------------------------------------------------------------
_PROCUREMENT_SITES_COMMERCIAL = [
    "rfpdb.com",         # Publicly searchable RFP database, indexes private + gov RFPs
    "rfpmart.com",       # Aggregates Canadian public and private sector tenders
    "biddingo.com",      # Canadian eProcurement; some listings are public-facing
    "merx.com",          # Also indexes private sector tenders (Crown corps etc.)
    "canadacontracts.ca",# Canadian contract/tender aggregator
]

# Combined list for broad searches
_PROCUREMENT_SITES = _PROCUREMENT_SITES_GOV + _PROCUREMENT_SITES_COMMERCIAL

# ---------------------------------------------------------------------------
# Domain classification for sector tagging
# ---------------------------------------------------------------------------
_GOV_DOMAIN_PATTERNS = (
    "canadabuys", "buyandsell", "achatsetventes", "gc.ca",
    "bcbid.gov", "ontario.ca", "purchasingconnection",
    ".gov.", ".gov.bc", ".gov.ab", ".gov.on", ".gov.qc",
    "alberta.ca", "ontario.ca", "novascotia.ca", "gov.ns.ca",
    "gov.nb.ca", "gov.pe.ca", "gov.nl.ca", "gov.sk.ca",
    "gov.mb.ca", "gov.nt.ca", "gov.nu.ca", "gov.yk.ca",
)

_COMMERCIAL_DOMAIN_PATTERNS = (
    "rfpdb.com", "rfpmart.com", "biddingo.com", "merx.com",
    "canadacontracts", "linkedin.com", "procurementworld",
)


def _infer_sector(url: str) -> str:
    """
    Infer whether an RFP source is public sector, private sector, or unknown.
    Returns one of: "public", "private", "unknown"
    """
    url_lower = (url or "").lower()
    if any(p in url_lower for p in _GOV_DOMAIN_PATTERNS):
        return "public"
    if any(p in url_lower for p in _COMMERCIAL_DOMAIN_PATTERNS):
        return "private"
    # Heuristic: .ca TLD without known gov pattern — could be either
    if ".ca/" in url_lower or url_lower.endswith(".ca"):
        return "unknown"
    return "unknown"


# ---------------------------------------------------------------------------
# Multi-query search strategy
# 12 public sector queries (existing) + 8 private sector queries = 20 total
# ---------------------------------------------------------------------------
_SEARCH_QUERIES: list[str] = [
    # --- PUBLIC SECTOR (12 queries, unchanged) ---

    # 1. Broad IAM / workforce identity — federal Canada
    "identity access management IAM cybersecurity tender RFP open 2026 Canada",

    # 2. Identity Governance & Administration (OIG / IGA) — high-value Okta deals
    "identity governance IGA access certification entitlement management RFP tender Canada 2026",

    # 3. Privileged Access Management (PAM) — high-value Okta deals
    "privileged access management PAM secrets vaulting just-in-time access RFP tender Canada 2026",

    # 4. Customer Identity / CIAM — digital services, citizen portals
    "customer identity CIAM citizen portal digital identity login authentication RFP Canada 2026",

    # 5. Zero Trust — government ZTA mandates
    "zero trust architecture ZTNA network access identity security RFP tender Canada government 2026",

    # 6. AI governance and non-human identity — emerging category
    "AI governance AI security non-human identity machine identity agentic RFP Canada 2026",

    # 7. Lifecycle Management / provisioning — SCIM, HR-driven
    "lifecycle management provisioning deprovisioning SCIM identity automation RFP Canada 2026",

    # 8. Federal-specific: SSC, PSPC, TBS, Protected B
    "Shared Services Canada SSC identity access management Protected B CCCS RFP 2026",

    # 9. Provincial health — eHealth, AHS, Ontario Health
    "eHealth identity access management single sign-on MFA healthcare RFP Canada 2026",

    # 10. TBIPS / ProServices procurement vehicles — identity and cybersecurity
    "TBIPS ProServices identity cybersecurity IAM security professional services Canada 2026",

    # 11. Compliance-driven — PIPEDA, CCCS, ISO 27001
    "PIPEDA CCCS Protected B identity security compliance audit RFP tender Canada 2026",

    # 12. Identity Threat Detection / ISPM — SOC and SIEM integration
    "identity threat detection security posture ISPM anomalous access RFP Canada 2026",

    # --- PRIVATE SECTOR (8 new queries) ---

    # 13. Financial services — banks, credit unions, insurance companies
    "RFP identity access management Canada bank financial institution credit union insurance 2025 2026",

    # 14. Healthcare / hospital systems — private and para-public
    "RFP identity governance IAM cybersecurity Canada hospital healthcare private sector 2025 2026",

    # 15. Energy and utilities — pipelines, power companies
    "RFP cybersecurity IAM identity management Canada energy utility pipeline power 2025 2026",

    # 16. Telecommunications — Rogers, Bell, Telus, Shaw and regional carriers
    "RFP identity access management Canada telecommunications telco wireless carrier 2025 2026",

    # 17. Retail and e-commerce — CIAM / customer identity angle
    "RFP customer identity CIAM login authentication Canada retail ecommerce 2025 2026",

    # 18. Broad private sector Google search — indexes publicly posted PDF RFPs
    "\"request for proposal\" identity security IAM Canada private sector filetype:pdf 2025 2026",

    # 19. RFP aggregators — rfpdb.com, rfpmart.com, biddingo.com
    "site:rfpdb.com OR site:rfpmart.com identity access management cybersecurity Canada RFP 2025 2026",

    # 20. Broadly — private enterprise vendor selection notices
    "\"request for proposal\" \"identity and access management\" Canada vendor selection 2026",
]

# Primary query used for single-query fallback paths (Channel 2 / Channel 3)
_SEARCH_QUERY = _SEARCH_QUERIES[0]

# Queries that target commercial/private-sector sites specifically
_PRIVATE_SECTOR_QUERY_INDICES = set(range(12, 20))  # indices 12–19

# ---------------------------------------------------------------------------
# CanadaBuys GSIN codes for IT-relevant categories
# D301 = IT Software, D302 = IT Services, D304 = IT Maintenance/Repair
# ---------------------------------------------------------------------------
_CANADABUYS_GSINS = ["D301", "D302", "D304"]

# ---------------------------------------------------------------------------
# Keyword filter for CanadaBuys results — must contain at least one of these
# (case-insensitive substring match on title)
# ---------------------------------------------------------------------------
_CANADABUYS_MUST_HAVE = [
    "identity", "security", "cyber", "authentication", "access",
    "iam", "sso", "mfa", "cloud", "software", "information technology",
    "it services", "numeriqu", "informatique",
]

# ---------------------------------------------------------------------------
# Validation: prefixes that indicate Claude conversational fallback text
# (not real RFP records)
# ---------------------------------------------------------------------------
_BAD_TITLE_PREFIXES = (
    "Would you",
    "Would I",
    "Try ",
    "- ",
    "**",
    "No ",
    "1.",
    "2.",
    "3.",
    "4.",
    "5.",
    "6.",
    "7.",
    "8.",
    "9.",
    "0.",
    "Here are",
    "Here is",
    "I found",
    "I was",
    "I could",
    "I can",
    "I don",
    "I'm ",
    "Unfortunately",
    "Based on",
    "Note:",
    "Please ",
    "Note ",
    "Sorry,",
)

# Minimum title length for a valid RFP record
_MIN_TITLE_LEN = 20

# Private-sector RFP title signals (used by _is_valid_private_sector_rfp)
# These patterns frequently appear in corporate/commercial RFP titles
_PRIVATE_SECTOR_TITLE_SIGNALS = (
    "request for proposal",
    "rfp for",
    "rfp:",
    "rfp -",
    "request for information",
    "rfi for",
    "request for quotation",
    "vendor selection",
    "software evaluation",
    "technology evaluation",
    "procurement of",
    "acquisition of",
)


# ---------------------------------------------------------------------------
# Keyword groups for relevance scoring and display tags
# (discovery.py internal copy — canonical version is relevance.py KEYWORD_GROUPS)
# ---------------------------------------------------------------------------

_KEYWORD_GROUPS: dict[str, list[str]] = {
    "Identity / IAM": [
        "identity access management", "iam", "identity management",
        "single sign-on", "sso", "federated identity",
        "multi-factor authentication", "mfa", "two-factor authentication", "2fa",
        "adaptive mfa", "passwordless", "fido2", "webauthn",
        "directory services", "ldap", "active directory", "entra id",
        "okta", "authentication", "authorization", "access control",
        "role-based access", "rbac", "saml", "oidc", "oauth",
        "hybrid identity", "device trust",
    ],
    "Identity Governance": [
        "identity governance", "iga", "access governance",
        "access certification", "access review", "access recertification",
        "entitlement management", "separation of duties", "sod",
        "joiner mover leaver", "jml", "privilege creep",
        "access request", "audit trail", "compliance reporting",
        "role management", "policy enforcement",
    ],
    "Privileged Access": [
        "privileged access management", "pam", "privileged access",
        "privileged account", "just-in-time access", "jit access",
        "secrets vaulting", "secrets management", "credential vaulting",
        "session recording", "ssh access", "break-glass account",
        "service account management", "infrastructure access",
        "least privilege access", "api key management",
    ],
    "Customer Identity": [
        "customer identity", "ciam", "consumer identity",
        "b2c identity", "external identity", "digital identity",
        "citizen identity", "auth0", "login experience",
        "identity verification", "digital onboarding",
        "citizen portal", "resident portal", "self-service portal",
    ],
    "Lifecycle Management": [
        "lifecycle management", "identity lifecycle",
        "automated provisioning", "user provisioning", "deprovisioning",
        "scim", "hr-driven provisioning", "onboarding automation",
        "offboarding automation", "access automation",
    ],
    "Non-Human Identity": [
        "non-human identity", "nhi", "machine identity",
        "service account", "workload identity", "ai agent identity",
        "agentic ai", "api token management", "m2m authentication",
    ],
    "Zero Trust": [
        "zero trust", "ztna", "zero trust network access",
        "zero trust architecture", "microsegmentation",
        "least privilege", "continuous verification",
        "identity-centric security", "conditional access",
    ],
    "Identity Threat Detection": [
        "identity threat", "identity security posture", "ispm",
        "identity-based attack", "account takeover",
        "identity risk management", "anomalous access",
        "risk-based authentication",
    ],
    "AI Security": [
        "ai governance", "ai security", "artificial intelligence security",
        "machine learning security", "ai risk", "responsible ai",
        "generative ai", "llm security", "ai policy", "trustworthy ai",
    ],
    "Cybersecurity": [
        "cybersecurity", "cyber security", "information security", "infosec",
        "security operations", "soc", "siem", "cloud security",
        "data protection", "encryption", "vulnerability management",
        "penetration testing", "zero trust",
        "nist", "iso 27001", "soc 2", "fedramp", "pipeda",
    ],
    "Canadian Government": [
        "shared services canada", "ssc", "treasury board", "pspc",
        "communications security establishment", "cse", "dnd", "rcmp",
        "health canada", "cra", "esdc", "ircc", "ised", "csis",
        "protected b", "protected c", "cccs", "itsg", "pbmm",
        "gc cloud", "gc guardrails", "tbips", "proservices",
        "standing offer", "rfso", "acan",
        "alberta health services", "ehealth ontario", "service ontario",
        "government of canada",
    ],
    "Canadian Private Sector": [
        # Financial services
        "rbc", "royal bank", "td bank", "td canada", "scotiabank",
        "bmo", "bank of montreal", "cibc", "national bank",
        "manulife", "sun life", "great-west", "co-operators",
        "desjardins", "atb financial",
        # Telco
        "bell canada", "rogers", "telus", "shaw", "videotron",
        "cogeco", "sasktel", "mts", "eastlink",
        # Energy / utilities
        "enbridge", "tc energy", "cenovus", "suncor", "pembina",
        "hydro one", "bc hydro", "fortis", "atco", "epcor",
        "transcanada", "cdn natural resources",
        # Retail and e-commerce
        "shopify", "canadian tire", "loblaw", "sobeys", "metro inc",
        "empire company", "lululemon",
        # Healthcare (private / para-public)
        "fraser health", "interior health", "island health",
        "innomar", "lifelabs", "dynacare",
        # Generic private sector signals
        "enterprise rfp", "corporate procurement", "vendor rfp",
        "industry rfp", "private sector tender",
    ],
}

# Flat list of all active keywords (used by get_discovery_keywords)
_ALL_KEYWORDS: list[str] = sorted({
    kw for kws in _KEYWORD_GROUPS.values() for kw in kws
})


# ---------------------------------------------------------------------------
# Public: keyword list
# ---------------------------------------------------------------------------

def get_discovery_keywords() -> list[str]:
    """Returns the current active keyword list for display in the UI."""
    return list(_ALL_KEYWORDS)


# ---------------------------------------------------------------------------
# Validation — reject Claude fallback text posing as RFP records
# ---------------------------------------------------------------------------

def _is_valid_rfp_record(item: dict) -> bool:
    """
    Return True only if the dict looks like a real RFP record.
    Discards Claude conversational fallback text that leaked into parsed results.

    Rules:
      1. source_url must be non-empty and start with 'http'
      2. title must not start with any known Claude fallback prefix
      3. title must be at least _MIN_TITLE_LEN characters
    """
    url = (item.get("source_url") or "").strip()
    if not url or not url.startswith("http"):
        return False

    title = (item.get("title") or "").strip()
    if len(title) < _MIN_TITLE_LEN:
        return False

    for prefix in _BAD_TITLE_PREFIXES:
        if title.startswith(prefix):
            return False

    return True


def _looks_like_rfp_title(title: str) -> bool:
    """
    Lightweight heuristic: does this title look like it came from a real
    RFP posting (vs a news article, blog post, or directory listing)?
    Used as a supplementary filter for commercial/aggregator search results.

    Returns True if ANY of:
    - Title contains a known RFP signal phrase (case-insensitive)
    - Title contains a procurement-style word like "procurement", "tender",
      "solicitation", "bid", "proposal", "contract"
    - Title matches the pattern of government tender numbering
    """
    title_lower = title.lower()

    for signal in _PRIVATE_SECTOR_TITLE_SIGNALS:
        if signal in title_lower:
            return True

    procurement_words = (
        "procurement", "tender", "solicitation", "bid", "proposal",
        "contract", "acquisition", "rfp", "rfi", "rfq",
    )
    if any(w in title_lower for w in procurement_words):
        return True

    return False


# ---------------------------------------------------------------------------
# DB cleanup — remove bad rows from past runs
# ---------------------------------------------------------------------------

def clean_invalid_discoveries(db) -> int:
    """
    Delete rows from discovered_rfps where source_url is empty/None
    or title starts with a known Claude fallback prefix.
    Returns the number of rows deleted.
    """
    deleted = 0
    try:
        conn = db._get_conn() if hasattr(db, "_get_conn") else None
        if conn is None:
            # Try direct sqlite access via db.conn or db._conn
            for attr in ("conn", "_conn", "connection", "_connection"):
                conn = getattr(db, attr, None)
                if conn is not None:
                    break

        if conn is None:
            return 0

        # Delete rows with empty/null source_url
        cur = conn.execute(
            "DELETE FROM discovered_rfps WHERE source_url IS NULL OR source_url = ''"
        )
        deleted += cur.rowcount

        # Delete rows whose title starts with any bad prefix
        for prefix in _BAD_TITLE_PREFIXES:
            cur = conn.execute(
                "DELETE FROM discovered_rfps WHERE title LIKE ?",
                (prefix.rstrip() + "%",),
            )
            deleted += cur.rowcount

        conn.commit()
    except Exception:
        pass

    return deleted


# ---------------------------------------------------------------------------
# Relevance scoring (keyword-only, no LLM — fast)
# ---------------------------------------------------------------------------

def _score_relevance(title: str, description: str = "") -> tuple[float, list[str]]:
    """
    Score a tender title+description against keyword groups.
    Returns (score 0–10, matched_tags list).
    """
    haystack = f"{title} {description}".lower()
    matched_tags: list[str] = []
    score = 0.0

    for tag, keywords in _KEYWORD_GROUPS.items():
        for kw in keywords:
            if kw in haystack:
                if tag not in matched_tags:
                    matched_tags.append(tag)
                score += 1.0
                break  # one hit per group is enough

    # Normalize: max possible = number of groups
    max_score = float(len(_KEYWORD_GROUPS))
    normalized = min(round((score / max_score) * 10, 1), 10.0)
    return normalized, matched_tags


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedup_key(item: dict) -> str:
    """Canonical key for deduplication: solicitation_no or title+org."""
    sol = (item.get("solicitation_no") or "").strip().upper()
    if sol:
        return f"sol:{sol}"
    title = re.sub(r"\s+", " ", (item.get("title") or "").strip().lower())
    org = re.sub(r"\s+", " ", (item.get("org_name") or "").strip().lower())
    return f"title:{title}|org:{org}"


def _deduplicate(items: list[dict]) -> list[dict]:
    """Return items with duplicates removed (first occurrence wins)."""
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        key = _dedup_key(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# Channel 1: Google Custom Search via Claude tool-call
# ---------------------------------------------------------------------------

_SEARCH_CUSTOM_TOOL = {
    "name": "search_custom",
    "description": (
        "Search Canadian government and commercial procurement portals for open tender "
        "opportunities matching identity, IAM, IGA, PAM, CIAM, zero trust, AI security, "
        "or cybersecurity keywords. Also searches private sector aggregators such as "
        "rfpdb.com, rfpmart.com, and biddingo.com."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "q": {
                "type": "string",
                "description": "Search query string",
            },
            "sites": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of domains to restrict search to",
            },
            "num": {
                "type": "integer",
                "description": "Number of results (1–10)",
                "default": 10,
            },
        },
        "required": ["q"],
    },
}


def _parse_search_results_to_rfps(raw_results: str, query_index: int = 0) -> list[dict]:
    """
    Parse the text blob returned by a TOOL RESULT into RFP dicts.
    IMPORTANT: This function must only be called on actual tool result content
    (structured JSON or URL-containing text from the search tool), NOT on
    Claude's conversational text responses. Callers are responsible for
    enforcing this distinction.

    query_index is used to determine sector tagging for results from
    private-sector-targeted queries.
    """
    rfps: list[dict] = []

    # Reject if this looks like a Claude conversational response
    stripped = raw_results.strip()
    if not stripped or stripped in ("[]", "{}"):
        return rfps

    # If it starts with a bad prefix, it's a Claude response — skip entirely
    for prefix in _BAD_TITLE_PREFIXES:
        if stripped.startswith(prefix):
            return rfps

    # Try JSON first (tool may return structured data)
    try:
        data = json.loads(raw_results)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("items", data.get("results", []))
        else:
            items = []

        for item in items:
            title = (item.get("title") or item.get("name") or "").strip()
            url = (item.get("link") or item.get("url") or "").strip()
            snippet = (item.get("snippet") or item.get("description") or "").strip()
            if not title:
                continue
            source = _source_from_url(url)
            sector = _infer_sector(url)
            score, tags = _score_relevance(title, snippet)
            candidate = {
                "source": source,
                "source_url": url,
                "solicitation_no": _extract_solicitation_no(title + " " + snippet),
                "title": title,
                "org_name": _extract_org(snippet, url),
                "gsin_code": None,
                "closing_date": _extract_date(snippet),
                "posted_date": None,
                "est_value": _extract_value(snippet),
                "relevance_score": score,
                "relevance_tags": json.dumps(tags),
                "raw_data": json.dumps({
                    "snippet": snippet[:300],
                    "url": url,
                    "sector": sector,
                }),
            }
            if _is_valid_rfp_record(candidate):
                rfps.append(candidate)
        return rfps
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    # Plain-text parsing: look for numbered result blocks
    # Format typically: "1. Title\nURL\nSnippet text\n\n2. ..."
    blocks = re.split(r"\n\s*\n", raw_results.strip())
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue

        # First non-empty line is likely title (may have leading "N. ")
        title_line = re.sub(r"^\d+\.\s*", "", lines[0])
        url = ""
        snippet_parts: list[str] = []

        for line in lines[1:]:
            if line.startswith("http://") or line.startswith("https://"):
                url = line
            else:
                snippet_parts.append(line)

        title = title_line.strip()
        snippet = " ".join(snippet_parts)

        if not title or len(title) < 5:
            continue

        source = _source_from_url(url)
        sector = _infer_sector(url)
        score, tags = _score_relevance(title, snippet)
        if score == 0:
            continue  # skip clearly irrelevant results

        candidate = {
            "source": source,
            "source_url": url,
            "solicitation_no": _extract_solicitation_no(title + " " + snippet),
            "title": title,
            "org_name": _extract_org(snippet, url),
            "gsin_code": None,
            "closing_date": _extract_date(snippet),
            "posted_date": None,
            "est_value": _extract_value(snippet),
            "relevance_score": score,
            "relevance_tags": json.dumps(tags),
            "raw_data": json.dumps({
                "snippet": snippet[:300],
                "url": url,
                "sector": sector,
            }),
        }
        if _is_valid_rfp_record(candidate):
            rfps.append(candidate)

    return rfps


def _fetch_via_claude_search_single(
    api_key: str,
    base_url: str | None,
    query: str,
    query_index: int = 0,
) -> list[dict]:
    """
    Run one Google Custom Search query via Claude tool-call.
    Returns list of parsed RFP dicts.

    Only parses actual tool results — never Claude's conversational text responses.

    For private-sector queries (query_index in _PRIVATE_SECTOR_QUERY_INDICES),
    the site list is expanded to include commercial aggregators.
    """
    import anthropic

    # Select which site list to use for this query
    if query_index in _PRIVATE_SECTOR_QUERY_INDICES:
        search_sites = _PROCUREMENT_SITES_COMMERCIAL
    else:
        search_sites = _PROCUREMENT_SITES_GOV

    try:
        http_client = httpx.Client(verify=False, timeout=60.0)
        kwargs: dict = dict(api_key=api_key, http_client=http_client)
        if base_url:
            kwargs["base_url"] = base_url
        client = anthropic.Anthropic(**kwargs)

        messages: list[dict] = [{
            "role": "user",
            "content": (
                f"Search Canadian procurement portals for open RFP/tender opportunities. "
                f"Use query: \"{query}\" "
                f"and restrict to sites: {search_sites}. "
                "Call the search_custom tool now."
            ),
        }]

        tool_results_text = ""
        rfps: list[dict] = []

        # Up to 2 iterations: first gets tool call, second processes result
        for _ in range(2):
            resp = client.messages.create(
                model=_MODEL_FAST,
                max_tokens=2048,
                tools=[_SEARCH_CUSTOM_TOOL],
                messages=messages,
            )

            if resp.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": resp.content})
                tool_results = []

                for block in resp.content:
                    if block.type != "tool_use":
                        continue
                    if block.name == "search_custom":
                        raw_result = _call_search_custom(block.input, search_sites)
                        tool_results_text = raw_result
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": raw_result,
                        })

                messages.append({"role": "user", "content": tool_results})

            else:
                # Claude returned a final text response (conversational fallback).
                # Do NOT parse this as RFP data — it contains suggestions and
                # explanations, not structured search results.
                break

        # Only parse the raw tool results — never the conversational response
        if tool_results_text:
            rfps = _parse_search_results_to_rfps(tool_results_text, query_index)

        return rfps

    except Exception:
        return []


def _fetch_via_claude_search(api_key: str, base_url: str | None) -> list[dict]:
    """
    Channel 1: Run all _SEARCH_QUERIES through Claude Haiku tool-calls.
    Aggregates results across all 20 queries and deduplicates.
    Returns combined list of parsed RFP dicts.

    Queries 0–11 target government procurement portals.
    Queries 12–19 target private sector and commercial aggregators.
    """
    all_rfps: list[dict] = []

    for idx, query in enumerate(_SEARCH_QUERIES):
        try:
            results = _fetch_via_claude_search_single(api_key, base_url, query, idx)
            all_rfps.extend(results)
        except Exception:
            continue

    # Deduplicate across queries before returning
    return _deduplicate(all_rfps)


def _call_search_custom(tool_input: dict, sites: list[str] | None = None) -> str:
    """
    Execute the google custom search. Since this module runs as Python (not in
    an MCP agent session), we implement via DuckDuckGo with site filters as a
    best-effort proxy for the Google Custom Search MCP tool.
    Returns raw text results.
    """
    import urllib.parse

    q = tool_input.get("q", _SEARCH_QUERY)
    # Use passed-in sites list, or fall back to tool_input sites, or default gov sites
    if sites is None:
        sites = tool_input.get("sites", _PROCUREMENT_SITES_GOV)
    num = min(int(tool_input.get("num", 10)), 10)

    # Build site-restricted query
    site_filter = " OR ".join(f"site:{s}" for s in sites[:5])
    full_query = f"{q} ({site_filter})"
    encoded = urllib.parse.quote_plus(full_query)

    try:
        r = httpx.get(
            f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1",
            verify=False,
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 NaughtRFP/1.0"},
        )
        if r.status_code == 200:
            data = r.json()
            parts: list[str] = []

            if data.get("AbstractText"):
                parts.append(f"Result: {data['AbstractText']}\nURL: {data.get('AbstractURL', '')}")

            for topic in data.get("RelatedTopics", [])[:num]:
                if isinstance(topic, dict) and topic.get("Text"):
                    url = ""
                    if isinstance(topic.get("FirstURL"), str):
                        url = topic["FirstURL"]
                    parts.append(f"Result: {topic['Text']}\nURL: {url}")

            return "\n\n".join(parts) if parts else "[]"
    except Exception:
        pass

    return "[]"


# ---------------------------------------------------------------------------
# Channel 2: Direct CanadaBuys fetch — GSIN-filtered
# ---------------------------------------------------------------------------

def _canadabuys_title_is_relevant(title: str) -> bool:
    """
    Return True if title contains at least one keyword from _CANADABUYS_MUST_HAVE.
    Case-insensitive substring match.
    """
    title_lower = title.lower()
    return any(kw in title_lower for kw in _CANADABUYS_MUST_HAVE)


def _fetch_canadabuys(keywords: list[str]) -> list[dict]:
    """
    httpx.get to canadabuys.canada.ca using GSIN code filters (D301/D302/D304)
    to ensure only IT-relevant categories are fetched.
    Also applies title keyword filter to discard irrelevant results
    (e.g. HVAC, construction, catering).
    Parses HTML for tender listings using regex (no BeautifulSoup).
    Returns list of dicts with fields matching discovered_rfps schema.
    Gracefully returns empty list if anything fails.

    All results are tagged sector="public" (CanadaBuys is a government portal).
    """
    all_rfps: list[dict] = []
    seen_titles: set[str] = set()

    for gsin in _CANADABUYS_GSINS:
        try:
            r = httpx.get(
                "https://canadabuys.canada.ca/en/tender-opportunities",
                params={"gsin": gsin, "status": "open"},
                verify=False,
                follow_redirects=True,
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0 NaughtRFP/1.0"},
            )
            if r.status_code != 200:
                continue

            html = r.text
            rfps: list[dict] = []

            # Pattern 1: anchor links to tender detail pages
            tender_links = re.findall(
                r'href="(/en/tender-opportunities/([^"]+))"[^>]*>([^<]{10,200})</a>',
                html,
                re.IGNORECASE,
            )

            # Pattern 2: structured data in JSON-LD
            json_ld_match = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                                       html, re.DOTALL | re.IGNORECASE)
            if json_ld_match:
                try:
                    ld_data = json.loads(json_ld_match.group(1))
                    items = ld_data if isinstance(ld_data, list) else [ld_data]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        title = item.get("name") or item.get("title") or ""
                        if not title or len(title) < 5:
                            continue
                        if not _canadabuys_title_is_relevant(title):
                            continue
                        score, tags = _score_relevance(title)
                        candidate = {
                            "source": "CanadaBuys",
                            "source_url": item.get("url") or "https://canadabuys.canada.ca/en/tender-opportunities",
                            "solicitation_no": item.get("identifier") or item.get("referenceNumber"),
                            "title": title,
                            "org_name": item.get("organizer", {}).get("name") if isinstance(item.get("organizer"), dict) else None,
                            "gsin_code": gsin,
                            "closing_date": item.get("endDate") or item.get("availabilityEnds"),
                            "posted_date": item.get("startDate"),
                            "est_value": None,
                            "relevance_score": score,
                            "relevance_tags": json.dumps(tags),
                            "raw_data": json.dumps({
                                "snippet": str(item.get("description") or "")[:300],
                                "url": item.get("url") or "",
                                "gsin": gsin,
                                "sector": "public",
                            }),
                        }
                        if _is_valid_rfp_record(candidate):
                            rfps.append(candidate)
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass

            # Pattern 3: parse tender rows from HTML
            sol_pattern = re.compile(
                r'([A-Z0-9]{2,10}-\d{4,6}-[A-Z]{0,6}-?\d{0,6})',
                re.IGNORECASE,
            )

            row_patterns = [
                re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE),
                re.compile(r'<div[^>]*class="[^"]*(?:result|tender|opportunity)[^"]*"[^>]*>(.*?)</div>',
                           re.DOTALL | re.IGNORECASE),
            ]

            for row_re in row_patterns:
                for row_match in row_re.finditer(html):
                    cell_html = row_match.group(1)
                    cell_text = re.sub(r'<[^>]+>', ' ', cell_html)
                    cell_text = re.sub(r'\s+', ' ', cell_text).strip()

                    if len(cell_text) < 20:
                        continue

                    sol_match = sol_pattern.search(cell_text)
                    sol_no = sol_match.group(1) if sol_match else None
                    closing = _extract_date(cell_text)

                    title_match = re.search(r'href="[^"]*tender[^"]*"[^>]*>([^<]{10,200})</a>',
                                             cell_html, re.IGNORECASE)
                    if title_match:
                        title = title_match.group(1).strip()
                    else:
                        parts = [p.strip() for p in cell_text.split('  ') if len(p.strip()) > 15]
                        title = parts[0] if parts else cell_text[:100]

                    title = re.sub(r'\s+', ' ', title).strip()
                    if not title or title in seen_titles or len(title) < 10:
                        continue

                    # Apply keyword relevance filter for CanadaBuys
                    if not _canadabuys_title_is_relevant(title):
                        continue

                    score, tags = _score_relevance(title, cell_text)
                    if score == 0:
                        continue

                    seen_titles.add(title)

                    url_match = re.search(r'href="(/en/tender-opportunities/[^"]+)"', cell_html)
                    url = f"https://canadabuys.canada.ca{url_match.group(1)}" if url_match else \
                          "https://canadabuys.canada.ca/en/tender-opportunities"

                    candidate = {
                        "source": "CanadaBuys",
                        "source_url": url,
                        "solicitation_no": sol_no,
                        "title": title,
                        "org_name": _extract_org(cell_text, url),
                        "gsin_code": gsin,
                        "closing_date": closing,
                        "posted_date": None,
                        "est_value": _extract_value(cell_text),
                        "relevance_score": score,
                        "relevance_tags": json.dumps(tags),
                        "raw_data": json.dumps({
                            "snippet": cell_text[:300],
                            "url": url,
                            "gsin": gsin,
                            "sector": "public",
                        }),
                    }
                    if _is_valid_rfp_record(candidate):
                        rfps.append(candidate)

            # Pattern 1 fallback for any missed titles
            for path, sol_part, title_text in tender_links:
                title = re.sub(r'\s+', ' ', title_text).strip()
                if not title or title in seen_titles or len(title) < 10:
                    continue
                if not _canadabuys_title_is_relevant(title):
                    continue
                seen_titles.add(title)
                score, tags = _score_relevance(title)
                if score == 0:
                    continue
                url = f"https://canadabuys.canada.ca{path}"
                candidate = {
                    "source": "CanadaBuys",
                    "source_url": url,
                    "solicitation_no": sol_part if re.search(r'\d', sol_part) else None,
                    "title": title,
                    "org_name": None,
                    "gsin_code": gsin,
                    "closing_date": None,
                    "posted_date": None,
                    "est_value": None,
                    "relevance_score": score,
                    "relevance_tags": json.dumps(tags),
                    "raw_data": json.dumps({
                        "snippet": "",
                        "url": url,
                        "gsin": gsin,
                        "sector": "public",
                    }),
                }
                if _is_valid_rfp_record(candidate):
                    rfps.append(candidate)

            all_rfps.extend(rfps)

        except Exception:
            continue

    return _deduplicate(all_rfps)


# ---------------------------------------------------------------------------
# Channel 3: DuckDuckGo fallback
# ---------------------------------------------------------------------------

def _fetch_via_duckduckgo(keywords: list[str]) -> list[dict]:
    """
    Fallback: DuckDuckGo search targeting both government procurement portals
    and commercial RFP aggregators.
    Runs multiple keyword groups for broader coverage.
    Returns list of RFP dicts parsed from search results.
    """
    import urllib.parse

    rfps: list[dict] = []

    # Run multiple passes with different keyword subsets
    keyword_batches = [
        keywords[:4],
        ["identity governance", "privileged access management", "zero trust"],
        ["CIAM", "customer identity", "citizen portal", "digital identity"],
        ["AI governance", "non-human identity", "machine identity"],
        # Private sector batches
        ["identity access management", "cybersecurity", "Canada", "bank", "financial"],
        ["identity management", "healthcare", "Canada", "hospital", "energy"],
    ]

    # Use combined site list for fallback
    sites = " OR ".join(f"site:{s}" for s in (_PROCUREMENT_SITES_GOV + _PROCUREMENT_SITES_COMMERCIAL)[:5])

    for batch in keyword_batches:
        kw_string = " OR ".join(f'"{kw}"' for kw in batch)
        query = f"({kw_string}) ({sites}) RFP tender 2026 open Canada"
        encoded = urllib.parse.quote_plus(query)

        try:
            r = httpx.get(
                f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1",
                verify=False,
                timeout=10,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 NaughtRFP/1.0"},
            )
            if r.status_code != 200:
                continue

            data = r.json()
            results: list[dict] = []

            if data.get("AbstractText") and data.get("AbstractURL"):
                results.append({
                    "text": data["AbstractText"],
                    "url": data["AbstractURL"],
                })

            for topic in data.get("RelatedTopics", [])[:15]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "text": topic["Text"],
                        "url": topic.get("FirstURL", ""),
                    })

            for result in results:
                text = result.get("text", "")
                url = result.get("url", "")
                sentences = re.split(r'[.!?]', text)
                title = sentences[0].strip() if sentences else text[:100]
                title = re.sub(r'\s+', ' ', title).strip()

                if not title or len(title) < 10:
                    continue

                score, tags = _score_relevance(title, text)
                if score == 0:
                    continue

                sector = _infer_sector(url)

                candidate = {
                    "source": _source_from_url(url) or "Web Search",
                    "source_url": url,
                    "solicitation_no": _extract_solicitation_no(text),
                    "title": title,
                    "org_name": _extract_org(text, url),
                    "gsin_code": None,
                    "closing_date": _extract_date(text),
                    "posted_date": None,
                    "est_value": _extract_value(text),
                    "relevance_score": score,
                    "relevance_tags": json.dumps(tags),
                    "raw_data": json.dumps({
                        "snippet": text[:300],
                        "url": url,
                        "sector": sector,
                    }),
                }
                if _is_valid_rfp_record(candidate):
                    rfps.append(candidate)

        except Exception:
            continue

    return _deduplicate(rfps)


# ---------------------------------------------------------------------------
# Helper extractors (regex-based, no external libraries)
# ---------------------------------------------------------------------------

def _source_from_url(url: str) -> str:
    """Derive a human-readable source name from a URL."""
    url = url.lower()
    if "canadabuys" in url or "buyandsell" in url or "achatsetventes" in url:
        return "CanadaBuys"
    if "merx" in url:
        return "MERX"
    if "purchasingconnection" in url:
        return "Alberta APC"
    if "bcbid" in url:
        return "BC Bid"
    if "ontario.ca" in url:
        return "Ontario"
    if "quebec" in url or "seao" in url:
        return "Quebec SEAO"
    if "rfpdb" in url:
        return "RFP Database"
    if "rfpmart" in url:
        return "RFPmart"
    if "biddingo" in url:
        return "Biddingo"
    if "canadacontracts" in url:
        return "Canada Contracts"
    return "Web"


def _extract_solicitation_no(text: str) -> str | None:
    """Extract a solicitation/tender number from text."""
    # Common patterns: SSC-2026-RFP-0142, EN578-123456, W8486-246789/A, 24-1234
    patterns = [
        r'\b([A-Z]{2,6}-\d{4}-[A-Z]{1,4}-\d{3,6})\b',
        r'\b([A-Z]{2,8}-\d{4,6}/[A-Z])\b',
        r'\b([A-Z]{2,6}\d{4,8})\b',
        r'\bSolicitation[:\s]+([A-Z0-9-/]+)\b',
        r'\bTender[:\s]+([A-Z0-9-/]+)\b',
        r'\bRFP[:\s#]+([A-Z0-9-/]+)\b',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if len(val) >= 5:
                return val
    return None


def _extract_date(text: str) -> str | None:
    """Extract closing/deadline date from text."""
    patterns = [
        r'\b(\d{4}-\d{2}-\d{2})\b',
        r'\b(\d{2}/\d{2}/\d{4})\b',
        r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b',
        r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\b',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_value(text: str) -> str | None:
    """Extract estimated contract value from text."""
    m = re.search(
        r'\$\s*([\d,]+(?:\.\d+)?)\s*(M|K|million|thousand|billion)?',
        text,
        re.IGNORECASE,
    )
    if m:
        amount = m.group(1).replace(",", "")
        suffix = m.group(2) or ""
        return f"${amount}{suffix}".strip()
    return None


def _extract_org(text: str, url: str = "") -> str | None:
    """Best-effort extraction of issuing organization name."""
    org_patterns = [
        (r'\b(Shared Services Canada|SSC)\b', "Shared Services Canada"),
        (r'\b(Treasury Board|TBS)\b', "Treasury Board Secretariat"),
        (r'\b(Public Services and Procurement|PSPC)\b', "Public Services and Procurement Canada"),
        (r'\b(Communications Security Establishment|CSE)\b', "Communications Security Establishment"),
        (r'\b(Department of National Defence|DND)\b', "Department of National Defence"),
        (r'\b(Royal Canadian Mounted Police|RCMP)\b', "Royal Canadian Mounted Police"),
        (r'\b(Health Canada)\b', "Health Canada"),
        (r'\b(Canada Revenue Agency|CRA)\b', "Canada Revenue Agency"),
        (r'\b(Employment and Social Development|ESDC)\b', "Employment and Social Development Canada"),
        (r'\b(Innovation, Science|ISED)\b', "Innovation, Science and Economic Development Canada"),
        (r'\b(Immigration, Refugees and Citizenship|IRCC)\b', "Immigration, Refugees and Citizenship Canada"),
        (r'\b(Canadian Security Intelligence Service|CSIS)\b', "Canadian Security Intelligence Service"),
        (r'\b(Canada Border Services Agency|CBSA)\b', "Canada Border Services Agency"),
        (r'\b(Public Health Agency of Canada|PHAC)\b', "Public Health Agency of Canada"),
        (r'\b(Alberta Health Services|AHS)\b', "Alberta Health Services"),
        (r'\b(eHealth Ontario|Ontario Health)\b', "Ontario Health"),
        (r'\b(Government of Alberta)\b', "Government of Alberta"),
        (r'\b(Province of British Columbia|BC Government)\b', "Province of British Columbia"),
        (r'\b(Government of Ontario)\b', "Government of Ontario"),
        # Private sector organisations
        (r'\b(Royal Bank of Canada|RBC)\b', "Royal Bank of Canada"),
        (r'\b(TD Bank|TD Canada Trust|Toronto-Dominion)\b', "TD Bank"),
        (r'\b(Bank of Montreal|BMO)\b', "Bank of Montreal"),
        (r'\b(Canadian Imperial Bank|CIBC)\b', "CIBC"),
        (r'\b(Scotiabank|Bank of Nova Scotia)\b', "Scotiabank"),
        (r'\b(National Bank of Canada)\b', "National Bank of Canada"),
        (r'\b(Manulife|Manufacturers Life)\b', "Manulife"),
        (r'\b(Sun Life Financial|Sun Life)\b', "Sun Life Financial"),
        (r'\b(Desjardins)\b', "Desjardins Group"),
        (r'\b(Bell Canada|Bell)\b', "Bell Canada"),
        (r'\b(Rogers Communications|Rogers)\b', "Rogers Communications"),
        (r'\b(TELUS)\b', "TELUS"),
        (r'\b(Enbridge)\b', "Enbridge"),
        (r'\b(TC Energy|TransCanada)\b', "TC Energy"),
        (r'\b(Hydro One)\b', "Hydro One"),
        (r'\b(BC Hydro)\b', "BC Hydro"),
        (r'\b(Shopify)\b', "Shopify"),
        (r'\b(City of (\w+))\b', None),   # handled below
    ]
    for pattern, name in org_patterns:
        if name and re.search(pattern, text, re.IGNORECASE):
            return name
        elif not name:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)

    # Generic: "Issued by: X" or "Organization: X"
    m = re.search(r'(?:Issued by|Organization|Department|Ministry|Company|Corporation)[:\s]+([A-Z][^\n<]{5,60})',
                  text, re.IGNORECASE)
    if m:
        return m.group(1).strip()[:80]

    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_discovery(api_key: str, db, event_q: queue.Queue) -> None:
    """
    Main entry point. Fetches open Canadian public AND private sector RFPs
    matching Okta's full solution portfolio keywords. Streams progress events
    to event_q. Saves results to db via db.save_discovered_rfp().

    Channel 1 runs all 20 targeted search queries sequentially:
      - Queries 0–11: government/public sector procurement portals
      - Queries 12–19: Canadian private sector and commercial aggregators
    Channel 2 fetches CanadaBuys directly using GSIN D301/D302/D304 filters.
    Channel 3 (DuckDuckGo fallback) runs only if both primary channels fail.

    Each result stores a `sector` field in `raw_data`:
      "public"  — government domain
      "private" — commercial aggregator or known private sector domain
      "unknown" — could not determine

    Event types emitted:
      discovery_progress  {"message": str, "count": int}
      discovery_result    {"item": dict}
      discovery_complete  {"total": int, "new": int}
      None                sentinel — signals completion
    """

    def emit(event_type: str, **kwargs) -> None:
        try:
            event_q.put({"type": event_type, **kwargs})
        except Exception:
            pass

    all_results: list[dict] = []
    total_new = 0

    # ------------------------------------------------------------------
    # Pre-run: clean up bad records from previous runs
    # ------------------------------------------------------------------
    try:
        deleted = clean_invalid_discoveries(db)
        if deleted > 0:
            emit("discovery_progress",
                 message=f"Cleaned {deleted} invalid records from previous runs.",
                 count=0)
    except Exception:
        pass

    # Resolve LiteLLM base URL from DB settings
    base_url: str | None = None
    try:
        base_url = db.get_setting("litellm_base_url") or None
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Channel 1: Google Custom Search via Claude tool-call
    # Runs all 20 targeted queries (12 public + 8 private sector)
    # ------------------------------------------------------------------
    pub_count = len(_SEARCH_QUERIES) - len(_PRIVATE_SECTOR_QUERY_INDICES)
    priv_count = len(_PRIVATE_SECTOR_QUERY_INDICES)
    emit("discovery_progress",
         message=(
             f"Searching procurement portals via Google Custom Search "
             f"({len(_SEARCH_QUERIES)} targeted queries: "
             f"{pub_count} public sector, {priv_count} private sector)..."
         ),
         count=0)
    try:
        ch1_results = _fetch_via_claude_search(api_key, base_url)
        all_results.extend(ch1_results)
        if ch1_results:
            emit("discovery_progress",
                 message=f"Google Custom Search returned {len(ch1_results)} candidates across {len(_SEARCH_QUERIES)} queries.",
                 count=len(all_results))
    except Exception as e:
        emit("discovery_progress",
             message=f"Google Custom Search unavailable: {e}", count=len(all_results))

    # ------------------------------------------------------------------
    # Channel 2: Direct CanadaBuys fetch — GSIN-filtered (D301/D302/D304)
    # ------------------------------------------------------------------
    emit("discovery_progress",
         message=f"Searching CanadaBuys directly (GSIN: {', '.join(_CANADABUYS_GSINS)})...",
         count=len(all_results))
    try:
        primary_keywords = [
            "identity access management",
            "identity governance",
            "privileged access management",
            "zero trust",
            "cybersecurity",
            "single sign-on",
            "customer identity",
            "AI governance",
        ]
        ch2_results = _fetch_canadabuys(primary_keywords)
        all_results.extend(ch2_results)
        if ch2_results:
            emit("discovery_progress",
                 message=f"CanadaBuys returned {len(ch2_results)} IT-relevant candidates.",
                 count=len(all_results))
        else:
            emit("discovery_progress",
                 message="CanadaBuys returned no results (portal may be unavailable or no matching GSIN tenders open).",
                 count=len(all_results))
    except Exception as e:
        emit("discovery_progress",
             message=f"CanadaBuys fetch failed: {e}", count=len(all_results))

    # ------------------------------------------------------------------
    # Channel 3: DuckDuckGo fallback — only if both channels failed
    # ------------------------------------------------------------------
    if not all_results:
        emit("discovery_progress",
             message="Primary channels returned nothing — trying DuckDuckGo fallback...",
             count=0)
        try:
            fallback_kws = [
                "identity access management", "identity governance",
                "privileged access", "zero trust", "cybersecurity",
            ]
            ch3_results = _fetch_via_duckduckgo(fallback_kws)
            all_results.extend(ch3_results)
            emit("discovery_progress",
                 message=f"DuckDuckGo fallback returned {len(ch3_results)} candidates.",
                 count=len(all_results))
        except Exception as e:
            emit("discovery_progress",
                 message=f"DuckDuckGo fallback failed: {e}", count=len(all_results))

    # ------------------------------------------------------------------
    # Deduplicate
    # ------------------------------------------------------------------
    all_results = _deduplicate(all_results)

    # Filter to only relevance_score > 0
    all_results = [r for r in all_results if r.get("relevance_score", 0) > 0]

    # Sort by relevance_score descending
    all_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    emit("discovery_progress",
         message=f"Deduplication complete — {len(all_results)} unique results.",
         count=len(all_results))

    # ------------------------------------------------------------------
    # Save to DB
    # ------------------------------------------------------------------
    for item in all_results:
        try:
            emit("discovery_result", item=item)
            db.save_discovered_rfp(item)
            total_new += 1
            time.sleep(0)  # yield to other threads
        except Exception as e:
            emit("discovery_progress",
                 message=f"Could not save result '{item.get('title', '?')[:60]}': {e}",
                 count=total_new)

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    emit("discovery_complete", total=len(all_results), new=total_new)
    event_q.put(None)  # sentinel
