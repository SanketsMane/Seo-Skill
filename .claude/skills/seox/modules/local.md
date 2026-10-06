# /seox local <url> — Local SEO

## Gather
`page.py --text` + `schema.py` on homepage, contact page and every location/service-area page (find them in a crawl: `crawl.py --max 80`). Collect the NAP (name, address, phone) exactly as written on each page, in schema, and in the footer.

## Evaluate
- **Business model**: storefront, service-area business (SAB), hybrid, multi-location. SABs shouldn't show a street address publicly if they hide it on their Business Profile.
- **NAP consistency** across site pages and schema (character-level: suite numbers, abbreviations, phone formats). Off-site citations (directories) are UNVERIFIED unless you check them via WebSearch/WebFetch — if you do, list sources checked.
- **Google Business Profile**: you can't read GBP data without an API/tool. Check what's verifiable (Maps link/embed on site, review links); mark profile completeness, categories, hours and review data as UNVERIFIED unless the user provides them or a tool is connected. Never invent ratings or review counts.
- **Location pages**: one per real location, unique content (staff, directions, parking, local photos, area-specific services, local testimonials with permission), embedded map, hours, LocalBusiness schema with correct subtype, `geo`, `openingHoursSpecification`. Flag near-duplicate city pages (doorway risk).
- **Service-area pages**: genuine differentiation per area; avoid swapping only the city name.
- **Local schema**: subtype accuracy, address/phone matching visible NAP, no self-serving review markup.
- **Local intent coverage**: services × locations users actually search (label volume as not measured without data).
- **Reviews**: on-site testimonials authentic, attributed, dated; review acquisition process (recommendation only).

## Multi-location
Analyze each location separately in a table: URL · NAP match · schema · unique content · map · hours · issues.

## Output
Local findings into manual.json (`content`/`schema`/`onpage` categories as appropriate), location table, prioritized fixes, and a GBP checklist the owner can verify themselves.
