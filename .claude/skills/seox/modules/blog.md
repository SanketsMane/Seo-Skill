# /seox blog — Content engine

Sub-commands: `blog <topic>` (full article) · `blog plan <topic>` (cluster + calendar) · `blog optimize <url>` (improve existing) · `content brief <keyword>` (brief only).

Principle: useful first, optimised second. Never invent facts, statistics, quotes, studies, experiences or sources.

## Research (all sub-commands)
1. Intent and audience for the topic (`keywords.md` method).
2. WebSearch the main query: what page types rank, what they cover, what they miss. Don't copy their text.
3. Collect sources: primary/official where possible; record URL + date for every factual claim you'll use. Claims you can't source → leave out or mark `[VERIFY]`.
4. If a site/codebase is known: find existing related pages (crawl or grep) for internal links and to avoid cannibalisation — if a page already targets the topic, recommend updating it instead.

## Brief (`content brief`, and the first part of `blog`)
Primary keyword · secondary/related terms · search intent · audience & their level · angle (what makes ours better: first-hand data, expert input, tool, template) · title options (2–3) · meta title (~50–60 chars) · meta description (~120–155) · slug · H1 · H2/H3 outline with what each section must answer and approximate depth · questions to answer · entities to cover · internal links (source/target/anchor) · external references to cite · schema recommendation · image/visual recommendations with alt text · CTA · E-E-A-T requirements (author, reviewer, experience to include) · GEO answer blocks to include.

## Article (`blog <topic>`)
After the brief, write the full article:
- Intro that states who it's for and answers the core question in the first ~100 words.
- Sections each opening with a direct answer, then depth, examples, steps, tables.
- First-hand experience and opinions only as `[PLACEHOLDER: author's experience with X]` unless the user supplied them.
- FAQ only for real follow-up questions not covered above.
- Author box with `[PLACEHOLDER]` name/credentials; "last updated" date.
- Keyword usage natural; no density targets.
- JSON-LD draft (BlogPosting + author Person + BreadcrumbList), validated with `schema.py --jsonld`.
Deliver as Markdown (or the codebase's content format, e.g. MDX with its frontmatter conventions) plus a checklist of placeholders to fill.

## Plan (`blog plan`)
Pillar + 8–20 supporting topics, each with intent, angle, priority, internal links, and publishing order; flag topics needing original data or expert input.

## Optimize (`blog optimize <url>`)
`page.py --text` + `schema.py`; compare against the intent and current SERP; output: keep / rewrite / add / cut / merge per section, new title/description options, missing questions, outdated facts, internal links, schema fixes, and a rewritten version of the weakest sections.
