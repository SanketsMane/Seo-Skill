# /seox competitor-pages [our-url] [competitor-urls…] — Comparison & alternatives pages

## Gather
- Our product: `page.py --text` on homepage, pricing, features pages. Facts only from these pages or the user.
- Competitors: user-supplied or found via WebSearch ("<category> alternatives", "<us> vs"). For each, `page.py --text` + `schema.py` on homepage/pricing/features — titles, headings, topical coverage, schema, internal links. Backlink data only from a connected tool; otherwise "not measured".
- SERP patterns: WebSearch "<competitor> alternatives", "<us> vs <competitor>" — note what page types appear.

## Analyse
Content gaps (topics/questions they cover that we don't), feature gaps (verifiable from public pages, with date checked), intent of each comparison query, their page structure.

## Generate (choose what fits)
- **X vs Y** page: honest summary up top (who each is best for), feature matrix, pricing comparison (dated, sourced), use-case sections, migration notes, FAQ only for real questions, CTA.
- **Alternatives to X**: criteria for choosing, 4–8 genuine options including us (not only us), each with fair pros/cons.
- **Buyer's guide**: evaluation criteria, checklist, comparison table.
Rules: no copying competitor text; every competitor claim must be verifiable and dated ("as of [date], per [their pricing page]"); no disparagement; mark unverified claims `[VERIFY]`. Schema: `Article`/`WebPage` + `ItemList` where it's a list; no review stars about competitors.
Provide: title, meta description, slug, H1–H3 outline, full draft, internal-link suggestions, table markup.
