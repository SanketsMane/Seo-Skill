# /seox maps <business/location> — Map-pack intelligence

Map rankings, geo-grid positions, GBP fields and review metrics require a data source (a connected maps/SERP API MCP tool, or data the user provides). Check for available tools first.

## With a data source
- Geo-grid: query the target keyword(s) across a grid of points around the business (e.g. 5×5 or 7×7, radius matched to the trade area); report rank per point, average rank, share of points in top 3.
- GBP completeness: primary/secondary categories, hours, services, description, photos, Q&A, posts recency.
- Reviews: count, rating, velocity (per month), response rate, recurring themes (summarise; quote sparingly).
- Competitors within radius: categories, review counts/ratings, distance, website quality (run `page.py` on their sites).

## Without a data source
Say clearly that rank positions and GBP metrics are **not measured**. Still deliver:
- Category-relevance analysis (which GBP categories fit the services, based on the website).
- Website-side local signals (run the local module).
- A geo-grid *plan*: keywords, grid size, radius, cadence — ready for the user's tool.
- Competitor discovery via WebSearch (names and websites only; no fabricated ranks).

Never fabricate rank positions, review counts or ratings.
