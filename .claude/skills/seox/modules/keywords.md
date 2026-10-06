# /seox keywords <topic or url> — Keywords & search intent

## Data honesty
Search volume, difficulty, CPC and rankings require a data tool (connected MCP such as a keyword/SERP API, Search Console export, or user-provided CSV). If none is available, say so up front and prioritise by intent, business value and observed SERP signals instead — never estimate volumes as if measured.

## Method
1. **Seed** — from the topic, or from a URL (`page.py --text`: title, headings, entities) and the site's existing pages.
2. **Expand** — modifiers (best, vs, alternatives, price, near me, how to, for <audience>, <year> only when genuinely time-bound), questions (who/what/why/how/can/does), related entities, problems the product solves. Use WebSearch to observe related searches/"People also ask"-style questions where visible.
3. **Classify intent** — informational · commercial investigation · transactional · navigational · local. Validate on the SERP for important terms: the page types ranking reveal the intent better than the wording.
4. **Cluster** — group terms a single page can satisfy (same intent + overlapping results). Separate clusters when intent or ranking page types differ.
5. **Map** — each cluster → existing URL (if any) or new page; flag cannibalisation (two of our pages for one cluster).
6. **Entities** — key entities and relationships the content must cover for topical completeness.

## Output
Table: Cluster · primary term · secondary terms · intent · SERP page type · mapped URL / new page · priority (with reason) · volume (measured value + source, or "not measured"). Then a short list of topical gaps and recommended next commands (`blog plan`, `content brief`).
Keyword density is not a target; recommend natural usage in title, H1, early copy and headings where it reads well.
