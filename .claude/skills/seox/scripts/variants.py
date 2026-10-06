#!/usr/bin/env python3
"""Host/protocol/URL-variant consistency and soft-404 checks.

Usage:
  variants.py <url>

Checks that http->https, www<->non-www, trailing-slash and uppercase
variants each 301/308 to one preferred URL, and that a nonexistent path
returns 404/410 (not 200 = soft 404).
"""

import argparse
import os
import random
import string
import sys
from urllib import parse

sys.path.insert(0, os.path.dirname(__file__))
from common import check, emit, fetch, normalize_url  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    a = ap.parse_args()
    base = fetch(normalize_url(a.url), html_only=True)
    pref = base["final_url"]
    p = parse.urlsplit(pref)
    host = p.netloc
    alt_host = host[4:] if host.startswith("www.") else "www." + host
    path = p.path or "/"
    variants = {
        "http": parse.urlunsplit(("http", host, path, p.query, "")),
        "alt_host": parse.urlunsplit(("https", alt_host, path, p.query, "")),
        "http_alt_host": parse.urlunsplit(("http", alt_host, path, p.query, "")),
    }
    if path != "/":
        variants["slash_toggle"] = parse.urlunsplit(("https", host, path[:-1] if path.endswith("/") else path + "/", p.query, ""))
        if path != path.upper():
            variants["uppercase"] = parse.urlunsplit(("https", host, path.upper(), p.query, ""))
    checks, rows = [], []
    for name, v in variants.items():
        r = fetch(v, timeout=12, html_only=True)
        codes = [c["status"] for c in r["chain"]]
        ok_final = r["final_url"].rstrip("/") == pref.rstrip("/")
        rows.append({"variant": name, "url": v, "chain": codes, "status": r["status"], "final": r["final_url"], "error": r.get("error")})
        if r["status"] is None:
            if name in ("alt_host", "http_alt_host"):
                continue  # host simply not served
            checks.append(check("variants.%s" % name, "technical", "WARNING", "LOW", "Variant unreachable: %s" % name, "%s: %s" % (v, r.get("error")), v, "Make the variant redirect to the preferred URL."))
        elif name == "uppercase":
            if r["status"] == 200 and not codes:
                checks.append(check("variants.case", "crawl_index", "WARNING", "LOW", "Uppercase URL serves 200",
                                    v, v, "Redirect or canonicalize case variants (rely on canonical if redirects are hard)."))
        elif not ok_final or r["status"] != 200:
            checks.append(check("variants.%s" % name, "crawl_index", "FAIL", "HIGH" if name.startswith("http") or name == "alt_host" else "MEDIUM",
                                "Variant not consolidated: %s" % name,
                                "%s -> %s [%s, chain %s]" % (v, r["final_url"], r["status"], codes), v,
                                "301/308 every variant to %s." % pref))
        elif not codes:
            checks.append(check("variants.%s" % name, "crawl_index", "WARNING", "MEDIUM", "Duplicate variant serves 200: %s" % name,
                                "%s returns 200 without redirect" % v, v, "Redirect to the preferred URL (canonical alone is a weaker signal)."))
        elif any(c in (302, 303, 307) for c in codes) or len(codes) > 2:
            checks.append(check("variants.%s" % name, "technical", "WARNING", "LOW", "Weak redirect: %s" % name,
                                "%s chain %s" % (v, codes), v, "Use a single permanent (301/308) hop."))
        else:
            checks.append(check("variants.%s" % name, "crawl_index", "PASS", "INFO", "Variant %s" % name, "%s -> %s %s" % (v, pref, codes), v))
    junk = "/" + "".join(random.choice(string.ascii_lowercase) for _ in range(14)) + "-seox-404-test"
    r = fetch(parse.urlunsplit(("https", host, junk, "", "")), timeout=12, html_only=True)
    if r["status"] == 200:
        checks.append(check("variants.soft404", "crawl_index", "FAIL", "HIGH", "Soft 404",
                            "Nonexistent %s returned 200%s" % (junk, " after redirect to %s" % r["final_url"] if r["chain"] else ""),
                            pref, "Return a real 404/410 status for missing pages (SPAs: configure server/edge 404s for unknown routes)."))
    else:
        checks.append(check("variants.soft404", "crawl_index", "PASS", "INFO", "404 handling", "Nonexistent path -> %s" % r["status"], pref))
    emit({"preferred": pref, "variants": rows, "checks": checks})


if __name__ == "__main__":
    main()
