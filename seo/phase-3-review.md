# Phase 3 review packet

Prepared September 7, 2026. All three posts remain unpublished drafts with
`noindex, nofollow`. They are excluded from the blog collections, sitemap, RSS
feed, `llms.txt`, and `llms-full.txt` until the go-live gate.

## Drafts

1. [Group decision making process for teams](../blog/guides/group-decision-making-process/index.html)
   targets `group decision making process` and cites Atlassian's DACI framework.
2. [Decision matrix template for team choices](../blog/templates/decision-matrix-template/index.html)
   targets `decision matrix template`, cites the American Society for Quality,
   and includes a downloadable workbook.
3. [Pairwise comparison method for team decisions](../blog/guides/pairwise-comparison-method/index.html)
   targets `pairwise comparison method` and cites the 1000minds methodology guide
   for the pair-count formula and preference-cycle limitation.

Each draft includes a dedicated Open Graph image, a LinkedIn square image, a
Markdown alternate, ready-to-paste social copy, a key-takeaways box, a visible FAQ
that matches its structured data, one signed blockquote, one primary call to
action, and links to both related drafts.

## Workbook verification

The decision-matrix workbook has a blank template and a separate hypothetical
worked example. Its formulas were recalculated and checked for:

- the published example totals of 3.3, 3.5, and 3.1;
- changed weights producing totals of 3.0, 3.8, and 4.0;
- blank, zero, and fractional ratings suppressing the total;
- weights outside a valid 100% set suppressing the total; and
- formula errors across the workbook.

Both sheets were rendered and visually reviewed. The downloadable site copy and
the review-output copy are identical.

## Validation result

`tools/check-seo.py` reports **0 errors and 18 review notes**. The notes identify
the expected publication gate, unpublished collection pages, existing placeholder
footer links, and checks that require a live URL. The publishing regression suite
reports **12 tests passed**. The three X drafts are 216, 242, and 240 characters,
including their URLs.

## Required before publication

- Complete editorial review of the prose, source framing, workbook, and images.
- Confirm the actual publication date and update the publication metadata.
- Run Google's Rich Results Test on the live candidate.
- Add the post cards and incoming links from the blog and series pages.
- After an explicit “Ready to publish?” approval, switch the posts to `index`, add
  them to the sitemap and feed, regenerate the AI indexes, and repeat the checker.
- After deployment, verify the live links and social previews, submit to IndexNow,
  request Google indexing, and schedule the one-week and one-month citation checks.
