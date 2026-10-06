# /seox hreflang <url> — International SEO

First decide whether it's needed: hreflang is for equivalent content in different languages or regional variants. A single-language, single-market site doesn't need it — say so and stop.

## Run
```bash
python3 $S/hreflang.py <url> [<more urls>] --follow 60 > $D/hreflang.json
# or across a crawl:
python3 $S/crawl.py <url> --max 200 --out $D/crawl.json && python3 $S/hreflang.py --crawl $D/crawl.json
```
Checks code format (language[-script][-region], ISO codes, common mistakes like `en-UK`), self-reference, duplicates, x-default, return tags, bad targets (non-200, redirect, noindex, non-canonical) and canonical conflicts. It reads HTML `<link>` tags only — if the site uses HTTP `Link` headers or sitemap `xhtml:link` annotations, inspect those manually and say so.

## Also evaluate
- URL strategy: ccTLD vs subdomain vs subdirectory; consistency.
- Each language version canonicalizes to itself (never to the default language).
- Content is actually translated/localised (currency, units, contact info), not machine-duplicated.
- No forced IP/Accept-Language redirects that hide versions from crawlers; offer a selector instead.
- `<html lang>` matches the hreflang language.
- Cross-domain sets: every domain must carry the full reciprocal set.

Output per-cluster tables (URL · lang code · return OK · issues) and a corrected tag set example for the template.
