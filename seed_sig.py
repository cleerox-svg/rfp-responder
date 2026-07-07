"""
Seed the NaughtRFP knowledge base from Okta's completed SIG Core questionnaire.
Run: py seed_sig.py
"""
import os
import openpyxl
from db import Database

SIG_PATH = os.path.join(
    os.path.expanduser("~"), "Desktop", "Claude Code Projects",
    "Sample RFP's", "Okta_SIG_Core.xlsm"
)

# Map SIG control families to RFP categories
CATEGORY_MAP = {
    "Identity and Access Management":     "Access Management",
    "Network Management":                 "Security & Compliance",
    "Contingency Planning":               "Security & Compliance",
    "Program Management":                 "Security & Compliance",
    "IT Services and Infrastructure":     "Technical Platform",
    "Data Governance":                    "Security & Compliance",
    "Risk Management Principles":         "Security & Compliance",
    "Personnel Security":                 "Security & Compliance",
    "Incident Event and Communications Management": "Security & Compliance",
    "Privacy":                            "Security & Compliance",
    "Cryptographic Controls":             "Security & Compliance",
    "Vulnerability Management":           "Security & Compliance",
    "Change Management":                  "Technical Platform",
    "Physical and Environmental":         "Security & Compliance",
    "Application Security":               "Technical Platform",
    "Audit Logging and Monitoring":       "Security & Compliance",
    "Business Continuity Management":     "Security & Compliance",
    "Cloud and Virtualization":           "Technical Platform",
    "Compliance":                         "Security & Compliance",
    "Human Resources Security":           "Security & Compliance",
}

OKTA_PRODUCTS_MAP = {
    "Identity and Access Management": ["OIG", "LCM", "SSO", "MFA", "Universal Directory"],
    "Cryptographic Controls":         ["Platform"],
    "Application Security":           ["Platform"],
    "Cloud and Virtualization":       ["Platform"],
    "Business Continuity Management": ["Platform"],
    "Contingency Planning":           ["Platform"],
}


def _build_answer(q_text, resp, detail, family):
    """Construct a meaningful KB answer from SIG data."""
    if detail and len(detail) > 20:
        prefix = f"Okta's response: {resp}. " if resp != "Yes" else ""
        return prefix + detail
    elif resp == "Yes":
        return (
            f"Yes. Okta has implemented controls to address this requirement "
            f"as part of its {family or 'security'} program. "
            f"This is covered by Okta's SOC 2 Type II, ISO 27001, and FedRAMP certifications. "
            f"See trust.okta.com for audit reports and compliance documentation."
        )
    elif resp == "No":
        return (
            f"No. This control is not currently in scope for Okta. "
            f"Please consult your Okta account team for details."
        )
    else:  # N/A
        return f"Not applicable to Okta's cloud-native SaaS architecture."


def seed_from_sig(db):
    wb = openpyxl.load_workbook(SIG_PATH, read_only=True, data_only=True, keep_vba=False)
    ws = wb["SIG 2024"]

    inserted = skipped = 0
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 4:
            continue
        q_num  = str(row[1]).strip() if row[1] else ""
        q_text = str(row[2]).strip() if row[2] else ""
        resp   = str(row[3]).strip() if row[3] else ""
        detail = str(row[4]).strip() if row[4] else ""
        family = str(row[6]).strip() if len(row) > 6 and row[6] else ""

        if not q_text or len(q_text) < 15 or resp not in ("Yes", "No", "N/A"):
            continue

        # Skip trivial No / N/A entries without detail
        if resp in ("No", "N/A") and not detail:
            skipped += 1
            continue

        # De-duplicate
        existing = db.search_knowledge_base(q_text[:60], limit=1)
        if existing and len(existing[0]["question"]) > 20:
            skipped += 1
            continue

        category = CATEGORY_MAP.get(family, "Security & Compliance")
        products = OKTA_PRODUCTS_MAP.get(family, ["Platform"])
        answer   = _build_answer(q_text, resp, detail, family)

        # Prefix question with SIG reference
        full_q = f"[SIG {q_num}] {q_text}"

        db.add_to_knowledge_base(
            source_rfp_name="Okta SIG Core 2024",
            category=category,
            question=full_q,
            answer=answer,
            response_code="F" if resp == "Yes" else ("N" if resp == "No" else "NE"),
            okta_products=products,
        )
        inserted += 1

    return inserted, skipped


if __name__ == "__main__":
    db = Database("naughtrfp.db")
    db.init()
    print(f"Loading SIG from:\n  {SIG_PATH}")
    n, s = seed_from_sig(db)
    stats = db.get_kb_stats()
    print(f"\nInserted: {n}  |  Skipped/dedup: {s}")
    print(f"KB total: {stats['total']} entries from {stats['source_rfps']} sources")
    print("\nTop categories:")
    for c in stats["categories"][:6]:
        print(f"  {c['category']}: {c['n']}")
