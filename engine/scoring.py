"""
Filtering, scoring, and visa/OPT annotation.
Phase 1 = deterministic keyword logic (no AI). The AI fit-scoring layer
plugs in here in Phase 2.
"""
import re
import datetime as dt


def days_old(job):
    """Days since posting; large number if unknown."""
    d = (job.get("date_posted") or "")[:10]
    try:
        posted = dt.date.fromisoformat(d)
        return (dt.date.today() - posted).days
    except Exception:
        return 999


# --------------------------------------------------------------------------- #
# Hard filter: exclude by title (too senior / wrong field)
# --------------------------------------------------------------------------- #
def is_excluded(job, cfg):
    title = job["title"].lower()
    for bad in cfg["search"]["titles_exclude"]:
        if bad.lower() in title:
            return True
    return False


def has_finance_signal(job, cfg):
    """True only if the role actually matches a target title or keyword.
    Prevents irrelevant local jobs from surviving on location points alone."""
    text = (job["title"] + " " + job["description"]).lower()
    title = job["title"].lower()
    if any(t.lower() in title for t in cfg["search"]["titles_positive"]):
        return True
    if any(k.lower() in text for k in cfg["search"]["keywords_target"]):
        return True
    return False


def passes_location(job, cfg):
    countries = cfg["locations"]["countries"]
    # keep if country matches, is unknown (don't drop), or remote allowed
    if job["country"] and job["country"] not in countries:
        return False
    return True


# --------------------------------------------------------------------------- #
# Score 0–100
# --------------------------------------------------------------------------- #
def score(job, cfg):
    s = cfg["scoring"]
    text = (job["title"] + " " + job["description"]).lower()
    title = job["title"].lower()
    reasons = []
    total = 0

    # strong title hit
    for t in cfg["search"]["titles_positive"]:
        if t.lower() in title:
            total += s["strong_title_hit"]
            reasons.append(f"title: '{t}'")
            break

    # target keywords (capped)
    kw_pts = 0
    hits = []
    for k in cfg["search"]["keywords_target"]:
        if k.lower() in text:
            kw_pts += s["target_keyword_each"]
            hits.append(k)
    kw_pts = min(kw_pts, s["target_keyword_cap"])
    if kw_pts:
        total += kw_pts
        reasons.append("keywords: " + ", ".join(hits[:5]))

    # seniority match
    for lvl in cfg["search"]["seniority_target"]:
        if lvl.lower() in title:
            total += s["seniority_match"]
            reasons.append(f"level: {lvl}")
            break

    # location
    if job["country"] == "us":
        total += s["us_location"]
        reasons.append("US")
    elif job["country"] in cfg["locations"]["countries"]:
        total += s["other_target_country"]
        reasons.append(job["country"].upper())

    if not job["remote"]:
        total += s["in_person_bonus"]
        reasons.append("in-person")

    for city in cfg["locations"].get("preferred_us", []):
        if city.lower() in job["location"].lower():
            total += s["preferred_city_bonus"]
            reasons.append(f"pref: {city}")
            break

    # recency
    d = days_old(job)
    if d <= 7:
        total += s.get("recency_7d", 0)
        reasons.append("new (<7d)")
    elif d <= 30:
        total += s.get("recency_30d", 0)
        reasons.append("recent (<30d)")

    return min(total, 100), "; ".join(reasons)


# --------------------------------------------------------------------------- #
# Visa / OPT annotation
# --------------------------------------------------------------------------- #
_NO_SPONSOR = [
    "will not sponsor", "unable to sponsor", "not able to sponsor",
    "do not offer sponsorship", "does not offer sponsorship",
    "not provide sponsorship", "without sponsorship",
    "without the need for sponsorship", "no sponsorship",
    "must be authorized to work in the united states without",
    "not require sponsorship", "not require visa sponsorship",
]
_YES_SPONSOR = [
    "visa sponsorship available", "will sponsor", "sponsorship is available",
    "offer sponsorship", "provide sponsorship", "h-1b", "h1b",
]
_CITIZEN_REQ = [
    "u.s. citizen", "us citizen", "united states citizen", "citizenship is required",
    "must be a citizen", "security clearance", "active clearance", "ts/sci", "secret clearance",
]


def annotate_visa(job, cfg, company_cache):
    """
    Returns (visa_sponsorship, opt_viable, visa_note).

    visa_sponsorship: Yes | No | Unknown | Posting says no
    opt_viable:       Yes | No           (No only if citizenship/clearance required)
    """
    wa = (cfg.get("profile") or {}).get("work_auth") or {}
    if wa.get("track_sponsorship", True) is False:
        # No sponsorship needed (e.g. US citizen / permanent resident): nothing to flag.
        return "N/A", "N/A", ""
    opt_years = wa.get("stem_opt_years") or 0

    text = (job["title"] + " " + job["description"]).lower()
    company_key = job["company"].strip().lower()

    # 1) Hard blocker: citizenship / clearance -> not viable regardless of OPT
    if any(p in text for p in _CITIZEN_REQ):
        return "No", "No", "Requires US citizenship or security clearance"

    # 2) Posting explicitly refuses sponsorship
    posting_no = any(p in text for p in _NO_SPONSOR)
    posting_yes = any(p in text for p in _YES_SPONSOR)

    # 3) Company cache (seeded + grows over time; Phase 2 auto-research fills it)
    cached = company_cache.get(company_key, {})
    cached_status = cached.get("sponsors")  # "Yes"/"No"/None

    if posting_yes or cached_status == "Yes":
        visa = "Yes"
    elif posting_no:
        visa = "Posting says no"
    elif cached_status == "No":
        visa = "No"
    else:
        visa = "Unknown"

    # OPT viability: with STEM OPT, sponsorship isn't needed for internships or the
    # first few years, so almost everything is viable except citizenship roles.
    opt = "Yes" if opt_years else ("No" if visa in ("No", "Posting says no") else "Unknown")
    note = ""
    if visa in ("No", "Posting says no"):
        note = (f"No sponsorship, but OK on STEM OPT (~{opt_years} yrs) for internship/early role"
                if opt_years else "Employer does not sponsor")
    return visa, opt, note
