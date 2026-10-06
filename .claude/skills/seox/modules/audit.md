# /seox audit <url> — Full website audit

Flags: `--max N` (crawl limit, default 150), `--quick` (max 60, no link checks), `--no-crawl`.

## 1. Setup
`D=seox-runs/<domain>/<date>`; `mkdir -p $D`. `S=${CLAUDE_SKILL_DIR}/scripts`.

## 2. Collect evidence (run independent steps in parallel)
```bash
python3 $S/page.py <url> --check-links 30 --image-sizes 15 --text > $D/home.json
python3 $S/robots.py <url> --paths / <2-4 key section paths> > $D/robots.json
python3 $S/variants.py <url> > $D/variants.json
python3 $S/sitemap.py check <url> --sample 30 --urls-out $D/sitemap-urls.txt > $D/sitemap.json
python3 $S/schema.py <url> > $D/schema-home.json
python3 $S/psi.py <url> > $D/psi.json            # mobile; add --strategy desktop if relevant
```
Then the crawl (needs sitemap URLs for orphan detection):
```bash
python3 $S/crawl.py <url> --max 150 --sitemap-urls $D/sitemap-urls.txt --out $D/crawl.json
```
Then pick **5–8 representative pages** from the crawl — one per template (product, category, article, service, location, landing) plus the top-linked pages — and run `page.py --text` and `schema.py` on each (`$D/page-<slug>.json`). If hreflang tags appear in the crawl: `hreflang.py --crawl $D/crawl.json`. If Playwright exists and content looks JS-dependent: `render.py`.

If the homepage fetch fails or returns 403/429/503, retry once with `--ua googlebot`; if still blocked, report that bot-blocking itself as a CRITICAL finding (verify it isn't just your network) and continue with what is reachable.

## 3. Classify the site
From homepage + crawl (nav, schema types, URL patterns, copy), choose: SaaS, e-commerce, local business, marketplace, publisher/blog, education, healthcare, finance, real estate, agency, directory, government/service, community, other. One-line justification. YMYL (health, finance, legal, safety) raises the E-E-A-T bar.

## 4. Specialist judgment (read the modules you need)
Always: `content.md` (sample the representative pages), `geo.md` (steps 2–4 only), `internal-links.md` (analysis section).
Conditional: local signals (address, map, service areas) → `local.md`; products/prices → schema Product/merchant checks in `schema.md`; multiple languages → `hreflang.md`; >500 URLs of one template → programmatic quality notes from `programmatic.md`.
Record judgment findings in `$D/manual.json` (shape in `references/scoring.md`).

## 5. Score
```bash
python3 $S/score.py score $D/*.json --manual $D/manual.json --out $D/score.json --md > $D/score.md
```
(`score.py` ignores files without `checks`; exclude `score.json` itself on re-runs.) Use `--na` only with a stated reason.

## 6. Write the report
Follow `references/report-template.md`. Merge duplicate findings (e.g. a missing meta description on 40 pages is one template issue), call out "fix once in template" items, and add the GEO readiness section. Save to `seox-reports/<domain>-audit-<date>.md`.

## 7. Reply in terminal
Score + status, critical issues, top quick wins, what wasn't measured, report path. Offer next steps: `/seox fix` (if a codebase is available), `/seox plan`, or deeper modules.
