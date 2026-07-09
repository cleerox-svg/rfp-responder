import sqlite3
import json
import threading
from contextlib import contextmanager

_PRAGMAS = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA cache_size=-32000;
PRAGMA synchronous=NORMAL;
PRAGMA temp_store=MEMORY;
PRAGMA mmap_size=268435456;
"""


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._local = threading.local()

    def _get_con(self) -> sqlite3.Connection:
        """Return a thread-local connection, creating it on first use per thread."""
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
            con.row_factory = sqlite3.Row
            con.executescript(_PRAGMAS)
            self._local.con = con
        return con

    @contextmanager
    def conn(self):
        con = self._get_con()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise

    def init(self):
        with self.conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS rfps (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    name           TEXT    NOT NULL,
                    filename       TEXT,
                    status         TEXT    DEFAULT 'pending',
                    fit_score      REAL,
                    risk_score     REAL,
                    question_count INTEGER DEFAULT 0,
                    answered_count INTEGER DEFAULT 0,
                    flagged_count  INTEGER DEFAULT 0,
                    source         TEXT    DEFAULT 'upload',
                    drive_file_id  TEXT,
                    risk_profile   TEXT,
                    upload_preview TEXT,
                    customer_info  TEXT,
                    created_at     TEXT    DEFAULT (datetime('now')),
                    processed_at   TEXT
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    rfp_id        INTEGER REFERENCES rfps(id) ON DELETE CASCADE,
                    row_index     INTEGER,
                    category      TEXT,
                    question_text TEXT    NOT NULL,
                    answer        TEXT,
                    response_code TEXT,
                    confidence    REAL    DEFAULT 0,
                    fit_score     INTEGER DEFAULT 0,
                    risk_score    INTEGER DEFAULT 0,
                    status        TEXT    DEFAULT 'pending',
                    sources       TEXT    DEFAULT '[]',
                    okta_products TEXT    DEFAULT '[]',
                    needs_review  INTEGER DEFAULT 0,
                    review_reason TEXT,
                    document_id   INTEGER,
                    created_at    TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_rfp_name TEXT,
                    category        TEXT,
                    question        TEXT NOT NULL,
                    answer          TEXT NOT NULL,
                    response_code   TEXT,
                    okta_products   TEXT DEFAULT '[]',
                    quality_score   REAL DEFAULT 0.8,
                    use_count       INTEGER DEFAULT 0,
                    created_at      TEXT DEFAULT (datetime('now'))
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS kb_search
                USING fts5(
                    question, answer, category, okta_products,
                    content=knowledge_base, content_rowid=id
                );

                CREATE TABLE IF NOT EXISTS agent_logs (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    rfp_id     INTEGER REFERENCES rfps(id) ON DELETE CASCADE,
                    agent_name TEXT, status TEXT, message TEXT, details TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS rfp_documents (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    rfp_id         INTEGER REFERENCES rfps(id) ON DELETE CASCADE,
                    filename       TEXT,
                    display_name   TEXT,
                    status         TEXT    DEFAULT 'pending',
                    question_count INTEGER DEFAULT 0,
                    answered_count INTEGER DEFAULT 0,
                    flagged_count  INTEGER DEFAULT 0,
                    sort_order     INTEGER DEFAULT 0,
                    created_at     TEXT DEFAULT (datetime('now')),
                    processed_at   TEXT
                );

                CREATE TABLE IF NOT EXISTS demo_plans (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    rfp_id        INTEGER REFERENCES rfps(id) ON DELETE CASCADE,
                    status        TEXT DEFAULT 'draft',
                    sections      TEXT DEFAULT '[]',
                    summary       TEXT,
                    total_minutes INTEGER DEFAULT 0,
                    notes         TEXT,
                    confirmed_at  TEXT,
                    created_at    TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS token_usage (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    rfp_id        INTEGER REFERENCES rfps(id) ON DELETE CASCADE,
                    agent_name    TEXT, model TEXT,
                    input_tokens  INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    created_at    TEXT DEFAULT (datetime('now'))
                );

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
                    relevance_tags  TEXT,
                    status          TEXT DEFAULT 'new',
                    raw_data        TEXT,
                    fetched_at      TEXT DEFAULT (datetime('now')),
                    rfp_id          INTEGER REFERENCES rfps(id)
                );

                -- All indexes after all tables
                CREATE INDEX IF NOT EXISTS idx_questions_rfp_status   ON questions(rfp_id, status);
                CREATE INDEX IF NOT EXISTS idx_questions_rfp_rowindex  ON questions(rfp_id, row_index);
                CREATE INDEX IF NOT EXISTS idx_kb_category             ON knowledge_base(category);
                CREATE INDEX IF NOT EXISTS idx_kb_source               ON knowledge_base(source_rfp_name);
                CREATE INDEX IF NOT EXISTS idx_rfps_status             ON rfps(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_token_rfp               ON token_usage(rfp_id);
                CREATE INDEX IF NOT EXISTS idx_agent_logs_rfp          ON agent_logs(rfp_id);
                CREATE INDEX IF NOT EXISTS idx_demo_rfp                ON demo_plans(rfp_id, status);
                CREATE INDEX IF NOT EXISTS idx_rfp_docs_rfp            ON rfp_documents(rfp_id);
                CREATE INDEX IF NOT EXISTS idx_discovered_rfps_status  ON discovered_rfps(status);
                CREATE INDEX IF NOT EXISTS idx_discovered_rfps_source  ON discovered_rfps(source);
                CREATE INDEX IF NOT EXISTS idx_discovered_rfps_closing ON discovered_rfps(closing_date);
            """)
            # Migrate existing DBs
            for col, defn in [
                ("risk_profile",   "TEXT"),
                ("upload_preview", "TEXT"),
                ("customer_info",  "TEXT"),
                ("last_error",     "TEXT"),
            ]:
                try:
                    c.execute(f"ALTER TABLE rfps ADD COLUMN {col} {defn}")
                except Exception:
                    pass
            # questions.document_id — links a question to its source document
            try:
                c.execute("ALTER TABLE questions ADD COLUMN document_id INTEGER")
            except Exception:
                pass
            # Index on document_id must come after column exists
            try:
                c.execute("CREATE INDEX IF NOT EXISTS idx_questions_doc ON questions(document_id)")
            except Exception:
                pass

    # ── Settings ─────────────────────────────────────────────────────────────

    def get_setting(self, key):
        with self.conn() as c:
            row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else None

    def set_setting(self, key, value):
        with self.conn() as c:
            c.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                updated_at=datetime('now')
            """, (key, value))

    # ── RFPs ──────────────────────────────────────────────────────────────────

    def create_rfp(self, name, filename=None, source="upload", drive_file_id=None):
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO rfps (name, filename, source, drive_file_id) VALUES (?,?,?,?)",
                (name, filename, source, drive_file_id),
            )
            return cur.lastrowid

    def list_rfps(self):
        with self.conn() as c:
            rows = c.execute("SELECT * FROM rfps ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def get_rfp(self, rfp_id):
        with self.conn() as c:
            row = c.execute("SELECT * FROM rfps WHERE id=?", (rfp_id,)).fetchone()
            return dict(row) if row else None

    def update_rfp(self, rfp_id, **kwargs):
        if not kwargs:
            return
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [rfp_id]
        with self.conn() as c:
            c.execute(f"UPDATE rfps SET {sets} WHERE id=?", vals)

    def delete_rfp(self, rfp_id):
        with self.conn() as c:
            c.execute("DELETE FROM rfps WHERE id=?", (rfp_id,))

    # ── Questions ─────────────────────────────────────────────────────────────

    def create_question(self, rfp_id, row_index, category, question_text):
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO questions (rfp_id, row_index, category, question_text) VALUES (?,?,?,?)",
                (rfp_id, row_index, category, question_text),
            )
            return cur.lastrowid

    def get_questions(self, rfp_id):
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM questions WHERE rfp_id=? ORDER BY row_index", (rfp_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def update_question(self, q_id, **kwargs):
        if not kwargs:
            return
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [q_id]
        with self.conn() as c:
            c.execute(f"UPDATE questions SET {sets} WHERE id=?", vals)

    # ── Knowledge Base ────────────────────────────────────────────────────────

    def add_to_knowledge_base(self, source_rfp_name, category, question, answer,
                               response_code=None, okta_products=None):
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO knowledge_base
                   (source_rfp_name, category, question, answer, response_code, okta_products)
                   VALUES (?,?,?,?,?,?)""",
                (source_rfp_name, category, question, answer, response_code,
                 json.dumps(okta_products or [])),
            )
            kb_id = cur.lastrowid
            c.execute(
                "INSERT INTO kb_search(rowid, question, answer, category, okta_products) VALUES (?,?,?,?,?)",
                (kb_id, question, answer, category or "", json.dumps(okta_products or [])),
            )
            return kb_id

    @staticmethod
    def _build_fts_queries(raw: str) -> list[str]:
        """
        Turn a raw search string into a prioritised list of FTS5 query variants.
        Handles: single words, phrases, fragments, acronyms, mixed case.
        """
        q = raw.strip()
        if not q:
            return []

        variants: list[str] = []

        # 1. Exact phrase if multi-word
        if " " in q:
            variants.append(f'"{q}"')          # phrase match

        # 2. All words as prefix tokens (word* OR word2*) — handles fragments
        words = [w.strip('",;:.()[]') for w in q.split() if len(w.strip('",;:.()[]')) >= 2]
        if words:
            variants.append(" AND ".join(f'{w}*' for w in words))   # all words present
            if len(words) > 1:
                variants.append(" OR ".join(f'{w}*' for w in words)) # any word

        # 3. Each word individually (helps when query has stop words)
        for w in words:
            if len(w) >= 3:
                variants.append(f'{w}*')

        return variants

    def search_knowledge_base(self, query: str, limit: int = 10) -> list[dict]:
        """
        Multi-strategy search: FTS phrase → prefix-AND → prefix-OR → LIKE fallback.
        Deduplicates results and preserves relevance ordering.
        """
        if not query or not query.strip():
            return self.get_kb_entries(limit=limit)

        seen: dict[int, dict] = {}

        with self.conn() as c:
            fts_variants = self._build_fts_queries(query)

            for fts_q in fts_variants:
                if len(seen) >= limit:
                    break
                try:
                    rows = c.execute(
                        """SELECT kb.*, bm25(kb_search) AS rank
                           FROM kb_search
                           JOIN knowledge_base kb ON kb.id = kb_search.rowid
                           WHERE kb_search MATCH ?
                           ORDER BY rank LIMIT ?""",
                        (fts_q, limit),
                    ).fetchall()
                    for r in rows:
                        if r["id"] not in seen:
                            seen[r["id"]] = dict(r)
                except Exception:
                    continue

            # LIKE fallback — catches anything FTS missed
            if len(seen) < limit:
                terms = [t for t in query.split() if len(t) >= 3]
                for term in terms[:3]:
                    if len(seen) >= limit:
                        break
                    like = f"%{term}%"
                    try:
                        rows = c.execute(
                            """SELECT * FROM knowledge_base
                               WHERE (question LIKE ? OR answer LIKE ?)
                               LIMIT ?""",
                            (like, like, limit),
                        ).fetchall()
                        for r in rows:
                            if r["id"] not in seen:
                                seen[r["id"]] = dict(r)
                    except Exception:
                        continue

        return list(seen.values())[:limit]

    def search_knowledge_base_ranked(self, query: str, limit: int = 10) -> list[dict]:
        """
        Like search_knowledge_base() but includes fts_rank (1-based) and fts_score
        fields on each result, enabling Reciprocal Rank Fusion in the caller.
        Uses the same multi-strategy FTS5 fallback chain.

        fts_score is the raw SQLite bm25() value — negative, more negative = more
        relevant. ORDER BY fts_score ASC puts the best results first.
        LIKE fallback rows get fts_score=None.
        """
        if not query or not query.strip():
            results = self.get_kb_entries(limit=limit)
            for i, r in enumerate(results):
                r["fts_rank"] = i + 1
                r["fts_score"] = None
            return results

        variants = self._build_fts_queries(query)
        with self.conn() as c:
            for fts_q in variants:
                try:
                    rows = c.execute(
                        """SELECT kb.*, bm25(kb_search) AS fts_score
                           FROM kb_search
                           JOIN knowledge_base kb ON kb.id = kb_search.rowid
                           WHERE kb_search MATCH ?
                           ORDER BY fts_score
                           LIMIT ?""",
                        (fts_q, limit),
                    ).fetchall()
                    if rows:
                        results = [dict(r) for r in rows]
                        for i, r in enumerate(results):
                            r["fts_rank"] = i + 1
                        return results
                except Exception:
                    continue

            # LIKE fallback (no FTS score available — assign synthetic rank)
            if len(query.strip()) >= 3:
                pattern = f"%{query.strip()[:50]}%"
                try:
                    rows = c.execute(
                        """SELECT *, NULL AS fts_score FROM knowledge_base
                           WHERE question LIKE ? OR answer LIKE ?
                           ORDER BY use_count DESC LIMIT ?""",
                        (pattern, pattern, limit),
                    ).fetchall()
                    if rows:
                        results = [dict(r) for r in rows]
                        for i, r in enumerate(results):
                            r["fts_rank"] = i + 1
                            r["fts_score"] = r.get("fts_score")  # None for LIKE results
                        return results
                except Exception:
                    pass

        return []

    def get_kb_entries(self, limit=50, offset=0):
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM knowledge_base ORDER BY use_count DESC, created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── KB Sources Management ─────────────────────────────────────────────────

    def get_kb_sources(self) -> list[dict]:
        """
        Aggregate knowledge_base entries by source document/origin.
        Infers source_type: 'seed' for the three known seed origins,
        'rfp_ingest' if source matches an rfps.name, 'direct_upload' otherwise.
        """
        _SEED_NAMES = {
            "Okta Baseline Knowledge",
            "Okta SIG Core 2024",
            "Okta Confluence (Internal)",
        }
        with self.conn() as c:
            rows = c.execute("""
                SELECT
                    source_rfp_name                    AS source_name,
                    COUNT(*)                           AS entry_count,
                    GROUP_CONCAT(DISTINCT category)    AS categories_raw,
                    MAX(created_at)                    AS last_added,
                    MIN(created_at)                    AS first_added
                FROM knowledge_base
                WHERE source_rfp_name IS NOT NULL
                GROUP BY source_rfp_name
                ORDER BY entry_count DESC
            """).fetchall()

            rfp_names = {
                r[0] for r in c.execute("SELECT name FROM rfps").fetchall()
            }

        result = []
        for row in rows:
            d = dict(row)
            name = d["source_name"]
            cats_raw = d.pop("categories_raw") or ""
            # Split, deduplicate, truncate to 10
            seen = []
            for cat in cats_raw.split(","):
                cat = cat.strip()
                if cat and cat not in seen:
                    seen.append(cat)
            d["categories"] = seen[:10]
            if name in _SEED_NAMES:
                d["source_type"] = "seed"
            elif name in rfp_names:
                d["source_type"] = "rfp_ingest"
            else:
                d["source_type"] = "direct_upload"
            result.append(d)
        return result

    def get_kb_entries_by_source(self, source_name: str, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return KB entries belonging to one source, ordered by use_count desc."""
        with self.conn() as c:
            rows = c.execute(
                """SELECT * FROM knowledge_base
                   WHERE source_rfp_name = ?
                   ORDER BY use_count DESC, created_at DESC
                   LIMIT ? OFFSET ?""",
                (source_name, limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_kb_source(self, source_name: str) -> int:
        """
        Delete all KB entries from the given source.
        Manually cleans the kb_search FTS5 content table before deleting from
        knowledge_base — there are no automatic triggers maintaining sync.
        Returns the number of entries deleted.
        """
        with self.conn() as c:
            ids = [r[0] for r in c.execute(
                "SELECT id FROM knowledge_base WHERE source_rfp_name = ?",
                (source_name,),
            ).fetchall()]
            if not ids:
                return 0
            placeholders = ",".join("?" * len(ids))
            # FTS5 content table must be cleaned first — deleting base rows first
            # leaves orphaned FTS index entries that corrupt future searches.
            c.execute(f"DELETE FROM kb_search WHERE rowid IN ({placeholders})", ids)
            c.execute("DELETE FROM knowledge_base WHERE source_rfp_name = ?", (source_name,))
            return len(ids)

    def search_knowledge_base_by_source(self, query: str, source_name: str, limit: int = 20) -> list[dict]:
        """FTS5 search scoped to a single source_rfp_name."""
        variants = self._build_fts_queries(query)
        with self.conn() as c:
            for fts_q in variants:
                try:
                    rows = c.execute(
                        """SELECT kb.*
                           FROM kb_search
                           JOIN knowledge_base kb ON kb.id = kb_search.rowid
                           WHERE kb_search MATCH ? AND kb.source_rfp_name = ?
                           ORDER BY rank
                           LIMIT ?""",
                        (fts_q, source_name, limit),
                    ).fetchall()
                    if rows:
                        return [dict(r) for r in rows]
                except Exception:
                    continue
            # LIKE fallback
            pattern = f"%{query.strip()[:50]}%"
            try:
                rows = c.execute(
                    """SELECT * FROM knowledge_base
                       WHERE source_rfp_name = ? AND (question LIKE ? OR answer LIKE ?)
                       ORDER BY use_count DESC LIMIT ?""",
                    (source_name, pattern, pattern, limit),
                ).fetchall()
                return [dict(r) for r in rows]
            except Exception:
                return []

    def get_kb_stats(self):
        with self.conn() as c:
            total = c.execute("SELECT COUNT(*) AS n FROM knowledge_base").fetchone()["n"]
            sources = c.execute(
                "SELECT COUNT(DISTINCT source_rfp_name) AS n FROM knowledge_base"
            ).fetchone()["n"]
            cats = c.execute(
                "SELECT category, COUNT(*) AS n FROM knowledge_base GROUP BY category ORDER BY n DESC"
            ).fetchall()
            return {"total": total, "source_rfps": sources,
                    "categories": [dict(r) for r in cats]}

    # ── Agent Logs ────────────────────────────────────────────────────────────

    def log_agent(self, rfp_id, agent_name, status, message, details=None):
        with self.conn() as c:
            c.execute(
                "INSERT INTO agent_logs (rfp_id, agent_name, status, message, details) VALUES (?,?,?,?,?)",
                (rfp_id, agent_name, status, message,
                 json.dumps(details) if details else None),
            )

    def get_agent_logs(self, rfp_id):
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM agent_logs WHERE rfp_id=? ORDER BY id", (rfp_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── RFP Documents ─────────────────────────────────────────────────────────

    def add_document(self, rfp_id: int, filename: str, display_name: str,
                     sort_order: int = 0) -> int:
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO rfp_documents (rfp_id, filename, display_name, sort_order)
                   VALUES (?,?,?,?)""",
                (rfp_id, filename, display_name, sort_order),
            )
            return cur.lastrowid

    def get_documents(self, rfp_id: int) -> list[dict]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM rfp_documents WHERE rfp_id=? ORDER BY sort_order, id",
                (rfp_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_document(self, doc_id: int) -> dict | None:
        with self.conn() as c:
            row = c.execute(
                "SELECT * FROM rfp_documents WHERE id=?", (doc_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_document(self, doc_id: int, **kwargs) -> None:
        if not kwargs:
            return
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [doc_id]
        with self.conn() as c:
            c.execute(f"UPDATE rfp_documents SET {sets} WHERE id=?", vals)

    def delete_document(self, doc_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM rfp_documents WHERE id=?", (doc_id,))

    def get_questions_by_document(self, rfp_id: int, doc_id: int) -> list[dict]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM questions WHERE rfp_id=? AND document_id=? ORDER BY row_index",
                (rfp_id, doc_id)
            ).fetchall()
            return [dict(r) for r in rows]

    def sync_rfp_counts(self, rfp_id: int) -> None:
        """Recalculate RFP-level counts from all documents."""
        with self.conn() as c:
            docs = c.execute(
                "SELECT * FROM rfp_documents WHERE rfp_id=?", (rfp_id,)
            ).fetchall()
            total_q = sum(d["question_count"] for d in docs)
            total_a = sum(d["answered_count"] for d in docs)
            total_f = sum(d["flagged_count"]  for d in docs)

            # Score averages across all answered questions
            fits  = c.execute(
                "SELECT fit_score  FROM questions WHERE rfp_id=? AND status='answered' AND fit_score>0",
                (rfp_id,)
            ).fetchall()
            risks = c.execute(
                "SELECT risk_score FROM questions WHERE rfp_id=? AND status='answered' AND risk_score>0",
                (rfp_id,)
            ).fetchall()

            avg_fit  = round(sum(r[0] for r in fits)  / len(fits),  2) if fits  else None
            avg_risk = round(sum(r[0] for r in risks) / len(risks), 2) if risks else None

            all_complete = all(d["status"] in ("complete", "error") for d in docs) if docs else False
            status = "complete" if all_complete else ("processing" if any(d["status"] == "processing" for d in docs) else "pending")

            update = {"question_count": total_q, "answered_count": total_a, "flagged_count": total_f}
            if avg_fit  is not None: update["fit_score"]  = avg_fit
            if avg_risk is not None: update["risk_score"] = avg_risk
            if docs: update["status"] = status

            sets = ", ".join(f"{k}=?" for k in update)
            c.execute(f"UPDATE rfps SET {sets} WHERE id=?", list(update.values()) + [rfp_id])

    # ── Demo Plans ────────────────────────────────────────────────────────────

    def create_demo_plan(self, rfp_id, sections, summary, total_minutes):
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO demo_plans (rfp_id, sections, summary, total_minutes)
                   VALUES (?,?,?,?)""",
                (rfp_id, json.dumps(sections), summary, total_minutes),
            )
            return cur.lastrowid

    def get_demo_plan(self, rfp_id):
        with self.conn() as c:
            row = c.execute(
                "SELECT * FROM demo_plans WHERE rfp_id=? ORDER BY id DESC LIMIT 1",
                (rfp_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_demo_plan(self, plan_id, **kwargs):
        if not kwargs:
            return
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [plan_id]
        with self.conn() as c:
            c.execute(f"UPDATE demo_plans SET {sets} WHERE id=?", vals)

    def list_confirmed_demos(self):
        with self.conn() as c:
            rows = c.execute("""
                SELECT d.*, r.name AS rfp_name, r.fit_score, r.risk_score,
                       r.customer_info
                FROM demo_plans d
                JOIN rfps r ON r.id = d.rfp_id
                WHERE d.status = 'confirmed'
                ORDER BY d.confirmed_at DESC
            """).fetchall()
            return [dict(r) for r in rows]

    # ── Token Usage ───────────────────────────────────────────────────────────

    def record_tokens(self, rfp_id, agent_name, model, input_tokens, output_tokens):
        with self.conn() as c:
            c.execute(
                """INSERT INTO token_usage
                   (rfp_id, agent_name, model, input_tokens, output_tokens)
                   VALUES (?,?,?,?,?)""",
                (rfp_id, agent_name, model, input_tokens, output_tokens),
            )

    def get_token_summary(self):
        with self.conn() as c:
            totals = c.execute("""
                SELECT
                    SUM(input_tokens)  AS total_input,
                    SUM(output_tokens) AS total_output,
                    COUNT(*)           AS total_calls
                FROM token_usage
            """).fetchone()
            by_rfp = c.execute("""
                SELECT r.name, SUM(t.input_tokens) AS inp, SUM(t.output_tokens) AS out
                FROM token_usage t
                JOIN rfps r ON r.id = t.rfp_id
                GROUP BY t.rfp_id
                ORDER BY inp + out DESC
                LIMIT 10
            """).fetchall()
            by_model = c.execute("""
                SELECT model, SUM(input_tokens) AS inp, SUM(output_tokens) AS out
                FROM token_usage
                GROUP BY model
                ORDER BY inp + out DESC
            """).fetchall()
            return {
                "total_input":  totals["total_input"]  or 0,
                "total_output": totals["total_output"] or 0,
                "total_calls":  totals["total_calls"]  or 0,
                "by_rfp":   [dict(r) for r in by_rfp],
                "by_model": [dict(r) for r in by_model],
            }

    # ── Discovered RFPs ───────────────────────────────────────────────────────

    def save_discovered_rfp(self, data: dict) -> int:
        """Insert or update a discovered RFP. Returns the row id.
        Deduplicates by solicitation_no (if present) or (source + title) composite."""
        sol_no = data.get("solicitation_no") or ""
        with self.conn() as c:
            existing_id = None
            if sol_no:
                row = c.execute(
                    "SELECT id FROM discovered_rfps WHERE solicitation_no=?", (sol_no,)
                ).fetchone()
                if row:
                    existing_id = row["id"]
            else:
                source = data.get("source", "")
                title  = data.get("title", "")
                row = c.execute(
                    "SELECT id FROM discovered_rfps WHERE source=? AND title=?",
                    (source, title),
                ).fetchone()
                if row:
                    existing_id = row["id"]

            # Serialise relevance_tags and raw_data if passed as non-string
            fields = dict(data)
            if "relevance_tags" in fields and not isinstance(fields["relevance_tags"], str):
                fields["relevance_tags"] = json.dumps(fields["relevance_tags"])
            if "raw_data" in fields and not isinstance(fields["raw_data"], str):
                fields["raw_data"] = json.dumps(fields["raw_data"])

            if existing_id is not None:
                sets = ", ".join(f"{k}=?" for k in fields)
                vals = list(fields.values()) + [existing_id]
                c.execute(f"UPDATE discovered_rfps SET {sets} WHERE id=?", vals)
                return existing_id
            else:
                cols = ", ".join(fields.keys())
                placeholders = ", ".join("?" for _ in fields)
                cur = c.execute(
                    f"INSERT INTO discovered_rfps ({cols}) VALUES ({placeholders})",
                    list(fields.values()),
                )
                return cur.lastrowid

    def get_discovered_rfps(self, status=None, source=None) -> list:
        """Return discovered RFPs, optionally filtered by status or source.
        Ordered by relevance_score DESC, then closing_date ASC."""
        filters = []
        params  = []
        if status is not None:
            filters.append("status=?")
            params.append(status)
        if source is not None:
            filters.append("source=?")
            params.append(source)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        with self.conn() as c:
            rows = c.execute(
                f"""SELECT * FROM discovered_rfps
                    {where}
                    ORDER BY relevance_score DESC,
                             CASE WHEN closing_date IS NULL THEN 1 ELSE 0 END,
                             closing_date ASC""",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def update_discovered_rfp(self, discovery_id: int, **kwargs) -> None:
        """Update any fields on a discovered_rfp row."""
        if not kwargs:
            return
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [discovery_id]
        with self.conn() as c:
            c.execute(f"UPDATE discovered_rfps SET {sets} WHERE id=?", vals)

    def dismiss_discovered_rfp(self, discovery_id: int) -> None:
        """Set status = 'dismissed' on a discovered RFP."""
        with self.conn() as c:
            c.execute(
                "UPDATE discovered_rfps SET status='dismissed' WHERE id=?",
                (discovery_id,),
            )

    def import_discovered_rfp(self, discovery_id: int) -> int:
        """Create an RFP record from a discovered_rfp row.
        Sets discovered_rfps.rfp_id = new rfp id, status = 'imported'.
        Returns the new rfp_id."""
        with self.conn() as c:
            row = c.execute(
                "SELECT * FROM discovered_rfps WHERE id=?", (discovery_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"discovered_rfp id={discovery_id} not found")
            disc = dict(row)

        # Build customer_info JSON from discovery metadata
        customer_info = json.dumps({
            "org_name":        disc.get("org_name"),
            "solicitation_no": disc.get("solicitation_no"),
            "source":          disc.get("source"),
            "source_url":      disc.get("source_url"),
            "closing_date":    disc.get("closing_date"),
            "posted_date":     disc.get("posted_date"),
            "est_value":       disc.get("est_value"),
            "gsin_code":       disc.get("gsin_code"),
            "relevance_tags":  disc.get("relevance_tags"),
        })

        rfp_name = disc.get("title") or f"Imported RFP {discovery_id}"
        rfp_id = self.create_rfp(
            name=rfp_name,
            source="discovery",
        )
        self.update_rfp(rfp_id, customer_info=customer_info)

        # Link discovery row back to the new rfp
        with self.conn() as c:
            c.execute(
                "UPDATE discovered_rfps SET rfp_id=?, status='imported' WHERE id=?",
                (rfp_id, discovery_id),
            )

        return rfp_id

    def get_discovery_stats(self) -> dict:
        """Return counts: total, new, imported, dismissed."""
        with self.conn() as c:
            rows = c.execute(
                """SELECT status, COUNT(*) AS n
                   FROM discovered_rfps
                   GROUP BY status"""
            ).fetchall()
            counts = {r["status"]: r["n"] for r in rows}
            total = c.execute(
                "SELECT COUNT(*) AS n FROM discovered_rfps"
            ).fetchone()["n"]
            return {
                "total":     total,
                "new":       counts.get("new",       0),
                "imported":  counts.get("imported",  0),
                "dismissed": counts.get("dismissed", 0),
            }
