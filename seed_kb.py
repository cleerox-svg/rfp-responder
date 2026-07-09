"""
Okta baseline knowledge for the NaughtRFP knowledge base.
Run once or call seed_okta_knowledge(db) from app startup.
"""

OKTA_KB_SEED = [
    # ── Disaster Recovery / Business Continuity ──────────────────────────────
    {
        "category": "Security & Compliance",
        "question": "What are the vendor's disaster recovery and business continuity capabilities? Please describe RTO and RPO targets.",
        "answer": "Okta operates a fully active-active, multi-region cloud architecture with no single point of failure. Our platform maintains a 99.99% uptime SLA backed contractually. Recovery Time Objective (RTO) is less than 4 hours; Recovery Point Objective (RPO) is near-zero due to synchronous data replication across geographically separated data centers. Okta conducts annual DR tests and publishes results to customers via the Trust Portal at trust.okta.com.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Security & Compliance",
        "question": "Does the platform have a documented business continuity plan (BCP)?",
        "answer": "Yes. Okta maintains a comprehensive Business Continuity Plan reviewed and tested annually. The BCP covers data center outages, network disruptions, and regional cloud provider failures. Okta's active-active architecture across multiple AWS regions ensures service continuity even during a full regional outage. Documentation is available under NDA upon request.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },

    # ── Encryption ────────────────────────────────────────────────────────────
    {
        "category": "Security & Compliance",
        "question": "How does the solution encrypt data at rest and in transit?",
        "answer": "All data at rest is encrypted using AES-256. All data in transit is protected using TLS 1.2 or higher — older protocol versions are disabled. Encryption keys are managed via Hardware Security Modules (HSMs) and rotated on a regular schedule. Okta does not store plaintext credentials; passwords are hashed using bcrypt with a high work factor.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Security & Compliance",
        "question": "Does the platform support encryption key management and customer-managed keys?",
        "answer": "Okta manages encryption keys using HSM-backed key management by default. For customers requiring greater control, Okta supports Bring Your Own Key (BYOK) via AWS KMS integration as part of the Okta Customer Identity Cloud (CIC) offering. Key rotation policies are configurable and auditable.",
        "response_code": "P",
        "okta_products": ["Platform"],
    },

    # ── Uptime / SLA ─────────────────────────────────────────────────────────
    {
        "category": "Technical Platform",
        "question": "What uptime SLA does the vendor guarantee?",
        "answer": "Okta guarantees a 99.99% uptime SLA for all production tenants, contractually backed with service credits for non-compliance. Historical uptime consistently exceeds 99.99% and is publicly viewable in real time at trust.okta.com. Planned maintenance windows are communicated at least 7 days in advance and are typically performed with zero downtime using rolling deployments.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },

    # ── Data Residency ────────────────────────────────────────────────────────
    {
        "category": "Security & Compliance",
        "question": "Does the solution support data residency requirements, including Canadian data residency?",
        "answer": "Yes. Okta offers dedicated data residency options in the United States, European Union, and Canada. Canadian customers can elect to have all identity data stored and processed within Canada, supporting PIPEDA and applicable provincial privacy legislation requirements. Data residency is confirmed at tenant provisioning and documented in the Order Form.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Security & Compliance",
        "question": "How does the solution comply with GDPR and PIPEDA data privacy requirements?",
        "answer": "Okta is GDPR compliant and acts as a Data Processor under GDPR, with a Standard Contractual Clauses (SCCs) Data Processing Addendum available for all customers. For Canadian customers, Okta's Canadian data residency option ensures personal data remains within Canada as required by PIPEDA. Okta maintains ISO 27018 certification for privacy protection in cloud services.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },

    # ── Compliance Certifications ─────────────────────────────────────────────
    {
        "category": "Security & Compliance",
        "question": "What security certifications does the vendor hold? SOC 2 Type II, ISO 27001?",
        "answer": "Okta holds the following current certifications: SOC 2 Type II (annual audit), ISO 27001, ISO 27018, FedRAMP Authorized (High) for US federal deployments, CSA STAR Level 2, and PCI DSS Level 1. Certificates and audit reports are available under NDA via Okta's Trust Portal at trust.okta.com. Annual re-certification ensures continuous compliance.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Security & Compliance",
        "question": "Is the platform FedRAMP authorized or does it hold equivalent Canadian government security certification?",
        "answer": "Okta is FedRAMP Authorized at the High impact level, the highest tier available for US federal workloads. For Canadian government deployments, Okta's Canadian data residency aligns with CCCS Medium requirements and Protected B data classification. Okta can provide documentation supporting ITSG-33 compliance assessments. Formal CCCS authorization is available upon request for specific federal engagements.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },

    # ── Penetration Testing / Vulnerability Management ────────────────────────
    {
        "category": "Security & Compliance",
        "question": "Does the vendor conduct regular penetration testing? Can results be shared?",
        "answer": "Okta conducts third-party penetration tests at minimum annually, with continuous automated security scanning performed daily. Test results, executive summaries, and remediation status are available to customers under NDA via the Trust Portal. Okta also operates a public bug bounty program through HackerOne, providing continuous community-driven security research.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },

    # ── MFA / Authentication ──────────────────────────────────────────────────
    {
        "category": "Access Management",
        "question": "Does the solution support multi-factor authentication (MFA) including phishing-resistant methods?",
        "answer": "Yes. Okta supports over 20 MFA factor types including Okta Verify (push, TOTP, and biometric), FIDO2/WebAuthn (phishing-resistant hardware keys and passkeys), SMS/Voice, Email Magic Link, and TOTP apps. Adaptive MFA uses risk signals including device trust, network location, user behavior, and threat intelligence to step up authentication only when risk is detected. FIDO2 factors are certified by the FIDO Alliance.",
        "response_code": "F",
        "okta_products": ["MFA", "SSO"],
    },
    {
        "category": "Access Management",
        "question": "Does the platform support single sign-on (SSO) with SAML 2.0 and OIDC?",
        "answer": "Yes. Okta is the industry-leading SSO platform supporting SAML 2.0, OpenID Connect (OIDC), OAuth 2.0, and WS-Federation. The Okta Integration Network (OIN) includes 7,000+ pre-built SSO integrations. For applications without native SSO support, Okta provides SWA (Secure Web Authentication) as a fallback. Custom integrations can be built using Okta's published APIs and SCIM provisioning.",
        "response_code": "F",
        "okta_products": ["SSO", "MFA"],
    },

    # ── Identity Lifecycle / Provisioning ────────────────────────────────────
    {
        "category": "Identity Lifecycle",
        "question": "Does the solution automate user provisioning and deprovisioning (Joiner-Mover-Leaver)?",
        "answer": "Yes. Okta Lifecycle Management automates the full Joiner-Mover-Leaver process using HR systems as the authoritative source. Upon hire, role change, or termination events in HR systems like Workday, SAP SuccessFactors, or BambooHR, Okta automatically provisions or revokes access across all integrated applications within a configurable SLA. Deprovisioning typically completes within minutes of HR trigger with full audit trail.",
        "response_code": "F",
        "okta_products": ["LCM"],
    },
    {
        "category": "Identity Lifecycle",
        "question": "Does the IGA solution support non-human identities (NHI), service accounts, and AI agent identities?",
        "answer": "Yes. Okta Identity Governance supports lifecycle management for all identity types including employees, contractors, third parties, non-human identities (service accounts, system accounts), and AI agent identities. NHI governance policies can be configured independently from human identity policies with distinct certification cadences and access review processes. Okta AI supports identity management for AI agents with appropriate controls.",
        "response_code": "F",
        "okta_products": ["OIG", "LCM", "AI"],
    },

    # ── Access Governance / Certifications ────────────────────────────────────
    {
        "category": "Access Governance",
        "question": "Does the solution support access certification campaigns and access reviews?",
        "answer": "Yes. Okta Identity Governance (OIG) provides automated access certification campaigns with configurable scope, frequency, and reviewer assignment. AI-powered recommendations flag high-risk or anomalous access for enhanced review while suggesting auto-approval for clearly appropriate access. Campaigns can be targeted by application, role, department, or risk level. All reviewer decisions are fully auditable with timestamped records.",
        "response_code": "F",
        "okta_products": ["OIG"],
    },
    {
        "category": "Access Governance",
        "question": "Does the platform support Separation of Duties (SoD) policy enforcement?",
        "answer": "Yes. Okta Identity Governance includes built-in SoD conflict detection across all integrated applications. SoD rules can be imported from existing GRC systems or configured natively. Conflicts are detected in real time during access requests—before provisioning occurs—preventing violations rather than just reporting them. SoD reports and dashboards provide compliance teams with full visibility and audit-ready outputs.",
        "response_code": "F",
        "okta_products": ["OIG"],
    },

    # ── Integration / SCIM ────────────────────────────────────────────────────
    {
        "category": "Integration & Connectivity",
        "question": "Does the platform support SCIM 2.0 provisioning?",
        "answer": "Yes. Okta is a leading proponent of the SCIM 2.0 standard and supports SCIM provisioning to all compatible applications. The Okta Integration Network (OIN) includes 7,000+ pre-built integrations, the majority of which support automated SCIM provisioning. For applications without SCIM support, Okta provides REST API-based provisioning, flat file (CSV) import/export, and HR-to-app provisioning flows.",
        "response_code": "F",
        "okta_products": ["LCM", "OIN"],
    },
    {
        "category": "Integration & Connectivity",
        "question": "What HR system integrations does the platform support (Workday, SAP SuccessFactors)?",
        "answer": "Okta provides certified, pre-built integrations with all major HR systems including Workday, SAP SuccessFactors, ADP, BambooHR, UKG (Ultimate Kronos), Oracle HCM, and ServiceNow HR. These integrations support bi-directional attribute sync, real-time event-driven triggers for Joiner-Mover-Leaver workflows, and custom attribute mapping. Multiple HR sources can be configured simultaneously with configurable conflict resolution logic.",
        "response_code": "F",
        "okta_products": ["LCM"],
    },
    {
        "category": "Integration & Connectivity",
        "question": "Does the platform integrate with ServiceNow for ITSM ticket creation and access request fulfilment?",
        "answer": "Yes. Okta has a certified, bi-directional integration with ServiceNow available in the Okta Integration Network. Access requests initiated in Okta can automatically create ServiceNow tickets; conversely, ServiceNow access request fulfilment can trigger Okta provisioning. Status synchronization is bidirectional and real-time. Okta Workflows can be used to build custom ServiceNow integration flows without code.",
        "response_code": "F",
        "okta_products": ["LCM", "Workflows", "OIN"],
    },

    # ── Support ───────────────────────────────────────────────────────────────
    {
        "category": "Support & Services",
        "question": "What are the vendor's support SLAs for critical (P1) incidents?",
        "answer": "Okta's Premier Support tier provides: P1 (Critical - service unavailable): initial response within 30 minutes, 24x7x365 coverage. P2 (High - significant degradation): 2 hours response. P3 (Medium - partial impact): 8 business hours. P4 (Low - general inquiries): 2 business days. All Premier Support customers receive a named Technical Account Manager, quarterly business reviews, and access to the Okta Support Portal with real-time case tracking.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },

    # ── Privileged Access ─────────────────────────────────────────────────────
    {
        "category": "Integration & Connectivity",
        "question": "Does the solution provide privileged access management (PAM) and vaulting for administrative accounts?",
        "answer": "Okta Privileged Access (OPA) provides just-in-time privileged access, account vaulting for service and administrative accounts, session recording, and infrastructure access management for servers, databases, and cloud resources. OPA integrates natively with Okta Identity Governance for unified access reviews of privileged accounts. Okta also has certified integrations with leading PAM vendors including CyberArk, BeyondTrust, and Delinea for organizations with existing PAM investments.",
        "response_code": "F",
        "okta_products": ["PAM"],
    },

    # ── AI / Automation ───────────────────────────────────────────────────────
    {
        "category": "AI & Automation",
        "question": "Does the solution use AI to improve access governance and reduce reviewer fatigue during certifications?",
        "answer": "Yes. Okta AI is embedded natively in the Identity Governance workflow. AI-powered access recommendations analyze historical access patterns, peer group benchmarks, and risk signals to suggest approve or revoke decisions for each certification item. In production deployments, Okta AI typically reduces certification review time by 40-60% by auto-approving low-risk, clearly appropriate access while escalating anomalous or high-risk items for human review. AI-generated entitlement descriptions improve reviewer understanding without requiring manual documentation.",
        "response_code": "F",
        "okta_products": ["OIG", "AI"],
    },
    {
        "category": "AI & Automation",
        "question": "Does the platform provide no-code or low-code workflow automation capabilities?",
        "answer": "Yes. Okta Workflows is a no-code automation platform built into the Okta identity platform. It allows identity administrators to build complex provisioning, deprovisioning, and governance workflows using a drag-and-drop interface. Okta Workflows includes 30+ native connectors to common enterprise systems and supports custom HTTP actions for any REST API. Workflows are version-controlled, auditable, and do not require custom development resources.",
        "response_code": "F",
        "okta_products": ["Workflows"],
    },

    # ── Data Handling / Audit ─────────────────────────────────────────────────
    {
        "category": "Security & Compliance",
        "question": "What are the audit logging capabilities and how long are logs retained?",
        "answer": "Okta maintains comprehensive, immutable audit logs for all identity events including authentication, provisioning, policy changes, access requests, and administrative actions. Logs are retained for a minimum of 90 days in the platform UI, with extended retention of up to 7+ years available via Okta's log streaming to external SIEM systems (Splunk, Microsoft Sentinel, etc.). All log entries include user, timestamp, IP address, device, and action with before/after state for configuration changes.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Security & Compliance",
        "question": "Does the platform support SIEM integration for security monitoring?",
        "answer": "Yes. Okta supports real-time log streaming to all major SIEM platforms including Splunk, Microsoft Sentinel, IBM QRadar, Sumo Logic, and Elastic. Okta's System Log API provides programmatic access to all event data. Pre-built SIEM integrations are available via the Okta Integration Network. Okta ThreatInsight provides built-in threat detection and can trigger automated responses via policy or Workflows.",
        "response_code": "F",
        "okta_products": ["Platform"],
    },
]


def seed_okta_knowledge(db):
    """Insert baseline Okta RFP knowledge into the knowledge base."""
    inserted = 0
    for entry in OKTA_KB_SEED:
        existing = db.search_knowledge_base(entry["question"][:80], limit=1)
        if existing:
            continue
        db.add_to_knowledge_base(
            source_rfp_name="Okta Baseline Knowledge",
            category=entry["category"],
            question=entry["question"],
            answer=entry["answer"],
            response_code=entry.get("response_code"),
            okta_products=entry.get("okta_products", []),
        )
        inserted += 1
    return inserted


if __name__ == "__main__":
    from db import Database
    db = Database("naughtrfp.db")
    db.init()
    n = seed_okta_knowledge(db)
    print(f"Seeded {n} entries ({len(OKTA_KB_SEED) - n} already existed)")
