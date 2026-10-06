# /seox technical <url> — Technical SEO

## Run
```bash
python3 $S/page.py <url> --check-links 20 > $D/page.json
python3 $S/robots.py <url> --paths / <key paths> > $D/robots.json
python3 $S/variants.py <url> > $D/variants.json
python3 $S/sitemap.py check <url> --urls-out $D/sitemap-urls.txt > $D/sitemap.json
python3 $S/crawl.py <url> --max 100 --sitemap-urls $D/sitemap-urls.txt --out $D/crawl.json
python3 $S/psi.py <url> > $D/psi.json
python3 $S/render.py <url> --mobile > $D/render.json        # if Playwright is available
python3 $S/schema.py <url> > $D/schema.json
```

## Cover these areas (each with PASS/WARNING/FAIL + evidence)
1. **Crawlability** — robots.txt rules per bot, WAF/bot blocking (compare default UA vs `--ua googlebot` status), crawl depth, internal link crawlability (real `<a href>`), infinite spaces (faceted/calendar/parameter URLs found in crawl).
2. **Indexability** — meta robots, X-Robots-Tag, canonicals (self, conflicting, cross-host, to redirects/404s), noindex in sitemap, soft 404s.
3. **HTTPS & security** — redirect from HTTP, mixed content, HSTS, certificate, security headers (hygiene, not ranking).
4. **URL architecture** — variants (www, slash, case), parameters, length, readability, consistency.
5. **Mobile** — viewport, render parity (render.py --mobile), horizontal overflow, tap targets/font size if rendered.
6. **Core Web Vitals** — field data first (LCP, INP, CLS at p75); lab only for diagnosis. Name the LCP element and top opportunities. If no field data, say so.
7. **JavaScript rendering** — raw vs rendered gap; metadata changing after JS; client-side-only routing/links.
8. **Structured data** — validity summary (detail in schema module).
9. **robots.txt / sitemap** — see their outputs.
10. **Redirects & status** — chains, temporary redirects, internal links to redirects, broken internal links.
11. **Compression, caching, server response** — encoding, cache-control on HTML vs static assets, TTFB (single-sample caveat).
12. **IndexNow** — relevant for Bing/Yandex discovery on frequently changing sites; check for a key file only if the user uses it; recommend, don't penalise.

## Per issue
severity · evidence · why it matters · affected URLs · fix · implementation steps (stack-specific via `references/frameworks.md` if code is known) · verification method.

Score with `score.py` and present the technical, crawl_index and performance categories, plus overall.
