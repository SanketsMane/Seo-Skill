# seox — SEO + GEO engineering skill for Claude Code

A Claude Code skill that audits websites with measured evidence, scores them with a weighted SEO Health Score, plans content, and implements fixes in codebases with before/after verification.

## Install

For all projects (user-level):

```bash
git clone https://github.com/SanketsMane/Seo-Skill.git
mkdir -p ~/.claude/skills && cp -R Seo-Skill/.claude/skills/seox ~/.claude/skills/seox
```

For one project only, copy `.claude/skills/seox/` into that project's `.claude/skills/` folder. Start a new Claude Code session afterwards, then run `/seox`.

Requirements: Python 3.9+ (stdlib only), `curl`. Optional: `PSI_API_KEY` env var for reliable PageSpeed/CrUX data; Playwright (`pip3 install playwright && python3 -m playwright install chromium`) for rendered-vs-raw HTML checks.

## Commands

```
/seox <url>                      auto-selects depth
/seox audit <url>                full site audit + report
/seox technical <url>            crawl/index/HTTPS/CWV/rendering
/seox page <url>                 deep single-page analysis
/seox content <url>              E-E-A-T and helpfulness
/seox schema <url>               validate + draft JSON-LD
/seox geo <url>                  AI search readiness
/seox local <url>                local SEO
/seox maps <business>            map-pack intelligence (needs a data source for ranks)
/seox images <url>               image SEO + alt text
/seox sitemap <url>              validate / generate
/seox hreflang <url>             international SEO
/seox competitor-pages ...       vs / alternatives pages
/seox plan <business|url>        strategy + 30/60/90
/seox programmatic ...           pSEO with quality gates
/seox blog <topic>               also: blog plan, blog optimize <url>, content brief <kw>
/seox keywords <topic|url>       intent + clusters
/seox internal-links <url>       link graph + suggestions
/seox fix <url> | fix all        AUDIT ONLY (default) / --mode recommend / --mode auto
```

## Layout

```
.claude/skills/seox/
├── SKILL.md              orchestrator: router, rules, conventions
├── modules/              one playbook per command (loaded on demand)
├── references/           rules, scoring, report template, AI-search, frameworks, schema-rules.json
└── scripts/              evidence collectors (JSON out, shared check format)
    page.py  robots.py  sitemap.py  schema.py  crawl.py  hreflang.py
    variants.py  psi.py  render.py  detect_stack.py  score.py
```

Scripts can be run directly (`python3 scripts/page.py https://example.com`), and each one supports `-h`.

## Maintenance

`references/schema-rules.json` and `references/ai-search.md` are dated snapshots of Google rich-result rules and AI crawler behaviour. Review them when Google or the AI vendors announce changes.
