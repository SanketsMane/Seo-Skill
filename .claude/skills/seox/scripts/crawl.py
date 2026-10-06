#!/usr/bin/env python3
"""Polite breadth-first site crawler for site-level SEO checks.

Usage:
  crawl.py <start-url> [--max 200] [--delay 0.5] [--sitemap-urls urls.txt]
           [--include REGEX] [--exclude REGEX] [--ignore-robots] [--out crawl.json]

Respects robots.txt for its user agent (unless --ignore-robots, for sites you
own). Records per page: status, depth, title, description, H1, canonical,
noindex, word count, inlinks, outlinks, hreflang, schema types. Then derives
site-level checks: duplicate titles/descriptions/H1s, missing tags, broken
internal links, redirecting internal links, deep pages, orphan candidates
(in sitemap but never linked), weakly linked pages, canonical/noindex
conflicts, URL hygiene (case, trailing slash, parameters).
"""

import argparse
import hashlib
import re
import sys
import time
from collections import Counter, defaultdict, deque
from urllib import parse

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import DEFAULT_UA, check, emit, fetch, normalize_url, origin, text_of  # noqa: E402
from htmlparse import extract  # noqa: E402
from robots import is_allowed, parse_robots, rules_for  # noqa: E402

SKIP_EXT = re.compile(r"\.(jpe?g|png|gif|webp|avif|svg|ico|css|js|mjs|pdf|zip|gz|mp4|webm|mp3|woff2?|ttf|eot|xml|json|txt|rss|atom)$", re.I)


def canon_key(u):
    p = parse.urlsplit(u)
    return parse.urlunsplit((p.scheme, p.netloc.lower(), p.path, p.query, ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("start")
    ap.add_argument("--max", type=int, default=200)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--sitemap-urls", help="file of sitemap URLs (from sitemap.py --urls-out) for orphan detection")
    ap.add_argument("--include")
    ap.add_argument("--exclude")
    ap.add_argument("--ignore-robots", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()

    start = normalize_url(a.start)
    first = fetch(start)
    start = first["final_url"] or start
    site = origin(start)
    host = parse.urlsplit(start).netloc.lower()
    inc = re.compile(a.include) if a.include else None
    exc = re.compile(a.exclude) if a.exclude else None

    rules = []
    if not a.ignore_robots:
        r = fetch(site + "/robots.txt", max_bytes=600 * 1024)
        if r["status"] == 200:
            groups, _, _, _ = parse_robots(text_of(r))
            _, rules = rules_for(groups, "seox-audit")

    sitemap_urls = []
    if a.sitemap_urls:
        sitemap_urls = [l.strip() for l in open(a.sitemap_urls) if l.strip()]

    queue = deque([(start, 0, None)])
    seen = {canon_key(start)}
    pages = {}
    edges = []  # (src, dst, anchor, contextual)
    blocked = []
    started = time.time()

    html_pages = 0
    while queue and html_pages < a.max and len(pages) < a.max * 3:
        url, depth, parent = queue.popleft()
        path = parse.urlsplit(url).path or "/"
        q = parse.urlsplit(url).query
        if rules and not is_allowed(rules, path + ("?" + q if q else ""))[0]:
            blocked.append(url)
            continue
        resp = first if url == start and first["final_url"] == url else fetch(url, timeout=15, html_only=True)
        ct = resp["headers"].get("content-type", "")
        rec = {"url": url, "final_url": resp["final_url"], "status": resp["status"],
               "redirects": [c["status"] for c in resp["chain"]], "depth": depth, "found_on": parent,
               "is_html": "html" in ct, "ttfb_ms": resp.get("ttfb_ms"),
               "bytes": len(resp.get("body") or b""), "error": resp.get("error")}
        lastmod = resp["headers"].get("last-modified")
        if resp["status"] == 200 and "html" in ct:
            html_pages += 1
            html = text_of(resp)
            f = extract(html, resp["final_url"])
            robots = " ".join(f["meta_robots"]).lower() + " " + resp["headers"].get("x-robots-tag", "").lower()
            can = parse.urljoin(resp["final_url"], f["canonicals"][0]) if f["canonicals"] else None
            h1 = [h["text"] for h in f["headings"] if h["level"] == 1]
            types = []
            for b in f["jsonld"]:
                if b["ok"]:
                    d = b["data"]
                    for it in (d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []):
                        if isinstance(it, dict):
                            t = it.get("@type")
                            types += t if isinstance(t, list) else [t]
            mod = f["article_meta"].get("article:modified_time")
            rec.update({
                "title": f["title"], "description": f["meta_description"], "h1": h1,
                "canonical": can, "noindex": bool(re.search(r"noindex|\bnone\b", robots)),
                "nofollow_page": "nofollow" in robots, "lang": f["lang"],
                "word_count": f["main_word_count"], "hreflang": f["hreflang"],
                "schema_types": [t for t in types if t], "images": len(f["images"]),
                "images_missing_alt": sum(1 for i in f["images"] if not i["has_alt_attr"]),
                "content_hash": hashlib.md5(re.sub(r"\s+", " ", f["main_text"]).encode("utf-8")).hexdigest(),
                "lastmod": (mod or "")[:25] or None,
            })
            if not rec["nofollow_page"]:
                for an in f["anchors"]:
                    if an["kind"] != "internal" or not an["url"] or an["nofollow"]:
                        continue
                    dst = an["url"]
                    edges.append((resp["final_url"], dst, an["accessible_name"][:80], not an["in_boilerplate"]))
                    k = canon_key(dst)
                    if k in seen or SKIP_EXT.search(parse.urlsplit(dst).path):
                        continue
                    if inc and not inc.search(dst):
                        continue
                    if exc and exc.search(dst):
                        continue
                    if parse.urlsplit(dst).netloc.lower() != host:
                        continue
                    seen.add(k)
                    queue.append((dst, depth + 1, resp["final_url"]))
        elif lastmod:
            rec["lastmod"] = None
        pages[url] = rec
        if a.delay:
            time.sleep(a.delay)

    # ---- graph metrics
    finals = {p["url"]: p["final_url"] for p in pages.values()}
    by_final = {}
    for p in pages.values():
        by_final.setdefault(p["final_url"], p)
    inlinks = defaultdict(set)
    ctx_inlinks = defaultdict(set)
    anchors_to = defaultdict(Counter)
    for src, dst, anchor, ctx in edges:
        tgt = finals.get(dst, dst)
        if tgt == src:
            continue
        inlinks[tgt].add(src)
        if ctx:
            ctx_inlinks[tgt].add(src)
        if anchor:
            anchors_to[tgt][anchor.lower()] += 1
    for p in pages.values():
        p["inlinks"] = len(inlinks.get(p["final_url"], ()))
        p["contextual_inlinks"] = len(ctx_inlinks.get(p["final_url"], ()))
        p["top_anchors"] = anchors_to.get(p["final_url"], Counter()).most_common(5)

    checks = []
    ok = [p for p in pages.values() if p["status"] == 200 and p.get("is_html")]
    indexable = [p for p in ok if not p.get("noindex") and (not p.get("canonical") or p["canonical"].rstrip("/") == p["final_url"].rstrip("/"))]

    def dup_check(field, cid, cat, title, sev, rec):
        groups = defaultdict(list)
        for p in indexable:
            v = p.get(field)
            if isinstance(v, list):
                v = v[0] if v else None
            if v:
                groups[v.strip().lower()].append(p["final_url"])
        d = {k: v for k, v in groups.items() if len(v) > 1}
        if d:
            n = sum(len(v) for v in d.values())
            ev = "; ".join('"%s" x%d (%s)' % (k[:60], len(v), ", ".join(v[:3])) for k, v in sorted(d.items(), key=lambda x: -len(x[1]))[:6])
            checks.append(check(cid, cat, "FAIL" if n > len(indexable) * 0.1 else "WARNING", sev, title,
                                "%d pages in %d groups: %s" % (n, len(d), ev), site, rec))
        else:
            checks.append(check(cid, cat, "PASS", "INFO", title, "No duplicates across %d indexable pages" % len(indexable), site))

    dup_check("title", "site.duplicate_titles", "onpage", "Duplicate titles", "MEDIUM",
              "Give each indexable page a unique title; templates should interpolate the page's specific entity.")
    dup_check("description", "site.duplicate_descriptions", "onpage", "Duplicate meta descriptions", "LOW",
              "Write unique descriptions for key pages; for large templated sets, generate from page data.")
    dup_check("h1", "site.duplicate_h1", "onpage", "Duplicate H1s", "LOW",
              "Make H1s page-specific.")

    hashes = defaultdict(list)
    for p in indexable:
        if p.get("word_count", 0) > 50:
            hashes[p["content_hash"]].append(p["final_url"])
    dupc = {k: v for k, v in hashes.items() if len(v) > 1}
    if dupc:
        checks.append(check("site.duplicate_content", "content", "FAIL", "HIGH", "Exact duplicate content",
                            "; ".join(str(v[:4]) for v in list(dupc.values())[:5]), site,
                            "Consolidate duplicates: 301 or canonical to one URL, or make each page genuinely distinct."))

    missing_title = [p["final_url"] for p in ok if not p.get("title")]
    missing_desc = [p["final_url"] for p in indexable if not p.get("description")]
    missing_h1 = [p["final_url"] for p in indexable if not p.get("h1")]
    for ids, lst, sev, title in (("site.missing_title", missing_title, "HIGH", "Pages without title"),
                                 ("site.missing_description", missing_desc, "LOW", "Pages without meta description"),
                                 ("site.missing_h1", missing_h1, "MEDIUM", "Pages without H1")):
        if lst:
            checks.append(check(ids, "onpage", "FAIL" if sev == "HIGH" else "WARNING", sev, title,
                                "%d pages: %s" % (len(lst), lst[:8]), site, "Add the missing element (fix in the shared template if many pages are affected)."))

    broken = [p for p in pages.values() if p["status"] is None or (p["status"] and p["status"] >= 400)]
    if broken:
        checks.append(check("site.broken_internal", "internal_links", "FAIL", "HIGH", "Broken internal links",
                            "%d URLs: %s" % (len(broken), ["%s [%s] linked from %s" % (p["url"], p["status"] or p["error"], p["found_on"]) for p in broken[:8]]),
                            site, "Fix the links at the source pages or 301 the dead URLs to the best equivalent."))
    else:
        checks.append(check("site.broken_internal", "internal_links", "PASS", "INFO", "Broken internal links",
                            "None in %d crawled URLs" % len(pages), site))
    redirected = [p for p in pages.values() if p["redirects"]]
    if redirected:
        checks.append(check("site.internal_redirects", "internal_links", "WARNING", "LOW" if len(redirected) < 10 else "MEDIUM",
                            "Internal links to redirects", "%d linked URLs redirect, e.g. %s" % (
                                len(redirected), ["%s -> %s" % (p["url"], p["final_url"]) for p in redirected[:6]]),
                            site, "Update internal links to point at the final URL (saves crawl hops)."))

    deep = [p for p in indexable if p["depth"] > 3]
    if deep:
        checks.append(check("site.depth", "internal_links", "WARNING", "MEDIUM" if len(deep) > len(indexable) * 0.2 else "LOW",
                            "Deep pages", "%d indexable pages >3 clicks from start, e.g. %s" % (len(deep), [p["final_url"] for p in deep[:6]]),
                            site, "Surface important deep pages via hubs, category pages, breadcrumbs or contextual links."))
    weak = [p for p in indexable if p["inlinks"] <= 1 and p["url"] != start]
    if weak:
        checks.append(check("site.weak_inlinks", "internal_links", "WARNING", "MEDIUM" if len(weak) > 5 else "LOW",
                            "Weakly linked pages", "%d pages with <=1 internal inlink, e.g. %s" % (len(weak), [p["final_url"] for p in weak[:8]]),
                            site, "Add contextual links from topically related pages (internal-links module produces source->target suggestions)."))
    no_ctx = [p for p in indexable if p["contextual_inlinks"] == 0 and p["inlinks"] > 0 and p["url"] != start]
    if no_ctx and len(indexable) > 5:
        checks.append(check("site.nav_only_links", "internal_links", "INFO", "LOW", "Pages linked only from navigation",
                            "%d pages receive links only from nav/header/footer, e.g. %s" % (len(no_ctx), [p["final_url"] for p in no_ctx[:6]]),
                            site, "In-content links with descriptive anchors carry more topical context than menu links.",
                            label="INFERRED"))

    crawled_keys = {canon_key(p["final_url"]) for p in pages.values()} | {canon_key(p["url"]) for p in pages.values()}
    orphans = []
    if sitemap_urls:
        orphans = [u for u in sitemap_urls if canon_key(u) not in crawled_keys]
        if orphans:
            hit_limit = bool(queue)
            checks.append(check("site.orphans", "internal_links", "INFO" if hit_limit else "WARNING", "MEDIUM",
                                "Orphan candidates (in sitemap, not reached by crawl)",
                                "%d of %d sitemap URLs not reached%s, e.g. %s" % (
                                    len(orphans), len(sitemap_urls), " (crawl hit --max limit, so this is an upper bound)" if hit_limit else "", orphans[:8]),
                                site, "Link to these pages from relevant hubs or remove them from the sitemap if obsolete.",
                                label="INFERRED" if hit_limit else "OBSERVED"))

    conflict = [p for p in ok if p.get("noindex") and p.get("canonical") and p["canonical"].rstrip("/") != p["final_url"].rstrip("/")]
    if conflict:
        checks.append(check("site.noindex_canonical_conflict", "crawl_index", "WARNING", "MEDIUM", "noindex + canonical to another URL",
                            str([p["final_url"] for p in conflict[:6]]), site, "Mixed signals; use one: canonical (for duplicates) or noindex (for exclusion)."))
    canon_targets = Counter(p["canonical"] for p in ok if p.get("canonical") and p["canonical"].rstrip("/") != p["final_url"].rstrip("/"))
    if canon_targets:
        checks.append(check("site.canonicalized", "crawl_index", "INFO", "INFO", "Canonicalized pages",
                            "%d pages canonicalize elsewhere; top targets: %s" % (sum(canon_targets.values()), canon_targets.most_common(4)), site))
    noindexed = [p["final_url"] for p in ok if p.get("noindex")]
    if noindexed:
        checks.append(check("site.noindex_pages", "crawl_index", "INFO", "INFO", "Noindexed pages",
                            "%d pages: %s" % (len(noindexed), noindexed[:10]), site,
                            "Confirm each is intentional; remove internal links to pages you don't want discovered."))

    paths = [parse.urlsplit(p["final_url"]).path for p in ok]
    upper = [x for x in paths if re.search(r"[A-Z]", x)]
    slash = Counter(x.endswith("/") for x in paths if x not in ("", "/") and "." not in x.rsplit("/", 1)[-1])
    uscore = [x for x in paths if "_" in x]
    hygiene = []
    if upper:
        hygiene.append("%d paths with uppercase (e.g. %s)" % (len(upper), upper[:3]))
    if slash.get(True) and slash.get(False):
        hygiene.append("mixed trailing-slash usage (%d with, %d without)" % (slash[True], slash[False]))
    if uscore:
        hygiene.append("%d paths with underscores" % len(uscore))
    long_urls = [p["final_url"] for p in ok if len(p["final_url"]) > 115]
    if long_urls:
        hygiene.append("%d URLs >115 chars" % len(long_urls))
    if hygiene:
        checks.append(check("site.url_hygiene", "technical", "WARNING", "LOW", "URL structure consistency",
                            "; ".join(hygiene), site, "Prefer lowercase, hyphenated, consistent slash policy; enforce with redirects/canonicals. Don't change working URLs without 301s."))

    thin = [p for p in indexable if p.get("word_count", 0) < 120]
    if thin and len(indexable) >= 5:
        checks.append(check("site.thin_pages", "content", "WARNING", "MEDIUM" if len(thin) > len(indexable) * 0.3 else "LOW",
                            "Low-text indexable pages", "%d of %d indexable pages <120 words of main content, e.g. %s" % (
                                len(thin), len(indexable), [p["final_url"] for p in thin[:6]]),
                            site, "Review by page type: enrich, consolidate or noindex genuinely thin pages. Short is fine when intent is satisfied.",
                            label="INFERRED"))
    slow = [p for p in ok if p.get("ttfb_ms") and p["ttfb_ms"] > 1500]
    if slow:
        checks.append(check("site.slow_pages", "performance", "WARNING", "MEDIUM", "Slow server responses",
                            "%d pages TTFB >1.5s from audit host, e.g. %s" % (len(slow), ["%s %dms" % (p["final_url"], p["ttfb_ms"]) for p in slow[:5]]),
                            site, "Check caching for these templates; confirm with field data."))

    status_counts = Counter(str(p["status"]) for p in pages.values())
    summary = {
        "start": start, "site": site, "crawled": len(pages), "html_pages": html_pages, "max": a.max, "hit_limit": bool(queue),
        "queue_remaining": len(queue), "blocked_by_robots": blocked[:50], "status_counts": dict(status_counts),
        "html_200": len(ok), "indexable": len(indexable), "edges": len(edges),
        "elapsed_s": int(time.time() - started),
        "depth_distribution": dict(Counter(p["depth"] for p in ok)),
    }
    out = {"summary": summary, "pages": list(pages.values()), "orphans": orphans[:500], "checks": checks}
    if a.out:
        import json
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, ensure_ascii=False, default=str)
        emit({"summary": summary, "checks": checks, "written": a.out})
    else:
        emit(out)


if __name__ == "__main__":
    main()
