# AI Search / GEO Reference (snapshot — verify vendor docs for decisions)

## Separate four questions — never merge them
1. **Crawler access** — can the bot fetch the URL? (robots.txt, WAF/CDN bot rules, auth, geo-blocks)
2. **Indexing** — has the engine stored it? (Google/Bing index status; AI engines' own indexes)
3. **Retrieval** — is the page pulled in for a given query? (relevance, freshness, passage quality)
4. **Citation** — is it shown/linked as a source? (clarity, authority, uniqueness, attribution)
Scripts can measure (1) and parts of extractability. (2)–(4) need engine-side data; otherwise label UNVERIFIED.

## Which crawler feeds what (as compiled; check current docs)
| Product | Retrieval/index source | Control |
|---|---|---|
| Google AI Overviews / AI Mode | Google Search index (Googlebot) | Normal Search controls; `nosnippet`/`max-snippet` limit use. `Google-Extended` does NOT affect Search or AI Overviews |
| Gemini app training/grounding | Google-Extended token | robots.txt `Google-Extended` |
| Bing / Microsoft Copilot | Bing index (bingbot) | bingbot; IndexNow speeds discovery |
| ChatGPT search | OAI-SearchBot index; ChatGPT-User for live user fetches | Separate from GPTBot (training) |
| Claude search | Claude-SearchBot; Claude-User for user fetches | Separate from ClaudeBot (training) |
| Perplexity | PerplexityBot; Perplexity-User for user fetches | — |
| Apple | Applebot (search); Applebot-Extended (training opt-out token) | — |
Blocking a training bot ≠ blocking that company's search product. User-initiated fetchers may not follow robots.txt the same way — check vendor docs before claiming either way.

## Most AI crawlers don't execute JavaScript
Treat server-rendered HTML as what AI crawlers see. If `render.py` shows a content gap, that is a GEO issue as well as an SEO one.

## Citability signals (what to evaluate)
- **Direct answers**: a question-style heading followed by a 1–3 sentence answer that stands alone, then detail.
- **Self-contained passages**: paragraphs that make sense out of context (name the subject; avoid "this/it" openers).
- **Facts with attribution**: specific numbers, dates, definitions, each with a source or first-party method.
- **Structure**: tables for comparisons/specs, ordered lists for steps, definition lists for glossaries.
- **Entity clarity**: consistent brand/product/person names; Organization/Person schema with `sameAs`; about page; one canonical name per entity.
- **First-hand evidence**: original data, testing, photos, case studies, expert commentary — the things AI answers can't synthesise from elsewhere.
- **Freshness**: visible updated dates that reflect real changes.
- **Semantic HTML**: `<main>`, `<article>`, real headings, no content in images/canvas only.

## GEO readiness score (0–100) — build from checks
| Factor | Points |
|---|---:|
| AI-search crawlers allowed for key content (robots + no WAF block) | 15 |
| Content server-rendered / extractable | 15 |
| Answer blocks & question coverage on key pages | 15 |
| Facts with sources / original data | 15 |
| Entity clarity (schema, about, consistent naming, sameAs) | 15 |
| Author & trust signals | 10 |
| Structured data appropriate to page types | 10 |
| Freshness signals | 5 |
Score each from evidence; show the table. This is readiness, not a prediction.

## Things not to do
Keyword stuffing for "LLM optimisation", hidden prompt text, fake statistics, auto-generated FAQ spam, claiming llms.txt is required.
