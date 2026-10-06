#!/usr/bin/env python3
"""Core Web Vitals via the PageSpeed Insights API (lab + CrUX field data).

Usage:
  psi.py <url> [--strategy mobile|desktop] [--key $PSI_API_KEY]

Works without a key at low quota; set PSI_API_KEY for reliability.
Field data (CrUX, real users, 28-day p75) is what Google uses; lab data
(Lighthouse) is for diagnosis. Never present lab numbers as field data.
Thresholds (p75): LCP <=2.5s good / >4s poor; INP <=200ms / >500ms;
CLS <=0.1 / >0.25.
"""

import argparse
import json
import os
import sys
from urllib import parse, request

sys.path.insert(0, os.path.dirname(__file__))
from common import check, emit, normalize_url  # noqa: E402

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
THRESH = {"LARGEST_CONTENTFUL_PAINT_MS": ("LCP", 2500, 4000, "ms"),
          "INTERACTION_TO_NEXT_PAINT": ("INP", 200, 500, "ms"),
          "CUMULATIVE_LAYOUT_SHIFT_SCORE": ("CLS", 10, 25, "x100")}


def run(url, strategy, key):
    q = {"url": url, "strategy": strategy, "category": "performance"}
    if key:
        q["key"] = key
    with request.urlopen(API + "?" + parse.urlencode(q), timeout=120) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--strategy", default="mobile")
    ap.add_argument("--key", default=os.environ.get("PSI_API_KEY"))
    a = ap.parse_args()
    url = normalize_url(a.url)
    try:
        d = run(url, a.strategy, a.key)
    except Exception as e:
        emit({"url": url, "error": str(e), "checks": [check(
            "cwv.unavailable", "performance", "INFO", "INFO", "PageSpeed Insights unavailable", str(e), url,
            "Retry with PSI_API_KEY set, or measure with Lighthouse locally / Search Console CWV report.")]})
        return
    checks, field = [], {}
    for scope in ("loadingExperience", "originLoadingExperience"):
        le = d.get(scope) or {}
        metrics = le.get("metrics") or {}
        if metrics and scope not in field:
            field[scope] = {}
            for k, (name, good, poor, unit) in THRESH.items():
                m = metrics.get(k)
                if m:
                    field[scope][name] = {"p75": m.get("percentile"), "category": m.get("category")}
    src = "loadingExperience" if field.get("loadingExperience") else ("originLoadingExperience" if field.get("originLoadingExperience") else None)
    if src:
        for k, (name, good, poor, unit) in THRESH.items():
            m = field[src].get(name)
            if not m:
                continue
            p = m["p75"]
            shown = "%.2f" % (p / 100.0) if unit == "x100" else "%d ms" % p
            st = "PASS" if p <= good else ("FAIL" if p > poor else "WARNING")
            sev = {"PASS": "INFO", "WARNING": "MEDIUM", "FAIL": "HIGH"}[st]
            checks.append(check("cwv.field.%s" % name.lower(), "performance", st, sev, "%s (field, p75)" % name,
                                "%s - %s (%s data, %s)" % (shown, m["category"], "URL" if src == "loadingExperience" else "origin-level", a.strategy),
                                url, "See lab diagnostics below for the main contributors."))
    else:
        checks.append(check("cwv.field", "performance", "INFO", "INFO", "No CrUX field data",
                            "Not enough real-user traffic in CrUX for this URL/origin", url,
                            "Rely on lab data and Search Console; field data appears once traffic is sufficient."))
    lh = d.get("lighthouseResult", {})
    audits = lh.get("audits", {})
    perf = (lh.get("categories", {}).get("performance") or {}).get("score")
    lab = {k: audits.get(k, {}).get("displayValue") for k in
           ("largest-contentful-paint", "cumulative-layout-shift", "total-blocking-time", "first-contentful-paint", "speed-index", "server-response-time")}
    checks.append(check("cwv.lab", "performance", "INFO", "INFO", "Lighthouse lab (%s)" % a.strategy,
                        "score %s; %s" % (int(perf * 100) if perf is not None else "?", lab), url))
    opps = []
    for k, v in audits.items():
        det = v.get("details") or {}
        if det.get("type") == "opportunity" and (v.get("score") is not None and v["score"] < 0.9):
            opps.append((det.get("overallSavingsMs") or 0, v.get("title"), v.get("displayValue", "")))
    opps.sort(reverse=True)
    if opps:
        checks.append(check("cwv.opportunities", "performance", "WARNING", "LOW", "Top lab opportunities",
                            "; ".join("%s (%s)" % (t, dv) for _, t, dv in opps[:6]), url,
                            "Prioritise items affecting the failing field metric."))
    lcp_el = (audits.get("largest-contentful-paint-element", {}).get("details") or {}).get("items")
    emit({"url": url, "strategy": a.strategy, "field": field, "lab": lab, "lab_score": perf,
          "lcp_element": lcp_el, "checks": checks})


if __name__ == "__main__":
    main()
