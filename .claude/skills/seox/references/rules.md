# Accuracy, Safety & Guideline Rules

## Evidence labels
- **OBSERVED** — directly measured by a script or by reading the page/code (quote it).
- **INFERRED** — a reasoned conclusion from observed evidence (state the reasoning). Heuristic script checks carry this label.
- **RECOMMENDED** — your proposed action or content.
- **UNVERIFIED** — could not be checked (blocked, needs credentials, needs paid data). Say what would verify it.

## Never fabricate
Backlinks, rankings, traffic, search volume, keyword difficulty, CTR, reviews, ratings, prices, addresses, phone numbers, opening hours, authors, credentials, dates, awards, certifications, statistics, quotes, sources/citations, schema property values, competitor data, AI-citation occurrences.
- In drafts use `[PLACEHOLDER: author name + credentials]`, `[PLACEHOLDER: verified statistic + source]`.
- Search volume without a data tool: give relative intent/priority reasoning, and label it "volume not measured".
- Never claim a page "will rank", "will get rich results", or "will be cited by ChatGPT/Perplexity/AI Overviews".

## Prohibited tactics
Keyword stuffing (including alt text and schema), hidden/cloaked text, doorway pages, scaled low-value pages, misleading or sneaky redirects, fake reviews/ratings markup, self-serving review markup on LocalBusiness/Organization, markup describing content not visible to users, link schemes, copying competitor content, expired-domain or site-reputation abuse.

## Myths to never hard-code
- No ideal keyword density; repetition is a symptom to read, not a target.
- No universal minimum word count; depth follows intent, page type and what satisfies users.
- Multiple H1s are not an error for Google (one clear H1 is still good practice).
- Not every page needs FAQ schema, an FAQ section, or outbound links.
- Decorative images should have `alt=""`, not descriptive alt.
- More headings, more backlinks, longer titles are not inherently better.
- Meta keywords are ignored by Google; `priority`/`changefreq` in sitemaps are ignored by Google.
- robots.txt blocks crawling, not indexing; use noindex (on a crawlable page) to keep pages out.
- `llms.txt` is an optional proposal; Google Search does not use it. Low priority.
- Core Web Vitals matter as part of page experience, but relevance and quality dominate; don't oversell speed fixes.
- E-E-A-T is a framework raters use, not a single ranking factor or score.

## Before acting on time-sensitive behaviour
Rich-result eligibility, AI crawler user agents, Google feature launches/retirements and CWV thresholds change. If a recommendation depends on them and matters to the user's decision, check official docs (developers.google.com/search, bing.com/webmasters, the AI vendor's crawler docs) and cite the URL and date.

## Write-ups
- Lead with what matters most; group by priority, not by script.
- One finding = issue · evidence · why it matters · fix · how to verify.
- Name affected URLs (or a count + examples for site-wide patterns).
- Separate "fix in the template once" from "fix page by page".
