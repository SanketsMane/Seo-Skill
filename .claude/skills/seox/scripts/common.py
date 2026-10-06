"""Shared helpers for the seox toolkit.

Stdlib only, Python 3.9+. Every script emits JSON on stdout so Claude (or
score.py) can consume it. Checks use one shared shape:

    {
      "id": "title.length",            # stable check id
      "category": "onpage",            # scoring category (see score.py)
      "status": "PASS|WARNING|FAIL|INFO|NA",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "label": "OBSERVED|INFERRED",    # evidence label
      "title": "Title length",
      "evidence": "...",               # concrete, quotable evidence
      "url": "https://...",
      "recommendation": "..."          # empty when PASS
    }
"""

import gzip
import json
import re
import ssl
import subprocess
import sys
import time
import zlib
from urllib import error, parse, request

DEFAULT_UA = (
    "Mozilla/5.0 (compatible; seox-audit/1.0; +https://example.invalid/seox) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
TIMEOUT = 20
MAX_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 10

CATEGORIES = (
    "technical", "crawl_index", "onpage", "content", "internal_links",
    "schema", "performance", "images", "geo",
)


def check(id_, category, status, severity, title, evidence="", url="",
          recommendation="", label="OBSERVED"):
    assert category in CATEGORIES, category
    return {
        "id": id_, "category": category, "status": status,
        "severity": severity if status not in ("PASS", "NA") else "INFO",
        "label": label, "title": title, "evidence": evidence, "url": url,
        "recommendation": "" if status == "PASS" else recommendation,
    }


def emit(obj):
    json.dump(obj, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


def normalize_url(url):
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    p = parse.urlsplit(url)
    path = p.path or "/"
    return parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), path, p.query, ""))


def origin(url):
    p = parse.urlsplit(url)
    return "%s://%s" % (p.scheme, p.netloc)


def same_site(a, b):
    """True when hosts match ignoring a leading www."""
    ha = parse.urlsplit(a).netloc.lower()
    hb = parse.urlsplit(b).netloc.lower()
    strip = lambda h: h[4:] if h.startswith("www.") else h
    return strip(ha) == strip(hb)


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _ctx(verify=True):
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _decode_body(raw, encoding):
    encoding = (encoding or "").lower()
    try:
        if encoding == "gzip":
            return gzip.decompress(raw)
        if encoding == "deflate":
            try:
                return zlib.decompress(raw)
            except zlib.error:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
    except Exception:
        pass
    return raw


def fetch(url, ua=DEFAULT_UA, method="GET", follow=True, max_bytes=MAX_BYTES,
          timeout=TIMEOUT, html_only=False):
    """Fetch a URL while recording the full redirect chain.

    Returns dict: url, final_url, status, headers (lower-cased), chain,
    body (bytes, decoded from gzip/deflate), raw_size, elapsed_ms, ttfb_ms,
    tls_verify_error, error.
    """
    chain = []
    current = url
    tls_error = None
    started = time.time()
    for _ in range(MAX_REDIRECTS + 1):
        req = request.Request(current, method=method, headers={
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en;q=0.9,*;q=0.5",
        })
        resp = None
        for verify in (True, False):
            opener = request.build_opener(
                _NoRedirect, request.HTTPSHandler(context=_ctx(verify)))
            t0 = time.time()
            try:
                resp = opener.open(req, timeout=timeout)
                break
            except error.HTTPError as e:
                resp = e
                break
            except error.URLError as e:
                if verify and isinstance(getattr(e, "reason", None), ssl.SSLError):
                    tls_error = str(e.reason)
                    continue
                return {"url": url, "final_url": current, "status": None,
                        "headers": {}, "chain": chain, "body": b"",
                        "raw_size": 0, "elapsed_ms": int((time.time() - started) * 1000),
                        "ttfb_ms": None, "tls_verify_error": tls_error,
                        "error": str(getattr(e, "reason", e))}
            except Exception as e:  # timeouts, resets
                return {"url": url, "final_url": current, "status": None,
                        "headers": {}, "chain": chain, "body": b"",
                        "raw_size": 0, "elapsed_ms": int((time.time() - started) * 1000),
                        "ttfb_ms": None, "tls_verify_error": tls_error,
                        "error": "%s: %s" % (type(e).__name__, e)}
        ttfb = int((time.time() - t0) * 1000)
        status = resp.getcode() if hasattr(resp, "getcode") else resp.code
        headers = {k.lower(): v for k, v in resp.headers.items()}
        if status in (301, 302, 303, 307, 308) and "location" in headers:
            nxt = parse.urljoin(current, headers["location"])
            chain.append({"url": current, "status": status, "location": nxt})
            if not follow:
                return {"url": url, "final_url": current, "status": status,
                        "headers": headers, "chain": chain, "body": b"",
                        "raw_size": 0, "elapsed_ms": int((time.time() - started) * 1000),
                        "ttfb_ms": ttfb, "tls_verify_error": tls_error, "error": None}
            if any(c["url"] == nxt for c in chain):
                return {"url": url, "final_url": nxt, "status": status,
                        "headers": headers, "chain": chain, "body": b"",
                        "raw_size": 0, "elapsed_ms": int((time.time() - started) * 1000),
                        "ttfb_ms": ttfb, "tls_verify_error": tls_error,
                        "error": "redirect loop"}
            current = nxt
            continue
        raw = b""
        ctype = headers.get("content-type", "").lower()
        skip_body = html_only and ctype and not any(t in ctype for t in ("html", "xml"))
        if method != "HEAD" and not skip_body:
            try:
                raw = resp.read(max_bytes + 1)
            except Exception:
                raw = b""
        body = _decode_body(raw, headers.get("content-encoding"))
        return {"url": url, "final_url": current, "status": status,
                "headers": headers, "chain": chain, "body": body,
                "raw_size": len(raw), "elapsed_ms": int((time.time() - started) * 1000),
                "ttfb_ms": ttfb, "tls_verify_error": tls_error,
                "truncated": len(raw) > max_bytes, "error": None}
    return {"url": url, "final_url": current, "status": None, "headers": {},
            "chain": chain, "body": b"", "raw_size": 0,
            "elapsed_ms": int((time.time() - started) * 1000), "ttfb_ms": None,
            "tls_verify_error": tls_error, "error": "too many redirects"}


def text_of(resp):
    body = resp.get("body") or b""
    ctype = resp.get("headers", {}).get("content-type", "")
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    enc = m.group(1) if m else None
    if not enc:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', body[:4096], re.I)
        enc = m.group(1).decode("ascii", "ignore") if m else "utf-8"
    try:
        return body.decode(enc, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def curl_http_version(url):
    """Ask curl which HTTP version the server negotiates. None if curl missing."""
    out = {}
    for flag, key in (("--http2", "h2"), ("--http3", "h3")):
        try:
            r = subprocess.run(
                ["curl", "-sS", "-o", "/dev/null", "-I", flag, "--max-time", "15",
                 "-w", "%{http_version}", url],
                capture_output=True, text=True, timeout=20)
            out[key] = r.stdout.strip() or None
            if r.returncode != 0 and "--http3" in flag:
                out[key] = None  # curl build without HTTP/3 support
        except (OSError, subprocess.SubprocessError):
            out[key] = None
    return out


def load_json_arg(path):
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
