#!/usr/bin/env python3
"""
JobHunt — daily job scan.

Pulls finance/banking roles from Adzuna + public ATS boards (Greenhouse/Lever/
Ashby), scores them, annotates visa/OPT, dedupes, and writes JobHunt.xlsx.

Run:  python engine/jobhunt.py
      python engine/jobhunt.py --sample   # use bundled fixture (no network)
"""
import argparse
import json
import os
import sys
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import yaml
import connectors
import scoring
import workbook

CONFIG = os.path.join(ROOT, "config", "config.yaml")
COMPANIES = os.path.join(ROOT, "config", "companies.yaml")
SECRETS = os.path.join(ROOT, "config", "secrets.yaml")
CACHE = os.path.join(ROOT, "data", "company_visa_cache.json")
DESCRIPTIONS = os.path.join(ROOT, "data", "descriptions.json")
LAST_SCAN = os.path.join(ROOT, "data", "last_scan.json")
LOG = os.path.join(ROOT, "data", "run_log.txt")
XLSX = os.path.join(ROOT, "JobHunt.xlsx")
SAMPLE = os.path.join(ROOT, "data", "sample_jobs.json")
TODAY_ISO = dt.date.today().isoformat()


def load_yaml(path, required=True):
    if not os.path.exists(path):
        if required:
            hint = (" - copy config/config.example.yaml to config/config.yaml and fill in your profile"
                    if path.endswith("config.yaml") else "")
            sys.exit(f"Missing config file: {path}{hint}")
        return {}
    with open(path) as f:
        return yaml.safe_load(f)


def log(msg):
    line = f"{dt.datetime.now().isoformat(timespec='seconds')}  {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def gather_live(cfg, companies, secrets):
    jobs, errors = [], []
    query = " ".join(cfg["search"]["titles_positive"][:8])

    if cfg["sources"]["adzuna"]["enabled"] and secrets.get("adzuna", {}).get("app_id", "").strip() and not secrets["adzuna"]["app_id"].startswith("YOUR_"):
        a = secrets["adzuna"]
        base = cfg["sources"]["adzuna"]["results_per_query"]
        weights = cfg["locations"]["country_weights"]
        maxw = max(weights.values())
        for country in cfg["sources"]["adzuna"]["countries"]:
            # fetch fewer results from lower-priority countries
            n = max(3, min(base, round(base * weights.get(country, 0.05) / maxw)))
            try:
                got = connectors.adzuna(a["app_id"], a["app_key"], query, country,
                                        n, cfg["sources"]["adzuna"]["max_days_old"])
                jobs += got
                log(f"adzuna/{country}: {len(got)} jobs (requested {n})")
            except Exception as e:
                errors.append(f"adzuna/{country}: {e}")

    if cfg["sources"]["usajobs"]["enabled"] and secrets.get("usajobs", {}).get("api_key", "").strip() and not secrets["usajobs"]["api_key"].startswith("YOUR_"):
        u = secrets["usajobs"]
        try:
            got = connectors.usajobs(u["email"], u["api_key"], query)
            jobs += got
            log(f"usajobs: {len(got)} jobs")
        except Exception as e:
            errors.append(f"usajobs: {e}")

    if cfg["sources"]["ats_boards"]["enabled"]:
        for fn, key in [(connectors.greenhouse, "greenhouse"),
                        (connectors.lever, "lever"),
                        (connectors.ashby, "ashby")]:
            for token in companies.get(key, []) or []:
                try:
                    got = fn(token)
                    jobs += got
                    log(f"{key}/{token}: {len(got)} jobs")
                except Exception as e:
                    errors.append(f"{key}/{token}: {e}")

    return jobs, errors


def process(raw_jobs, cfg, cache):
    """Filter, dedupe (by id AND by company+title), score, annotate."""
    seen_ids = set()
    seen_ct = {}          # (company,title) -> index in out, to keep the best
    out = []
    for j in raw_jobs:
        if not j.get("title") or not j.get("id"):
            continue
        if j["id"] in seen_ids:
            continue
        seen_ids.add(j["id"])
        if scoring.is_excluded(j, cfg):
            continue
        if not scoring.passes_location(j, cfg):
            continue
        if not scoring.has_finance_signal(j, cfg):
            continue
        sc, reasons = scoring.score(j, cfg)
        if sc < 20:                      # drop obvious non-matches
            continue
        visa, opt, note = scoring.annotate_visa(j, cfg, cache)
        j.update(score=sc, reasons=reasons, visa=visa, opt_viable=opt,
                 visa_note=note, _days=scoring.days_old(j))

        # collapse the same role cross-posted on multiple boards
        ct = (j["company"].strip().lower(), j["title"].strip().lower())
        if ct in seen_ct:
            prev = out[seen_ct[ct]]
            if j["score"] > prev["score"]:
                out[seen_ct[ct]] = j
            continue
        seen_ct[ct] = len(out)
        out.append(j)
    return out


def select_top(scored, cfg):
    """Keep the best max_jobs, split across countries by configured weights.
    Unknown-country jobs fall into the US bucket (most ATS roles are US)."""
    max_jobs = cfg["output"]["max_jobs"]
    weights = cfg["locations"]["country_weights"]
    order = ["us", "mx", "gb", "ca"]

    buckets = {c: [] for c in order}
    for j in scored:
        c = j["country"] if j["country"] in buckets else "us"
        buckets[c].append(j)
    for c in buckets:
        buckets[c].sort(key=lambda j: (j["score"], -j["_days"]), reverse=True)

    quota = {c: int(round(max_jobs * weights.get(c, 0))) for c in order}
    selected = []
    for c in order:
        selected += buckets[c][:quota[c]]

    # fill any remaining slots (short buckets) from leftovers, US first
    if len(selected) < max_jobs:
        chosen = {id(x) for x in selected}
        leftovers = [j for c in order for j in buckets[c][quota[c]:]]
        leftovers.sort(key=lambda j: (j["score"], -j["_days"]), reverse=True)
        for j in leftovers:
            if len(selected) >= max_jobs:
                break
            selected.append(j)

    selected.sort(key=lambda j: (j["score"], -j["_days"]), reverse=True)
    return selected[:max_jobs]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true",
                    help="use bundled fixture instead of live network calls")
    ap.add_argument("--sync", action="store_true",
                    help="no fetching — just refresh Applied sheet from Jobs Status")
    args = ap.parse_args()

    cfg = load_yaml(CONFIG)
    companies = load_yaml(COMPANIES, required=False) or {}
    secrets = load_yaml(SECRETS, required=False) or {}
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

    # --sync: rebuild Applied from current Jobs statuses without scanning
    if args.sync:
        last = json.load(open(LAST_SCAN)).get("date") if os.path.exists(LAST_SCAN) else None
        result = workbook.build(XLSX, [], cfg, is_scan=False, scan_date=last)
        log(f"sync: refreshed workbook ({result['applied']} in Applied)")
        return

    log("=== JobHunt run start ===")
    if args.sample:
        raw = json.load(open(SAMPLE))
        errors = []
        log(f"sample mode: {len(raw)} fixture jobs")
    else:
        if not os.path.exists(SECRETS):
            log("NOTE: config/secrets.yaml not found — Adzuna/USAJobs skipped. "
                "ATS boards will still run. Copy secrets.example.yaml to add keys.")
        raw, errors = gather_live(cfg, companies, secrets)

    log(f"raw jobs collected: {len(raw)}")
    scored = process(raw, cfg, cache)
    log(f"after filter/score/dedupe: {len(scored)}")
    top = select_top(scored, cfg)
    log(f"selected top {len(top)} (of {len(scored)})")

    # sidecar: descriptions kept out of the workbook, used for cover-letter
    # context. Accumulate so letters can be written for older jobs too.
    descs = json.load(open(DESCRIPTIONS)) if os.path.exists(DESCRIPTIONS) else {}
    descs.update({j["id"]: j["description"] for j in top})
    json.dump(descs, open(DESCRIPTIONS, "w"))

    json.dump({"date": TODAY_ISO}, open(LAST_SCAN, "w"))
    result = workbook.build(XLSX, top, cfg, is_scan=True, scan_date=TODAY_ISO)
    log(f"workbook written: {result['total']} rows ({result['new']} new), "
        f"{result['applied']} in Applied -> {result['path']}")

    for e in errors:
        log(f"  skipped source -> {e}")
    log("=== JobHunt run done ===\n")


if __name__ == "__main__":
    main()
