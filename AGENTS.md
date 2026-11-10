# Instructions for repository agents

For preparing or publishing daily reports, first read [DAILY_BRIEFING_PROMPT.md](DAILY_BRIEFING_PROMPT.md), [briefing.config.json](briefing.config.json), and [PUBLISHING.md](PUBLISHING.md). For GitHub discovery, also read [GITHUB_DISCOVERY_SOURCES.md](GITHUB_DISCOVERY_SOURCES.md). New reports begin with one educational arXiv survey: read the entire paper, explain it in depth, and fully translate its Introduction and Conclusion only under a verified license permitting public translation, with attribution. See canonical section 4.1. Old four-section reports remain compatible; only the owner's explicit request authorizes prepending to a published issue. Preserve all existing article bookmark IDs.

They contain the complete editorial scope, Tehran target-day/retry rules, evidence requirements, GitHub discovery criteria, source format and exact-SHA CI/merge process. No chat history is required.

Persist new owner instructions about this project in the canonical prompt and, where relevant, synchronize configuration and related documentation. Do not persist secrets or unnecessary personal information in the public repository.

Do not invent news, source URLs, dates, trending evidence or deployment success. Do not overwrite an already published day's file without an explicit owner request for that edit. Do not treat config flags as credentials or authorization. A fork needs its own publishing authorization, scheduler, hosting and authentication services; the full prompt documents migration.

Report content belongs in `content/briefings/` using Solar Hijri filenames and Persian display dates. Keep changes scoped to the task; do not alter authentication, archive history or infrastructure as part of routine daily publishing. Preserve existing bookmark IDs by avoiding gratuitous source-order changes in published items.

The site is built with `python3 build.py`. CI is `.github/workflows/container.yml`. It tests/builds the site but does not generate or schedule reports. Never commit `dist/` or secrets. Browser PWA tests stop/restart a Docker container named `weekly-news`; run them only in an isolated test environment. Consult [AUTH_SETUP.md](AUTH_SETUP.md) before account-related changes.
