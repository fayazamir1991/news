# Instructions for repository agents

For preparing or publishing daily reports, first read [DAILY_BRIEFING_PROMPT.md](DAILY_BRIEFING_PROMPT.md), [briefing.config.json](briefing.config.json), and [PUBLISHING.md](PUBLISHING.md). For GitHub discovery, also read [GITHUB_DISCOVERY_SOURCES.md](GITHUB_DISCOVERY_SOURCES.md). New reports begin with one educational arXiv survey: read the entire paper, explain it in depth, and fully translate its Introduction and Conclusion only under a verified license permitting public translation, with attribution. Store the full analysis/translations in `content/surveys/<arxiv_id>.md`; the first daily section contains a title, a verified submission/publication date line, one subject/value paragraph and a dedicated-page link. See canonical sections 4.1 and 8. Old four-section reports remain compatible; only the owner's explicit request authorizes prepending to a published issue. Preserve all existing article bookmark IDs.

They contain the complete editorial scope, Tehran target-day/retry rules, evidence requirements, GitHub discovery criteria, source format and exact-SHA CI/merge process. No chat history is required.

Persist new owner instructions about this project in the canonical prompt and, where relevant, synchronize configuration and related documentation. Do not persist secrets or unnecessary personal information in the public repository.

Do not invent news, source URLs, dates, trending evidence or deployment success. Do not overwrite an already published day's file without an explicit owner request for that edit. Do not treat config flags as credentials or authorization. A fork needs its own publishing authorization, scheduler, hosting and authentication services; the full prompt documents migration.

Report content belongs in `content/briefings/` using Solar Hijri filenames and Persian display dates. Keep changes scoped to the task; do not alter authentication, archive history or infrastructure as part of routine daily publishing. Preserve existing bookmark IDs by avoiding gratuitous source-order changes in published items.

The site is built with `python3 build.py`. CI is `.github/workflows/container.yml`. It tests/builds the site but does not generate or schedule reports. Never commit `dist/` or secrets. Browser PWA tests stop/restart a Docker container named `weekly-news`; run them only in an isolated test environment. Consult [AUTH_SETUP.md](AUTH_SETUP.md) before account-related changes.

Mobile bottom navigation is RTL with five short labels: آرشیو، مروری‌ها، خانه، حساب، ذخیره‌ها. The desktop header includes مقالات مروری. Auth/install controls belong on `/account/`; keep existing OAuth scopes and bookmark identities unchanged.

Survey metadata must include verified `paper_date`, `paper_date_kind` (`submitted` or `published`) and `paper_date_source`. Show the paper date on the daily card and beside the introduction date on its dedicated page. Put all original paper/license links in a separate panel next to the table of contents, before the full text. See the exact date-line contract in PUBLISHING.md.

Every report item supports account-bound like/dislike using the unchanged bookmark ID. Before selecting daily content, follow canonical section 12: query authorized aggregate `public.editorial_feedback`, join the published catalog, and apply collective semantic feedback. Never publish user identities or per-user feeds. See `feedback.py` and `AUTH_SETUP.md`; unknown item IDs are ignored.

Item actions use one adjacent row of icon-only SVG bookmark, like and dislike buttons, matching bottom-nav line icons (24px viewBox, 1.7 stroke). Keep 44px touch targets, accessible labels, tooltips and selected states; no visible text or emoji. Preserve icons when updating saved state, including the bookmarks list.

Render Persian paper date labels as a single inline span within the date flex container and isolate arXiv with `<bdi dir="ltr">`; keep the label RTL so mixed-script dates retain reading order.

From issue 1405-08-20 onward, GitHub repository discovery and validation use GitHub sources only. Start with official monthly Trending (including relevant language filters); external rankings and third-party lists hosted in repositories are excluded. Existing repositories in monthly Trending remain eligible; do not confuse topic/search results with Trending. See canonical section 6 and GITHUB_DISCOVERY_SOURCES.md.

From issue 1405-08-21 onward, add exactly one non-repeating «یادگیری از Face Benchmark» lesson immediately after the daily survey. Begin with face embeddings and training, then verification versus identification, operating-point error metrics, ArcFace, InsightFace and real-world domain shift. Treat face-benchmark.org as a secondary educational guide and verify technical claims, numbers and licenses against papers, official repositories or NIST. Keep the shared bookmark/reaction controls and the same public-report feedback policy.
