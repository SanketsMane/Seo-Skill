# SEO Audit Report Template

Fill every bracket from evidence; drop sections that don't apply (say so in one line rather than padding).

```markdown
# SEO AUDIT REPORT

**Website:** [url]  **Audit date:** [YYYY-MM-DD]  **Website type:** [type — one-line reason]
**Overall SEO Health Score:** [n]/100 ([status], data coverage [n]%)  **GEO readiness:** [n]/100
**Scope:** [pages crawled / sampled, crawl limit, user agent]  **Data sources:** [scripts run; PSI field data yes/no; render check yes/no; third-party data: none / which]

## Executive Summary
- **Critical issues:** [0–3 bullets, each with the business consequence]
- **Biggest opportunities:** [2–4 bullets]
- **Quick wins (< 1 day):** [bullets]
- **Strategic issues:** [bullets — architecture, content, authority]

## Scorecard
[score.py --md table]

## Page Overview (homepage or audited page)
| Metric | Value |
|---|---|
| HTTP status / redirects | |
| Indexable | |
| Language | |
| Response time (TTFB) | |
| HTML size | |
| Word count (main / total) | |
| Headings (H1/H2/H3) | |
| Paragraphs | |
| Images | |
| Internal / external links | |

## To-Do List (prioritized)
[score.py --md to-do table, then edit: merge duplicates, add "fix once in template" notes]

## Detailed Checks
### [Category]
**[Check name]** — PASS | WARNING | FAIL | INFO · [SEVERITY] · [OBSERVED/INFERRED]
- Evidence: [quote / numbers / URLs]
- Impact: [why it matters for users / crawling / indexing / ranking / AI retrieval]
- Recommendation: [what to do]
- Implementation: [exact change: file/template/config, code snippet if useful]
- Verify: [how to confirm — command, tool, or re-run]

# GEO / AI SEARCH READINESS
**Score:** [n]/100 (readiness, not a citation guarantee)
| Factor | Status | Evidence |
|---|---|---|
| AI crawler accessibility (search vs training bots) | | |
| Content extractability (server-rendered, semantic HTML) | | |
| Factual clarity & answer blocks | | |
| Entity clarity (Organization/Person, sameAs, consistent naming) | | |
| Source attribution & first-hand evidence | | |
| Author information | | |
| Structured data | | |
| Question coverage / topical authority | | |

### AI Citability Opportunities
| Page | Topic | Missing answer | Recommendation |
|---|---|---|---|

## Not measured
[What wasn't checked and which tool/access would measure it: rankings, backlinks, search volume, GSC coverage, CrUX…]

## Next steps
[30-day sequencing of the to-do list; who does what (dev / content / marketing)]
```
