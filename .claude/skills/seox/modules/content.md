# /seox content <url> — Content quality & E-E-A-T

## Gather
`page.py <url> --text` for the page (and for 3–6 sibling pages if auditing a section). Also fetch, if they exist: about page, author pages, contact page, editorial/review policy. For YMYL topics, apply a stricter bar.

## Evaluate — every point needs a quote or URL as evidence
**Experience**: first-hand use, original photos/data, specific details only a practitioner would know, case studies.
**Expertise**: named author, relevant credentials shown, author page with background, accuracy of claims (spot-check 2–3 factual claims; flag anything wrong or unsupported).
**Authoritativeness**: references to recognised sources, the site's own standing on the topic (topical depth across pages), mentions/citations (UNVERIFIED without backlink data).
**Trust**: business identity, contact details, about page, policies, editorial transparency, published/updated dates that reflect real edits, HTTPS, no deceptive design. Trust is the most important element.

**Helpfulness**: does it satisfy the intent better than a generic summary? Original information vs rehash; thin/templated/AI-generic patterns (vague claims, no specifics, repetitive structure, filler intros); duplication across pages; topical completeness; content freshness where the topic changes.

## Depth rule
No universal word count. Decide adequate depth from intent, page type, topic complexity, and what top-ranking pages cover (WebSearch if needed). Recommend adding content only when it serves a missing user need; recommend cutting or consolidating when content is padding.

## Output
- Verdict per E-E-A-T pillar: Strong / Adequate / Weak / Missing, with evidence.
- Helpful-content issues with examples (quote the passage).
- Specific improvements: what to add (e.g. "author box with [PLACEHOLDER: credential]", "original comparison table of X", "cite primary source for claim Y"), what to remove/merge.
- Write each judgment into manual.json under `content` (and `geo` for citability) so it is scored.
