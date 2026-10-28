"""
Job source connectors. Each returns a list of normalized job dicts:

    {
      "id": str,            # stable unique id
      "source": str,        # adzuna | usajobs | greenhouse | lever | ashby
      "company": str,
      "title": str,
      "location": str,
      "country": str,       # us | ca | mx | gb | ""
      "remote": bool,
      "salary": str,
      "url": str,
      "description": str,   # plain text
      "date_posted": str,   # YYYY-MM-DD or ""
    }

Runs on the user's machine (open network). In the sandbox these are
exercised via sample fixtures instead of live calls.
"""
import hashlib
import re
import html
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo

try:
    import requests
except ImportError:
    requests = None

UA = {"User-Agent": "jobhunt/1.0 (personal job search)"}
TIMEOUT = 20


def _clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(text))      # strip HTML tags
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _hash(*parts):
    return hashlib.sha1("|".join(p for p in parts if p).encode()).hexdigest()[:16]


def _get(url, **kwargs):
    if requests is None:
        raise RuntimeError("The 'requests' package is required. pip install requests")
    r = requests.get(url, headers=UA, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


# --------------------------------------------------------------------------- #
# Adzuna — broad aggregator (covers big banks, corporates, everything)
# --------------------------------------------------------------------------- #
def adzuna(app_id, app_key, query, country="us", results=50, max_days_old=21):
    jobs = []
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what_or": query,          # OR across the terms
        "results_per_page": results,
        "max_days_old": max_days_old,
        "content-type": "application/json",
    }
    data = _get(url, params=params).json()
    for it in data.get("results", []):
        loc = ", ".join(it.get("location", {}).get("area", [])[-2:]) or \
              it.get("location", {}).get("display_name", "")
        sal = ""
        if it.get("salary_min"):
            sal = f"{int(it['salary_min']):,}–{int(it.get('salary_max', it['salary_min'])):,} {it.get('salary_currency','')}".strip()
        jobs.append({
            "id": "adzuna_" + str(it.get("id") or _hash(it.get("redirect_url", ""))),
            "source": "adzuna",
            "company": _clean(it.get("company", {}).get("display_name", "")),
            "title": _clean(it.get("title", "")),
            "location": _clean(loc),
            # derive country from the actual location; fall back to the search index
            "country": geo.country_from_loc(loc) or country,
            "remote": "remote" in (it.get("title", "") + loc).lower(),
            "salary": sal,
            "url": it.get("redirect_url", ""),
            "description": _clean(it.get("description", "")),
            "date_posted": (it.get("created", "")[:10]),
        })
    return jobs


# --------------------------------------------------------------------------- #
# USAJobs — US government (mostly citizenship-required; off by default)
# --------------------------------------------------------------------------- #
def usajobs(email, api_key, query, results=50):
    jobs = []
    url = "https://data.usajobs.gov/api/search"
    headers = {**UA, "Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": api_key}
    params = {"Keyword": query, "ResultsPerPage": results}
    r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    for it in r.json().get("SearchResult", {}).get("SearchResultItems", []):
        d = it.get("MatchedObjectDescriptor", {})
        pay = d.get("PositionRemuneration", [{}])[0]
        sal = ""
        if pay.get("MinimumRange"):
            sal = f"${pay['MinimumRange']}–${pay.get('MaximumRange','')} {pay.get('RateIntervalCode','')}"
        jobs.append({
            "id": "usajobs_" + str(d.get("PositionID") or _hash(d.get("PositionURI", ""))),
            "source": "usajobs",
            "company": _clean(d.get("OrganizationName", "")),
            "title": _clean(d.get("PositionTitle", "")),
            "location": _clean(d.get("PositionLocationDisplay", "")),
            "country": "us",
            "remote": "telework" in str(d).lower(),
            "salary": sal,
            "url": d.get("PositionURI", ""),
            "description": _clean(d.get("UserArea", {}).get("Details", {}).get("JobSummary", "")),
            "date_posted": (d.get("PublicationStartDate", "")[:10]),
        })
    return jobs


# --------------------------------------------------------------------------- #
# Greenhouse / Lever / Ashby — public company job boards (no key)
# --------------------------------------------------------------------------- #
def greenhouse(token):
    jobs = []
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true").json()
    for it in data.get("jobs", []):
        loc = _clean(it.get("location", {}).get("name", ""))
        jobs.append({
            "id": "gh_" + str(it.get("id")),
            "source": "greenhouse",
            "company": token,
            "title": _clean(it.get("title", "")),
            "location": loc,
            "country": geo.country_from_loc(loc),
            "remote": "remote" in loc.lower(),
            "salary": "",
            "url": it.get("absolute_url", ""),
            "description": _clean(it.get("content", "")),
            "date_posted": (it.get("updated_at", "")[:10]),
        })
    return jobs


def lever(token):
    jobs = []
    data = _get(f"https://api.lever.co/v0/postings/{token}?mode=json").json()
    for it in data:
        loc = _clean(it.get("categories", {}).get("location", ""))
        jobs.append({
            "id": "lever_" + str(it.get("id")),
            "source": "lever",
            "company": token,
            "title": _clean(it.get("text", "")),
            "location": loc,
            "country": geo.country_from_loc(loc),
            "remote": "remote" in (loc + it.get("workplaceType", "")).lower(),
            "salary": "",
            "url": it.get("hostedUrl", ""),
            "description": _clean(it.get("descriptionPlain", "") or it.get("description", "")),
            "date_posted": _epoch_to_date(it.get("createdAt")),
        })
    return jobs


def ashby(token):
    jobs = []
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true").json()
    for it in data.get("jobs", []):
        loc = _clean(it.get("location", ""))
        comp = it.get("compensation", {}) or {}
        sal = ""
        summary = comp.get("compensationTierSummary")
        if summary:
            sal = _clean(summary)
        jobs.append({
            "id": "ashby_" + str(it.get("id")),
            "source": "ashby",
            "company": token,
            "title": _clean(it.get("title", "")),
            "location": loc,
            "country": geo.country_from_loc(loc),
            "remote": bool(it.get("isRemote")),
            "salary": sal,
            "url": it.get("jobUrl", ""),
            "description": _clean(it.get("descriptionPlain", "")),
            "date_posted": (it.get("publishedAt", "") or "")[:10],
        })
    return jobs


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _epoch_to_date(ms):
    try:
        return dt.datetime.utcfromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d")
    except Exception:
        return ""
