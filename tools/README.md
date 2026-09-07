# ChoiceBoard publishing tools

The site remains static HTML on GitHub Pages, with no deployment build step.
Run these tools from the repository with Python 3.9 or later. They never commit,
push, change a page to `index`, or publish social messages.

## Commands

| Command | Behavior |
|---|---|
| `python3 tools/new-article.py guides example-slug "Approved title" --type article --query "approved query" --author "The ChoiceBoard team"` | Creates a noindex skeleton; rejects duplicate slugs and overwrites. Complete intake first. Named authors still need the Person node, profile, and biography. |
| `python3 tools/social-images.py guides example-slug --source generated` | Creates the OG and LinkedIn cards from the completed title and first takeaway. Supports `image:PATH`, `screenshot:PATH`, and optional `--story`. Does not mark images approved. |
| `python3 tools/build-llms.py` | Regenerates post Markdown alternates and both root AI indexes. Draft alternates carry a draft label; only indexed posts enter the aggregates. |
| `python3 tools/check-seo.py` | Validates every page and template plus publication boundaries. Exits unsuccessfully on errors; separately prints human review notes. |
| `python3 tools/check-seo.py --post blog/guides/example-slug/index.html` | Checks a finished draft and global publication boundaries before requesting publication approval. |
| `tools/indexnow.sh https://choiceboard.io/blog/guides/example-slug/` | Requires `INDEXNOW_KEY`, a matching local and deployed key file, and an indexed canonical page. Sends an indexing notification only. `--dry-run` validates locally without sending. |
| `python3 tools/test-publishing.py` | Exercises draft exclusion, unpublishing, duplicate tracking, FAQ drift, broken links, input protection, Markdown preservation, image dimensions, and IndexNow boundaries in temporary fixtures. |

Only image generation requires a third-party package: Pillow, declared in
`tools/requirements.txt`. All other tools use Python's standard library.
Install it in your preferred isolated Python environment if unavailable.

Inter and Manrope are bundled under `tools/fonts/` with their respective Open
Font License files. Downloads came from the Google Fonts repository on September
7, 2026: `ofl/inter/Inter[opsz,wght].ttf` and `ofl/manrope/Manrope[wght].ttf`.
You can override paths using `--inter-font` and `--manrope-font` or the
`CHOICEBOARD_INTER_FONT` and `CHOICEBOARD_MANROPE_FONT` environment variables.
The generator uses the existing `logo.png` raster counterpart of `logo.svg`.
There is no font substitution, automatic text truncation, or remote image fetch.

## Draft review and go-live

1. Complete the AGENTS.md intake; create the skeleton.
2. Fill every TODO, including facts, source links, metadata, author, dates, and
   any video transcript/chapters. The skeleton deliberately fails finished-post checks.
3. Generate and visually inspect the cards. Fill image alt text and set
   `og-image: dedicated` only after review.
4. Add draft-to-draft links for a planned batch, regenerate alternates, and run
   the draft checker. Write and review social copy after the article is final.
5. Complete the manual checklist in `seo/audit-2026-09-07.md`, then ask the
   author “Ready to publish?” as required by AGENTS.md.
6. Only after a clear yes, change the approved post and applicable collection
   pages to the specified index directive. Replace “Draft for editorial review”
   and “Publication date pending approval” with honest publication/update dates.
7. Add real cards and incoming links on the hub/series page, remove the empty
   state where appropriate, and update the series ItemList, sitemap, and RSS.
   These editorial list changes are manual; the tools never infer publication
   approval or edit robots directives. Do not link to unapproved drafts from
   indexed publication lists.
8. Run the AI exporter and full checker again. Dates, social copy, and the
   required incoming links must now pass as published content.
9. Commit only when asked. Push only when asked. Verify the deployed pages and
   submit indexing notifications only after deployment.

For the first batch, the hub and series supply two incoming links; articles
link to one another. Collection pages require dedicated social visuals before
indexing. Those images remain pending until publication preparation.

## Scope of validation

The checker verifies machine-readable structure, metadata, links, crawler rules,
analytics installation, image dimensions, FAQ parity, and publication membership.
It does not certify factual accuracy, the completeness of a transcript, image
appearance, consent, expert credentials, search eligibility, indexing, or analytics
receipt. A zero-error report is a technical checkpoint, not publication permission.

Article dates must be synchronized manually at publication. The generator uses
the creation date only as an editable draft value, not proof of a publication date.
Draft Markdown files are editorial artifacts and must not be linked from the live
hub, feed, sitemap, or root AI indexes. HTML noindex does not make a draft private;
keep confidential drafts out of a deployed checkout.
