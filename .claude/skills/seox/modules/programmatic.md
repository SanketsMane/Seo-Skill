# /seox programmatic [dataset/idea/url] — Programmatic SEO

Design page systems generated from data. Default stance: build fewer, better pages.

## Quality gates (all must pass before recommending a page set)
1. **Unique value per page** — each page answers a distinct need with data that differs meaningfully (not just a swapped city/product name). Test: pick 3 random pages; would a user find each useful on its own?
2. **Demand** — evidence people search for these variations (data tool, Search Console, or SERP observation). Without data: mark UNVERIFIED and recommend piloting.
3. **Data quality** — source, freshness, completeness, licensing; how missing fields are handled (hide the section, don't print empty templates).
4. **Duplication risk** — estimate template-vs-unique text ratio; near-duplicates must be merged or canonicalised.
5. **Thin-page rule** — pages below the value threshold are not generated, or are `noindex` until enriched.
6. **Index management** — canonical strategy, which combinations are indexable (facets usually not), pagination, sitemap segmentation per template.
7. **Internal links** — every generated page reachable from hubs within ~3 clicks; related-page links computed from data similarity, not random.
8. **Structured data** — per template, from real fields only.
9. **Rollout** — pilot 20–100 pages, measure indexing and engagement for 4–8 weeks before scaling; monitor "Crawled/Discovered – currently not indexed".

## Deliver
Template spec (URL pattern, title/H1/description formulas with fallbacks, sections bound to data fields, schema mapping), gate assessment table, indexation rules, linking model, pilot plan. If auditing an existing pSEO site: crawl a template sample, measure uniqueness (`crawl.py` content hashes, duplicate titles), and recommend prune/merge/noindex where gates fail.

Never recommend generating thousands of low-value pages.
