#!/usr/bin/env python3
"""XML sitemap discovery, validation, URL sampling and generation.

Usage:
  sitemap.py check <site-or-sitemap-url> [--sample 30] [--max-sitemaps 50] [--urls-out urls.txt]
  sitemap.py generate <crawl.json> [--out sitemap.xml] [--base https://example.com]

`check` discovers sitemaps (robots.txt Sitemap: lines, then common paths),
follows sitemap indexes, validates the protocol, then fetches a sample of
listed URLs to verify they are 200, indexable and self-canonical.

`generate` builds a sitemap from crawl.py output, including only URLs that
returned 200, are indexable and are self-canonical. lastmod is included only
when a real Last-Modified/article:modified_time value was observed - never
fabricated.
"""

import argparse
import datetime
import gzip
import random
import re
import sys
import xml.etree.ElementTree as ET
from urllib import parse
from xml.sax.saxutils import escape

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import check, emit, fetch, load_json_arg, normalize_url, origin, text_of  # noqa: E402
from htmlparse import extract  # noqa: E402

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
W3C_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2}))?)?)?$")
COMMON = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml", "/wp-sitemap.xml", "/sitemap/sitemap.xml"]


def _body(resp):
    b = resp.get("body") or b""
    if b[:2] == b"\x1f\x8b":
        try:
            b = gzip.decompress(b)
        except OSError:
            pass
    return b


def discover(site):
    found, how = [], []
    r = fetch(site + "/robots.txt", max_bytes=600 * 1024)
    if r["status"] == 200:
        for line in text_of(r).splitlines():
            m = re.match(r"\s*sitemap\s*:\s*(\S+)", line, re.I)
            if m:
                found.append(m.group(1))
        if found:
            how.append("robots.txt")
    if not found:
        for p in COMMON:
            rr = fetch(site + p, max_bytes=1024 * 64)
            if rr["status"] == 200 and b"<" in _body(rr)[:200] and b"<html" not in _body(rr)[:500].lower():
                found.append(rr["final_url"])
                how.append("common path %s" % p)
                break
    return found, how


def parse_sitemap(url, checks, state):
    if url in state["seen"] or len(state["seen"]) >= state["max"]:
        return
    state["seen"].add(url)
    r = fetch(url, max_bytes=60 * 1024 * 1024)
    if r["status"] != 200:
        checks.append(check("sitemap.fetch", "crawl_index", "FAIL", "HIGH", "Sitemap fetch",
                            "HTTP %s %s" % (r["status"], r.get("error") or ""), url,
                            "Make the sitemap return 200, or remove the reference to it."))
        return
    if r["chain"]:
        checks.append(check("sitemap.redirect", "crawl_index", "WARNING", "LOW", "Sitemap redirects",
                            "%s -> %s" % (url, r["final_url"]), url, "Reference the final sitemap URL directly."))
    body = _body(r)
    if len(body) > 50 * 1024 * 1024:
        checks.append(check("sitemap.size", "crawl_index", "FAIL", "HIGH", "Sitemap too large",
                            "%d bytes uncompressed (limit 50 MB)" % len(body), url, "Split into multiple sitemaps under an index."))
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        checks.append(check("sitemap.xml_valid", "crawl_index", "FAIL", "HIGH", "Sitemap XML validity",
                            "Parse error: %s (first bytes: %r)" % (e, body[:120]), url,
                            "Serve well-formed XML (an HTML page here usually means a soft-404/SPA fallback)."))
        return
    tag = root.tag.replace(NS, "")
    if NS not in root.tag:
        checks.append(check("sitemap.namespace", "crawl_index", "WARNING", "MEDIUM", "Sitemap namespace",
                            "Root <%s> lacks the sitemaps.org 0.9 namespace" % root.tag, url,
                            'Use xmlns="http://www.sitemaps.org/schemas/sitemap/0.9".'))
    state["files"].append({"url": url, "type": tag, "bytes": len(body)})
    if tag == "sitemapindex":
        for sm in root.iter(NS + "sitemap"):
            loc = (sm.findtext(NS + "loc") or "").strip()
            if loc:
                parse_sitemap(loc, checks, state)
        return
    if tag != "urlset":
        checks.append(check("sitemap.root", "crawl_index", "FAIL", "HIGH", "Sitemap root element",
                            "Unexpected root <%s>" % tag, url, "Root must be <urlset> or <sitemapindex>."))
        return
    exts = set()
    for ch in root.iter():
        if "}" in ch.tag and NS not in ch.tag:
            exts.add(ch.tag.split("}")[0][1:])
    n = 0
    for u in root.iter(NS + "url"):
        loc = (u.findtext(NS + "loc") or "").strip()
        lastmod = (u.findtext(NS + "lastmod") or "").strip()
        n += 1
        state["entries"].append({"loc": loc, "lastmod": lastmod, "sitemap": url,
                                 "priority": u.findtext(NS + "priority"),
                                 "changefreq": u.findtext(NS + "changefreq")})
    if n > 50000:
        checks.append(check("sitemap.url_count", "crawl_index", "FAIL", "HIGH", "Too many URLs in one sitemap",
                            "%d URLs (limit 50,000)" % n, url, "Split the sitemap."))
    if exts:
        state["extensions"] |= exts


def check_cmd(a):
    target = normalize_url(a.target)
    site = origin(target)
    checks = []
    if re.search(r"\.xml(\.gz)?$|sitemap", parse.urlsplit(target).path, re.I):
        sitemaps, how = [target], ["given"]
    else:
        sitemaps, how = discover(site)
    if not sitemaps:
        checks.append(check("sitemap.present", "crawl_index", "WARNING", "MEDIUM", "XML sitemap",
                            "No sitemap in robots.txt or at common paths", site,
                            "Publish a sitemap of canonical, indexable URLs and reference it in robots.txt. Small, well-linked sites can do without one."))
        emit({"site": site, "sitemaps": [], "checks": checks})
        return
    checks.append(check("sitemap.present", "crawl_index", "PASS", "INFO", "XML sitemap",
                        "Found via %s: %s" % (", ".join(how), sitemaps[:5]), site))
    state = {"seen": set(), "max": a.max_sitemaps, "files": [], "entries": [], "extensions": set()}
    for sm in sitemaps:
        parse_sitemap(sm, checks, state)
    entries = state["entries"]
    locs = [e["loc"] for e in entries]

    bad_loc = [l for l in locs if not re.match(r"^https?://", l)]
    off_host = [l for l in locs if re.match(r"^https?://", l) and parse.urlsplit(l).netloc.lower() != parse.urlsplit(site).netloc.lower()]
    http_on_https = [l for l in locs if site.startswith("https") and l.startswith("http://")]
    dups = len(locs) - len(set(locs))
    if bad_loc:
        checks.append(check("sitemap.loc_absolute", "crawl_index", "FAIL", "MEDIUM", "Relative <loc> URLs",
                            "%d e.g. %s" % (len(bad_loc), bad_loc[:3]), site, "Use absolute URLs."))
    if off_host:
        checks.append(check("sitemap.loc_host", "crawl_index", "WARNING", "MEDIUM", "URLs on a different host",
                            "%d e.g. %s" % (len(off_host), off_host[:3]), site,
                            "List only URLs of the host serving the sitemap (or verify cross-site submission). Check www vs non-www."))
    if http_on_https:
        checks.append(check("sitemap.loc_protocol", "crawl_index", "WARNING", "MEDIUM", "HTTP URLs in sitemap",
                            "%d e.g. %s" % (len(http_on_https), http_on_https[:3]), site, "List the HTTPS canonical URLs."))
    if dups:
        checks.append(check("sitemap.duplicates", "crawl_index", "WARNING", "LOW", "Duplicate URLs",
                            "%d duplicate <loc> entries" % dups, site, "Deduplicate."))
    params = [l for l in locs if parse.urlsplit(l).query]
    if params:
        checks.append(check("sitemap.parameters", "crawl_index", "WARNING", "LOW", "Parameterized URLs",
                            "%d e.g. %s" % (len(params), params[:3]), site, "Sitemaps should list clean canonical URLs."))

    lm = [e["lastmod"] for e in entries if e["lastmod"]]
    bad_lm = [x for x in lm if not W3C_DATE.match(x)]
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    future = [x for x in lm if W3C_DATE.match(x) and x[:10] > now]
    if not lm and entries:
        checks.append(check("sitemap.lastmod", "crawl_index", "WARNING", "LOW", "No lastmod",
                            "0 of %d URLs have lastmod" % len(entries), site,
                            "Add accurate lastmod (when main content changed). Google uses it only if it is consistently accurate."))
    elif lm:
        top = max(set(lm), key=lm.count)
        same = lm.count(top) / float(len(lm))
        ev = "%d/%d URLs have lastmod; invalid=%d, future=%d, most common value %s (%.0f%%)" % (
            len(lm), len(entries), len(bad_lm), len(future), top, same * 100)
        if bad_lm or future or (same > 0.9 and len(lm) > 20):
            checks.append(check("sitemap.lastmod", "crawl_index", "WARNING", "LOW", "lastmod quality", ev, site,
                                "Use W3C date format and real modification dates; identical/future values teach Google to ignore lastmod."))
        else:
            checks.append(check("sitemap.lastmod", "crawl_index", "PASS", "INFO", "lastmod quality", ev, site))
    if any(e["priority"] or e["changefreq"] for e in entries):
        checks.append(check("sitemap.priority_changefreq", "crawl_index", "INFO", "INFO", "priority/changefreq",
                            "Present - Google ignores both", site, "Harmless; no action needed."))

    sample = locs[:]
    random.seed(7)
    random.shuffle(sample)
    sample = [s for s in sample if s.startswith("http")][: a.sample]
    results = []
    for u in sample:
        r = fetch(u, timeout=12)
        row = {"url": u, "status": r["status"], "final_url": r["final_url"], "redirects": len(r["chain"]),
               "noindex": False, "canonical": None}
        if r["status"] == 200 and "html" in r["headers"].get("content-type", ""):
            f = extract(text_of(r), r["final_url"])
            row["noindex"] = any(re.search(r"noindex|none", x, re.I) for x in f["meta_robots"]) or \
                bool(re.search(r"noindex", r["headers"].get("x-robots-tag", ""), re.I))
            row["canonical"] = parse.urljoin(r["final_url"], f["canonicals"][0]) if f["canonicals"] else None
        results.append(row)
    non200 = [x for x in results if x["status"] != 200 or x["redirects"]]
    noidx = [x for x in results if x["noindex"]]
    noncanon = [x for x in results if x["canonical"] and x["canonical"].rstrip("/") != x["url"].rstrip("/")]
    if results:
        if non200:
            checks.append(check("sitemap.sample_status", "crawl_index", "FAIL" if len(non200) > len(results) * 0.1 else "WARNING",
                                "HIGH" if len(non200) > len(results) * 0.1 else "MEDIUM", "Non-200 / redirected URLs in sitemap",
                                "%d of %d sampled: %s" % (len(non200), len(results), ["%s [%s%s]" % (x["url"], x["status"], ", redirect" if x["redirects"] else "") for x in non200[:6]]),
                                site, "List only final 200 URLs; remove 404s and replace redirected URLs with their targets."))
        if noidx:
            checks.append(check("sitemap.sample_noindex", "crawl_index", "FAIL", "HIGH", "Noindex URLs in sitemap",
                                "%d of %d sampled: %s" % (len(noidx), len(results), [x["url"] for x in noidx[:6]]), site,
                                "Remove noindex URLs from the sitemap (or remove the noindex if they should rank)."))
        if noncanon:
            checks.append(check("sitemap.sample_canonical", "crawl_index", "WARNING", "MEDIUM", "Non-canonical URLs in sitemap",
                                "%d of %d sampled: %s" % (len(noncanon), len(results), ["%s -> %s" % (x["url"], x["canonical"]) for x in noncanon[:5]]),
                                site, "List the canonical URL of each page only."))
        if not (non200 or noidx or noncanon):
            checks.append(check("sitemap.sample", "crawl_index", "PASS", "INFO", "Sampled sitemap URLs",
                                "%d sampled URLs all 200, indexable and self-canonical" % len(results), site))
    if a.urls_out:
        with open(a.urls_out, "w") as fh:
            fh.write("\n".join(locs))
    emit({"site": site, "sitemaps": state["files"], "url_count": len(locs), "extensions": sorted(state["extensions"]),
          "sample": results, "checks": checks})


def generate_cmd(a):
    crawl = load_json_arg(a.crawl)
    pages = crawl.get("pages", [])
    out = []
    skipped = {"non200": 0, "noindex": 0, "non_canonical": 0, "non_html": 0}
    for p in pages:
        if p.get("status") != 200:
            skipped["non200"] += 1
            continue
        if not p.get("is_html", True):
            skipped["non_html"] += 1
            continue
        if p.get("noindex"):
            skipped["noindex"] += 1
            continue
        can = p.get("canonical")
        if can and can.rstrip("/") != p["url"].rstrip("/"):
            skipped["non_canonical"] += 1
            continue
        out.append(p)
    out.sort(key=lambda p: (p.get("depth", 99), p["url"]))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in out[:50000]:
        lines.append("  <url>")
        lines.append("    <loc>%s</loc>" % escape(p["url"]))
        if p.get("lastmod"):
            lines.append("    <lastmod>%s</lastmod>" % escape(p["lastmod"]))
        lines.append("  </url>")
    lines.append("</urlset>")
    xml = "\n".join(lines) + "\n"
    if a.out:
        with open(a.out, "w") as fh:
            fh.write(xml)
    sys.stderr.write("included %d URLs; skipped %s\n" % (len(out), skipped))
    if not a.out:
        sys.stdout.write(xml)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("target")
    c.add_argument("--sample", type=int, default=30)
    c.add_argument("--max-sitemaps", type=int, default=50)
    c.add_argument("--urls-out")
    g = sub.add_parser("generate")
    g.add_argument("crawl")
    g.add_argument("--out")
    a = ap.parse_args()
    check_cmd(a) if a.cmd == "check" else generate_cmd(a)


if __name__ == "__main__":
    main()
