#!/usr/bin/env python3
"""hreflang validation.

Usage:
  hreflang.py <url> [<url> ...] [--follow 40]
  hreflang.py --crawl crawl.json [--follow 40]

Checks per page: code format, common code mistakes, self-reference,
duplicate codes, x-default, return tags (reciprocity), targets that are
non-200 / redirected / noindex / non-canonical, and canonical conflicts.
Alternate targets not already known are fetched (up to --follow).
Note: hreflang may also be declared in HTTP Link headers or XML sitemaps;
this tool reads HTML <link> tags only - say so when reporting.
"""

import argparse
import re
import sys
from urllib import parse

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import check, emit, fetch, load_json_arg, normalize_url, text_of  # noqa: E402
from htmlparse import extract  # noqa: E402

CODE_RX = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{4})?(-([A-Za-z]{2}|\d{3}))?$")
KNOWN_MISTAKES = {
    "en-uk": "use en-GB (UK is not an ISO 3166-1 code)",
    "jp": "Japanese language code is ja",
    "cn": "Chinese language code is zh (cn is a region)",
    "kr": "Korean language code is ko",
    "dk": "Danish language code is da",
    "se": "Swedish language code is sv (se is Northern Sami)",
    "gr": "Greek language code is el",
    "cz": "Czech language code is cs",
    "ua": "Ukrainian language code is uk",
    "eu": "eu is Basque; there is no 'Europe' code",
    "en-eu": "EU is not a valid region for hreflang",
    "es-la": "Latin America has no region code; use es-419 or specific countries",
}


def norm(u):
    return (u or "").rstrip("/").lower()


def page_info(url, cache):
    if url in cache:
        return cache[url]
    r = fetch(url, timeout=15, html_only=True)
    info = {"url": url, "status": r["status"], "final_url": r["final_url"], "redirected": bool(r["chain"]),
            "hreflang": [], "canonical": None, "noindex": False, "lang": None}
    if r["status"] == 200 and "html" in r["headers"].get("content-type", ""):
        f = extract(text_of(r), r["final_url"])
        info["hreflang"] = f["hreflang"]
        info["canonical"] = parse.urljoin(r["final_url"], f["canonicals"][0]) if f["canonicals"] else None
        info["noindex"] = any(re.search(r"noindex|none", x, re.I) for x in f["meta_robots"])
        info["lang"] = f["lang"]
    cache[url] = info
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--crawl")
    ap.add_argument("--follow", type=int, default=40)
    a = ap.parse_args()
    cache = {}
    if a.crawl:
        for p in load_json_arg(a.crawl).get("pages", []):
            if p.get("status") == 200:
                cache[p["final_url"]] = {"url": p["final_url"], "status": 200, "final_url": p["final_url"],
                                         "redirected": False, "hreflang": p.get("hreflang") or [],
                                         "canonical": p.get("canonical"), "noindex": p.get("noindex"),
                                         "lang": p.get("lang")}
        roots = [u for u, i in cache.items() if i["hreflang"]]
    else:
        roots = [page_info(normalize_url(u), cache)["final_url"] for u in a.urls]
    checks = []
    if not any(cache.get(u, {}).get("hreflang") for u in roots):
        checks.append(check("hreflang.present", "crawl_index", "NA", "INFO", "hreflang",
                            "No hreflang annotations in HTML on %d page(s)" % len(roots), roots[0] if roots else "",
                            "Only needed if the site serves equivalent content in multiple languages/regions."))
        emit({"pages": [], "checks": checks})
        return

    fetched = 0
    report = []
    for u in roots:
        info = cache[u]
        tags = info["hreflang"]
        issues = []
        codes = {}
        for t in tags:
            code = t["hreflang"].strip()
            low = code.lower().replace("_", "-")
            if "_" in code:
                issues.append("%s uses underscore (use hyphen)" % code)
            if low in KNOWN_MISTAKES:
                issues.append("%s: %s" % (code, KNOWN_MISTAKES[low]))
            elif low != "x-default" and not CODE_RX.match(code.replace("_", "-")):
                issues.append("%s is not a valid language[-script][-region] code" % code)
            if not t.get("in_head", True):
                issues.append("%s tag is outside <head>" % code)
            if not re.match(r"^https?://", t["href"]):
                issues.append("%s href is not absolute" % code)
            codes.setdefault(low, set()).add(norm(t["href"]))
        dup = {c: v for c, v in codes.items() if len(v) > 1}
        if dup:
            issues.append("same code -> different URLs: %s" % {c: sorted(v) for c, v in dup.items()})
        if not any(norm(t["href"]) == norm(u) for t in tags):
            issues.append("no self-referencing hreflang")
        if "x-default" not in codes:
            issues.append("no x-default (recommended for language/region selectors or fallback pages)")
        if info["canonical"] and norm(info["canonical"]) != norm(u):
            issues.append("page canonicalizes to %s - hreflang on non-canonical pages is ignored" % info["canonical"])
        missing_return, bad_targets = [], []
        for t in tags:
            tgt = t["href"]
            if norm(tgt) == norm(u):
                continue
            if tgt not in cache:
                if fetched >= a.follow:
                    continue
                fetched += 1
            ti = page_info(tgt, cache)
            if ti["status"] != 200 or ti["redirected"]:
                bad_targets.append("%s [%s%s]" % (tgt, ti["status"], ", redirects" if ti["redirected"] else ""))
                continue
            if ti["noindex"]:
                bad_targets.append("%s [noindex]" % tgt)
            if ti["canonical"] and norm(ti["canonical"]) != norm(ti["final_url"]):
                bad_targets.append("%s [canonical -> %s]" % (tgt, ti["canonical"]))
            if not any(norm(x["href"]) == norm(u) for x in ti["hreflang"]):
                missing_return.append(tgt)
        report.append({"url": u, "tags": tags, "issues": issues, "missing_return": missing_return,
                       "bad_targets": bad_targets})
        if missing_return:
            checks.append(check("hreflang.return", "crawl_index", "FAIL", "HIGH", "Missing hreflang return tags",
                                "%s is not linked back from: %s" % (u, missing_return[:6]), u,
                                "Every alternate must list all versions including this one; one-way annotations are ignored."))
        if bad_targets:
            checks.append(check("hreflang.targets", "crawl_index", "FAIL", "HIGH", "hreflang points to bad URLs",
                                "; ".join(bad_targets[:6]), u, "Point hreflang only at final, 200, indexable, self-canonical URLs."))
        if issues:
            sev = "HIGH" if any("not a valid" in i or "canonicalizes" in i or "self-ref" in i for i in issues) else "LOW"
            checks.append(check("hreflang.tags", "crawl_index", "WARNING", sev, "hreflang tag issues",
                                "; ".join(issues[:8]), u, "Fix the listed issues in the shared template."))
        if not (missing_return or bad_targets or issues):
            checks.append(check("hreflang.tags", "crawl_index", "PASS", "INFO", "hreflang",
                                "%d alternates valid and reciprocal" % len(tags), u))
    emit({"pages": report, "followed": fetched, "checks": checks,
          "note": "HTML <link> annotations only; also inspect HTTP Link headers / sitemap xhtml:link if used."})


if __name__ == "__main__":
    main()
