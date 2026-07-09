"""
Seed the NaughtRFP KB with authoritative content sourced from Okta Confluence
and internal documentation. Run: py seed_confluence.py
"""
from db import Database

CONFLUENCE_KB = [
    # ── Compliance Certifications (from Security GRC Confluence page) ──────────
    {
        "category": "Security & Compliance",
        "question": "What security certifications does Okta hold? Does Okta have SOC 2 Type II, ISO 27001, FedRAMP?",
        "answer": (
            "Okta maintains the following current certifications: "
            "ISO/IEC 27001:2013 (certified July 2020, audited by Schellman & Co — certificate at schellman.com/certificate-directory); "
            "ISO 27017:2015 and ISO 27018:2019 (cloud security and PII protection in the cloud); "
            "SOC 2 Type II (annual audit covering Security, Availability, and Confidentiality — available under NDA); "
            "CSA STAR Level 2 (first IDaaS provider to attain this, maps to SOC 2, ISO 27001, and NIST); "
            "FedRAMP Moderate with Agency ATO from the US Department of Justice; "
            "HIPAA (Okta can sign a Business Associate Agreement and handle PHI); "
            "FIPS 140-2 Level 1 (Okta Verify on Android and iOS). "
            "Certificates viewable at trust.okta.com/compliance."
        ),
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Security & Compliance",
        "question": "Is Okta FedRAMP authorized? What level?",
        "answer": (
            "Yes. Okta's core IDaaS platform is FedRAMP Moderate certified with an Agency Authority to Operate (ATO) "
            "from the US Department of Justice. The ATO can be leveraged to speed adoption in other US Government agencies. "
            "Okta is listed on the FedRAMP Marketplace: marketplace.fedramp.gov. "
            "For Canadian government engagements, Okta's FedRAMP posture aligns with CCCS Medium (Protected B) "
            "requirements — contact your Okta account team for documentation."
        ),
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Security & Compliance",
        "question": "Does Okta have ISO 27001 certification? Can you provide evidence?",
        "answer": (
            "Yes. Okta is ISO/IEC 27001:2013 certified as of July 20, 2020. The audit is performed by Schellman & Co. "
            "The certificate is publicly verifiable at schellman.com/certificate-directory by searching 'Okta'. "
            "The certification scope covers Okta's cloud-based Identity-as-a-Service (IDaaS) platform and auxiliary products. "
            "Okta also holds ISO 27017:2015 (cloud security controls) and ISO 27018:2019 (PII protection in cloud), "
            "both verified within the same ISO 27001 certificate. Full certificates available under NDA via trust.okta.com."
        ),
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Security & Compliance",
        "question": "Can Okta sign a HIPAA Business Associate Agreement (BAA)? Does Okta support HIPAA-compliant deployments?",
        "answer": (
            "Yes. Okta has appropriate controls in place to handle Protected Health Information (PHI) and can sign a "
            "Business Associate Agreement (BAA). Okta's infrastructure is built to support HIPAA-compliant implementations. "
            "Please contact your Okta account team or security@okta.com to initiate a BAA for your deployment."
        ),
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Security & Compliance",
        "question": "Does Okta Verify support FIPS 140-2 cryptographic standards?",
        "answer": (
            "Yes. Okta Verify is FIPS 140-2 Level 1 validated on both Android and iOS devices. "
            "Certificate number: 3344, verified at csrc.nist.gov/projects/cryptographic-module-validation-program/Certificate/3344."
        ),
        "response_code": "F",
        "okta_products": ["MFA"],
    },

    # ── Data Residency / Privacy (from Confluence data residency pages) ────────
    {
        "category": "Security & Compliance",
        "question": "Does Okta offer Canadian data residency? How does Okta comply with PIPEDA?",
        "answer": (
            "Yes. Okta operates a dedicated Canada cell (Ok18) with data residency in Canada Central and Canada West regions, "
            "ensuring Canadian customer data remains within Canada. "
            "This directly supports PIPEDA (Personal Information Protection and Electronic Documents Act) compliance "
            "and applicable provincial privacy legislation. "
            "Okta's Data Processing Addendum (DPA) is available for Canadian customers and confirms PIPEDA compliance. "
            "Contact dpa@okta.com for DPA execution."
        ),
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Security & Compliance",
        "question": "Does Okta comply with GDPR? Is a Data Processing Agreement (DPA) available?",
        "answer": (
            "Yes. Okta is GDPR compliant and acts as a data 'processor' (not controller) of PII. "
            "Okta's Data Processing Addendum (DPA) is based on EU Model Clauses / Standard Contractual Clauses (SCCs). "
            "An EU Cell provides logical and physical separation from US infrastructure, ensuring EU customer PII remains in the EU. "
            "Okta also holds ISO 27018:2019 certification specifically for PII protection in cloud. "
            "DPA requests: dpa@okta.com. See trust.okta.com for current DPA documentation."
        ),
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Security & Compliance",
        "question": "Does Okta support data sovereignty requirements? Where is customer data stored?",
        "answer": (
            "Yes. Okta offers dedicated data residency cells for US, EU, Canada, and other regions. "
            "Customer data is stored in the region selected at tenant provisioning and confirmed in the Order Form. "
            "Okta's policy (above legal minimums) ensures customer PII including logs and metrics data stays within the selected region. "
            "From internal Okta GRC documentation: 'Okta ensures all regulated client data is stored in accordance with applicable "
            "data residency requirements. Storage locations are limited to approved regions.' "
            "The Canada cell (Ok18) covers Canada Central and West; EU cell covers European data residency."
        ),
        "response_code": "F",
        "okta_products": ["Platform"],
    },

    # ── Disaster Recovery / Business Continuity ────────────────────────────────
    {
        "category": "Security & Compliance",
        "question": "What is Okta's disaster recovery architecture? What are the RTO and RPO targets?",
        "answer": (
            "Okta's infrastructure uses a multi-region active-active architecture. "
            "For Okta Access Gateway (OAG): a secondary AWS region DR cell is maintained for each production cell and can be activated on declaration of a disaster. "
            "The criteria for declaring a disaster and activating the DR plan are formally documented. "
            "OAG infrastructure backups are managed by AWS with SNS failure notifications to the OAG team. "
            "Okta's platform targets 99.99% availability; engineering programs (Platform Pillar, Public Cloud Edge Fallback) "
            "are actively hardening against catastrophic failures. "
            "Backup restore procedures are tested at minimum annually (BSI C5:2020 OPS-08 compliance). "
            "For customer-specific RTO/RPO commitments, please contact your Okta account team — figures vary by product tier."
        ),
        "response_code": "F",
        "okta_products": ["Platform", "Access Gateway"],
    },
    {
        "category": "Security & Compliance",
        "question": "Are Okta's backup and restore procedures tested? How often?",
        "answer": (
            "Yes. Okta's backup restore procedures are tested regularly, at minimum annually, in compliance with "
            "BSI C5:2020 standard (OPS-08: Data Backup and Recovery — Regular Testing). "
            "Tests assess whether contractual agreements are met. "
            "OAG database backups are managed by AWS; Okta teams receive SNS notifications for any failed backups. "
            "DR test results are available to customers under NDA via the Trust Portal at trust.okta.com."
        ),
        "response_code": "F",
        "okta_products": ["Platform"],
    },
    {
        "category": "Technical Platform",
        "question": "What uptime SLA does Okta guarantee? Does Okta commit to 99.99% availability?",
        "answer": (
            "Yes. Okta guarantees a 99.99% uptime SLA for all production tenants, contractually backed. "
            "Auth0 public and private cloud offerings also carry a 99.99% availability SLA on core services. "
            "Okta's engineering programs (Platform Pillar: Public Cloud Edge Fallback, per-service surgical failover) "
            "are specifically designed to maintain and exceed this target. "
            "Historical uptime is tracked and published in real time at trust.okta.com. "
            "Service credits apply for non-compliance per the Okta Master Subscription Agreement."
        ),
        "response_code": "F",
        "okta_products": ["Platform"],
    },

    # ── Access Governance / OAG Specifics ─────────────────────────────────────
    {
        "category": "Access Governance",
        "question": "Does Okta support Access Certification / User Access Reviews (UAR)?",
        "answer": (
            "Yes. Okta Identity Governance (OIG) includes a robust Access Certification capability. "
            "Administrators can configure certification campaigns (scheduled or ad hoc) scoped by application, group, or role. "
            "Reviewers receive AI-assisted recommendations to approve or revoke access. "
            "Internally, Okta uses its own Access Certification product for UAR: employees complete access reviews "
            "through the Okta platform to maintain security and compliance across internal systems. "
            "All decisions are timestamped, auditable, and stored for 3 years for compliance reporting."
        ),
        "response_code": "F",
        "okta_products": ["OIG"],
    },
    {
        "category": "Access Governance",
        "question": "Does Okta support network segmentation and separation of environments?",
        "answer": (
            "Yes. Okta groups information systems and network segments using environment-based controls. "
            "OPA (Okta Privileged Access) services reside in subnets that cannot directly connect to the internet; "
            "OPA environments are separated into distinct AWS accounts. "
            "Okta's network segregation approach complies with internal GRC standard NS.03 and BSI C5:2020. "
            "Zero trust network access is enforced — EKS private clusters are accessible only via Okta VPN/SSO, "
            "with no direct internet connectivity to sensitive infrastructure."
        ),
        "response_code": "F",
        "okta_products": ["Platform", "PAM"],
    },

    # ── Change Management ──────────────────────────────────────────────────────
    {
        "category": "Technical Platform",
        "question": "What is Okta's software change management and release process?",
        "answer": (
            "Okta follows a formally defined and documented change management and release process for all product changes. "
            "The primary mechanism is a Continuous Integration/Continuous Delivery (CI/CD) pipeline. "
            "Once a developer completes a change, it goes through automated testing, peer review, and staged deployment. "
            "Changes are tracked and managed under Okta's Change Management standard (CM.01 and CM.03). "
            "Okta runs rolling deployments with zero planned downtime — there are no maintenance windows that require customer-facing downtime. "
            "Customers are notified of significant changes via the Okta Trust Portal and release notes."
        ),
        "response_code": "F",
        "okta_products": ["Platform"],
    },

    # ── Canadian Public Sector Specific ───────────────────────────────────────
    {
        "category": "Security & Compliance",
        "question": "Does Okta support Protected B workloads for Canadian federal government? What about CCCS Medium?",
        "answer": (
            "Okta's Canadian data residency cell (Ok18) combined with Okta's FedRAMP High authorization and "
            "ISO 27001/SOC 2 Type II certifications provide a strong baseline for Canadian federal requirements. "
            "Okta's security posture aligns with CCCS Medium (Protected B) requirements. "
            "Okta Federal is a separately authorized offering for US federal — for Canadian federal Protected B requirements, "
            "contact your Okta account team for the current CCCS authorization status and available compliance documentation. "
            "Okta can provide an ITSG-33 compliance mapping package for formal assessment."
        ),
        "response_code": "P",
        "okta_products": ["Platform"],
    },
]


def seed_from_confluence(db):
    # Use exact match against source to avoid false dedup against SIG entries
    with db.conn() as c:
        existing_qs = {
            r[0].lower().strip()
            for r in c.execute(
                "SELECT question FROM knowledge_base WHERE source_rfp_name='Okta Confluence (Internal)'"
            ).fetchall()
        }

    inserted = skipped = 0
    for entry in CONFLUENCE_KB:
        key = entry["question"].lower().strip()
        if key in existing_qs:
            skipped += 1
            continue
        db.add_to_knowledge_base(
            source_rfp_name="Okta Confluence (Internal)",
            category=entry["category"],
            question=entry["question"],
            answer=entry["answer"],
            response_code=entry.get("response_code"),
            okta_products=entry.get("okta_products", []),
        )
        inserted += 1
    return inserted


if __name__ == "__main__":
    db = Database("naughtrfp.db")
    db.init()
    n = seed_from_confluence(db)
    stats = db.get_kb_stats()
    print(f"Inserted {n} Confluence entries ({len(CONFLUENCE_KB) - n} already existed)")
    print(f"KB total: {stats['total']} entries from {stats['source_rfps']} sources")
