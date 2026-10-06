# /seox fix <url> | fix all — SEO implementation

Modes: **AUDIT ONLY** (default) · **RECOMMEND** · **AUTO-FIX**. The user selects with `--mode recommend|auto` or by saying so. AUDIT ONLY reports what would change; RECOMMEND adds exact diffs without applying; AUTO-FIX applies after the plan is shown and approved.

## 1. Baseline
- Need the codebase (current dir or given path) and, ideally, a running/deployed URL. If only a codebase: build and serve locally (`npm run build && npm run start`, `astro preview`, `php artisan serve`, etc.) and audit `http://localhost:<port>` (`page.py`, `schema.py`, `crawl.py` work on localhost; skip `variants.py`/`psi.py`). On localhost, drop server-level findings that are dev-server artifacts (HTTPS, HSTS/security headers, compression, caching, HTTP version, TTFB) from both before and after runs so the diff measures code changes only.
- `git status` — if the tree is dirty, tell the user; recommend committing/stashing first. Work on a branch (`seo/fixes-<date>`) if in git.
- Run the relevant audit and save `$D/score-before.json`.

## 2. Inspect the implementation
```bash
python3 $S/detect_stack.py <path> > $D/stack.json
```
Then read the files that control each concern: layouts/metadata, sitemap/robots routes, schema components, image components, link components, redirects/headers config, i18n config. Understand existing patterns before proposing anything. Use `references/frameworks.md` for the stack's idioms.

## 3. Plan (show before changing anything)
For each fix, a block:
- **Issue** (finding id + evidence)
- **Current implementation** (file:line + snippet)
- **Proposed change** (minimal diff, using existing patterns/components)
- **Expected benefit** (honest, no guarantees)
- **Risk** (what could break: other routes using the layout, i18n, caching, analytics) and mitigation
Order: indexing blockers → template-wide metadata/canonical → structured data → internal links/content → performance. Group template-level fixes; avoid per-page edits when one layout change fixes 200 pages.
In AUTO-FIX, ask for approval of the plan (one confirmation for the batch, separate confirmation for anything risky: redirects, robots.txt, noindex changes, URL changes, deleting files).

## 4. Implement
- Minimal diffs; preserve behaviour; no unrelated refactors or reformatting; match code style.
- Content values (titles, descriptions, schema fields) only from real data: page content, CMS fields, config, or the user. Missing facts → `TODO(seo):` placeholders listed for the user, never invented.
- Never: add noindex/robots disallows without explicit approval, change public URLs without 301s, remove existing tracking/analytics, inject hidden text.

## 5. Verify
- Run the project's build, typecheck, lint and tests (from `package.json` scripts or equivalents). Fix what you broke; report anything pre-existing.
- Re-audit the same scope with the same inputs: metadata (`page.py`), structured data (`schema.py`, plus `--jsonld` on generated blocks), links (`crawl.py`), sitemap (`sitemap.py check`), robots (`robots.py`), canonicals.
- `score.py score … --out $D/score-after.json` then `score.py diff $D/score-before.json $D/score-after.json --md`.

## 6. Report
Before/after table (SEO score, technical, on-page, content, schema, performance, GEO) · files changed with one-line reasons · fixed issues · remaining issues (and why: needs content, needs server/CDN access, needs owner decision) · new warnings · placeholders to fill · next actions (deploy, submit sitemap, request indexing for key URLs, monitor Search Console).
Production deploys are the user's call — never deploy or push without being asked.
