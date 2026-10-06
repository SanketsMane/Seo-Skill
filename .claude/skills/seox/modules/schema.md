# /seox schema <url> — Structured data

## Detect & validate
```bash
python3 $S/schema.py <url> > $D/schema.json
```
Run on one URL per template. Report per entity, keeping two verdicts apart:
- **Schema.org validity** (syntax, @context, types, value formats, @id references).
- **Google rich-result status** (`google[].eligibility`): meets required properties / missing required / restricted / retired / no standalone feature. Rules come from `references/schema-rules.json` (dated snapshot). For any entity marked `verify: true`, or before telling the user to invest in a feature, check Google's current Search Gallery docs.
- **Policy**: marked-up content must be visible on the page; no self-serving review stars for LocalBusiness/Organization; FAQ/QAPage only where the page genuinely is that.
Microdata/RDFa are detected but only JSON-LD is fully validated — recommend Google's Rich Results Test for the others.

## Recommend
Choose types from what the page *is*, not from what earns stars:
- Homepage: `Organization` (or `LocalBusiness` subtype) + `WebSite`; connect with `@id`.
- Articles: `Article`/`BlogPosting` with `author` → `Person` (with `url`, `sameAs`), `publisher` → the Organization `@id`, real dates.
- Products: `Product` + `Offer` (price, priceCurrency, availability) + shipping/return policies where applicable; reviews only if real and visible.
- Breadcrumbs: `BreadcrumbList` matching the visible breadcrumb.
- Others as genuinely applicable: Event, JobPosting, Recipe, VideoObject, SoftwareApplication, Course, Service, Person/ProfilePage, DiscussionForumPosting, Dataset.

## Generate drafts
- Use only verified information from the page/codebase/user. Unknown values → `"[PLACEHOLDER: …]"` and list them for the user to fill. Never invent ratings, reviews, prices, addresses, authors, dates, awards, certifications.
- Prefer one `@graph` per page with stable `@id`s (`https://site/#organization`, `<page-url>#article`).
- Validate every draft before handing it over:
  `python3 $S/schema.py --jsonld draft.json --page-url <url>` — fix until no FAILs (placeholders will be flagged; that's expected until filled).
- In fix mode, insert via the framework's pattern (`references/frameworks.md`), then re-run `schema.py` on the built/served page.
