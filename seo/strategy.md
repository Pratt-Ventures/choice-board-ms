# ChoiceBoard SEO strategy

The publishing and search optimization strategy is maintained in
[AGENTS.md](../AGENTS.md). Follow its keyword targeting, technical SEO,
AI-search, and publication requirements for every new page.

## Analytics on every page

Google Analytics 4 uses measurement ID `G-ZLZMXRHMBS`. Every existing and
future HTML page must include the canonical Google tag snippet in
[AGENTS.md §12](../AGENTS.md#12-head-checklist-every-article) immediately
after the opening `<head>`, exactly once. This includes the landing page,
blog hub, series pages, articles, video/story pages, and drafts. All new
templates and page generators must include the same snippet.

Before shipping a page, verify the async script URL contains this ID, the
data layer and `gtag` function are initialized, and there is exactly one
configuration call for this ID in the head. Do not install a duplicate
through another script or tag manager. The planned `tools/check-seo.py`
must enforce this requirement across all HTML pages and templates,
including `noindex` pages. Until that checker exists, check it manually.

After deployment, confirm a visit to the landing page and each newly
published page appears in the intended Google Analytics property using
Realtime or DebugView. Record any verification that still needs account
access; adding the snippet alone does not confirm data receipt.

## Measurement and review

Use Google Analytics to review landing-page traffic, acquisition sources,
and engagement by page. Review these alongside Search Console and Bing
Webmaster query and indexing data, plus the AI citation checks in
AGENTS.md §18, when deciding which content to improve. Keep target queries
in `seo/keyword-plan.md` when that plan is created. Analytics installation
is required regardless of whether a page targets a query.
