import csv
import json
import os
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
from copy import copy


def export_rfp(filepath, questions, rfp_id):
    ext = filepath.rsplit(".", 1)[-1].lower()
    os.makedirs("exports", exist_ok=True)

    if ext == "csv":
        return _export_csv(filepath, questions, rfp_id)
    elif ext in ("xlsx", "xls"):
        return _export_xlsx(filepath, questions, rfp_id)
    raise ValueError(f"Unsupported file type: {ext}")


def _build_lookup(questions):
    """Map first 120 chars of question text (lowercased) to question dict."""
    lookup = {}
    for q in questions:
        if q.get("status") == "answered" and q.get("answer"):
            key = str(q["question_text"])[:120].lower().strip()
            lookup[key] = q
    return lookup


def _export_xlsx(filepath, questions, rfp_id):
    wb = openpyxl.load_workbook(filepath)
    ws = wb.active

    # Locate header row (first row with content)
    header_row_idx = None
    headers = []
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if any(c for c in row if c is not None):
            header_row_idx = i
            headers = [str(c).strip().lower() if c is not None else "" for c in row]
            break

    if header_row_idx is None:
        raise ValueError("Could not find header row")

    # Detect relevant column indices (1-based)
    req_col = resp_col = comment_col = None
    for j, h in enumerate(headers):
        if any(k in h for k in ("requirement", "criteria", "question", "description")):
            if req_col is None:
                req_col = j + 1
        if any(k in h for k in ("vendor response", "response required", "vendor resp")):
            resp_col = j + 1
        if any(k in h for k in ("comment", "assumption", "notes", "vendor comment")):
            comment_col = j + 1

    # Fallback column positions
    max_col = ws.max_column
    if resp_col is None:
        resp_col = max_col - 1 if max_col > 2 else max_col
    if comment_col is None:
        comment_col = max_col

    lookup = _build_lookup(questions)

    green_fill = PatternFill(start_color="00BF6F", end_color="00BF6F", fill_type="solid")
    amber_fill = PatternFill(start_color="F5A623", end_color="F5A623", fill_type="solid")

    filled = 0
    for row_num in range(header_row_idx + 1, ws.max_row + 1):
        if req_col is None:
            break
        cell_val = ws.cell(row=row_num, column=req_col).value
        if not cell_val:
            continue
        key = str(cell_val)[:120].lower().strip()
        if key not in lookup:
            continue

        q = lookup[key]
        rc = q.get("response_code", "")
        answer = q.get("answer", "")
        # Strip internal review notes from export
        answer = answer.split("\n\n⚠")[0].strip()

        resp_cell = ws.cell(row=row_num, column=resp_col)
        resp_cell.value = rc
        resp_cell.font = Font(bold=True)
        resp_cell.alignment = Alignment(horizontal="center")
        if rc == "F":
            resp_cell.fill = green_fill
        elif rc in ("P", "C"):
            resp_cell.fill = amber_fill

        comment_cell = ws.cell(row=row_num, column=comment_col)
        comment_cell.value = answer
        comment_cell.alignment = Alignment(wrap_text=True, vertical="top")
        filled += 1

    export_path = os.path.join("exports", f"rfp_{rfp_id}_naughtrfp_export.xlsx")
    wb.save(export_path)
    return export_path


def _export_csv(filepath, questions, rfp_id):
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    if "Vendor Response" not in fieldnames:
        fieldnames += ["Vendor Response", "Vendor Comments"]

    lookup = _build_lookup(questions)

    for row in rows:
        for val in row.values():
            key = str(val)[:120].lower().strip() if val else ""
            if key in lookup:
                q = lookup[key]
                answer = q.get("answer", "")
                answer = answer.split("\n\n⚠")[0].strip()
                row["Vendor Response"] = q.get("response_code", "")
                row["Vendor Comments"] = answer
                break

    export_path = os.path.join("exports", f"rfp_{rfp_id}_naughtrfp_export.csv")
    with open(export_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return export_path
