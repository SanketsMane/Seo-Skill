#!/usr/bin/env python3
"""Structured-data detection and validation.

Usage:
  schema.py <url>                      # fetch page, validate all JSON-LD
  schema.py --file page.html [--base-url URL]
  schema.py --jsonld draft.json [--page-url URL]   # validate a draft before inserting it

Two verdicts are kept strictly separate for every entity:
  schema_org  - is it structurally sound Schema.org? (syntax, @context, known
                @type, sane values, resolvable @id refs)
  google      - does it meet Google's rich-result requirements for that type,
                and is that feature still active? (references/schema-rules.json)
Valid Schema.org is NOT the same as rich-result eligible.

Also cross-checks marked-up values against visible page text (names,
prices, ratings) because markup that doesn't match the page violates
Google's structured-data policies.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import check, emit, fetch, normalize_url, text_of  # noqa: E402
from htmlparse import extract  # noqa: E402

RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "references", "schema-rules.json")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")
DATE_KEYS = {"datePublished", "dateModified", "dateCreated", "uploadDate", "startDate", "endDate",
             "datePosted", "validThrough", "priceValidUntil", "validFrom"}
URL_KEYS = {"url", "logo", "image", "thumbnailUrl", "contentUrl", "embedUrl", "item", "sameAs", "@id"}
PLACEHOLDER = re.compile(r"\b(lorem|ipsum|example\.com|your (company|business|name)|todo|tbd|xxx+|placeholder|\[.*?\])\b", re.I)


def load_rules():
    with open(RULES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def rule_for(rules, t):
    r = rules["types"].get(t)
    seen = 0
    while r and "alias" in r and seen < 5:
        t = r["alias"]
        r = rules["types"].get(t)
        seen += 1
    return t, r


def types_of(node):
    t = node.get("@type")
    if isinstance(t, list):
        return [str(x) for x in t]
    return [str(t)] if t else []


def flatten(data):
    """Yield (path, node) for every dict with @type, walking @graph and nesting."""
    out = []

    def walk(x, path):
        if isinstance(x, dict):
            if "@type" in x:
                out.append((path, x))
            for k, v in x.items():
                if k != "@context":
                    walk(v, path + "." + k if path else k)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, "%s[%d]" % (path, i))
    walk(data, "")
    return out


def has_prop(node, spec):
    """spec may be 'a|b' meaning either."""
    for alt in spec.split("|"):
        v = node.get(alt)
        if v not in (None, "", [], {}):
            return True
    return False


def scan_values(node, issues, path=""):
    for k, v in node.items():
        p = "%s.%s" % (path, k) if path else k
        if isinstance(v, dict):
            if "@type" not in v:
                scan_values(v, issues, p)
            continue
        vals = v if isinstance(v, list) else [v]
        for item in vals:
            if isinstance(item, dict):
                continue
            if item in ("", None):
                issues.append("%s is empty" % p)
                continue
            s = str(item)
            if k in DATE_KEYS and not ISO_DATE.match(s):
                issues.append("%s=%r is not ISO 8601" % (p, s))
            if k in URL_KEYS and k != "@id" and isinstance(item, str) and not re.match(r"^https?://", s) and not s.startswith("/"):
                issues.append("%s=%r is not a URL" % (p, s[:80]))
            if k in URL_KEYS and isinstance(item, str) and s.startswith("/"):
                issues.append("%s=%r is relative (use absolute URLs)" % (p, s[:80]))
            if PLACEHOLDER.search(s):
                issues.append("%s=%r looks like placeholder text" % (p, s[:80]))
            if "<" in s and re.search(r"</?\w+[^>]*>", s) and k not in ("text", "articleBody", "description"):
                issues.append("%s contains HTML markup" % p)


def visible_mismatch(node, page_text):
    """Return list of marked-up facts not found in the visible text."""
    if not page_text:
        return []
    low = re.sub(r"\s+", " ", page_text.lower())
    misses = []
    for key in ("name", "headline"):
        v = node.get(key)
        if isinstance(v, str) and len(v) > 3 and v.lower().strip() not in low:
            words = [w for w in re.findall(r"\w+", v.lower()) if len(w) > 3]
            if words and sum(1 for w in words if w in low) / float(len(words)) < 0.6:
                misses.append("%s %r not visible on page" % (key, v[:80]))
    offers = node.get("offers")
    for o in (offers if isinstance(offers, list) else [offers] if isinstance(offers, dict) else []):
        price = o.get("price")
        if price not in (None, ""):
            p = str(price)
            variants = {p, p.rstrip("0").rstrip(".") if "." in p else p}
            try:
                fp = float(p)
                variants |= {"{:,.2f}".format(fp), "{:,.0f}".format(fp), "{:.2f}".format(fp)}
            except ValueError:
                pass
            if not any(v in page_text for v in variants if v):
                misses.append("offers.price %s not visible on page" % p)
    ar = node.get("aggregateRating")
    if isinstance(ar, dict) and ar.get("ratingValue") not in (None, ""):
        rv = str(ar["ratingValue"])
        if rv not in page_text and rv.rstrip("0").rstrip(".") not in page_text:
            misses.append("aggregateRating.ratingValue %s not visible on page" % rv)
    return misses


def validate_entity(node, rules, page_text, ids):
    res = {"types": types_of(node), "schema_org": {"issues": []}, "google": []}
    known = set(rules["schema_org_known_types"])
    for t in res["types"]:
        if t not in known and t not in rules["types"] and not re.search(r"(Organization|Business|Store|Service|Page|Event|Action)$", t):
            res["schema_org"]["issues"].append("@type %r not in local known-types list - verify on schema.org (may be valid)" % t)
    scan_values(node, res["schema_org"]["issues"])
    for k, v in node.items():
        if isinstance(v, dict) and set(v.keys()) == {"@id"} and v["@id"] not in ids:
            res["schema_org"]["issues"].append("%s references @id %s which is not defined on this page (fine if defined elsewhere)" % (k, v["@id"]))
    ar = node.get("aggregateRating") if node.get("@type") != "AggregateRating" else node
    if isinstance(ar, dict):
        try:
            rv = float(ar.get("ratingValue"))
            best = float(ar.get("bestRating", 5))
            worst = float(ar.get("worstRating", 1 if best == 5 else 0))
            if not (worst <= rv <= best):
                res["schema_org"]["issues"].append("ratingValue %s outside %s-%s" % (rv, worst, best))
            cnt = ar.get("ratingCount") or ar.get("reviewCount")
            if cnt is not None and float(cnt) <= 0:
                res["schema_org"]["issues"].append("rating count is %s" % cnt)
        except (TypeError, ValueError):
            pass
    for t in res["types"]:
        canon, r = rule_for(rules, t)
        if not r:
            res["google"].append({"type": t, "feature": None, "status": "no-rule",
                                  "missing_required": [], "missing_recommended": [],
                                  "note": "No Google rich-result rule recorded for this type."})
            continue
        missing_req = [p for p in r.get("required", []) if not has_prop(node, p)]
        for group in r.get("required_one_of", []):
            if not any(has_prop(node, p) for p in group):
                missing_req.append("one of: " + "/".join(group))
        gating = set(r.get("required", [])) | {p for g in r.get("required_one_of", []) for p in g}
        for parent, kids in r.get("nested", {}).items():
            pv = node.get(parent)
            for item in (pv if isinstance(pv, list) else [pv] if isinstance(pv, dict) else []):
                if set(item.keys()) <= {"@id"}:
                    continue  # reference to an entity defined elsewhere
                if item.get("@type") in ("AggregateOffer",) and parent == "offers":
                    kids = ["lowPrice", "priceCurrency"]
                for kp in kids:
                    if not has_prop(item, kp):
                        (missing_req if parent in gating else res["schema_org"]["issues"]).append(
                            "%s.%s missing" % (parent, kp))
        li = r.get("list_items")
        if li:
            items = node.get(li["key"])
            for i, it in enumerate(items if isinstance(items, list) else [items] if isinstance(items, dict) else []):
                for kp in li["required"]:
                    if isinstance(it, dict) and not has_prop(it, kp):
                        missing_req.append("%s[%d].%s" % (li["key"], i, kp))
        missing_rec = [p for p in r.get("recommended", []) if not has_prop(node, p)]
        status = r.get("status")
        if status == "deprecated":
            eligibility = "NOT ELIGIBLE - Google feature retired"
        elif status == "restricted":
            eligibility = "RESTRICTED - feature limited to certain sites"
        elif status in ("component", "no-direct-feature"):
            eligibility = "N/A - no standalone Google feature (supports parent entity / understanding)"
        elif missing_req:
            eligibility = "NOT ELIGIBLE - missing required properties"
        else:
            eligibility = "MEETS REQUIRED PROPERTIES (eligibility still depends on policies & Google's discretion)"
        res["google"].append({"type": t, "rule_type": canon, "feature": r.get("feature"), "status": status,
                              "eligibility": eligibility, "missing_required": missing_req,
                              "missing_recommended": missing_rec, "note": r.get("notes", ""),
                              "verify": bool(r.get("verify"))})
    res["visible_mismatch"] = visible_mismatch(node, page_text)
    return res


def analyze(blocks, page_url, page_text, microdata, rdfa):
    rules = load_rules()
    checks, entities = [], []
    parsed = [b for b in blocks if b.get("ok")]
    broken = [b for b in blocks if not b.get("ok")]
    for b in broken:
        checks.append(check("schema.jsonld_syntax", "schema", "FAIL", "HIGH", "JSON-LD syntax error",
                            "%s | %s" % (b.get("error"), b.get("raw", "")[:160]), page_url,
                            "Fix the JSON (trailing commas, unescaped quotes, unclosed braces). The whole block is ignored."))
    ids = set()
    all_nodes = []
    for b in parsed:
        data = b["data"]
        ctxs = [data.get("@context")] if isinstance(data, dict) else [d.get("@context") for d in data if isinstance(d, dict)]
        if not any(c and "schema.org" in json.dumps(c) for c in ctxs):
            checks.append(check("schema.context", "schema", "FAIL", "MEDIUM", "Missing/invalid @context",
                                "@context: %s" % ctxs, page_url, 'Use "@context": "https://schema.org".'))
        for path, node in flatten(data):
            if "@id" in node:
                ids.add(node["@id"])
            all_nodes.append((path, node))
    for path, node in all_nodes:
        v = validate_entity(node, rules, page_text, ids)
        v["path"] = path or "(root)"
        entities.append(v)
    for e in entities:
        label = "/".join(e["types"])
        if e["schema_org"]["issues"]:
            checks.append(check("schema.validity.%s" % label, "schema", "WARNING", "MEDIUM", "%s: Schema.org issues" % label,
                                "; ".join(e["schema_org"]["issues"][:8]), page_url,
                                "Fix the listed values; placeholders and non-ISO dates commonly break parsing."))
        for g in e["google"]:
            if g["status"] in ("deprecated", "restricted"):
                checks.append(check("schema.google.%s" % g["type"], "schema", "INFO", "INFO",
                                    "%s: Google feature %s" % (g["type"], g["status"]),
                                    "%s. %s%s" % (g["eligibility"], g["note"],
                                                  " Also missing: %s" % ", ".join(g["missing_required"]) if g["missing_required"] else ""),
                                    page_url,
                                    "Keep only if it accurately describes the page; don't expect a rich result.", label="OBSERVED"))
            elif g.get("missing_required"):
                checks.append(check("schema.google.%s" % g["type"], "schema", "FAIL", "HIGH",
                                    "%s: missing required properties for %s" % (g["type"], g["feature"]),
                                    "Missing: %s" % ", ".join(g["missing_required"]), page_url,
                                    "Add the missing properties using real, visible data only - never invent values."))
            elif g.get("feature"):
                status = "WARNING" if len(g["missing_recommended"]) >= 3 else "PASS"
                checks.append(check("schema.google.%s" % g["type"], "schema", status, "LOW",
                                    "%s: %s" % (g["type"], g["feature"]),
                                    "%s. Missing recommended: %s" % (g["eligibility"], g["missing_recommended"] or "none"),
                                    page_url, "Add recommended properties where the data genuinely exists."))
        if e["visible_mismatch"]:
            checks.append(check("schema.visible_mismatch.%s" % label, "schema", "WARNING", "HIGH",
                                "%s: markup not matching visible content" % label,
                                "; ".join(e["visible_mismatch"]), page_url,
                                "Structured data must describe content users can see. Fix the markup or show the information on the page (JS-rendered values may cause false positives - verify).",
                                label="INFERRED"))
    all_types = sorted({t for _, n in all_nodes for t in types_of(n)})
    if not parsed and not microdata and not rdfa:
        checks.append(check("schema.present", "schema", "WARNING", "MEDIUM", "Structured data",
                            "No JSON-LD, Microdata or RDFa detected", page_url,
                            "Add JSON-LD describing the page's primary entity (Organization/WebSite on the homepage, plus a type matching the page)."))
    if microdata or rdfa:
        checks.append(check("schema.microdata", "schema", "INFO", "INFO", "Microdata/RDFa present",
                            "Microdata: %s; RDFa: %s" % (sorted(set(microdata))[:10], sorted(set(rdfa))[:10]), page_url,
                            "Validate these with Google's Rich Results Test; this tool fully validates JSON-LD only."))
    types_flat = set(all_types)
    org_like = {t for t in types_flat if t.endswith("Organization") or t.endswith("Business")
                or rule_for(rules, t)[0] in ("Organization", "LocalBusiness")}
    if not org_like:
        checks.append(check("schema.entity_org", "geo", "INFO", "INFO", "No Organization entity on this page",
                            "Types found: %s" % (all_types or "none"), page_url,
                            "On the homepage/about page, an Organization (or LocalBusiness) entity with name, url, logo and sameAs helps entity disambiguation for search and AI systems."))
    return {"types": all_types, "entities": entities, "checks": checks,
            "rules_as_of": rules.get("as_of")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?")
    ap.add_argument("--file")
    ap.add_argument("--base-url", default="https://example.com/")
    ap.add_argument("--jsonld", help="validate a standalone JSON-LD file (draft)")
    ap.add_argument("--page-url", default="")
    a = ap.parse_args()
    if a.jsonld:
        raw = open(a.jsonld, encoding="utf-8").read()
        try:
            blocks = [{"ok": True, "data": json.loads(raw)}]
        except ValueError as e:
            blocks = [{"ok": False, "error": str(e), "raw": raw[:300]}]
        emit(analyze(blocks, a.page_url or a.jsonld, "", [], []))
        return
    if a.file:
        html = open(a.file, encoding="utf-8", errors="replace").read()
        url = a.base_url
    elif a.url:
        url = normalize_url(a.url)
        r = fetch(url)
        html = text_of(r)
        url = r["final_url"]
    else:
        ap.error("url, --file or --jsonld required")
    f = extract(html, url)
    out = analyze(f["jsonld"], url, f["text"], f["microdata_types"], f["rdfa_types"])
    out["url"] = url
    emit(out)


if __name__ == "__main__":
    main()
