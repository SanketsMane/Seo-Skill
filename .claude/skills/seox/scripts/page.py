#!/usr/bin/env python3
"""Deep single-page SEO analysis.

Usage:
  page.py <url> [--check-links 40] [--image-sizes 25] [--text] [--ua googlebot]
  page.py --file page.html --base-url https://example.com/page

Emits JSON: overview, facts, checks (common.check shape). Detects what is
measurable from HTML + headers; anything needing judgment (search intent,
E-E-A-T, topical coverage) is left to the skill module, which reads the
`main_text` returned with --text.
"""

import argparse
import datetime
import re
import sys
from collections import Counter
from urllib import parse

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import (DEFAULT_UA, check, curl_http_version, emit, fetch,  # noqa: E402
                    normalize_url, text_of)
from htmlparse import extract  # noqa: E402

UAS = {
    "default": DEFAULT_UA,
    "googlebot": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36 "
                 "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "bingbot": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
}

GENERIC_ANCHORS = {
    "click here", "here", "read more", "learn more", "more", "this", "link",
    "details", "more info", "continue", "go", "click", "this page", "see more",
    "find out more", "view more", "info",
}
PLACEHOLDER_RX = re.compile(
    r"lorem ipsum|dolor sit amet|\[object object\]|\bundefined\b|\{\{\s*\w+|"
    r"your (title|headline|text) here|coming soon|todo:|placeholder text|"
    r"sample text|insert (text|content) here", re.I)
STOP = set("""a about above after again against all am an and any are as at be because been
before being below between both but by can did do does doing down during each few for from
further had has have having he her here hers herself him himself his how i if in into is it
its itself just me more most my myself no nor not now of off on once only or other our ours
ourselves out over own same she should so some such than that the their theirs them themselves
then there these they this those through to too under until up very was we were what when
where which while who whom why will with you your yours yourself yourselves""".split())
QUESTION_START = re.compile(
    r"^(what|how|why|when|where|which|who|whom|whose|can|should|is|are|does|do|will|"
    r"was|were|could|would)\b", re.I)

# Approximate Arial 20px glyph widths used by Google desktop titles (estimate only).
_NARROW = set("ijl.,;:'|!`ІI ")
_MID = set("frt()[]{}-\"/*")
_WIDE = set("mwMW%@")
_CAPS = set("ABCDEFGHKNOPQRSUVXYZ&")


def title_px(s):
    w = 0.0
    for ch in s or "":
        if ch == " ":
            w += 5.6
        elif ch in _NARROW:
            w += 4.5
        elif ch in _MID:
            w += 6.7
        elif ch in _WIDE:
            w += 16.7
        elif ch in _CAPS:
            w += 13.3
        elif ch.isdigit():
            w += 11.1
        else:
            w += 11.1 if ch.isupper() else 10.0
    return int(round(w))


def syllables(word):
    word = word.lower()
    if len(word) <= 3:
        return 1
    word = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", word)
    word = re.sub(r"^y", "", word)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", word)))


def readability(text):
    sentences = [s for s in re.split(r"[.!?]+[\s\n]", text) if len(s.split()) >= 3]
    words = re.findall(r"[A-Za-z]+", text)
    if len(sentences) < 3 or len(words) < 80:
        return None
    syl = sum(syllables(w) for w in words)
    wps = len(words) / len(sentences)
    fre = 206.835 - 1.015 * wps - 84.6 * (syl / len(words))
    long_sent = sum(1 for s in sentences if len(s.split()) > 30)
    return {"flesch_reading_ease": round(fre, 1), "avg_words_per_sentence": round(wps, 1),
            "sentences": len(sentences), "long_sentences_over_30w": long_sent}


def tokens(s):
    return [t for t in re.findall(r"[a-z0-9][a-z0-9'-]*", (s or "").lower())]


def overlap(a, b):
    ta = {t for t in tokens(a) if t not in STOP}
    tb = {t for t in tokens(b) if t not in STOP}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(min(len(ta), len(tb)))


def img_format(src):
    if not src:
        return "unknown"
    if src.startswith("data:"):
        m = re.match(r"data:image/([\w+.-]+)", src)
        return (m.group(1) if m else "data").replace("svg+xml", "svg")
    path = parse.urlsplit(src).path.lower()
    m = re.search(r"\.(avif|webp|jpe?g|png|gif|svg|bmp|ico|tiff?)$", path)
    if m:
        return m.group(1).replace("jpeg", "jpg")
    q = parse.urlsplit(src).query.lower()
    m = re.search(r"(?:fm|format|f)=(avif|webp|jpe?g|png|gif)", q)
    return m.group(1).replace("jpeg", "jpg") if m else "unknown"


def weak_alt_reason(alt, src):
    a = (alt or "").strip()
    low = a.lower()
    fname = parse.unquote(parse.urlsplit(src or "").path.rsplit("/", 1)[-1]).lower()
    if re.match(r"^(img|image|dsc|pxl|screenshot|photo)[_ -]?\d+", low) or re.search(
            r"\.(jpe?g|png|gif|webp|avif|svg)$", low):
        return "looks like a filename"
    if low in ("image", "photo", "picture", "img", "logo", "icon", "banner", "graphic", "untitled"):
        return "generic single word"
    if fname and low == fname.rsplit(".", 1)[0].replace("-", " ").replace("_", " "):
        return "duplicates filename"
    if len(a) > 150:
        return "over 150 characters (likely a description dump)"
    if a.count(",") >= 4 and len(set(tokens(a))) < len(tokens(a)) * 0.7:
        return "comma-separated repeated terms (possible keyword stuffing)"
    return None


# ----------------------------------------------------------------- checks --

def server_checks(resp, url, http_versions):
    c = []
    h = resp["headers"]
    st = resp["status"]
    final = resp["final_url"]
    if st is None:
        c.append(check("http.status", "technical", "FAIL", "CRITICAL", "Page fetch",
                       "Fetch failed: %s" % resp.get("error"), url,
                       "Make the URL reachable for crawlers; verify DNS, TLS, firewall/WAF bot rules."))
        return c
    if st >= 500:
        c.append(check("http.status", "technical", "FAIL", "CRITICAL", "HTTP status",
                       "Final status %s" % st, final, "Fix the server error; 5xx responses slow crawling and drop pages from the index if persistent."))
    elif st in (404, 410):
        c.append(check("http.status", "technical", "FAIL", "CRITICAL", "HTTP status",
                       "Final status %s" % st, final, "Restore the page or redirect it (301) to the closest equivalent; remove internal links to it."))
    elif st >= 400:
        c.append(check("http.status", "technical", "FAIL", "HIGH", "HTTP status",
                       "Final status %s (may be bot blocking / WAF)" % st, final,
                       "Check whether the server/WAF blocks crawler user agents; serve 200 to verified search bots."))
    else:
        c.append(check("http.status", "technical", "PASS", "INFO", "HTTP status", "200 OK" if st == 200 else str(st), final))

    chain = resp["chain"]
    if chain:
        hops = " -> ".join("%s [%s]" % (x["url"], x["status"]) for x in chain) + " -> " + final
        temp = [x for x in chain if x["status"] in (302, 303, 307)]
        if len(chain) > 2:
            c.append(check("http.redirect_chain", "technical", "WARNING", "MEDIUM", "Redirect chain",
                           "%d hops: %s" % (len(chain), hops), url,
                           "Collapse to a single 301/308 hop from the origin URL to the final URL and update internal links to point at the final URL."))
        elif temp:
            c.append(check("http.redirect_type", "technical", "WARNING", "LOW", "Temporary redirect",
                           hops, url, "Use 301/308 for permanent moves so signals consolidate on the target."))
        else:
            c.append(check("http.redirect_chain", "technical", "INFO", "INFO", "Redirect", hops, url))

    if final.startswith("https://"):
        c.append(check("https.enabled", "technical", "PASS", "INFO", "HTTPS", "Served over HTTPS", final))
    else:
        c.append(check("https.enabled", "technical", "FAIL", "HIGH", "HTTPS", "Final URL is plain HTTP", final,
                       "Serve the site over HTTPS and 301 all HTTP URLs to HTTPS."))
    if resp.get("tls_verify_error"):
        c.append(check("https.certificate", "technical", "WARNING", "HIGH", "TLS certificate",
                       "Verification failed from audit host: %s" % resp["tls_verify_error"], final,
                       "Confirm the certificate chain is complete and valid (check with an external SSL tester; this can also be a local trust-store issue).",
                       label="INFERRED"))

    v = http_versions or {}
    if v.get("h2") or v.get("h3"):
        best = "HTTP/3" if v.get("h3") == "3" else ("HTTP/2" if v.get("h2") == "2" else "HTTP/%s" % v.get("h2"))
        status = "PASS" if best in ("HTTP/2", "HTTP/3") else "WARNING"
        c.append(check("http.version", "performance", status, "LOW", "HTTP protocol",
                       "Negotiated %s (curl probe: h2=%s, h3=%s)" % (best, v.get("h2"), v.get("h3")), final,
                       "Enable HTTP/2 (and ideally HTTP/3) at the CDN/server for multiplexed asset loading."))

    enc = h.get("content-encoding", "")
    if enc:
        c.append(check("http.compression", "performance", "PASS", "INFO", "Compression", "content-encoding: %s" % enc, final))
    elif resp.get("raw_size", 0) > 2048:
        # Edge caches can differ per node; re-probe before calling it a failure.
        probes = [fetch(final, max_bytes=4096, timeout=10)["headers"].get("content-encoding") for _ in range(3)]
        hits = [p for p in probes if p]
        if hits:
            c.append(check("http.compression", "performance", "WARNING", "LOW", "Compression",
                           "Inconsistent: %d of 4 requests compressed (%s)" % (len(hits), hits[0]), final,
                           "Some edge/cache nodes serve uncompressed HTML; check CDN/cache config so every node compresses."))
        else:
            c.append(check("http.compression", "performance", "FAIL", "MEDIUM", "Compression",
                           "No content-encoding on %d-byte HTML across 4 requests (requested gzip)" % resp["raw_size"], final,
                           "Enable gzip or Brotli for text/html, CSS, JS, JSON, SVG at the server or CDN."))

    cc = h.get("cache-control", "")
    c.append(check("http.cache_control", "performance", "INFO", "INFO", "HTML caching",
                   "cache-control: %s | etag: %s | last-modified: %s" % (
                       cc or "(none)", "yes" if h.get("etag") else "no", h.get("last-modified", "(none)")), final))

    ttfb = resp.get("ttfb_ms")
    if ttfb is not None:
        if ttfb > 1800:
            c.append(check("http.ttfb", "performance", "FAIL", "HIGH", "Server response time",
                           "TTFB ~%d ms from audit host (single sample)" % ttfb, final,
                           "Investigate server/database time, enable full-page or edge caching. Re-measure with field data (CrUX) before acting.", label="OBSERVED"))
        elif ttfb > 800:
            c.append(check("http.ttfb", "performance", "WARNING", "MEDIUM", "Server response time",
                           "TTFB ~%d ms from audit host (single sample; 'good' guidance is <=800 ms)" % ttfb, final,
                           "Add caching/CDN; confirm with field data since one sample from one location is noisy."))
        else:
            c.append(check("http.ttfb", "performance", "PASS", "INFO", "Server response time", "TTFB ~%d ms (single sample)" % ttfb, final))

    size = len(resp.get("body") or b"")
    if size > 15 * 1024 * 1024:
        c.append(check("html.size", "technical", "FAIL", "HIGH", "HTML size",
                       "%.1f MB decoded HTML; Googlebot documents processing only the first 15 MB" % (size / 1048576.0), final,
                       "Move inline data/assets out of the HTML document."))
    elif size > 1024 * 1024:
        c.append(check("html.size", "performance", "WARNING", "MEDIUM", "HTML size",
                       "%.0f KB decoded HTML" % (size / 1024.0), final,
                       "Large documents slow parsing; check for inlined JSON state, SVG sprites or base64 images."))
    else:
        c.append(check("html.size", "performance", "PASS", "INFO", "HTML size", "%.0f KB decoded HTML" % (size / 1024.0), final))

    sec = {
        "strict-transport-security": "HSTS", "content-security-policy": "CSP",
        "x-content-type-options": "X-Content-Type-Options", "referrer-policy": "Referrer-Policy",
        "permissions-policy": "Permissions-Policy",
    }
    missing = [n for k, n in sec.items() if k not in h]
    framing = "x-frame-options" in h or "frame-ancestors" in h.get("content-security-policy", "")
    if not framing:
        missing.append("X-Frame-Options/frame-ancestors")
    if missing:
        sev = "MEDIUM" if "HSTS" in missing and final.startswith("https") else "LOW"
        c.append(check("security.headers", "technical", "WARNING", sev, "Security headers",
                       "Missing: " + ", ".join(missing), final,
                       "Add the missing headers at the server/CDN. These are trust/security hygiene, not direct ranking factors; HSTS matters most for HTTPS consistency."))
    else:
        c.append(check("security.headers", "technical", "PASS", "INFO", "Security headers", "All common security headers present", final))

    leaks = []
    if re.search(r"\d", h.get("server", "")):
        leaks.append("server: " + h["server"])
    for k in ("x-powered-by", "x-aspnet-version", "x-aspnetmvc-version", "x-generator"):
        if k in h:
            leaks.append("%s: %s" % (k, h[k]))
    if leaks:
        c.append(check("security.leakage", "technical", "WARNING", "LOW", "Server information leakage",
                       "; ".join(leaks), final, "Remove version-revealing headers (not an SEO ranking issue; security hygiene)."))

    xr = h.get("x-robots-tag", "")
    if xr:
        bad = re.search(r"noindex|none", xr, re.I)
        c.append(check("index.x_robots_tag", "crawl_index", "FAIL" if bad else "INFO",
                       "CRITICAL" if bad else "INFO", "X-Robots-Tag header", "x-robots-tag: " + xr, final,
                       "Remove noindex from the X-Robots-Tag header if this page should be indexed."))
    return c


def index_checks(f, final, status):
    c = []
    robots = " ".join(f["meta_robots"]).lower()
    if re.search(r"\bnoindex\b|\bnone\b", robots):
        c.append(check("index.meta_robots", "crawl_index", "FAIL", "CRITICAL", "Meta robots noindex",
                       "meta robots: %s" % robots, final,
                       "Remove noindex if this page should rank. If intentional (thank-you, cart, filters), ignore and keep it out of the sitemap."))
    elif "nofollow" in robots:
        c.append(check("index.meta_robots", "crawl_index", "WARNING", "MEDIUM", "Meta robots nofollow",
                       "meta robots: %s" % robots, final, "Page-level nofollow stops link discovery from this page; remove unless intentional."))
    else:
        c.append(check("index.meta_robots", "crawl_index", "PASS", "INFO", "Meta robots",
                       "meta robots: %s" % (robots or "(none; defaults to index,follow)"), final))
    for k, vals in f["meta_robots_by_bot"].items():
        if k != "robots" and any(re.search(r"noindex", v, re.I) for v in vals):
            c.append(check("index.meta_bot_specific", "crawl_index", "WARNING", "HIGH", "Bot-specific noindex",
                           "%s: %s" % (k, vals), final, "Confirm this bot-specific noindex is intentional."))
        for v in vals:
            if re.search(r"max-snippet:\s*0|nosnippet", v, re.I):
                c.append(check("index.snippet_restrict", "geo", "WARNING", "MEDIUM", "Snippet restrictions",
                               "%s: %s" % (k, v), final,
                               "nosnippet / max-snippet:0 also limits use in AI Overviews and rich snippets. Keep only if deliberate.", label="OBSERVED"))

    cans = f["canonicals"]
    if not cans:
        c.append(check("canonical.present", "crawl_index", "WARNING", "MEDIUM", "Canonical tag",
                       "No rel=canonical found", final,
                       "Add a self-referencing absolute canonical to consolidate duplicate URL variants (parameters, trailing slash, case)."))
    elif len(set(cans)) > 1:
        c.append(check("canonical.multiple", "crawl_index", "FAIL", "HIGH", "Multiple canonicals",
                       "Found %d different canonicals: %s" % (len(set(cans)), cans), final,
                       "Emit exactly one canonical; conflicting canonicals are ignored by Google."))
    else:
        can = cans[0]
        absu = parse.urljoin(final, can)
        norm = lambda u: u.rstrip("/").lower()
        if not re.match(r"^https?://", can):
            c.append(check("canonical.relative", "crawl_index", "WARNING", "LOW", "Relative canonical",
                           "canonical href=%s" % can, final, "Use an absolute URL in the canonical."))
        if norm(absu) == norm(final):
            c.append(check("canonical.self", "crawl_index", "PASS", "INFO", "Canonical", "Self-referencing: %s" % absu, final))
        else:
            c.append(check("canonical.self", "crawl_index", "WARNING", "HIGH", "Canonical points elsewhere",
                           "Final URL %s declares canonical %s" % (final, absu), final,
                           "If this page should rank on its own, make the canonical self-referencing. If it is a duplicate, this is correct - confirm the target returns 200 and is indexable."))
        if absu.startswith("http://") and final.startswith("https://"):
            c.append(check("canonical.protocol", "crawl_index", "FAIL", "HIGH", "Canonical protocol",
                           "HTTPS page canonicalizes to HTTP: %s" % absu, final, "Point the canonical at the HTTPS URL."))
    if f["canonical_in_body"]:
        c.append(check("canonical.in_body", "crawl_index", "WARNING", "MEDIUM", "Canonical outside <head>",
                       str(f["canonical_in_body"]), final, "Move rel=canonical into <head>; Google ignores it in <body>."))
    return c


def meta_checks(f, final):
    c = []
    titles = f["titles"]
    t = f["title"]
    if not t:
        c.append(check("title.present", "onpage", "FAIL", "HIGH", "Title tag", "No <title> (or empty)", final,
                       "Add a unique, descriptive title that states the page's primary topic and brand."))
    else:
        px = title_px(t)
        n = len(t)
        ev = '"%s" - %d chars, ~%d px (estimate)' % (t, n, px)
        if n < 15:
            c.append(check("title.length", "onpage", "WARNING", "MEDIUM", "Title length", ev, final,
                           "Title is very short; describe the page's topic more specifically."))
        elif px > 600:
            c.append(check("title.length", "onpage", "WARNING", "LOW", "Title length", ev, final,
                           "Likely truncated in desktop results (~580-600 px). Front-load the primary topic; truncation is a display issue, not a ranking penalty."))
        else:
            c.append(check("title.length", "onpage", "PASS", "INFO", "Title length", ev, final))
        words = [w for w in tokens(t) if w not in STOP and len(w) > 2]
        dup = [w for w, k in Counter(words).items() if k > 1]
        if dup:
            c.append(check("title.duplicate_words", "onpage", "WARNING", "LOW", "Repeated words in title",
                           "Repeated: %s" % ", ".join(dup), final, "Remove repetition; it reads as keyword stuffing and wastes width."))
    if len(titles) > 1:
        c.append(check("title.multiple", "onpage", "WARNING", "LOW", "Multiple <title> elements",
                       "%d titles found" % len(titles), final, "Emit one <title> in <head> (often a framework/layout duplication)."))

    d = f["meta_description"]
    if d is None or not d.strip():
        c.append(check("description.present", "onpage", "WARNING", "MEDIUM", "Meta description",
                       "Missing", final, "Write a unique summary (~120-160 chars) of what the page offers; Google may still rewrite it."))
    else:
        n = len(d.strip())
        ev = '"%s" - %d chars' % (d.strip()[:200], n)
        if n < 70:
            c.append(check("description.length", "onpage", "WARNING", "LOW", "Meta description length", ev, final,
                           "Short descriptions are often replaced by Google; expand with the page's specific value."))
        elif n > 165:
            c.append(check("description.length", "onpage", "WARNING", "LOW", "Meta description length", ev, final,
                           "Likely truncated around 155-160 chars on desktop; put the key point first."))
        else:
            c.append(check("description.length", "onpage", "PASS", "INFO", "Meta description length", ev, final))

    vp = f["viewport"]
    if not vp:
        c.append(check("mobile.viewport", "technical", "FAIL", "HIGH", "Viewport meta",
                       "No <meta name=viewport>", final,
                       'Add <meta name="viewport" content="width=device-width, initial-scale=1">. Google indexes the mobile rendering.'))
    elif "width=device-width" not in vp.replace(" ", ""):
        c.append(check("mobile.viewport", "technical", "WARNING", "MEDIUM", "Viewport meta", vp, final,
                       "Use width=device-width so the layout adapts to the device."))
    elif re.search(r"user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b", vp):
        c.append(check("mobile.viewport", "technical", "WARNING", "LOW", "Viewport blocks zoom", vp, final,
                       "Allow pinch-zoom (accessibility)."))
    else:
        c.append(check("mobile.viewport", "technical", "PASS", "INFO", "Viewport meta", vp, final))

    if not f["charset"]:
        c.append(check("html.charset", "technical", "WARNING", "LOW", "Charset", "No charset declared in HTML", final,
                       'Add <meta charset="utf-8"> as the first element in <head>.'))
    if not f["lang"]:
        c.append(check("html.lang", "onpage", "WARNING", "LOW", "HTML lang", "<html> has no lang attribute", final,
                       'Add lang (e.g. <html lang="en">) for accessibility and language detection.'))
    else:
        c.append(check("html.lang", "onpage", "PASS", "INFO", "HTML lang", "lang=%s" % f["lang"], final))
    if not f["doctype"] or "html" not in f["doctype"].lower():
        c.append(check("html.doctype", "technical", "WARNING", "LOW", "Doctype", "Missing <!DOCTYPE html>", final,
                       "Add <!DOCTYPE html> to avoid quirks-mode rendering."))

    og = f["og"]
    need = ["og:title", "og:description", "og:image", "og:url", "og:type"]
    miss = [k for k in need if not og.get(k)]
    if miss:
        c.append(check("social.og", "onpage", "WARNING", "LOW", "Open Graph", "Missing: " + ", ".join(miss), final,
                       "Add Open Graph tags so shares and some AI/chat previews render correctly (not a ranking factor)."))
    else:
        c.append(check("social.og", "onpage", "PASS", "INFO", "Open Graph", "All core OG tags present", final))
    if og.get("og:image") and not re.match(r"^https?://", og["og:image"]):
        c.append(check("social.og_image_abs", "onpage", "WARNING", "LOW", "OG image URL",
                       og["og:image"], final, "og:image must be an absolute URL."))
    if not f["twitter"].get("twitter:card"):
        c.append(check("social.twitter", "onpage", "INFO", "INFO", "Twitter/X card",
                       "No twitter:card (X falls back to OG tags)", final,
                       'Optional: add <meta name="twitter:card" content="summary_large_image">.'))
    return c


def heading_checks(f, final):
    c = []
    hs = f["headings"]
    h1 = [h for h in hs if h["level"] == 1]
    if not h1:
        c.append(check("h1.present", "onpage", "FAIL", "HIGH", "H1", "No <h1> found in served HTML", final,
                       "Add one visible H1 that states the page's main topic (check rendered HTML if the H1 is injected by JS)."))
    else:
        texts = [h["text"] for h in h1]
        if len(h1) > 1:
            c.append(check("h1.multiple", "onpage", "WARNING", "LOW", "Multiple H1s",
                           "%d H1s: %s" % (len(h1), texts[:5]), final,
                           "Not an error for Google, but one clear H1 usually communicates the topic best (often a logo/heading in the header)."))
        else:
            c.append(check("h1.present", "onpage", "PASS", "INFO", "H1", '"%s"' % texts[0], final))
        if any(not t for t in texts):
            c.append(check("h1.empty", "onpage", "FAIL", "MEDIUM", "Empty H1", "An H1 has no text (image-only or empty)", final,
                           "Give the H1 text content (or an image with descriptive alt)."))
        if f["title"] and texts[0]:
            ov = overlap(f["title"], texts[0])
            if ov < 0.2:
                c.append(check("h1.title_alignment", "onpage", "WARNING", "LOW", "H1 / title alignment",
                               'Title "%s" vs H1 "%s" share few terms (overlap %.0f%%)' % (f["title"], texts[0], ov * 100), final,
                               "Make the title and H1 describe the same topic (they need not be identical).", label="INFERRED"))
    skips = []
    prev = 0
    for h in hs:
        if prev and h["level"] > prev + 1:
            skips.append("H%d->H%d (\"%s\")" % (prev, h["level"], h["text"][:40]))
        prev = h["level"]
    if skips:
        c.append(check("headings.hierarchy", "onpage", "WARNING", "LOW", "Heading hierarchy",
                       "Skipped levels: " + "; ".join(skips[:6]), final,
                       "Keep headings nested in order (accessibility and outline clarity; minor SEO impact)."))
    empty = [h for h in hs if not h["text"]]
    if empty:
        c.append(check("headings.empty", "onpage", "WARNING", "LOW", "Empty headings",
                       "%d empty heading elements" % len(empty), final, "Remove empty headings or give them text."))
    c.append(check("headings.outline", "onpage", "INFO", "INFO", "Heading outline",
                   " | ".join("H%d %s" % (h["level"], h["text"][:60]) for h in hs[:25]) or "(none)", final))
    return c


def content_checks(f, final):
    c = []
    wc = f["main_word_count"]
    c.append(check("content.word_count", "content", "INFO", "INFO", "Word count",
                   "%d words in main content (%d incl. nav/header/footer), %d paragraphs" % (
                       wc, f["word_count"], len(f["paragraphs"])), final))
    if wc < 120:
        c.append(check("content.thin", "content", "WARNING", "MEDIUM", "Low text content",
                       "Only %d words of main content in served HTML" % wc, final,
                       "Judge against the page's intent: fine for a contact/login page, thin for an informational or category page. If content is client-rendered, verify with render.py.",
                       label="INFERRED"))
    m = PLACEHOLDER_RX.search(f["text"])
    if m:
        s = max(0, m.start() - 60)
        c.append(check("content.placeholder", "content", "FAIL", "HIGH", "Placeholder / broken content",
                       '...%s...' % f["text"][s:m.end() + 60].replace("\n", " "), final,
                       "Replace placeholder or template-leak text with real content."))
    words = tokens(f["main_text"])
    if len(words) >= 150:
        stop_ratio = sum(1 for w in words if w in STOP) / float(len(words))
        content_words = [w for w in words if w not in STOP and len(w) > 2 and not w.isdigit()]
        top = Counter(content_words).most_common(10)
        dens = [(w, k, round(100.0 * k / len(words), 2)) for w, k in top]
        host_label = parse.urlsplit(final).netloc.lower().split(":")[0]
        host_label = re.sub(r"^www\.", "", host_label).split(".")[0]
        c.append(check("content.term_frequency", "content", "INFO", "INFO", "Top terms",
                       "stop-word ratio %.0f%%; top terms: %s" % (stop_ratio * 100, ", ".join(
                           "%s(%d, %.1f%%)" % d for d in dens)), final))
        stuffed = [d for d in dens if d[2] > 4.0 and d[1] >= 12 and d[0] not in host_label]
        if stuffed:
            c.append(check("content.keyword_stuffing", "content", "WARNING", "MEDIUM", "Possible keyword repetition",
                           ", ".join("'%s' %d times (%.1f%% of words)" % s for s in stuffed), final,
                           "Read the copy aloud; if repetition is unnatural, use synonyms/pronouns and cover related subtopics instead. Density is a symptom, not a target.",
                           label="INFERRED"))
    if f["lang"] is None or f["lang"].lower().startswith("en"):
        r = readability(f["main_text"])
        if r:
            status = "WARNING" if r["flesch_reading_ease"] < 30 else "INFO"
            c.append(check("content.readability", "content", status, "LOW", "Readability (English heuristic)",
                           "Flesch %.0f, avg %.1f words/sentence, %d sentences >30 words" % (
                               r["flesch_reading_ease"], r["avg_words_per_sentence"], r["long_sentences_over_30w"]), final,
                           "Shorten long sentences where the audience isn't specialist; readability scores are a proxy, not a ranking factor.",
                           label="INFERRED"))
    c.append(check("content.structure", "content", "INFO", "INFO", "Content structures",
                   "lists=%d (items=%d), tables=%d, details/accordions=%d, definition lists=%d, videos=%d" % (
                       f["lists"], f["list_items"], f["tables"], f["details"], f["definition_lists"], f["videos"]), final))
    dates = {k: v for k, v in f["article_meta"].items() if "time" in k}
    if dates or f["times"]:
        c.append(check("content.dates", "content", "INFO", "INFO", "Visible/declared dates",
                       "meta: %s; <time>: %s" % (dates or "-", f["times"][:5]), final))
    return c


def image_checks(f, final, size_info):
    c = []
    imgs = f["images"]
    if not imgs:
        c.append(check("images.count", "images", "NA", "INFO", "Images", "No <img> elements", final))
        return c
    content_imgs = [i for i in imgs if not (i["role"] == "presentation" or i["aria_hidden"])]
    missing = [i for i in content_imgs if not i["has_alt_attr"]]
    empty = [i for i in content_imgs if i["has_alt_attr"] and not (i["alt"] or "").strip()]
    weak = [(i, weak_alt_reason(i["alt"], i["src"])) for i in content_imgs if (i["alt"] or "").strip()]
    weak = [(i, r) for i, r in weak if r]
    c.append(check("images.count", "images", "INFO", "INFO", "Images",
                   "%d <img> (%d with alt text, %d alt=\"\" decorative, %d missing alt attr)" % (
                       len(imgs), len(content_imgs) - len(missing) - len(empty), len(empty), len(missing)), final))
    if missing:
        sev = "HIGH" if len(missing) > 5 or any(i["in_link"] for i in missing) else "MEDIUM"
        c.append(check("images.alt_missing", "images", "FAIL", sev, "Missing alt attribute",
                       "%d images: %s" % (len(missing), [i["src"] for i in missing[:8]]), final,
                       'Add alt describing each informative image; use alt="" only for purely decorative images. Linked images need alt as the link text.'))
    else:
        c.append(check("images.alt_missing", "images", "PASS", "INFO", "Alt attributes", "Every image has an alt attribute", final))
    linked_empty = [i for i in empty if i["in_link"]]
    if linked_empty:
        c.append(check("images.linked_empty_alt", "images", "WARNING", "MEDIUM", "Linked images with empty alt",
                       str([i["src"] for i in linked_empty[:6]]), final,
                       "An image that is the only content of a link needs alt text describing the destination."))
    if weak:
        c.append(check("images.alt_weak", "images", "WARNING", "LOW", "Weak alt text",
                       "; ".join('%s alt="%s" (%s)' % (i["src"].rsplit("/", 1)[-1][:50], (i["alt"] or "")[:60], r)
                                 for i, r in weak[:8]), final,
                       "Describe what the image actually shows and why it is on the page; never stuff keywords."))
    no_dims = [i for i in imgs if not (i["width"] and i["height"]) and not i["style_has_aspect"]
               and img_format(i["src"]) != "svg"]
    if no_dims:
        c.append(check("images.dimensions", "performance", "WARNING", "MEDIUM" if len(no_dims) > 3 else "LOW",
                       "Images without width/height", "%d images lack explicit dimensions: %s" % (
                           len(no_dims), [i["src"].rsplit("/", 1)[-1][:50] for i in no_dims[:6]]), final,
                       "Set width/height attributes (or CSS aspect-ratio) so the browser reserves space and avoids CLS."))
    fmts = Counter(img_format(i["src"]) for i in imgs)
    legacy = sum(v for k, v in fmts.items() if k in ("jpg", "png", "gif", "bmp", "tiff"))
    has_modern_sources = any("webp" in (s["type"] or "") or "avif" in (s["type"] or "") for s in f["picture_sources"])
    c.append(check("images.formats", "images", "WARNING" if legacy >= 3 and not has_modern_sources else "INFO",
                   "LOW", "Image formats", "Formats: %s; <picture> modern sources: %s" % (dict(fmts), has_modern_sources), final,
                   "Serve WebP/AVIF (via CDN negotiation or <picture>) for photographic images. Note: CDNs may negotiate format by Accept header, so extension alone can mislead.",
                   label="INFERRED"))
    first = imgs[0]
    if first["loading"] == "lazy":
        c.append(check("images.lcp_lazy", "performance", "WARNING", "MEDIUM", "First image lazy-loaded",
                       "First <img> (%s) has loading=lazy" % first["src"].rsplit("/", 1)[-1][:60], final,
                       "If this is the hero/LCP image, remove loading=lazy and consider fetchpriority=high.", label="INFERRED"))
    later = imgs[4:]
    if len(later) >= 4 and not any(i["loading"] == "lazy" or i["lazy_js"] for i in later):
        c.append(check("images.lazy", "performance", "WARNING", "LOW", "No lazy loading",
                       "%d images beyond the first 4 load eagerly" % len(later), final,
                       'Add loading="lazy" to below-the-fold images.', label="INFERRED"))
    no_srcset = [i for i in imgs if not i["srcset"] and not i["in_picture"] and img_format(i["src"]) in ("jpg", "png", "webp", "avif")]
    if len(no_srcset) >= 3:
        c.append(check("images.responsive", "images", "WARNING", "LOW", "No responsive images",
                       "%d raster images without srcset/<picture>" % len(no_srcset), final,
                       "Provide srcset/sizes so mobile devices download appropriately sized files."))
    if size_info:
        big = [s for s in size_info if s.get("bytes") and s["bytes"] > 250 * 1024]
        if big:
            c.append(check("images.oversized", "performance", "WARNING", "MEDIUM" if any(b["bytes"] > 600 * 1024 for b in big) else "LOW",
                           "Heavy images", "; ".join("%s %.0f KB" % (b["src"].rsplit("/", 1)[-1][:50], b["bytes"] / 1024.0) for b in big[:8]), final,
                           "Compress and resize; serve modern formats; aim well under 200 KB for most content images."))
        else:
            c.append(check("images.oversized", "performance", "PASS", "INFO", "Image weight",
                           "%d images sampled, none >250 KB" % len(size_info), final))
    return c


def link_checks(f, final, broken):
    c = []
    a = f["anchors"]
    internal = [x for x in a if x["kind"] == "internal"]
    external = [x for x in a if x["kind"] == "external"]
    contextual = [x for x in internal if not x["in_boilerplate"]]
    c.append(check("links.count", "internal_links", "INFO", "INFO", "Links",
                   "internal=%d (unique %d, contextual/in-body %d), external=%d (unique %d)" % (
                       len(internal), len({x["url"] for x in internal}), len(contextual),
                       len(external), len({x["url"] for x in external})), final))
    if not internal:
        c.append(check("links.internal_none", "internal_links", "FAIL", "HIGH", "No internal links",
                       "No crawlable internal <a href> links in served HTML", final,
                       "Link to related pages with real <a href> elements (JS onclick navigation isn't followed)."))
    bad_kinds = Counter(x["kind"] for x in a if x["kind"] in ("javascript", "empty-href", "missing-href"))
    if bad_kinds:
        c.append(check("links.uncrawlable", "internal_links", "WARNING", "LOW", "Non-crawlable links",
                       dict(bad_kinds).__repr__(), final, "Use <a href=\"/path\"> for navigation; buttons for actions."))
    no_name = [x for x in a if x["url"] and not x["accessible_name"]]
    if no_name:
        c.append(check("links.empty_anchor", "internal_links", "WARNING", "MEDIUM", "Links without anchor text",
                       "%d links: %s" % (len(no_name), [x["href"] for x in no_name[:6]]), final,
                       "Give every link text (or an image alt / aria-label) that describes the target."))
    generic = [x for x in a if x["url"] and x["accessible_name"].lower().strip(" .>»→") in GENERIC_ANCHORS]
    if generic:
        c.append(check("links.generic_anchor", "internal_links", "WARNING", "LOW", "Generic anchor text",
                       "%d links e.g. %s" % (len(generic), ['"%s" -> %s' % (x["accessible_name"], x["href"]) for x in generic[:5]]), final,
                       "Use descriptive anchors (e.g. 'pricing for teams' instead of 'learn more') on in-content links."))
    by_text = {}
    for x in internal:
        t = x["accessible_name"].lower()
        if t:
            by_text.setdefault(t, set()).add(x["url"].rstrip("/"))
    conflicts = {t: u for t, u in by_text.items() if len(u) > 1 and t not in GENERIC_ANCHORS}
    if conflicts:
        c.append(check("links.anchor_conflict", "internal_links", "WARNING", "LOW", "Same anchor, different targets",
                       "; ".join('"%s" -> %s' % (t, sorted(u)[:3]) for t, u in list(conflicts.items())[:5]), final,
                       "Identical anchor text pointing to different URLs blurs which page is about that topic."))
    params = [x for x in internal if x["url"] and parse.urlsplit(x["url"]).query
              and re.search(r"(utm_|sessionid|sid=|ref=|sort=|filter)", parse.urlsplit(x["url"]).query, re.I)]
    if params:
        c.append(check("links.parameterized", "crawl_index", "WARNING", "LOW", "Parameterized internal links",
                       "%d links, e.g. %s" % (len(params), [x["url"] for x in params[:4]]), final,
                       "Link to clean canonical URLs; tracking/sort params create crawlable duplicates."))
    if final.startswith("https://"):
        http_int = [x for x in internal if x["url"] and x["url"].startswith("http://")]
        if http_int:
            c.append(check("links.http_internal", "technical", "WARNING", "MEDIUM", "Internal links to HTTP",
                           "%d links, e.g. %s" % (len(http_int), [x["url"] for x in http_int[:4]]), final,
                           "Update internal links to HTTPS to avoid redirect hops."))
    if len({x["url"] for x in a if x["url"]}) > 300:
        c.append(check("links.excessive", "internal_links", "WARNING", "LOW", "Very many links",
                       "%d unique link targets" % len({x["url"] for x in a if x["url"]}), final,
                       "Very large link counts dilute emphasis; check mega-menus/footers.", label="INFERRED"))
    ext_follow = [x for x in external if not (x["nofollow"] or x["sponsored"] or x["ugc"])]
    c.append(check("links.external", "content", "INFO", "INFO", "Outbound links",
                   "%d external (%d followed). Domains: %s" % (
                       len(external), len(ext_follow),
                       sorted({parse.urlsplit(x["url"]).netloc for x in external})[:15]), final))
    if broken is not None:
        bad = [b for b in broken if b["status"] is None or b["status"] >= 400]
        if bad:
            internal_bad = [b for b in bad if b["kind"] == "internal"]
            c.append(check("links.broken", "internal_links" if internal_bad else "content", "FAIL",
                           "HIGH" if internal_bad else "LOW", "Broken links",
                           "; ".join("%s [%s]" % (b["url"], b["status"] or b.get("error")) for b in bad[:10]), final,
                           "Fix or remove broken links (403/429 on external sites can be bot-blocking false positives - verify manually)."))
        else:
            c.append(check("links.broken", "internal_links", "PASS", "INFO", "Broken links",
                           "%d links sampled, none broken" % len(broken), final))
    return c


def schema_summary(f, final):
    c = []
    types = []
    errors = []
    for b in f["jsonld"]:
        if not b["ok"]:
            errors.append(b["error"])
            continue
        data = b["data"]
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for it in items:
            if isinstance(it, dict):
                t = it.get("@type")
                types.extend(t if isinstance(t, list) else [t])
    if errors:
        c.append(check("schema.jsonld_syntax", "schema", "FAIL", "HIGH", "JSON-LD syntax",
                       "%d block(s) fail to parse: %s" % (len(errors), errors[:3]), final,
                       "Fix the JSON syntax; invalid blocks are ignored entirely."))
    found = [t for t in types if t]
    md = sorted(set(re.sub(r"^https?://schema\.org/", "", t) for t in f["microdata_types"]))
    if not found and not md and not f["rdfa_types"]:
        c.append(check("schema.present", "schema", "WARNING", "MEDIUM", "Structured data",
                       "No JSON-LD, Microdata or RDFa found in served HTML", final,
                       "Add JSON-LD appropriate to the page type (run schema.py and the schema module)."))
    else:
        c.append(check("schema.present", "schema", "PASS", "INFO", "Structured data",
                       "JSON-LD types: %s; Microdata: %s; RDFa: %s" % (found or "-", md or "-", f["rdfa_types"][:5] or "-"), final))
    return c


def perf_checks(f, final):
    c = []
    rb = f["render_blocking_js"]
    if rb:
        c.append(check("perf.render_blocking_js", "performance", "WARNING", "MEDIUM" if len(rb) > 2 else "LOW",
                       "Render-blocking scripts", "%d sync scripts in <head>: %s" % (len(rb), [s[-60:] for s in rb[:6]]), final,
                       "Add defer (or async for independent scripts) or move non-critical scripts out of <head>."))
    css = f["render_blocking_css"]
    if len(css) > 4:
        c.append(check("perf.render_blocking_css", "performance", "WARNING", "LOW", "Many blocking stylesheets",
                       "%d stylesheets in <head>" % len(css), final, "Bundle critical CSS; defer non-critical stylesheets."))
    if f["element_count"] > 1500:
        c.append(check("perf.dom_size", "performance", "WARNING", "LOW" if f["element_count"] < 3000 else "MEDIUM",
                       "Large DOM", "%d elements in served HTML" % f["element_count"], final,
                       "Large DOMs slow rendering and interaction (INP); trim hidden menus/duplicated mobile+desktop markup."))
    c.append(check("perf.resources", "performance", "INFO", "INFO", "Resource summary",
                   "scripts=%d (external %d), stylesheets=%d, preloads=%s, iframes=%d" % (
                       f["scripts_total"], f["scripts_external"], len(f["stylesheets"]),
                       [p["href"][-40:] for p in f["preloads"] if p.get("href")][:5], len(f["iframes"])), final))
    return c


def render_risk(f, final):
    c = []
    if f["main_word_count"] < 60 and f["scripts_external"] >= 3:
        c.append(check("render.csr_risk", "crawl_index", "WARNING", "HIGH", "Content may be client-rendered",
                       "Served HTML has %d words of main content but %d external scripts" % (f["main_word_count"], f["scripts_external"]), final,
                       "Run render.py to compare raw vs rendered HTML. Prefer SSR/SSG for indexable content - many AI crawlers do not execute JavaScript.",
                       label="INFERRED"))
    return c


def geo_checks(f, final):
    c = []
    qh = [h["text"] for h in f["headings"] if h["level"] >= 2 and (h["text"].endswith("?") or QUESTION_START.match(h["text"]))]
    text = f["main_text"]
    defs = re.findall(r"(?m)^[A-Z][\w\s()-]{2,60}\s(?:is|are|refers to|means)\s(?:a|an|the)\s[^.]{10,200}\.", text)
    stats = re.findall(r"\b\d+(?:\.\d+)?\s?%|\b\d{1,3}(?:,\d{3})+\b|\$\s?\d", text)
    sem = f["semantic"]
    answer_len_paras = [p for p in f["paragraphs"] if 25 <= len(p.split()) <= 80]
    c.append(check("geo.extractability", "geo", "INFO", "INFO", "Extractable structures",
                   "question headings=%d, definition sentences=%d, stat/number mentions=%d, tables=%d, lists=%d, "
                   "40-80-word answer-sized paragraphs=%d, <main>=%s, <article>=%s" % (
                       len(qh), len(defs), len(stats), f["tables"], f["lists"], len(answer_len_paras),
                       sem.get("main", 0), sem.get("article", 0)), final))
    if not sem.get("main") and not sem.get("article"):
        c.append(check("geo.semantic_html", "geo", "WARNING", "LOW", "No <main>/<article> landmark",
                       "Page lacks main/article landmarks", final,
                       "Wrap primary content in <main> (and <article> for posts) so parsers can separate it from boilerplate."))
    author = f["author_meta"] or any("author" in str(b.get("data", "")) for b in f["jsonld"] if b["ok"])
    c.append(check("geo.author_signal", "geo", "INFO", "INFO", "Author signal",
                   "author meta/JSON-LD author: %s" % ("present" if author else "not found"), final))
    return c


def sample_links(f, n, ua):
    seen = []
    for x in f["anchors"]:
        if x["url"] and x["url"] not in [s["url"] for s in seen]:
            seen.append({"url": x["url"], "kind": x["kind"]})
    internal = [s for s in seen if s["kind"] == "internal"]
    external = [s for s in seen if s["kind"] == "external"]
    pick = internal[: int(n * 0.7)] + external[: n - int(n * 0.7)]
    out = []
    for s in pick:
        r = fetch(s["url"], ua=ua, method="HEAD", timeout=10)
        if r["status"] in (405, 403, 501) or r["status"] is None:
            r = fetch(s["url"], ua=ua, timeout=10, max_bytes=2048)
        out.append({"url": s["url"], "kind": s["kind"], "status": r["status"], "error": r.get("error"),
                    "redirects": len(r["chain"])})
    return out


def sample_image_sizes(f, n, ua):
    out = []
    for im in f["images"][:n]:
        src = im["src"]
        if not src or not src.startswith("http"):
            continue
        r = fetch(src, ua=ua, method="HEAD", timeout=10)
        size = r["headers"].get("content-length")
        out.append({"src": src, "status": r["status"], "bytes": int(size) if size and size.isdigit() else None,
                    "type": r["headers"].get("content-type")})
    return out


def analyze(url, html=None, ua_key="default", link_n=0, img_n=0, include_text=False, http_version=True):
    ua = UAS.get(ua_key, ua_key)
    fetched = html is None
    if fetched:
        resp = fetch(url, ua=ua)
        html = text_of(resp)
    else:
        resp = {"url": url, "final_url": url, "status": 200, "headers": {}, "chain": [],
                "body": html.encode("utf-8"), "raw_size": len(html), "ttfb_ms": None,
                "elapsed_ms": None, "tls_verify_error": None, "error": None}
    final = resp["final_url"]
    f = extract(html, final)
    versions = curl_http_version(final) if (http_version and resp["status"]) else None
    checks = []
    if fetched:
        checks += server_checks(resp, url, versions)
    if resp["status"] and resp["status"] < 400:
        checks += index_checks(f, final, resp["status"])
        checks += meta_checks(f, final)
        checks += heading_checks(f, final)
        checks += content_checks(f, final)
        sizes = sample_image_sizes(f, img_n, ua) if img_n else None
        checks += image_checks(f, final, sizes)
        broken = sample_links(f, link_n, ua) if link_n else None
        checks += link_checks(f, final, broken)
        checks += schema_summary(f, final)
        checks += perf_checks(f, final)
        checks += render_risk(f, final)
        checks += geo_checks(f, final)
    ct = resp["headers"].get("content-type", "")
    overview = {
        "url": url, "final_url": final, "status": resp["status"], "redirects": len(resp["chain"]),
        "content_type": ct, "language": f["lang"], "response_time_ms": resp.get("elapsed_ms"),
        "ttfb_ms": resp.get("ttfb_ms"), "html_bytes_decoded": len(resp.get("body") or b""),
        "html_bytes_transfer": resp.get("raw_size"),
        "indexable": not any(c["id"] in ("index.meta_robots", "index.x_robots_tag") and c["status"] == "FAIL" for c in checks)
                     and bool(resp["status"]) and resp["status"] < 300,
        "title": f["title"], "meta_description": f["meta_description"],
        "canonical": f["canonicals"][0] if f["canonicals"] else None,
        "word_count": f["word_count"], "main_word_count": f["main_word_count"],
        "headings": Counter("h%d" % h["level"] for h in f["headings"]),
        "paragraphs": len(f["paragraphs"]), "images": len(f["images"]),
        "internal_links": len([a for a in f["anchors"] if a["kind"] == "internal"]),
        "external_links": len([a for a in f["anchors"] if a["kind"] == "external"]),
        "jsonld_blocks": len(f["jsonld"]), "hreflang_count": len(f["hreflang"]),
        "fetched_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "user_agent": ua_key,
    }
    facts = {k: f[k] for k in ("og", "twitter", "hreflang", "headings", "meta_robots",
                               "canonicals", "semantic", "article_meta", "author_meta", "preloads",
                               "render_blocking_js", "duplicate_ids")}
    facts["headers"] = resp["headers"]
    facts["redirect_chain"] = resp["chain"]
    facts["http_versions"] = versions
    facts["images"] = f["images"][:60]
    facts["anchors_sample"] = f["anchors"][:150]
    facts["jsonld"] = f["jsonld"]
    if include_text:
        facts["main_text"] = f["main_text"][:60000]
        facts["paragraphs"] = f["paragraphs"][:300]
    return {"overview": overview, "facts": facts, "checks": checks}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?")
    ap.add_argument("--file", help="analyze a local HTML file instead of fetching")
    ap.add_argument("--base-url", default="https://example.com/")
    ap.add_argument("--check-links", type=int, default=0, metavar="N", help="HEAD-check up to N links")
    ap.add_argument("--image-sizes", type=int, default=0, metavar="N", help="HEAD up to N images for byte size")
    ap.add_argument("--text", action="store_true", help="include main text + paragraphs for content review")
    ap.add_argument("--ua", default="default", help="default | googlebot | bingbot | <custom UA string>")
    ap.add_argument("--no-http-version", action="store_true")
    a = ap.parse_args()
    if a.file:
        with open(a.file, encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        emit(analyze(a.url or a.base_url, html=html, include_text=a.text, http_version=False))
        return
    if not a.url:
        ap.error("url or --file required")
    emit(analyze(normalize_url(a.url), ua_key=a.ua, link_n=a.check_links, img_n=a.image_sizes,
                 include_text=a.text, http_version=not a.no_http_version))


if __name__ == "__main__":
    main()
