#!/usr/bin/env python3
"""Raw HTML vs JavaScript-rendered DOM comparison.

Usage:
  render.py <url> [--mobile]

Needs Playwright (pip install playwright && playwright install chromium).
If unavailable, reports that and exits cleanly - never guess rendered
content. Compares title, meta description, canonical, robots, H1, word
count, internal links and JSON-LD between raw and rendered. Big gaps mean
search engines must render to see content, and most AI crawlers do not
execute JavaScript at all.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import check, emit, fetch, normalize_url, text_of  # noqa: E402
from htmlparse import extract  # noqa: E402


def summary(f):
    return {"title": f["title"], "description": f["meta_description"],
            "canonical": f["canonicals"][0] if f["canonicals"] else None,
            "robots": " ".join(f["meta_robots"]), "h1": [h["text"] for h in f["headings"] if h["level"] == 1],
            "words": f["main_word_count"],
            "internal_links": len({a["url"] for a in f["anchors"] if a["kind"] == "internal"}),
            "jsonld": len([b for b in f["jsonld"] if b["ok"]])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--mobile", action="store_true")
    a = ap.parse_args()
    url = normalize_url(a.url)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        emit({"url": url, "available": False, "checks": [check(
            "render.unavailable", "crawl_index", "INFO", "INFO", "Rendered comparison not run",
            "Playwright not installed", url,
            "Install with: pip3 install playwright && python3 -m playwright install chromium. Or compare with Google's URL Inspection tool.")]})
        return
    r = fetch(url)
    raw = summary(extract(text_of(r), r["final_url"]))
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(**(p.devices["Pixel 7"] if a.mobile else {}))
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        html = page.content()
        overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        b.close()
    ren = summary(extract(html, r["final_url"]))
    checks = []
    diffs = []
    for k in ("title", "description", "canonical", "robots", "h1"):
        if raw[k] != ren[k]:
            diffs.append("%s: raw=%r rendered=%r" % (k, raw[k], ren[k]))
    if raw["robots"] != ren["robots"] and "noindex" in (raw["robots"] + ren["robots"]):
        checks.append(check("render.robots_change", "crawl_index", "FAIL", "CRITICAL", "JS changes robots directives",
                            "raw=%r rendered=%r" % (raw["robots"], ren["robots"]), url,
                            "Never toggle noindex with JavaScript; Google may not render a page served with noindex."))
    gap = ren["words"] - raw["words"]
    if ren["words"] and gap > max(100, ren["words"] * 0.3):
        checks.append(check("render.content_gap", "crawl_index", "FAIL", "HIGH", "Content depends on JavaScript",
                            "raw %d words vs rendered %d; links raw %d vs rendered %d" % (raw["words"], ren["words"], raw["internal_links"], ren["internal_links"]),
                            url, "Server-render (SSR/SSG) primary content and links. Googlebot renders later; most AI crawlers never do."))
    else:
        checks.append(check("render.content_gap", "crawl_index", "PASS", "INFO", "Raw vs rendered content",
                            "raw %d words / rendered %d" % (raw["words"], ren["words"]), url))
    if diffs:
        checks.append(check("render.meta_diff", "crawl_index", "WARNING", "MEDIUM", "Head tags differ after rendering",
                            "; ".join(diffs), url, "Emit final metadata in the server response."))
    if a.mobile and overflow:
        checks.append(check("mobile.overflow", "technical", "WARNING", "MEDIUM", "Horizontal overflow on mobile",
                            "document wider than viewport", url, "Find the overflowing element (fixed widths, wide tables/images)."))
    emit({"url": url, "available": True, "raw": raw, "rendered": ren, "checks": checks})


if __name__ == "__main__":
    main()
