"""
Build/update JobHunt.xlsx — ACCUMULATE model.

Every scan MERGES into the existing workbook; jobs are never lost.
  - A job seen for the first time in the latest scan  -> Status "New"
  - A previously-seen job the user hasn't triaged      -> Status "Old"
  - A job the user set to Interested/Applied/Not interested is never overwritten
  - The Applied sheet is derived from Jobs rows whose Status == "Applied"

Sheets: Jobs, Applied, Config.
"""
import datetime as dt
import hashlib
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter

import geo

TODAY = dt.date.today().isoformat()

JOBS_HEADERS = ["Score", "Status", "Month", "Date Found", "Last Seen", "Title",
                "Company", "Location", "Country", "State", "Remote", "Salary",
                "Visa Sponsorship", "OPT-viable", "Visa Notes", "Fit Reasons",
                "Source", "Link", "Cover Letter", "Doc #", "Notes", "Job ID"]

APPLIED_HEADERS = ["Date Applied", "Month", "Company", "Title", "Location", "State",
                   "Link", "Decision", "Outcome", "Outcome Date", "Visa Sponsorship",
                   "Doc #", "Notes", "Next Step", "Job ID"]

STATUS_OPTIONS = "New,Suggested,Interested,Applied,Not interested,Old"
OUTCOME_OPTIONS = "Applied,Rejected,Interview,Offer,Ghosted,Withdrawn"
# Statuses the scan never auto-overwrites (user picks + AI suggestions).
TRIAGED = {"Suggested", "Interested", "Applied", "Not interested"}

HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(color="FFFFFF", bold=True, size=11)
WRAP = Alignment(vertical="center", wrap_text=False)
WRAP_ON = Alignment(vertical="top", wrap_text=True)
LINKF = Font(color="0563C1", underline="single")
ROW_H = 15
THIN = Border(bottom=Side(style="thin", color="D9D9D9"))


def _style_header(ws, headers):
    for c, h in enumerate(headers, 1):
        cell = ws.cell(1, c, h)
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"


def _widths(ws, widths):
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


def _coerce_date(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return v.strftime("%Y-%m-%d")
    return str(v)[:10] if v else ""


# --------------------------------------------------------------------------- #
# read existing state
# --------------------------------------------------------------------------- #
def _read_jobs(path):
    rows = {}
    try:
        wb = openpyxl.load_workbook(path)
    except FileNotFoundError:
        return rows
    if "Jobs" not in wb.sheetnames:
        return rows
    ws = wb["Jobs"]
    hdr = [c.value for c in ws[1]]
    idx = {h: i for i, h in enumerate(hdr)}
    if "Job ID" not in idx:
        return rows
    for r in range(2, ws.max_row + 1):
        jid = ws.cell(r, idx["Job ID"] + 1).value
        if not jid:
            continue
        d = {h: ws.cell(r, idx[h] + 1).value for h in hdr}
        lk = ws.cell(r, idx["Link"] + 1) if "Link" in idx else None
        cl = ws.cell(r, idx["Cover Letter"] + 1) if "Cover Letter" in idx else None
        d["_link_url"] = lk.hyperlink.target if (lk and lk.hyperlink) else ""
        d["_cl_url"] = cl.hyperlink.target if (cl and cl.hyperlink) else ""
        d["Date Found"] = _coerce_date(d.get("Date Found"))
        d["Last Seen"] = _coerce_date(d.get("Last Seen"))
        rows[jid] = d
    return rows


def _read_applied_user(path):
    """Read the whole Applied sheet, keyed by Job ID. Rows the user typed by hand
    (no Job ID) get a stable synthetic id so they survive rebuilds."""
    ua = {}
    try:
        wb = openpyxl.load_workbook(path)
    except FileNotFoundError:
        return ua
    if "Applied" not in wb.sheetnames:
        return ua
    ws = wb["Applied"]
    hdr = [c.value for c in ws[1]]
    idx = {h: i for i, h in enumerate(hdr)}
    for r in range(2, ws.max_row + 1):
        rec = {h: ws.cell(r, idx[h] + 1).value for h in hdr if h != "Job ID"}
        if "Link" in idx:
            lc = ws.cell(r, idx["Link"] + 1)
            rec["url"] = lc.hyperlink.target if lc.hyperlink else ""
            rec["link_text"] = lc.value
        rec["Date Applied"] = _coerce_date(rec.get("Date Applied"))
        rec["Outcome Date"] = _coerce_date(rec.get("Outcome Date"))
        jid = ws.cell(r, idx["Job ID"] + 1).value if "Job ID" in idx else None
        # ignore blank rows
        if not jid and not (rec.get("Company") or rec.get("Title")):
            continue
        if not jid:
            seed = f"{rec.get('Company','')}|{rec.get('Title','')}|{rec.get('Date Applied','')}"
            jid = "manual-" + hashlib.sha1(seed.encode()).hexdigest()[:8]
            rec["_manual"] = True
        rec["Job ID"] = jid
        ua[jid] = rec
    return ua


def _row_from_scan(j):
    code = geo.country_from_loc(j.get("location", "")) or j.get("country", "")
    return {
        "Score": j["score"], "Status": "New", "Date Found": TODAY, "Last Seen": TODAY,
        "Title": j["title"], "Company": j["company"], "Location": j["location"],
        "Country": geo.label(code), "State": geo.us_state(j["location"]) if code == "us" else "",
        "Remote": "Yes" if j["remote"] else "", "Salary": j["salary"],
        "Visa Sponsorship": j["visa"], "OPT-viable": j["opt_viable"],
        "Visa Notes": j["visa_note"], "Fit Reasons": j["reasons"], "Source": j["source"],
        "Link": "Open posting", "Cover Letter": "", "Doc #": "", "Notes": "",
        "Job ID": j["id"], "_link_url": j["url"], "_cl_url": "",
    }


# --------------------------------------------------------------------------- #
def build(path, scanned_jobs, cfg, is_scan=True, scan_date=None):
    scan_date = scan_date or TODAY
    existing = _read_jobs(path)
    applied_user = _read_applied_user(path)

    # merge in this scan's jobs
    for j in scanned_jobs:
        if j["id"] in existing:
            row = existing[j["id"]]
            row["Last Seen"] = scan_date
            row["Score"] = j["score"]
            row["Visa Sponsorship"] = j["visa"]
            row["OPT-viable"] = j["opt_viable"]
            row["Visa Notes"] = j["visa_note"]
            row["Fit Reasons"] = j["reasons"]
            if not row.get("Salary"):
                row["Salary"] = j["salary"]
            if not row.get("_link_url"):
                row["_link_url"] = j["url"]
        else:
            existing[j["id"]] = _row_from_scan(j)

    # normalize Country/State for every row (fixes old mislabels + adds State),
    # and drop foreign noise: rows in a clearly non-target country that the user
    # hasn't triaged (leftovers from before the country fix). Target-country and
    # unknown-location rows are always kept.
    target = set(cfg["locations"]["countries"])
    for jid in list(existing.keys()):
        row = existing[jid]
        code = geo.country_from_loc(row.get("Location", ""))
        if code:
            row["Country"] = geo.label(code)
            row["State"] = geo.us_state(row.get("Location", "")) if code == "us" else ""
        elif "State" not in row:
            row["State"] = row.get("State", "")
        if code and code not in target and (row.get("Status") or "") not in TRIAGED:
            del existing[jid]
            continue
        row["Month"] = (row.get("Date Found") or "")[:7]   # YYYY-MM

    # New/Old only on a real scan, and only for untriaged rows
    if is_scan:
        for row in existing.values():
            if (row.get("Status") or "") not in TRIAGED:
                row["Status"] = "New" if row.get("Date Found") == scan_date else "Old"

    # ---- write Jobs --------------------------------------------------------
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Jobs"
    _style_header(ws, JOBS_HEADERS)

    def sortkey(row):
        is_new = 1 if row.get("Status") == "New" else 0
        return (is_new, row.get("Score") or 0, row.get("Date Found") or "")

    allrows = sorted(existing.values(), key=sortkey, reverse=True)
    r = 2
    for row in allrows:
        for c, h in enumerate(JOBS_HEADERS, 1):
            cell = ws.cell(r, c, row.get(h, ""))
            cell.alignment = WRAP
            cell.border = THIN
        ws.row_dimensions[r].height = ROW_H
        lc = ws.cell(r, JOBS_HEADERS.index("Link") + 1)
        if row.get("_link_url"):
            lc.hyperlink = row["_link_url"]
            lc.font = LINKF
        if row.get("_cl_url"):
            cc = ws.cell(r, JOBS_HEADERS.index("Cover Letter") + 1)
            cc.hyperlink = row["_cl_url"]
            cc.font = LINKF
        r += 1

    dv = DataValidation(type="list", formula1=f'"{STATUS_OPTIONS}"', allow_blank=True)
    ws.add_data_validation(dv)
    col = get_column_letter(JOBS_HEADERS.index("Status") + 1)
    dv.add(f"{col}2:{col}{max(r, 3000)}")

    _widths(ws, {"A": 7, "B": 14, "C": 9, "D": 12, "E": 12, "F": 44, "G": 22,
                 "H": 26, "I": 10, "J": 14, "K": 8, "L": 16, "M": 15, "N": 11,
                 "O": 34, "P": 40, "Q": 11, "R": 13, "S": 16, "T": 8, "U": 30,
                 "V": 26})
    ws.column_dimensions["V"].hidden = True   # Job ID

    # ---- Applied (derived from Jobs Status == Applied) ---------------------
    wa = wb.create_sheet("Applied")
    _style_header(wa, APPLIED_HEADERS)
    ar = 2

    def emit(d):
        nonlocal ar
        da = d.get("Date Applied") or ""
        month = str(da)[:7] if da else ""
        link_text = "Open posting" if d.get("url") else (d.get("link_text") or "")
        vals = [da, month, d.get("Company", ""), d.get("Title", ""),
                d.get("Location", ""), d.get("State", ""), link_text,
                d.get("Decision") or "", d.get("Outcome") or "Applied",
                d.get("Outcome Date") or "", d.get("Visa Sponsorship", ""),
                d.get("Doc #", ""), d.get("Notes") or "", d.get("Next Step") or "",
                d.get("Job ID", "")]
        for c, v in enumerate(vals, 1):
            cell = wa.cell(ar, c, v)
            cell.alignment = WRAP
            cell.border = THIN
        wa.row_dimensions[ar].height = ROW_H
        if d.get("url"):
            lc = wa.cell(ar, APPLIED_HEADERS.index("Link") + 1)
            lc.hyperlink = d["url"]
            lc.font = LINKF
        ar += 1

    applied_ids = set()
    # 1) jobs you marked Applied in the Jobs sheet
    for row in allrows:
        if row.get("Status") == "Applied":
            au = applied_user.get(row["Job ID"], {})
            emit({
                "Date Applied": au.get("Date Applied") or TODAY,
                "Company": row.get("Company", ""), "Title": row.get("Title", ""),
                "Location": row.get("Location", ""), "State": row.get("State", ""),
                "url": row.get("_link_url", ""),
                "Decision": au.get("Decision") or "",
                "Outcome": au.get("Outcome") or "Applied",
                "Outcome Date": au.get("Outcome Date") or "",
                "Visa Sponsorship": row.get("Visa Sponsorship", ""),
                "Doc #": row.get("Doc #", ""),
                "Notes": au.get("Notes") or "", "Next Step": au.get("Next Step") or "",
                "Job ID": row["Job ID"],
            })
            applied_ids.add(row["Job ID"])
    # 2) rows you typed by hand (or that left the Jobs feed) — preserved as-is
    for jid, rec in applied_user.items():
        if jid not in applied_ids:
            emit(rec)

    dvo = DataValidation(type="list", formula1=f'"{OUTCOME_OPTIONS}"', allow_blank=True)
    wa.add_data_validation(dvo)
    oc = get_column_letter(APPLIED_HEADERS.index("Outcome") + 1)
    dvo.add(f"{oc}2:{oc}{max(ar, 2000)}")

    # Decision dropdown (Yes / No / blank-to-clear). The trailing comma adds an
    # empty option so a mis-click can be reset to blank from the dropdown itself.
    dvd = DataValidation(type="list", formula1='"Yes,No,"', allow_blank=True)
    wa.add_data_validation(dvd)
    dcol = get_column_letter(APPLIED_HEADERS.index("Decision") + 1)   # H
    last = max(ar, 2000)
    dvd.add(f"{dcol}2:{dcol}{last}")

    # Conditional formatting: whole row green when Decision=Yes, red when No.
    last_col = get_column_letter(len(APPLIED_HEADERS))
    rng = f"A2:{last_col}{last}"
    green = PatternFill("solid", fgColor="C6EFCE")
    green_font = Font(color="006100")
    red = PatternFill("solid", fgColor="FFC7CE")
    red_font = Font(color="9C0006")
    wa.conditional_formatting.add(
        rng, FormulaRule(formula=[f'${dcol}2="Yes"'], fill=green, font=green_font))
    wa.conditional_formatting.add(
        rng, FormulaRule(formula=[f'${dcol}2="No"'], fill=red, font=red_font))

    _widths(wa, {"A": 13, "B": 9, "C": 20, "D": 40, "E": 22, "F": 14, "G": 13,
                 "H": 10, "I": 13, "J": 13, "K": 15, "L": 8, "M": 30, "N": 26,
                 "O": 26})
    wa.column_dimensions["O"].hidden = True

    # ---- Config ------------------------------------------------------------
    wc = wb.create_sheet("Config")
    wc["A1"] = "JobHunt — current settings (edit config/config.yaml to change)"
    wc["A1"].font = Font(bold=True, size=12)
    cw = cfg["locations"].get("country_weights", {})
    rows_cfg = [
        ("Name", cfg["profile"]["name"]),
        ("Graduation", cfg["profile"]["graduation"]),
        ("Work auth", cfg["profile"]["work_auth"]["status"]),
        ("STEM OPT years", cfg["profile"]["work_auth"].get("stem_opt_years", "")),
        ("Max jobs kept", cfg.get("output", {}).get("max_jobs", "")),
        ("Country weights", ", ".join(f"{k.upper()} {v}" for k, v in cw.items())),
        ("Gov position (self/relative 5y)", cfg["standard_answers"]["government_position_self_or_relative_past_5y"]),
        ("Requires sponsorship now", cfg["standard_answers"]["require_sponsorship_now"]),
    ]
    for i, (k, v) in enumerate(rows_cfg, 3):
        wc.cell(i, 1, k).font = Font(bold=True)
        wc.cell(i, 2, str(v)).alignment = WRAP_ON
    _widths(wc, {"A": 32, "B": 90})

    wb.save(path)
    new_ct = sum(1 for x in allrows if x.get("Status") == "New")
    return {"total": len(allrows), "new": new_ct, "applied": ar - 2, "path": path}
