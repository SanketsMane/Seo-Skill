# /seox internal-links <url> — Internal linking

## Analysis
```bash
python3 $S/sitemap.py check <url> --sample 10 --urls-out $D/sitemap-urls.txt > $D/sitemap.json
python3 $S/crawl.py <url> --max 300 --sitemap-urls $D/sitemap-urls.txt --out $D/crawl.json
```
From `crawl.json` (`pages[]` has `inlinks`, `contextual_inlinks`, `depth`, `top_anchors`, `title`, `h1`):
- Orphan candidates (in sitemap, not reached) — upper bound if the crawl hit its limit.
- Weak pages: important pages (money pages, pillars) with few inlinks or only nav/footer links.
- Depth: important pages >3 clicks deep.
- Excessive links per page; broken and redirecting internal links.
- Anchor quality: generic ("read more"), duplicate anchors pointing to different pages, same page reached by many unrelated anchors, over-optimised exact-match anchors repeated sitewide.
- Hub structure: do pillar pages link to all their supporting pages and vice versa?

## Recommendations
Identify topical relationships by reading titles/H1s/text of pages (use `page.py --text` on candidates). For each suggestion: a real place in the source page where a link reads naturally.

| Source page | Target page | Suggested anchor | Placement (sentence/section) | Reason |
|---|---|---|---|---|

Prioritise: links into weak high-value pages, from strong/topically close pages, contextual over navigational, varied descriptive anchors. Cap suggestions to what's useful (typically 10–40). In fix mode, insert links in content files/CMS exports only with user approval per batch.
