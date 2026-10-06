# /seox page <url> — Deep single-page analysis

## Run
```bash
python3 $S/page.py <url> --check-links 40 --image-sizes 25 --text > $D/page.json
python3 $S/schema.py <url> > $D/schema.json
python3 $S/psi.py <url> > $D/psi.json
python3 $S/render.py <url> > $D/render.json   # if available
```
Read `facts.main_text` and the heading outline yourself — the content verdict is yours, not the script's.

## Judge (add to manual.json)
- **Search intent**: what query family is this page for? informational / commercial / transactional / navigational / local. Does page type and content match what that intent needs? If unclear, use WebSearch to look at what currently ranks (types of pages, not copying content).
- **Topical coverage**: subtopics a satisfied searcher expects; which are missing.
- **Title/H1/description**: specific, accurate, front-loaded, not duplicated; propose rewrites (give 2 title options with char counts).
- **E-E-A-T** signals visible on the page (see content module).
- **Citability** (see geo module): answer blocks, facts with sources, definitions, tables.

## Output
1. **Page Overview** table (status, indexability, language, TTFB, HTML size, words, headings, paragraphs, images, internal/external links).
2. **Metadata** table: title (length, ~px), description (length), canonical, robots, viewport, charset, lang, OG, Twitter.
3. **Content**: H1, outline, word count (as context, not a target), readability, intent match, coverage gaps, keyword usage (natural?), entities, E-E-A-T.
4. **Images**, **Links**, **Performance**, **Schema** summaries.
5. **Prioritized fixes** with exact proposed copy/markup where helpful.
Score with `score.py` (single-page scope; say so).
