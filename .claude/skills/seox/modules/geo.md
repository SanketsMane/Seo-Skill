# /seox geo <url> — GEO / AI search readiness

Read `references/ai-search.md` first.

## 1. Crawler access (measured)
```bash
python3 $S/robots.py <url> --paths / <key content paths> > $D/robots.json
python3 $S/page.py <url> --text > $D/page.json
python3 $S/page.py <url> --ua googlebot --no-http-version > $D/page-gbot.json   # compare status/content
```
Also test a real AI-search UA for WAF blocking, e.g. `page.py <url> --ua "Mozilla/5.0 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)"` — a 403/challenge page that robots.txt doesn't explain is a CDN/WAF bot rule. Report crawler access separately for search, AI-search, user-fetch and training bots.

## 2. Extractability
Server-rendered content (page.py word count, `render.py` gap), semantic landmarks, headings that describe sections, content not locked in images/PDF-only/tabs requiring JS, `nosnippet`/`max-snippet` restrictions.

## 3. Citability review (your judgment, on 3–8 key pages)
For each page: Which questions does it answer? Is there a concise, self-contained answer near the top of each section? Are facts specific and sourced? Original data or first-hand evidence? Definitions, comparisons in tables, steps in lists? Clear entity naming? Author + date?
Use WebSearch for 3–5 target questions to see what kinds of sources currently get cited/rank (describe patterns; don't claim measured AI citation share).

## 4. Entity clarity
Organization/Person schema with `sameAs` to real profiles, consistent brand naming site-wide, about page that states who/what/where, product/service names used consistently.

## 5. Score & report
Build the GEO readiness score with the factor table in `references/ai-search.md`; write judgments into manual.json (`geo` category). Output:
- GEO readiness table (factor, status, evidence)
- **AI Citability Opportunities** table: Page · Topic · Missing answer · Recommendation (include a drafted answer block where useful, with `[PLACEHOLDER]`s for facts you can't verify)
- Crawler-policy note: who's allowed/blocked and the business trade-off (never auto-recommend unblocking training bots — it's the owner's choice)
- `llms.txt`: optional, low priority; mention only as such.
Never promise citations; say "improves readiness/likelihood".
