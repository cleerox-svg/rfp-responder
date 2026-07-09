"""
relevance.py
Keyword-based relevance scoring for discovered RFPs.
No LLM call — fast, deterministic, zero token cost.
Returns a score 0-10 and a list of matched tag strings.

Expanded keyword groups covering the full Okta solutions portfolio:
  - Identity Governance & Administration (IGA / OIG)
  - Privileged Access Management (PAM)
  - Customer Identity & Access Management (CIAM / Auth0)
  - Workforce Identity (SSO, Adaptive MFA, Passwordless)
  - Lifecycle Management (provisioning, SCIM, HR-driven)
  - Non-Human Identity / AI Agent Identity (NHI, machine identity)
  - Zero Trust Architecture
  - Identity Threat Detection & Response (ISPM, ITP)
  - AI Security & Governance
  - Cybersecurity & Compliance
  - Canadian Government (bonus signals for public sector relevance)
  - Canadian Private Sector (signals for commercial/enterprise RFPs)
"""

import re


# ---------------------------------------------------------------------------
# Keyword groups — each group that fires contributes a base score
# ---------------------------------------------------------------------------

KEYWORD_GROUPS: dict[str, list[str]] = {

    # ------------------------------------------------------------------
    # Core IAM / Workforce Identity — broad base signals
    # ------------------------------------------------------------------
    "Identity / IAM": [
        "identity access management", "iam", "identity management",
        "single sign-on", "sso", "federated identity", "federation",
        "multi-factor authentication", "mfa", "two-factor authentication", "2fa",
        "adaptive mfa", "adaptive authentication",
        "passwordless", "fido2", "webauthn", "passkey",
        "directory services", "ldap", "active directory", "entra id",
        "universal directory", "okta", "authentication", "authorisation",
        "authorization", "access control", "role-based access", "rbac",
        "attribute-based access", "abac",
        "identity provider", "idp", "service provider", "sp",
        "saml", "oidc", "oauth", "openid connect",
        "access gateway", "on-premise access", "hybrid identity",
        "device trust", "device access", "endpoint trust",
    ],

    # ------------------------------------------------------------------
    # Identity Governance & Administration (IGA / OIG) — HIGH VALUE
    # ------------------------------------------------------------------
    "Identity Governance": [
        "identity governance", "iga", "identity governance administration",
        "access governance", "access certification", "access review",
        "access recertification", "certification campaign",
        "entitlement management", "entitlement review",
        "separation of duties", "sod", "segregation of duties",
        "joiner mover leaver", "joiner-mover-leaver", "jml",
        "privilege creep", "least privilege",
        "governance analyzer", "access request workflow",
        "access request", "self-service access",
        "audit trail", "compliance reporting", "identity audit",
        "role management", "role mining", "role definition",
        "policy enforcement", "access policy",
    ],

    # ------------------------------------------------------------------
    # Privileged Access Management (PAM) — HIGH VALUE
    # ------------------------------------------------------------------
    "Privileged Access": [
        "privileged access management", "pam", "privileged access",
        "privileged account", "privileged identity",
        "just-in-time access", "jit access", "time-bound access",
        "secrets vaulting", "secrets management", "credential vaulting",
        "password vaulting", "vault", "secrets vault",
        "session recording", "session audit", "rdp session",
        "ssh access", "ssh key management",
        "break-glass account", "emergency access",
        "service account management", "shared account",
        "infrastructure access", "server access",
        "least privilege access", "standing privilege",
        "just enough access", "jea",
        "api key management", "database credential",
    ],

    # ------------------------------------------------------------------
    # Customer Identity & Access Management (CIAM / Auth0) — HIGH VALUE
    # ------------------------------------------------------------------
    "Customer Identity": [
        "customer identity", "ciam", "consumer identity",
        "customer identity access management",
        "b2c identity", "b2b identity", "external identity",
        "digital identity", "citizen identity", "resident identity",
        "auth0", "login experience", "registration experience",
        "social login", "progressive profiling",
        "consent management", "privacy consent",
        "passwordless login", "magic link",
        "identity verification", "digital onboarding",
        "citizen portal", "resident portal", "client portal",
        "self-service portal", "customer portal",
        "branded login", "universal login",
        "api access management", "developer identity",
    ],

    # ------------------------------------------------------------------
    # Lifecycle Management — automated provisioning
    # ------------------------------------------------------------------
    "Lifecycle Management": [
        "lifecycle management", "identity lifecycle",
        "automated provisioning", "automated deprovisioning",
        "user provisioning", "user deprovisioning",
        "account provisioning", "account deprovisioning",
        "scim", "system for cross-domain identity management",
        "hr-driven provisioning", "hris integration",
        "onboarding automation", "offboarding automation",
        "employee onboarding", "employee offboarding",
        "access automation", "identity automation",
        "group management", "group provisioning",
    ],

    # ------------------------------------------------------------------
    # Non-Human Identity / AI Agent Identity (NHI) — EMERGING, GROWING
    # ------------------------------------------------------------------
    "Non-Human Identity": [
        "non-human identity", "nhi", "machine identity",
        "service account", "workload identity",
        "ai agent identity", "agentic ai", "ai agent access",
        "ai agent governance", "agent identity",
        "cross-app access", "cross-application access",
        "api token management", "token governance",
        "bot identity", "automated agent",
        "machine-to-machine", "m2m authentication",
        "service mesh identity", "microservice identity",
    ],

    # ------------------------------------------------------------------
    # Zero Trust Architecture
    # ------------------------------------------------------------------
    "Zero Trust": [
        "zero trust", "ztna", "zero trust network access",
        "zero trust architecture", "zta",
        "never trust always verify",
        "microsegmentation", "micro-segmentation",
        "network segmentation", "least privilege access",
        "continuous verification", "continuous authentication",
        "identity-centric security", "identity-based security",
        "context-aware access", "risk-based access",
        "conditional access",
    ],

    # ------------------------------------------------------------------
    # Identity Threat Detection & Response (ISPM / ITP)
    # ------------------------------------------------------------------
    "Identity Threat Detection": [
        "identity threat", "identity threat protection",
        "identity security posture", "ispm",
        "identity-based attack", "credential attack",
        "identity threat detection", "identity threat response",
        "anomalous access", "suspicious login",
        "account takeover", "ato prevention",
        "identity risk", "identity risk management",
        "continuous risk assessment", "risk-based authentication",
        "threat intelligence identity",
    ],

    # ------------------------------------------------------------------
    # AI Security & Governance
    # ------------------------------------------------------------------
    "AI Security": [
        "ai governance", "ai security", "artificial intelligence security",
        "machine learning security", "ai risk", "ai risk management",
        "responsible ai", "trustworthy ai",
        "generative ai", "genai", "llm security",
        "ai policy", "ai posture", "ai security posture",
        "model governance", "ai model security",
        "ai agent security", "agentic security",
        "llm governance", "prompt injection",
    ],

    # ------------------------------------------------------------------
    # Cybersecurity & Compliance (general)
    # ------------------------------------------------------------------
    "Cybersecurity": [
        "cybersecurity", "cyber security", "information security", "infosec",
        "security operations", "soc", "siem",
        "endpoint protection", "endpoint security",
        "cloud security", "data protection", "data privacy",
        "encryption", "data encryption",
        "vulnerability management", "penetration testing",
        "threat detection", "threat response",
        "incident response", "security incident",
        "nist", "iso 27001", "iso27001",
        "soc 2", "soc2", "fedramp",
        "pipeda", "privacy law", "privacy compliance",
        "gdpr", "data residency",
        "security assessment", "security audit",
        "security architecture", "security framework",
    ],

    # ------------------------------------------------------------------
    # Canadian Government (bonus scoring — strong public sector signals)
    # ------------------------------------------------------------------
    "Canadian Government": [
        # Federal departments and agencies
        "shared services canada", "ssc",
        "treasury board", "treasury board secretariat", "tbs",
        "public services and procurement canada", "pspc",
        "communications security establishment", "cse",
        "department of national defence", "dnd",
        "royal canadian mounted police", "rcmp",
        "health canada",
        "canada revenue agency", "cra",
        "employment and social development canada", "esdc",
        "immigration refugees citizenship canada", "ircc",
        "innovation science and economic development", "ised",
        "canadian security intelligence service", "csis",
        "border services canada", "cbsa",
        "natural resources canada", "nrcan",
        "public health agency of canada", "phac",
        "indigenous services canada",
        "veterans affairs canada",
        "transport canada",
        "environment and climate change canada",
        "government of canada", "gc",
        # Provincial
        "ehealth ontario", "ontario health",
        "service ontario", "serviceontario",
        "service bc", "servicebc",
        "ministry of health", "ministry of finance",
        "ministry of digital government",
        "alberta health services", "ahs",
        "government of alberta", "government of bc",
        "government of ontario", "province of ontario",
        "province of british columbia",
        "societe quebecoise", "centre gouvernemental",
        # Procurement vehicle terms
        "tbips", "task-based informatics professional services",
        "proservices", "pro services",
        "sbips", "tsps",
        "standing offer", "supply arrangement",
        "request for standing offer", "rfso",
        "notice of intended procurement", "nip",
        "advance contract award notice", "acan",
        "national master standing offer", "nmso",
        "call-up against standing offer",
        # Security classifications
        "protected b", "protected c", "secret clearance",
        "top secret", "reliability status",
        "cccs", "cyber centre",
        "itsg", "it security guidelines",
        "pbmm", "protected b medium integrity",
        "gc cloud", "government of canada cloud",
        "cloud guardrails", "gc guardrails",
        "security categorization", "security assessment authorization",
        "privacy impact assessment", "pia",
    ],

    # ------------------------------------------------------------------
    # Canadian Private Sector (bonus scoring — commercial enterprise signals)
    # Matches RFPs from Canadian banks, telcos, utilities, retail, healthcare.
    # Lower base score than "Canadian Government" since these are broader signals.
    # ------------------------------------------------------------------
    "Canadian Private Sector": [
        # Financial services
        "rbc", "royal bank of canada",
        "td bank", "td canada trust", "toronto-dominion",
        "bank of montreal", "bmo",
        "cibc", "canadian imperial bank",
        "scotiabank", "bank of nova scotia",
        "national bank of canada",
        "manulife", "sun life", "great-west life",
        "co-operators", "intact financial",
        "desjardins",
        "atb financial",
        # Telco / wireless
        "bell canada",
        "rogers communications",
        "telus",
        "shaw communications",
        "videotron",
        "cogeco",
        "sasktel",
        # Energy and utilities
        "enbridge",
        "tc energy",
        "cenovus",
        "suncor",
        "pembina pipeline",
        "hydro one",
        "bc hydro",
        "fortis inc",
        "atco",
        "epcor",
        # Retail and e-commerce
        "shopify",
        "canadian tire",
        "loblaw",
        "sobeys",
        "metro inc",
        "empire company",
        "lululemon",
        # Healthcare (private / para-public)
        "fraser health",
        "interior health",
        "island health",
        "lifelabs",
        "dynacare",
        # Aggregator / discovery context signals
        "rfpdb", "rfpmart", "biddingo",
        "enterprise rfp",
        "corporate procurement",
        "vendor rfp",
        "private sector tender",
        "industry tender",
    ],
}

# Base score contribution per group when at least one keyword matches
_GROUP_BASE_SCORES: dict[str, float] = {
    "Identity / IAM":          3.0,
    "Identity Governance":     4.0,   # high-value OIG deal signal
    "Privileged Access":       4.0,   # high-value PAM deal signal
    "Customer Identity":       3.5,   # strong CIAM deal signal
    "Lifecycle Management":    2.5,
    "Non-Human Identity":      3.0,   # growing category
    "Zero Trust":              2.5,
    "Identity Threat Detection": 2.5,
    "AI Security":             2.5,
    "Cybersecurity":           1.5,   # broad — lower base
    "Canadian Government":     2.0,   # public sector procurement context bonus
    "Canadian Private Sector": 1.5,   # commercial/enterprise procurement context bonus
}

# Additional points per extra keyword match beyond the first, capped per group
_EXTRA_KW_POINTS: float = 0.5
_EXTRA_KW_CAP:    float = 1.5   # increased cap to reward deeper matches

# Title matches count double vs description matches
_TITLE_WEIGHT: float       = 2.0
_DESCRIPTION_WEIGHT: float = 1.0

_MAX_SCORE: float = 10.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase and collapse whitespace so multi-word keywords match cleanly."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _count_matches(text: str, keywords: list[str]) -> list[str]:
    """Return the subset of keywords that appear as whole-word substrings in text."""
    matched = []
    for kw in keywords:
        # Word-boundary match so "soc" doesn't hit "socioeconomic"
        pattern = r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])"
        if re.search(pattern, text):
            matched.append(kw)
    return matched


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_rfp(title: str, description: str = "") -> dict:
    """
    Score a discovered RFP for relevance to Okta's solution areas.

    Parameters
    ----------
    title : str
        The RFP title (weighted 2x).
    description : str, optional
        Body text / summary (weighted 1x).  None is treated as empty string.

    Returns
    -------
    dict with keys:
        score            float       0-10
        tags             list[str]   matched group names
        matched_keywords list[str]   specific keywords that fired
    """
    title_norm = _normalise(title or "")
    desc_norm  = _normalise(description or "")

    total_score:    float      = 0.0
    tags:           list[str]  = []
    matched_kws:    list[str]  = []

    for group, keywords in KEYWORD_GROUPS.items():
        title_matches = _count_matches(title_norm, keywords)
        desc_matches  = _count_matches(desc_norm,  keywords)

        # Deduplicate across title and description for tag/keyword reporting
        all_matched = list(dict.fromkeys(title_matches + desc_matches))

        if not all_matched:
            continue

        tags.append(group)
        matched_kws.extend(all_matched)

        base = _GROUP_BASE_SCORES.get(group, 2.0)

        # Count weighted hits (title double, description single)
        title_hit_count = len(title_matches)
        desc_hit_count  = len(desc_matches)

        # Weighted unique hits: a keyword matched in both title and description
        # counts once at title weight (avoid double-penalising the description bonus)
        unique_title_only = len([kw for kw in title_matches if kw not in desc_matches])
        unique_desc_only  = len([kw for kw in desc_matches  if kw not in title_matches])
        both              = len([kw for kw in title_matches  if kw in  desc_matches])

        # Effective weighted hits (each keyword scored once at its highest weight)
        weighted_hits = (
            unique_title_only * _TITLE_WEIGHT
            + unique_desc_only * _DESCRIPTION_WEIGHT
            + both            * _TITLE_WEIGHT       # title weight wins for cross-matches
        )

        # First weighted hit fires the base score; extras give bonus (capped)
        first_hit_weight = max(_TITLE_WEIGHT if title_hit_count > 0 else 0.0,
                               _DESCRIPTION_WEIGHT if desc_hit_count > 0 else 0.0)
        extra_weighted = max(0.0, weighted_hits - first_hit_weight)

        extra_bonus = min(
            (extra_weighted / max(_TITLE_WEIGHT, _DESCRIPTION_WEIGHT)) * _EXTRA_KW_POINTS,
            _EXTRA_KW_CAP,
        )

        total_score += base + extra_bonus

    total_score = min(total_score, _MAX_SCORE)

    return {
        "score":            round(total_score, 2),
        "tags":             tags,
        "matched_keywords": list(dict.fromkeys(matched_kws)),  # preserve order, dedup
    }


def filter_results(results: list[dict], min_score: float = 2.0) -> list[dict]:
    """
    Filter and sort a list of discovery result dicts.

    Keeps only results where ``relevance_score >= min_score``.
    Sorted by relevance_score DESC, then closing_date ASC (nulls last).

    Parameters
    ----------
    results : list[dict]
        Each dict is expected to have at minimum:
            relevance_score : float
            closing_date    : str | None  (ISO-8601 date string or None)

    min_score : float
        Minimum relevance_score to include.  Default 2.0.

    Returns
    -------
    list[dict]  — filtered and sorted copy; original list is not modified.
    """
    _CLOSING_DATE_SENTINEL = "9999-99-99"  # nulls sort last

    filtered = [r for r in results if r.get("relevance_score", 0.0) >= min_score]

    filtered.sort(
        key=lambda r: (
            -r.get("relevance_score", 0.0),
            r.get("closing_date") or _CLOSING_DATE_SENTINEL,
        )
    )

    return filtered
