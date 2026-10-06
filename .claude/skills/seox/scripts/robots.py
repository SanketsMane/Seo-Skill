#!/usr/bin/env python3
"""robots.txt analysis with Google-style matching + crawler access matrix.

Usage:
  robots.py <site-url> [--paths / /blog/ /products/x] [--file robots.txt]

Matching follows RFC 9309 / Google: user-agent groups are merged, the most
specific product token wins (fallback *), rule precedence is longest path
match, ties go to allow, `*` and `$` are supported.

The crawler list separates PURPOSE (search index vs AI search vs
user-initiated fetch vs model training). Blocking a training crawler does
not remove you from that company's search product, and vice versa. The
list is a snapshot (see references/ai-crawlers.md) - verify vendor docs
before giving definitive advice.
"""

import argparse
import re
import sys
from urllib import parse

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import check, emit, fetch, normalize_url, origin, text_of  # noqa: E402

CRAWLERS = [
    # token, operator, purpose
    ("Googlebot", "Google", "search-index (Google Search incl. AI Overviews/AI Mode)"),
    ("Google-Extended", "Google", "control-token: Gemini training/grounding (NOT Search/AI Overviews)"),
    ("Bingbot", "Microsoft", "search-index (Bing, Copilot grounding)"),
    ("OAI-SearchBot", "OpenAI", "ai-search (ChatGPT search results)"),
    ("ChatGPT-User", "OpenAI", "user-fetch (fetches on behalf of a ChatGPT user)"),
    ("GPTBot", "OpenAI", "training"),
    ("Claude-SearchBot", "Anthropic", "ai-search"),
    ("Claude-User", "Anthropic", "user-fetch"),
    ("ClaudeBot", "Anthropic", "training"),
    ("PerplexityBot", "Perplexity", "ai-search (Perplexity index)"),
    ("Perplexity-User", "Perplexity", "user-fetch"),
    ("Applebot", "Apple", "search-index (Siri/Spotlight/Safari)"),
    ("Applebot-Extended", "Apple", "control-token: Apple AI training"),
    ("DuckAssistBot", "DuckDuckGo", "ai-search (DuckAssist answers)"),
    ("Amazonbot", "Amazon", "search/assistant + training"),
    ("meta-externalagent", "Meta", "training / AI"),
    ("CCBot", "Common Crawl", "training corpus (used by many LLMs)"),
    ("Bytespider", "ByteDance", "training"),
    ("MistralAI-User", "Mistral", "user-fetch"),
]
SEARCH_CRITICAL = {"Googlebot", "Bingbot"}
AI_SEARCH = {"OAI-SearchBot", "Claude-SearchBot", "PerplexityBot", "DuckAssistBot", "ChatGPT-User",
             "Claude-User", "Perplexity-User"}


def parse_robots(text):
    groups = []  # list of {"agents": [...], "rules": [(type, path, line)]}
    sitemaps, issues, other = [], [], []
    cur = None
    last_was_agent = False
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            issues.append("line %d: no ':' separator -> %r" % (n, raw[:80]))
            continue
        key, val = line.split(":", 1)
        key = key.strip().lower()
        val = val.strip()
        if key in ("user-agent", "useragent", "user agent"):
            if not last_was_agent or cur is None:
                cur = {"agents": [], "rules": []}
                groups.append(cur)
            cur["agents"].append(val.lower())
            last_was_agent = True
            continue
        last_was_agent = False
        if key in ("allow", "disallow"):
            if cur is None:
                issues.append("line %d: %s before any user-agent (ignored)" % (n, key))
                continue
            cur["rules"].append((key, val, n))
        elif key == "sitemap":
            sitemaps.append(val)
        elif key in ("crawl-delay", "host", "clean-param", "noindex", "request-rate"):
            other.append({"line": n, "directive": key, "value": val})
            if key == "noindex":
                issues.append("line %d: 'noindex' in robots.txt is unsupported by Google since 2019" % n)
        else:
            issues.append("line %d: unknown directive %r" % (n, key))
    return groups, sitemaps, issues, other


def _pattern_rx(path):
    rx = ""
    for ch in path:
        if ch == "*":
            rx += ".*"
        elif ch == "$":
            rx += "$"
        else:
            rx += re.escape(ch)
    return re.compile("^" + rx)


def rules_for(groups, agent):
    agent = agent.lower()
    best_len, matched = -1, []
    for g in groups:
        for a in g["agents"]:
            if a != "*" and agent.startswith(a) and len(a) >= best_len:
                if len(a) > best_len:
                    best_len, matched = len(a), []
                matched.append(g)
    if not matched:
        matched = [g for g in groups if "*" in g["agents"]]
        token = "*" if matched else None
    else:
        token = matched[0]["agents"][0]
    rules = [r for g in matched for r in g["rules"]]
    return token, rules


def is_allowed(rules, path):
    best = None  # (length, type, rule)
    for typ, pat, line in rules:
        if typ == "disallow" and pat == "":
            continue
        if not pat:
            continue
        if _pattern_rx(pat).match(path):
            ln = len(pat)
            if best is None or ln > best[0] or (ln == best[0] and typ == "allow"):
                best = (ln, typ, "%s: %s (line %d)" % (typ.title(), pat, line))
    if best is None:
        return True, "no matching rule"
    return best[1] == "allow", best[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("site")
    ap.add_argument("--paths", nargs="*", default=["/"])
    ap.add_argument("--file", help="use a local robots.txt instead of fetching")
    a = ap.parse_args()
    site = origin(normalize_url(a.site))
    robots_url = site + "/robots.txt"
    checks = []

    if a.file:
        text, status = open(a.file, encoding="utf-8", errors="replace").read(), 200
        resp = {"headers": {}, "chain": []}
    else:
        resp = fetch(robots_url, max_bytes=600 * 1024)
        status = resp["status"]
        text = text_of(resp) if status and status < 400 else ""

    if status is None:
        checks.append(check("robots.fetch", "crawl_index", "FAIL", "HIGH", "robots.txt reachable",
                            "Fetch error: %s" % resp.get("error"), robots_url,
                            "Unreachable robots.txt can stall crawling; make it return 200 (or 404 if you have no rules)."))
    elif status >= 500:
        checks.append(check("robots.fetch", "crawl_index", "FAIL", "CRITICAL", "robots.txt server error",
                            "HTTP %s - Google treats prolonged 5xx on robots.txt as 'disallow all'" % status, robots_url,
                            "Fix the server error immediately."))
    elif status >= 400:
        checks.append(check("robots.fetch", "crawl_index", "INFO", "INFO", "robots.txt missing",
                            "HTTP %s - crawlers treat this as 'allow all'" % status, robots_url,
                            "Optional: add a robots.txt with your Sitemap: line."))
    else:
        ct = resp["headers"].get("content-type", "")
        checks.append(check("robots.fetch", "crawl_index", "PASS", "INFO", "robots.txt reachable",
                            "HTTP %s, %d bytes, content-type %s%s" % (status, len(text.encode()), ct or "?",
                                                                       ", redirected" if resp["chain"] else ""), robots_url))
        if ct and "text/plain" not in ct:
            checks.append(check("robots.content_type", "crawl_index", "WARNING", "LOW", "robots.txt content type",
                                ct, robots_url, "Serve robots.txt as text/plain."))
        if len(text.encode()) > 500 * 1024:
            checks.append(check("robots.size", "crawl_index", "WARNING", "MEDIUM", "robots.txt size",
                                "%d bytes; Google ignores content after 500 KiB" % len(text.encode()), robots_url,
                                "Consolidate rules."))
        if "<html" in text[:500].lower():
            checks.append(check("robots.html", "crawl_index", "FAIL", "HIGH", "robots.txt returns HTML",
                                "Body looks like an HTML page (soft-404 / SPA fallback)", robots_url,
                                "Serve a real text robots.txt or a 404."))

    groups, sitemaps, issues, other = parse_robots(text)
    if issues:
        checks.append(check("robots.syntax", "crawl_index", "WARNING", "LOW", "robots.txt syntax",
                            "; ".join(issues[:8]), robots_url, "Fix or remove unsupported lines."))

    star_token, star_rules = rules_for(groups, "*")
    if any(t == "disallow" and p == "/" for t, p, _ in star_rules):
        checks.append(check("robots.disallow_all", "crawl_index", "FAIL", "CRITICAL", "Disallow all (User-agent: *)",
                            "User-agent: * has 'Disallow: /'", robots_url,
                            "Remove unless this is a staging site. Check whether specific bots get an Allow group."))

    matrix = []
    for token, op, purpose in CRAWLERS:
        matched, rules = rules_for(groups, token)
        row = {"crawler": token, "operator": op, "purpose": purpose, "group": matched, "paths": {}}
        for path in a.paths:
            ok, why = is_allowed(rules, path)
            row["paths"][path] = {"allowed": ok, "rule": why}
        matrix.append(row)

    ai_blocked, train_blocked = [], []
    for row in matrix:
        blocked = [p for p, r in row["paths"].items() if not r["allowed"]]
        if not blocked:
            continue
        ev = "%s blocked for %s by %s" % (row["crawler"], blocked, row["paths"][blocked[0]]["rule"])
        if row["crawler"] in SEARCH_CRITICAL:
            checks.append(check("robots.block.%s" % row["crawler"].lower(), "crawl_index", "FAIL", "CRITICAL",
                                "%s blocked" % row["crawler"], ev, robots_url,
                                "Unblock these paths for search crawlers if they should rank (robots.txt blocks crawling, not indexing - blocked URLs can still be indexed without content)."))
        elif row["crawler"] in AI_SEARCH:
            ai_blocked.append(ev)
        else:
            train_blocked.append(ev + " [%s]" % row["purpose"])
    if ai_blocked:
        checks.append(check("robots.block.ai_search", "geo", "WARNING", "MEDIUM", "AI-search / user-fetch crawlers blocked",
                            "; ".join(ai_blocked), robots_url,
                            "These bots retrieve pages for AI answers and citations. Allow them if AI-search visibility is a goal - this is a business decision, not an error."))
    else:
        checks.append(check("robots.block.ai_search", "geo", "PASS", "INFO", "AI-search crawlers",
                            "No AI-search/user-fetch crawler is blocked for the tested paths", robots_url))
    if train_blocked:
        checks.append(check("robots.block.training", "geo", "INFO", "INFO", "Training crawlers blocked",
                            "; ".join(train_blocked), robots_url,
                            "Policy choice; does not affect Google/Bing rankings or AI-search retrieval by the separate search bots."))
    g_token, _ = rules_for(groups, "Googlebot")
    if g_token and g_token != "*" and star_rules:
        checks.append(check("robots.googlebot_group", "crawl_index", "INFO", "INFO", "Googlebot has its own group",
                            "A '%s' group exists, so rules under 'User-agent: *' do NOT apply to Googlebot" % g_token, robots_url,
                            "Confirm the Googlebot group repeats any '*' disallows you rely on (common mistake)."))

    if not a.file and status and status < 400:
        smap_check = "Sitemap lines: %s" % (sitemaps or "none")
        checks.append(check("robots.sitemap_ref", "crawl_index", "PASS" if sitemaps else "WARNING",
                            "LOW", "Sitemap referenced in robots.txt", smap_check, robots_url,
                            "Add 'Sitemap: https://.../sitemap.xml' (absolute URL)."))
        for s in sitemaps:
            if not s.startswith("http"):
                checks.append(check("robots.sitemap_abs", "crawl_index", "WARNING", "LOW", "Sitemap URL not absolute",
                                    s, robots_url, "Sitemap directives must use absolute URLs."))

    llms = None
    if not a.file:
        r = fetch(site + "/llms.txt", max_bytes=200 * 1024)
        body = text_of(r) if r["status"] == 200 else ""
        looks_html = "<html" in body[:500].lower()
        llms = {"status": r["status"], "bytes": len(body.encode()), "html_fallback": looks_html,
                "head": body[:600] if body and not looks_html else ""}
        checks.append(check("geo.llms_txt", "geo", "INFO", "INFO", "llms.txt",
                            "HTTP %s%s" % (r["status"], " (HTML fallback, not a real file)" if looks_html else
                                           (", %d bytes" % llms["bytes"] if body else "")), site + "/llms.txt",
                            "Optional proposal; Google Search does not use it and adoption by AI providers is unconfirmed. Low priority."))

    emit({"robots_url": robots_url, "status": status, "groups": groups, "sitemaps": sitemaps,
          "other_directives": other, "matrix": matrix, "llms_txt": llms, "raw": text[:20000], "checks": checks})


if __name__ == "__main__":
    main()
