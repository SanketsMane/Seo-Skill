# /seox sitemap <url> — XML sitemap

## Check
```bash
python3 $S/sitemap.py check <url> --sample 50 --urls-out $D/sitemap-urls.txt > $D/sitemap.json
```
Covers: discovery (robots.txt, common paths), HTTP status, XML validity, namespace, index files, URL count/size limits, absolute/same-host/HTTPS URLs, duplicates, parameters, lastmod quality, and a sampled check of listed URLs (200? redirected? noindex? self-canonical?). Increase `--sample` for large sites and state the sample size.

Also judge segmentation: for large sites, separate sitemaps per content type (products, categories, articles) make indexing coverage debuggable in Search Console.

## Generate (when missing or broken)
```bash
python3 $S/crawl.py <url> --max 500 --out $D/crawl.json
python3 $S/sitemap.py generate $D/crawl.json --out $D/sitemap.xml
```
Includes only 200, indexable, self-canonical HTML URLs; lastmod only from real modification data. The crawl only finds linked pages — say so, and merge in known unlinked URLs only after verifying them.

In a codebase, prefer a framework-native generated sitemap (`references/frameworks.md`) over a static file, so it stays current. Reference it in robots.txt and submit in Search Console/Bing Webmaster Tools.
