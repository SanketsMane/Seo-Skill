# SEO Health Score

| Category (`category` key) | Weight | What feeds it |
|---|---:|---|
| Technical SEO (`technical`) | 20 | status, HTTPS, redirects, security headers, viewport, doctype, URL hygiene, variants |
| Crawlability & Indexability (`crawl_index`) | 15 | robots.txt, meta robots/X-Robots-Tag, canonicals, sitemap quality, soft 404, JS-render dependence, hreflang |
| On-Page SEO (`onpage`) | 15 | titles, descriptions, H1/headings, lang, OG, duplicates across site |
| Content Quality / E-E-A-T (`content`) | 15 | thin/placeholder/duplicate content + **your manual judgment checks** |
| Internal Linking (`internal_links`) | 10 | broken links, depth, weak/orphan pages, anchors |
| Structured Data (`schema`) | 8 | JSON-LD validity, rich-result requirements, visible-content match |
| Performance / CWV (`performance`) | 7 | CrUX field data first, then lab, TTFB, compression, render-blocking, image weight |
| Image SEO (`images`) | 3 | alt, formats, responsive, dimensions |
| GEO / AI Search (`geo`) | 7 | AI-search crawler access, extractability, entity signals + manual citability checks |

## Formula
- Check weight by severity: CRITICAL 10, HIGH 6, MEDIUM 3, LOW 1; PASS checks weigh 2.
- Status factor: PASS 1, WARNING 0.5, FAIL 0. INFO/NA are listed, never scored.
- Category = 100 × Σ(w·factor) / Σw. A CRITICAL FAIL caps the category at 40.
- Overall = weight-averaged categories that have data. `coverage_pct` shows how much weight had data — report it next to the score.

## Status words
85+ Good · 65–84 Needs work · 40–64 Poor · <40 Critical.

## Applicability (`--na`)
Mark a category not applicable only with a reason (e.g. `images` for an API docs site with no images is fine to keep — scripts return NA anyway). Typical: none. Never use `--na` to inflate a score.

## Manual checks (`manual.json`)
Judgment calls must be scored, otherwise content/GEO depend only on heuristics. Shape:
```json
{"checks": [
  {"id": "eeat.author", "category": "content", "status": "FAIL", "severity": "HIGH", "label": "OBSERVED",
   "title": "No author attribution on advice articles", "evidence": "/blog/* (12 of 12 sampled) show no byline or author page",
   "url": "https://example.com/blog/", "recommendation": "Add bylines linking to author pages with real credentials"}
]}
```
Use distinct ids (`eeat.*`, `intent.*`, `coverage.*`, `geo.citability.*`, `local.*`). Each needs evidence a reader could verify.

## Comparing runs
Use identical inputs (same scripts, same crawl `--max`, same manual check ids) before and after; `score.py diff before.json after.json --md` produces the before/after table plus fixed / new / remaining issues.
