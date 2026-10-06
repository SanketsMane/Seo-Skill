#!/usr/bin/env python3
"""Weighted SEO Health Score + report tables + before/after diff.

Usage:
  score.py score <result.json> [<result.json> ...] [--manual manual.json]
                 [--na geo,images] [--md] [--out audit-score.json]
  score.py diff <before-score.json> <after-score.json> [--md]

Inputs are outputs of the other seox scripts (anything with a "checks"
list). --manual adds judgment checks Claude made (same shape, label
INFERRED/OBSERVED) - e.g. E-E-A-T, search intent, topical coverage.
--na marks categories irrelevant to this site; their weight is
redistributed instead of penalising the site.

Category score = 100 * sum(w * status_factor) / sum(w) over scored checks,
w by severity (CRITICAL 10, HIGH 6, MEDIUM 3, LOW 1), factor PASS 1,
WARNING 0.5, FAIL 0. INFO/NA checks are reported but not scored. Any
CRITICAL FAIL caps its category at 40. Overall = weighted mean of
categories with data. See references/scoring.md.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import emit, load_json_arg  # noqa: E402

WEIGHTS = {"technical": 20, "crawl_index": 15, "onpage": 15, "content": 15, "internal_links": 10,
           "schema": 8, "performance": 7, "images": 3, "geo": 7}
LABELS = {"technical": "Technical SEO", "crawl_index": "Crawlability & Indexability", "onpage": "On-Page SEO",
          "content": "Content Quality / E-E-A-T", "internal_links": "Internal Linking", "schema": "Structured Data",
          "performance": "Performance / CWV", "images": "Image SEO", "geo": "GEO / AI Search"}
SEV_W = {"CRITICAL": 10, "HIGH": 6, "MEDIUM": 3, "LOW": 1, "INFO": 0}
FACTOR = {"PASS": 1.0, "WARNING": 0.5, "FAIL": 0.0}
SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def gather(paths, manual):
    seen, checks = set(), []
    for p in paths + ([manual] if manual else []):
        d = load_json_arg(p)
        items = d if isinstance(d, list) else d.get("checks", [])
        for c in items:
            key = (c["id"], c.get("url", "").rstrip("/"))
            if key in seen:
                continue
            seen.add(key)
            checks.append(c)
    return checks


def status_word(s):
    return "Good" if s >= 85 else "Needs work" if s >= 65 else "Poor" if s >= 40 else "Critical"


def score(checks, na):
    cats = {}
    for cat in WEIGHTS:
        cs = [c for c in checks if c["category"] == cat]
        scored = [c for c in cs if c["status"] in FACTOR and SEV_W.get(c["severity"], 0) > 0 or c["status"] == "PASS"]
        num = den = 0.0
        for c in scored:
            w = SEV_W.get(c["severity"], 0) or 1  # PASS checks carry INFO severity; weight 1
            if c["status"] == "PASS":
                w = 2
            num += w * FACTOR[c["status"]]
            den += w
        crit = any(c["status"] == "FAIL" and c["severity"] == "CRITICAL" for c in cs)
        if cat in na or den == 0:
            cats[cat] = {"score": None, "applicable": cat not in na, "reason": "not applicable" if cat in na else "no scored checks"}
            continue
        s = 100.0 * num / den
        if crit:
            s = min(s, 40.0)
        cats[cat] = {"score": round(s), "applicable": True, "critical_cap": crit,
                     "fail": sum(1 for c in cs if c["status"] == "FAIL"),
                     "warning": sum(1 for c in cs if c["status"] == "WARNING"),
                     "pass": sum(1 for c in cs if c["status"] == "PASS"),
                     "info": sum(1 for c in cs if c["status"] in ("INFO", "NA"))}
    live = {k: v for k, v in cats.items() if v["score"] is not None}
    tw = sum(WEIGHTS[k] for k in live)
    overall = round(sum(WEIGHTS[k] * v["score"] for k, v in live.items()) / tw) if tw else None
    coverage = round(100.0 * tw / sum(WEIGHTS.values()))
    return {"overall": overall, "coverage_pct": coverage, "categories": cats, "weights": WEIGHTS}


def todo(checks):
    items = [c for c in checks if c["status"] in ("FAIL", "WARNING") and c["severity"] != "INFO"]
    items.sort(key=lambda c: (SEV_ORDER.index(c["severity"]), 0 if c["status"] == "FAIL" else 1, -WEIGHTS[c["category"]]))
    return items


def md_cell(s, n=160):
    s = str(s or "").replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def render_md(res, checks):
    out = ["## Scorecard", "", "**Overall SEO Health Score: %s / 100** (data coverage %d%% of weighted categories)" % (
        res["overall"] if res["overall"] is not None else "n/a", res["coverage_pct"]), "",
           "| Category | Weight | Score | Status | Fail | Warn | Pass |", "|---|---:|---:|---|---:|---:|---:|"]
    for k, v in res["categories"].items():
        if v["score"] is None:
            out.append("| %s | %d | – | %s | | | |" % (LABELS[k], WEIGHTS[k], v["reason"]))
        else:
            out.append("| %s | %d | %d%s | %s | %d | %d | %d |" % (LABELS[k], WEIGHTS[k], v["score"], " (capped)" if v["critical_cap"] else "",
                                                                status_word(v["score"]), v["fail"], v["warning"], v["pass"]))
    out += ["", "## To-Do List", "", "| # | Priority | Category | Issue | Evidence | Recommended action | Label |", "|---:|---|---|---|---|---|---|"]
    for i, c in enumerate(todo(checks), 1):
        out.append("| %d | %s | %s | %s | %s | %s | %s |" % (i, c["severity"], LABELS[c["category"]], md_cell(c["title"], 70),
                                                         md_cell(c["evidence"]), md_cell(c["recommendation"], 200), c.get("label", "")))
    return "\n".join(out) + "\n"


def diff_md(b, a):
    rows = ["| Metric | Before | After | Δ |", "|---|---:|---:|---:|"]
    fmt = lambda x: "–" if x is None else str(x)
    d = lambda x, y: "" if x is None or y is None else "%+d" % (y - x)
    rows.append("| **SEO Health Score** | %s | %s | %s |" % (fmt(b["overall"]), fmt(a["overall"]), d(b["overall"], a["overall"])))
    for k in WEIGHTS:
        x, y = b["categories"][k]["score"], a["categories"][k]["score"]
        rows.append("| %s | %s | %s | %s |" % (LABELS[k], fmt(x), fmt(y), d(x, y)))
    bk = {(c["id"], c.get("url")): c for c in b.get("checks", []) if c["status"] in ("FAIL", "WARNING")}
    ak = {(c["id"], c.get("url")): c for c in a.get("checks", []) if c["status"] in ("FAIL", "WARNING")}
    fixed = [bk[k] for k in bk if k not in ak]
    new = [ak[k] for k in ak if k not in bk]
    remaining = [ak[k] for k in ak if k in bk]
    sec = lambda title, xs: ["", "### %s (%d)" % (title, len(xs))] + ["- [%s] %s — %s" % (c["severity"], c["title"], md_cell(c["evidence"], 120)) for c in xs[:40]]
    return "\n".join(rows + sec("Fixed issues", fixed) + sec("New warnings", new) + sec("Remaining issues", remaining)) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("inputs", nargs="+")
    s.add_argument("--manual")
    s.add_argument("--na", default="")
    s.add_argument("--md", action="store_true")
    s.add_argument("--out")
    d = sub.add_parser("diff")
    d.add_argument("before")
    d.add_argument("after")
    d.add_argument("--md", action="store_true")
    a = ap.parse_args()
    if a.cmd == "score":
        checks = gather(a.inputs, a.manual)
        na = {x.strip() for x in a.na.split(",") if x.strip()}
        res = score(checks, na)
        res["checks"] = checks
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                json.dump(res, fh, indent=1, ensure_ascii=False)
        if a.md:
            sys.stdout.write(render_md(res, checks))
        else:
            emit({k: v for k, v in res.items() if k != "checks"})
    else:
        b, af = load_json_arg(a.before), load_json_arg(a.after)
        if a.md:
            sys.stdout.write(diff_md(b, af))
        else:
            emit({"before": b["overall"], "after": af["overall"],
                  "categories": {k: [b["categories"][k]["score"], af["categories"][k]["score"]] for k in WEIGHTS}})


if __name__ == "__main__":
    main()
