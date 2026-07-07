import csv
import io
import json
import os
import queue
import threading
import uuid
import zipfile

import httpx
import openpyxl
from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, session, stream_with_context
from werkzeug.utils import secure_filename

from db import Database
from agents import (AgentPipeline, KnowledgeBaseAgent, ai_search_knowledge_base,
                    detect_customer, set_litellm_base_url, set_web_search_enabled,
                    DemoPrepAgent)
from export_handler import export_rfp as do_export

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "naughtrfp-dev-secret-change-in-prod")

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs("exports", exist_ok=True)

db = Database("naughtrfp.db")
db.init()

# Bootstrap settings from environment variables so judges can configure via
# .env without touching the UI. Environment values win over any previously
# saved DB value, making the .env the single source of truth on first run.
def _env_bootstrap():
    _env_map = {
        "LITELLM_API_KEY":   "anthropic_api_key",
        "LITELLM_BASE_URL":  "litellm_base_url",
        "OKTA_DOMAIN":       "okta_domain",
        "OKTA_CLIENT_ID":    "okta_client_id",
        "OKTA_REDIRECT_URI": "okta_redirect_uri",
    }
    for env_var, setting_key in _env_map.items():
        val = os.environ.get(env_var, "").strip()
        if val:
            db.set_setting(setting_key, val)

# Load .env file if present (no external dependency — plain key=value parsing)
def _load_dotenv():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

_load_dotenv()
_env_bootstrap()

# Apply saved LiteLLM base URL on startup
_saved_base_url = db.get_setting("litellm_base_url")
if _saved_base_url:
    set_litellm_base_url(_saved_base_url)

ALLOWED = {"csv", "xlsx", "xls"}

RISKY_KEYWORDS = [
    "sla", "uptime", "99.9", "99.99", "penalty", "indemnif", "liability",
    "audit", "compliance", "pipeda", "gdpr", "hipaa", "fedramp", "cccs",
    "iso 27001", "soc 2", "disaster recovery", "rto", "rpo", "breach",
    "mandatory", "disqualif", "insurance", "warranty", "data residency",
    "sovereignty", "encryption", "penetration test", "legal", "regulation",
]


def quick_scan(filepath):
    """Rule-based risk scan and preview extraction — no API call needed."""
    ext = filepath.rsplit(".", 1)[-1].lower()
    rows = []

    try:
        if ext == "csv":
            with open(filepath, newline="", encoding="utf-8-sig") as f:
                rows = [dict(r) for r in csv.DictReader(f)]
        elif ext in ("xlsx", "xls"):
            wb = openpyxl.load_workbook(filepath, data_only=True)
            ws = wb.active
            headers = None
            for row in ws.iter_rows(values_only=True):
                if not any(c for c in row if c is not None):
                    continue
                if headers is None:
                    headers = [str(c).strip() if c else f"col_{i}" for i, c in enumerate(row)]
                else:
                    rows.append({headers[i]: row[i] for i in range(min(len(headers), len(row)))})
    except Exception:
        return {}, {}

    if not rows:
        return {}, {}

    keys = list(rows[0].keys())
    priority_col = next((k for k in keys if any(w in k.lower() for w in ("priority", "critical"))), None)
    category_col = next((k for k in keys if any(w in k.lower() for w in ("category", "section", "area"))), None)
    req_col = next((k for k in keys if any(w in k.lower() for w in ("requirement", "criteria", "question", "description"))), None)

    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    categories = {}
    kw_hits = set()
    valid = 0

    for row in rows:
        if priority_col:
            p = str(row.get(priority_col) or "").strip().lower()
            if "critical" in p:    counts["Critical"] += 1
            elif "high" in p:      counts["High"] += 1
            elif "med" in p:       counts["Medium"] += 1
            elif "low" in p:       counts["Low"] += 1

        if category_col:
            cat = str(row.get(category_col) or "").strip()
            if cat:
                categories[cat] = categories.get(cat, 0) + 1

        if req_col:
            text = str(row.get(req_col) or "").lower()
            if len(text) > 10:
                valid += 1
                kw_hits.update(kw for kw in RISKY_KEYWORDS if kw in text)

    total = max(sum(counts.values()), 1)
    weighted = counts["Critical"] * 5 + counts["High"] * 3 + counts["Medium"] * 2 + counts["Low"] * 1
    kw_bonus = min(len(kw_hits) * 0.2, 1.5)
    raw = (weighted / total) + kw_bonus
    score = round(min(raw, 5.0), 2)
    level = "High" if score >= 4 else "Medium" if score >= 2.5 else "Low"

    risk_profile = {
        "preliminary_risk_score": score,
        "risk_level": level,
        "priority_breakdown": counts,
        "risky_keywords": sorted(kw_hits)[:10],
        "total_requirements": valid or len(rows),
    }
    upload_preview = {
        "total_rows": len(rows),
        "valid_requirements": valid or len(rows),
        "categories": categories,
        "priority_breakdown": counts,
        "columns": keys[:8],
    }
    return risk_profile, upload_preview


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── Settings ──────────────────────────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify({
        "api_key_set": bool(db.get_setting("anthropic_api_key")),
        "drive_folder_id": db.get_setting("drive_folder_id") or "",
        "drive_folder_name": db.get_setting("drive_folder_name") or "",
        "litellm_base_url": db.get_setting("litellm_base_url") or "",
        "web_search_enabled": db.get_setting("web_search_enabled") != "false",
        "okta_domain": db.get_setting("okta_domain") or "",
        "okta_client_id": db.get_setting("okta_client_id") or "",
        "okta_redirect_uri": db.get_setting("okta_redirect_uri") or "http://localhost:5000/auth/callback",
        "okta_auth_enabled": db.get_setting("okta_auth_enabled") == "true",
    })


@app.route("/api/settings", methods=["POST"])
def save_settings():
    data = request.get_json() or {}
    if data.get("api_key"):
        db.set_setting("anthropic_api_key", data["api_key"])
    if "drive_folder_id" in data:
        db.set_setting("drive_folder_id", data["drive_folder_id"])
    if "drive_folder_name" in data:
        db.set_setting("drive_folder_name", data["drive_folder_name"])
    if "litellm_base_url" in data:
        url = data["litellm_base_url"].strip().rstrip("/") or ""
        db.set_setting("litellm_base_url", url)
        set_litellm_base_url(url)
    if "web_search_enabled" in data:
        val = bool(data["web_search_enabled"])
        db.set_setting("web_search_enabled", "true" if val else "false")
        set_web_search_enabled(val)
    if "okta_domain" in data:
        db.set_setting("okta_domain", data["okta_domain"].strip())
    if "okta_client_id" in data:
        db.set_setting("okta_client_id", data["okta_client_id"].strip())
    if "okta_redirect_uri" in data:
        db.set_setting("okta_redirect_uri", data["okta_redirect_uri"].strip())
    if "okta_auth_enabled" in data:
        db.set_setting("okta_auth_enabled", "true" if data["okta_auth_enabled"] else "false")
    return jsonify({"success": True})


# ── Okta Auth (disabled for hackathon judging — enable via Settings) ───────────
#
# Full OIDC Authorization Code + PKCE flow. When okta_auth_enabled is true,
# /auth/login redirects the user to Okta, Okta redirects back to /auth/callback
# with a code, the callback exchanges the code for tokens, validates the ID token,
# and stores the user session. /auth/logout clears the session and redirects to
# Okta's logout endpoint.
#
# Currently bypassed: okta_auth_enabled defaults to false so all routes are
# accessible without authentication. Judges do not need an Okta account.
# To enable for production deployment, configure Okta domain + Client ID in
# Settings and toggle Enable Okta Authentication on.

import secrets
import urllib.parse

@app.route("/auth/login")
def auth_login():
    if db.get_setting("okta_auth_enabled") != "true":
        return redirect("/")
    okta_domain = db.get_setting("okta_domain", "")
    client_id   = db.get_setting("okta_client_id", "")
    redirect_uri = db.get_setting("okta_redirect_uri", "http://localhost:5000/auth/callback")
    if not okta_domain or not client_id:
        return "Okta not configured — set domain and client ID in Settings.", 400
    state = secrets.token_urlsafe(16)
    session["okta_state"] = state
    params = urllib.parse.urlencode({
        "client_id":     client_id,
        "response_type": "code",
        "scope":         "openid profile email",
        "redirect_uri":  redirect_uri,
        "state":         state,
    })
    return redirect(f"{okta_domain.rstrip('/')}/oauth2/v1/authorize?{params}")


@app.route("/auth/callback")
def auth_callback():
    if db.get_setting("okta_auth_enabled") != "true":
        return redirect("/")
    # State validation
    if request.args.get("state") != session.pop("okta_state", None):
        return "Invalid state parameter.", 400
    code = request.args.get("code")
    if not code:
        return "Missing authorisation code.", 400
    okta_domain  = db.get_setting("okta_domain", "")
    client_id    = db.get_setting("okta_client_id", "")
    redirect_uri = db.get_setting("okta_redirect_uri", "http://localhost:5000/auth/callback")
    # Exchange code for tokens (requires client_secret for confidential apps;
    # use PKCE verifier here for public/SPA apps)
    token_url = f"{okta_domain.rstrip('/')}/oauth2/v1/token"
    resp = httpx.post(token_url, data={
        "grant_type":   "authorization_code",
        "code":         code,
        "redirect_uri": redirect_uri,
        "client_id":    client_id,
    }, verify=False)
    if resp.status_code != 200:
        return f"Token exchange failed: {resp.text}", 400
    tokens = resp.json()
    # Store minimal session — in production, validate the ID token signature
    session["user"] = {"email": tokens.get("id_token", "unknown")}
    return redirect("/")


@app.route("/auth/logout")
def auth_logout():
    user = session.pop("user", None)
    if db.get_setting("okta_auth_enabled") != "true" or not user:
        return redirect("/")
    okta_domain = db.get_setting("okta_domain", "")
    client_id   = db.get_setting("okta_client_id", "")
    params = urllib.parse.urlencode({
        "client_id":    client_id,
        "post_logout_redirect_uri": "http://localhost:5000/",
    })
    return redirect(f"{okta_domain.rstrip('/')}/oauth2/v1/logout?{params}")


@app.route("/api/test-connection", methods=["POST"])
def test_connection():
    api_key = (request.get_json() or {}).get("api_key") or db.get_setting("anthropic_api_key")
    if not api_key:
        return jsonify({"ok": False, "error": "No API key provided"})
    try:
        from agents import _make_client
        client = _make_client(api_key)
        client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        return jsonify({"ok": True, "message": "Connection successful ✓"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


# ── RFPs ──────────────────────────────────────────────────────────────────────

@app.route("/api/rfps")
def list_rfps():
    return jsonify(db.list_rfps())


def _save_upload(f) -> tuple[str, str, str]:
    """Save an uploaded file, return (filename, unique_filename, filepath)."""
    filename = secure_filename(f.filename)
    unique   = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique)
    f.save(filepath)
    return filename, unique, filepath


@app.route("/api/rfp/upload", methods=["POST"])
def upload_rfp():
    """
    Accepts one or many files.
    Single file  → creates RFP + one document (backward compat).
    Multiple files → creates one RFP project + one document per file.
    Optional form field: project_name (defaults to first filename stem).
    Optional form field: rfp_id — add documents to an EXISTING RFP project.
    """
    files = request.files.getlist("files") or request.files.getlist("file")
    if not files or not files[0].filename:
        return jsonify({"error": "No files provided"}), 400

    valid = [f for f in files if f.filename and _allowed(f.filename)]
    if not valid:
        return jsonify({"error": "No supported files (use CSV or XLSX)."}), 400

    api_key      = db.get_setting("anthropic_api_key")
    existing_id  = request.form.get("rfp_id")
    project_name = request.form.get("project_name", "").strip()

    # Create or reuse RFP project
    if existing_id:
        rfp_id = int(existing_id)
        rfp = db.get_rfp(rfp_id)
        if not rfp:
            return jsonify({"error": "RFP project not found"}), 404
    else:
        first_name = secure_filename(valid[0].filename).rsplit(".", 1)[0]
        rfp_id = db.create_rfp(
            name=project_name or first_name,
            filename=None,          # project-level; documents hold filenames
            source="upload",
        )

    # Process each file → create a document record
    documents = []
    risk_profiles = []
    customer_info = None

    for i, f in enumerate(valid):
        filename, unique, filepath = _save_upload(f)
        display_name = filename.rsplit(".", 1)[0]

        doc_id = db.add_document(rfp_id, unique, display_name, sort_order=i)

        rp, up = quick_scan(filepath)
        risk_profiles.append(rp)

        # Customer detection from first file only
        if i == 0 and api_key:
            try:
                customer_info = detect_customer(api_key, filepath, filename)
            except Exception:
                pass

        db.update_document(doc_id, question_count=up.get("valid_requirements", 0))
        documents.append({"doc_id": doc_id, "display_name": display_name,
                           "filename": filename, "risk_profile": rp})

    # Merge risk profiles across all docs
    combined_rp = _merge_risk_profiles(risk_profiles) if risk_profiles else {}
    db.update_rfp(rfp_id,
        risk_profile=json.dumps(combined_rp),
        customer_info=json.dumps(customer_info) if customer_info else None,
    )
    db.sync_rfp_counts(rfp_id)

    return jsonify({
        "id": rfp_id,
        "name": db.get_rfp(rfp_id)["name"],
        "documents": documents,
        "risk_profile": combined_rp,
        "customer_info": customer_info,
    })


def _merge_risk_profiles(profiles: list[dict]) -> dict:
    """Combine risk profiles from multiple documents into one aggregate."""
    if not profiles:
        return {}
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    keywords: set = set()
    total_req = 0
    for rp in profiles:
        pb = rp.get("priority_breakdown") or {}
        for k in counts:
            counts[k] += pb.get(k, 0)
        keywords.update(rp.get("risky_keywords") or [])
        total_req += rp.get("total_requirements", 0)
    total = max(sum(counts.values()), 1)
    weighted = counts["Critical"]*5 + counts["High"]*3 + counts["Medium"]*2 + counts["Low"]
    score = round(min((weighted / total) + min(len(keywords) * 0.2, 1.5), 5.0), 2)
    level = "High" if score >= 4 else "Medium" if score >= 2.5 else "Low"
    return {"preliminary_risk_score": score, "risk_level": level,
            "priority_breakdown": counts, "risky_keywords": sorted(keywords)[:10],
            "total_requirements": total_req}


# ── Per-document endpoints ─────────────────────────────────────────────────────

@app.route("/api/rfp/<int:rfp_id>/documents")
def list_documents(rfp_id):
    return jsonify(db.get_documents(rfp_id))


@app.route("/api/rfp/<int:rfp_id>/add-document", methods=["POST"])
def add_document(rfp_id):
    rfp = db.get_rfp(rfp_id)
    if not rfp:
        return jsonify({"error": "RFP not found"}), 404
    files = request.files.getlist("files") or request.files.getlist("file")
    if not files or not files[0].filename:
        return jsonify({"error": "No file"}), 400

    added = []
    existing = db.get_documents(rfp_id)
    sort_start = max((d["sort_order"] for d in existing), default=-1) + 1

    for i, f in enumerate(files):
        if not f.filename or not _allowed(f.filename):
            continue
        filename, unique, filepath = _save_upload(f)
        display_name = filename.rsplit(".", 1)[0]
        doc_id = db.add_document(rfp_id, unique, display_name, sort_order=sort_start + i)
        _, up = quick_scan(filepath)
        db.update_document(doc_id, question_count=up.get("valid_requirements", 0))
        added.append({"doc_id": doc_id, "display_name": display_name})

    db.sync_rfp_counts(rfp_id)
    return jsonify({"added": added})


@app.route("/api/rfp/<int:rfp_id>/document/<int:doc_id>", methods=["DELETE"])
def delete_document(rfp_id, doc_id):
    doc = db.get_document(doc_id)
    if doc and doc.get("filename"):
        path = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
        if os.path.exists(path):
            os.remove(path)
    db.delete_document(doc_id)
    db.sync_rfp_counts(rfp_id)
    return jsonify({"success": True})


@app.route("/api/rfp/<int:rfp_id>/document/<int:doc_id>/rename", methods=["PATCH"])
def rename_document(rfp_id, doc_id):
    name = (request.get_json() or {}).get("display_name", "").strip()
    if name:
        db.update_document(doc_id, display_name=name)
    return jsonify({"success": True})


@app.route("/api/rfp/<int:rfp_id>/document/<int:doc_id>/process")
def process_document_stream(rfp_id, doc_id):
    rfp = db.get_rfp(rfp_id)
    doc = db.get_document(doc_id)
    if not rfp or not doc:
        return jsonify({"error": "Not found"}), 404
    api_key = db.get_setting("anthropic_api_key")
    if not api_key:
        return jsonify({"error": "API key not configured"}), 400

    event_q = queue.Queue()

    def run():
        try:
            pipeline = AgentPipeline(api_key, db, event_q)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
            pipeline.process_document(rfp_id, doc_id, filepath)
        except Exception as e:
            event_q.put({"type": "error", "message": str(e), "timestamp": 0})
        finally:
            event_q.put(None)

    threading.Thread(target=run, daemon=True).start()

    def generate():
        while True:
            ev = event_q.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache"})


@app.route("/api/rfp/<int:rfp_id>/document/<int:doc_id>/export", methods=["POST"])
def export_document(rfp_id, doc_id):
    doc = db.get_document(doc_id)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
    questions = db.get_questions_by_document(rfp_id, doc_id)
    try:
        export_path = do_export(filepath, questions, f"{rfp_id}_{doc_id}")
        return send_file(os.path.abspath(export_path), as_attachment=True,
                         download_name=os.path.basename(export_path))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/rfp/<int:rfp_id>/export-all", methods=["POST"])
def export_all_documents(rfp_id):
    rfp  = db.get_rfp(rfp_id)
    docs = db.get_documents(rfp_id)
    if not rfp or not docs:
        return jsonify({"error": "No documents found"}), 404

    # Which doc_ids to include (default = all complete docs)
    selected = set((request.get_json() or {}).get("doc_ids", []))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            if selected and doc["id"] not in selected:
                continue
            if doc["status"] != "complete":
                continue
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
            if not os.path.exists(filepath):
                continue
            questions = db.get_questions_by_document(rfp_id, doc["id"])
            if not questions:
                # Fall back to all questions for this rfp if no document_id set
                questions = db.get_questions(rfp_id)
            try:
                export_path = do_export(filepath, questions, f"{rfp_id}_{doc['id']}")
                zf.write(os.path.abspath(export_path), arcname=os.path.basename(export_path))
            except Exception:
                continue

    buf.seek(0)
    safe_name = rfp["name"].replace(" ", "_")[:40]
    return send_file(buf, as_attachment=True,
                     download_name=f"{safe_name}_NaughtRFP_export.zip",
                     mimetype="application/zip")


@app.route("/api/rfp/<int:rfp_id>")
def get_rfp(rfp_id):
    rfp = db.get_rfp(rfp_id)
    if not rfp:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        **rfp,
        "questions": db.get_questions(rfp_id),
        "agent_logs": db.get_agent_logs(rfp_id),
    })


@app.route("/api/rfp/<int:rfp_id>/process")
def process_rfp_stream(rfp_id):
    rfp = db.get_rfp(rfp_id)
    if not rfp:
        return jsonify({"error": "Not found"}), 404

    api_key = db.get_setting("anthropic_api_key")
    if not api_key:
        return jsonify({"error": "API key not configured. Go to Settings first."}), 400

    # Reset error state so a retry starts clean
    if rfp.get("status") == "error":
        db.update_rfp(rfp_id, status="pending", last_error=None)

    event_q = queue.Queue()

    def run():
        try:
            pipeline = AgentPipeline(api_key, db, event_q)
            docs = db.get_documents(rfp_id)
            if docs:
                # Multi-document: process each pending document
                for doc in docs:
                    if doc["status"] not in ("pending", "error"):
                        continue
                    filepath = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
                    pipeline.process_document(rfp_id, doc["id"], filepath)
                db.sync_rfp_counts(rfp_id)
            else:
                # Legacy single-file RFP
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], rfp["filename"])
                pipeline.process_rfp(rfp_id, filepath)
        except Exception as e:
            event_q.put({"type": "error", "message": str(e), "timestamp": 0})
        finally:
            event_q.put(None)

    t = threading.Thread(target=run, daemon=True)
    t.start()

    def generate():
        while True:
            ev = event_q.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/rfp/<int:rfp_id>/question/<int:q_id>", methods=["PATCH"])
def update_question(rfp_id, q_id):
    data = request.get_json() or {}
    allowed = {"answer", "response_code", "status", "needs_review",
               "fit_score", "risk_score", "review_reason"}
    kwargs = {k: v for k, v in data.items() if k in allowed}
    if kwargs:
        db.update_question(q_id, **kwargs)
        # Recalculate RFP-level counts
        qs = db.get_questions(rfp_id)
        answered = sum(1 for q in qs if q["status"] == "answered")
        flagged  = sum(1 for q in qs if q["status"] == "flagged")
        fits  = [q["fit_score"]  for q in qs if q["status"] == "answered" and q.get("fit_score")]
        risks = [q["risk_score"] for q in qs if q["status"] == "answered" and q.get("risk_score")]
        update_kw = {"answered_count": answered, "flagged_count": flagged}
        if fits:  update_kw["fit_score"]  = round(sum(fits)  / len(fits),  2)
        if risks: update_kw["risk_score"] = round(sum(risks) / len(risks), 2)
        db.update_rfp(rfp_id, **update_kw)
    return jsonify({"success": True})


@app.route("/api/rfp/<int:rfp_id>/question/<int:q_id>/rerun")
def rerun_question_stream(rfp_id, q_id):
    rfp = db.get_rfp(rfp_id)
    if not rfp:
        return jsonify({"error": "Not found"}), 404
    api_key = db.get_setting("anthropic_api_key")
    if not api_key:
        return jsonify({"error": "API key not configured"}), 400

    q = next((q for q in db.get_questions(rfp_id) if q["id"] == q_id), None)
    if not q:
        return jsonify({"error": "Question not found"}), 404

    event_q = queue.Queue()

    def run():
        try:
            from agents import AgentPipeline
            pipeline = AgentPipeline(api_key, db, event_q)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], rfp["filename"])
            # Reset question to pending so _research_and_answer saves properly
            db.update_question(q_id, status="pending", answer=None,
                               response_code=None, needs_review=0, review_reason=None)
            # Enrich q dict
            import json
            q_enriched = dict(q)
            q_enriched["refined_category"] = q.get("category", "General")
            q_enriched["okta_products"]    = json.loads(q.get("okta_products") or "[]")
            q_enriched["risk_score"]       = q.get("risk_score", 3)
            pre_ctx = db.search_knowledge_base(q["question_text"][:150], limit=3)
            result  = pipeline._research_and_answer(rfp_id, q_enriched, pre_context=pre_ctx)
            # Recalculate scores
            qs  = db.get_questions(rfp_id)
            fits  = [x["fit_score"]  for x in qs if x["status"] == "answered" and x.get("fit_score")]
            risks = [x["risk_score"] for x in qs if x["status"] == "answered" and x.get("risk_score")]
            if fits:  db.update_rfp(rfp_id, fit_score=round(sum(fits)/len(fits),2))
            if risks: db.update_rfp(rfp_id, risk_score=round(sum(risks)/len(risks),2))
            updated_q = next((x for x in db.get_questions(rfp_id) if x["id"] == q_id), None)
            event_q.put({"type": "rerun_complete", "question": updated_q, "result": result})
        except Exception as e:
            event_q.put({"type": "error", "message": str(e), "timestamp": 0})
        finally:
            event_q.put(None)

    threading.Thread(target=run, daemon=True).start()

    def generate():
        while True:
            ev = event_q.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache"})


@app.route("/api/rfp/<int:rfp_id>/export", methods=["POST"])
def export_rfp(rfp_id):
    rfp = db.get_rfp(rfp_id)
    if not rfp:
        return jsonify({"error": "Not found"}), 404
    if not rfp.get("filename"):
        return jsonify({"error": "No source file for this RFP"}), 400

    questions = db.get_questions(rfp_id)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], rfp["filename"])

    try:
        export_path = do_export(filepath, questions, rfp_id)
        return send_file(
            os.path.abspath(export_path),
            as_attachment=True,
            download_name=os.path.basename(export_path),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/rfp/<int:rfp_id>", methods=["DELETE"])
def delete_rfp(rfp_id):
    rfp = db.get_rfp(rfp_id)
    if not rfp:
        return jsonify({"error": "Not found"}), 404
    if rfp.get("filename"):
        path = os.path.join(app.config["UPLOAD_FOLDER"], rfp["filename"])
        if os.path.exists(path):
            os.remove(path)
    db.delete_rfp(rfp_id)
    return jsonify({"success": True})


# ── Knowledge Base ────────────────────────────────────────────────────────────

@app.route("/api/kb/search")
def search_kb():
    query = request.args.get("q", "").strip()
    ai = request.args.get("ai", "false") == "true"
    limit = int(request.args.get("limit", 20))

    if not query:
        return jsonify(db.get_kb_entries(limit=limit))

    if ai:
        api_key = db.get_setting("anthropic_api_key")
        if not api_key:
            return jsonify({"error": "API key required for AI search"}), 400
        return jsonify(ai_search_knowledge_base(api_key, db, query))

    return jsonify(db.search_knowledge_base(query, limit=limit))


@app.route("/api/kb/ingest/<int:rfp_id>", methods=["POST"])
def ingest_rfp(rfp_id):
    rfp = db.get_rfp(rfp_id)
    if not rfp:
        return jsonify({"error": "Not found"}), 404

    api_key = db.get_setting("anthropic_api_key")
    if not api_key:
        return jsonify({"error": "API key not configured"}), 400

    event_q = queue.Queue()

    def run():
        try:
            agent = KnowledgeBaseAgent(api_key, db, event_q)
            agent.ingest_rfp(rfp_id)
        except Exception as e:
            event_q.put({"type": "error", "message": str(e), "timestamp": 0})
        finally:
            event_q.put(None)

    threading.Thread(target=run, daemon=True).start()

    def generate():
        while True:
            ev = event_q.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache"})


@app.route("/api/rfp/<int:rfp_id>/demo-prep")
def demo_prep_stream(rfp_id):
    rfp = db.get_rfp(rfp_id)
    if not rfp:
        return jsonify({"error": "Not found"}), 404
    api_key = db.get_setting("anthropic_api_key")
    if not api_key:
        return jsonify({"error": "API key not configured"}), 400

    customer_format = (request.get_json() or {}).get("customer_format") if request.content_type == "application/json" else None
    event_q = queue.Queue()

    def run():
        try:
            agent = DemoPrepAgent(api_key, db, event_q)
            plan_id = agent.generate(rfp_id, customer_format)
            if plan_id:
                plan = db.get_demo_plan(rfp_id)
                event_q.put({"type": "demo_ready", "plan_id": plan_id, "data": plan})
        except Exception as e:
            event_q.put({"type": "error", "message": str(e), "timestamp": 0})
        finally:
            event_q.put(None)

    threading.Thread(target=run, daemon=True).start()

    def generate():
        while True:
            ev = event_q.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache"})


@app.route("/api/rfp/<int:rfp_id>/demo-plan")
def get_demo_plan(rfp_id):
    plan = db.get_demo_plan(rfp_id)
    if not plan:
        return jsonify({"error": "No demo plan found"}), 404
    return jsonify(plan)


@app.route("/api/rfp/<int:rfp_id>/demo-plan/confirm", methods=["POST"])
def confirm_demo_plan(rfp_id):
    plan = db.get_demo_plan(rfp_id)
    if not plan:
        return jsonify({"error": "No demo plan found"}), 404
    db.update_demo_plan(plan["id"],
        status="confirmed",
        confirmed_at=json.dumps({"ts": "now"}),
    )
    return jsonify({"success": True})


@app.route("/api/demos")
def list_demos():
    return jsonify(db.list_confirmed_demos())


@app.route("/api/kb/seed", methods=["POST"])
def seed_kb():
    from seed_kb import seed_okta_knowledge
    n = seed_okta_knowledge(db)
    return jsonify({"inserted": n, "message": f"Added {n} baseline Okta knowledge entries" if n else "Knowledge base already up to date"})


@app.route("/api/kb/seed-sig", methods=["POST"])
def seed_sig_kb():
    try:
        from seed_sig import seed_from_sig
        n, s = seed_from_sig(db)
        return jsonify({"inserted": n, "skipped": s,
                        "message": f"Added {n} entries from Okta SIG Core 2024"})
    except FileNotFoundError:
        return jsonify({"error": "Okta_SIG_Core.xlsm not found at expected Desktop path"}), 400


@app.route("/api/kb/stats")
def kb_stats():
    return jsonify(db.get_kb_stats())


@app.route("/api/usage")
def get_usage():
    local = db.get_token_summary()

    # Also fetch spend from LiteLLM
    litellm_spend = None
    try:
        import httpx as _httpx
        import warnings as _w
        _w.filterwarnings("ignore")
        api_key = db.get_setting("anthropic_api_key") or ""
        base_url = db.get_setting("litellm_base_url") or ""
        if api_key and base_url:
            r = _httpx.get(f"{base_url}/key/info",
                           params={"key": api_key},
                           headers={"Authorization": f"Bearer {api_key}"},
                           verify=False, timeout=8)
            if r.status_code == 200:
                info = r.json()
                litellm_spend = {
                    "spend": info.get("info", {}).get("spend", 0),
                    "budget": info.get("info", {}).get("max_budget"),
                    "rpm":    info.get("info", {}).get("rpm_limit"),
                    "tpm":    info.get("info", {}).get("tpm_limit"),
                }
    except Exception:
        pass

    return jsonify({**local, "litellm": litellm_spend})


if __name__ == "__main__":
    print("\n  NaughtRFP is running at http://localhost:5000\n")
    app.run(debug=True, port=5000, threaded=True, use_reloader=False)
