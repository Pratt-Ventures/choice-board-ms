# ChoiceBoard content — publishing guide for AI agents

This file is the single source of truth for publishing content on
`choiceboard.io`. Read it in full before creating or editing any article,
landing page, or social copy. It is loaded automatically by `CLAUDE.md`.

The goal is not "write a blog post". The goal is that every piece we ship
ranks on traditional search engines (Google, Bing, DuckDuckGo), appears in
AI search results (Google AI Overviews / AI Mode, Perplexity, ChatGPT
search, Bing Copilot), and is served up as a cited source by multi-model
AI assistants (ChatGPT, Claude, Gemini, Grok, Meta AI, Siri). Every rule
below exists to serve one of those three outcomes.

---

## 1. Objective

Be the English-language reference on **group decision-making for teams**:
how teams compare options, weigh what matters, surface disagreement, and
reach a ranked, defensible result. Own that topic in Google **and** in the
answers of AI assistants.

Positioning in one sentence (use it, don't rewrite it):

> ChoiceBoard is group decision-making software. Teams define options and
> factors, answer quick head-to-head comparisons, and get a ranked result
> with a measured level of agreement — a decision they can defend.

## 2. Language and typography

- Everything is in **US English**: article body, `<title>`, meta
  description, OG/Twitter tags, alt text, JSON-LD strings, FAQ, `index.md`,
  text on social images, and git commit messages.
- Sentence case for headings ("How to make a group decision in four steps").
- Curly quotes (“ ”), Oxford comma, numerals for 10 and above, `%` with no
  space (`87%`), en dash for ranges (`3–5`), em dashes sparingly.
- No exclamation marks in body copy. One in a social post is the maximum.
- Spell out an acronym on first use in each post.

## 3. Non-negotiable rules — ask, never assume

1. **Post type.** Always ask which type the post is (`article`, `video`,
   `story`). Never generate without it.
2. **Series.** Always ask which series it belongs to (see §5).
3. **Target query.** Always ask which query from the keyword plan the post
   targets, or `none`. `none` is a recorded decision, not an omission.
4. **Author.** Always ask who signs the post. Default is `The ChoiceBoard
   team`. When a real person signs, apply the author procedure in §11.
5. **Facts.** Every number, statistic, or claim in a post must come from the
   author or from a cited source. **Never invent statistics, customer
   names, company names, quotes, or testimonials.** The `87% agreement`
   figure on the landing page is illustrative product output, not a stat.
6. **Images.** Always ask where the OG / social visuals come from: a file the
   author provides, a product screenshot, or a generated card. A dedicated OG
   image is mandatory for every indexed post.
7. **Style corpus.** Only **indexed, live** posts and the landing page are
   voice references. Never read drafts, unpublished or `noindex` pages, or
   templates for tone.
8. **Go-live gate.** Never switch `robots` to `index` on your own. When the
   post passes every check, ask "Ready to publish?" and wait for a clear yes.
9. **Git.** Commit only when asked. Push only when asked. Never force-push
   `main`.

## 4. Two layers of optimization — keep them separate

Every post goes through two distinct checks. Don't conflate them:

1. **Keyword targeting** (per post, *optional*): does this post target one
   priority query from the keyword plan? Guides, templates, and comparison
   posts almost always do. Company news and some product posts don't. The
   decision is recorded in the meta block (§8) as `query: …` or `query: none`.
2. **Baseline SEO and AI-search optimization** (*every post, no exceptions*):
   head tags, JSON-LD, canonical, sitemap, feed, dedicated OG image, social
   visuals and copy, "Key takeaways" box, FAQ, markdown alternate,
   `llms.txt`, internal links, honest dates, and the Google Analytics tag
   specified in §12 on every HTML page. See `seo/strategy.md` for the
   measurement requirements.

## 5. Series

| Series | URL | Intent | Typical formats |
|---|---|---|---|
| Decision-making guides | `/blog/guides/` | informational, top of funnel | long-form how-to, frameworks, explainers |
| Templates and frameworks | `/blog/templates/` | informational → consideration | reusable decision templates (vendor selection, hiring panel, roadmap prioritization) with a "run it in ChoiceBoard" section |
| Comparisons and alternatives | `/blog/compare/` | commercial investigation | "X vs Y", "best tools for…", "decision matrix alternatives" |
| Product | `/blog/product/` | navigational / consideration | release notes with screenshots, feature deep-dives, demo videos |
| Customer stories | `/blog/customers/` | transactional, social proof | interview-based stories, video + write-up |
| Company | `/blog/company/` | brand, E-E-A-T | founding story, how we think about decisions, team |

One post lives in exactly one series. A post that fits two intents is two
posts linked to each other.

## 6. Voice — derived from the live corpus

Before drafting anything, read `index.html` (the landing page) in full and
the three most recent indexed posts:

```bash
grep -L 'noindex' blog/*/*/index.html | xargs ls -t | head -3
```

The pool grows over time. The bigger it gets, the closer the match must be.

Voice observed on the landing page (keep it, don't drift):

- **Register.** Confident, direct, lightly witty. Talk to one reader as
  "you". "We" is ChoiceBoard. Never salesy, never breathless, never corporate.
- **Sentences.** Short and declarative. One idea per sentence. Paragraphs of
  two to four sentences. Headings that could stand alone as a claim
  ("Results you can defend in any boardroom").
- **Structure.** Opening paragraph names the problem the reader has right
  now. "Key takeaways" box with 4–5 self-contained bullets. `h2` sections
  that each answer one question. Numbered steps when describing a process.
  One blockquote signed by the author (or a customer in a story). A
  "Frequently asked questions" section. One call to action.
- **The refrain.** ChoiceBoard doesn't hide disagreement, it measures it. Say
  it once, explicitly, in every post that mentions the product.
- **Facts over adjectives.** Give figures with a scope and a source. Date
  every claim. Name the framework (pairwise comparison, weighted scoring,
  Condorcet, Bradley–Terry) when it's relevant, and define it in one sentence.
- **Honesty about the product.** ChoiceBoard structures a decision. It does
  not make the decision, and it does not replace the judgment of the person
  who has to make the call.

**Vocabulary to use:** group decision, team decision, head-to-head
comparison, pairwise comparison, options, factors, weights, ranking, ranked
result, level of agreement, dissent, buy-in, defensible decision, decision
matrix, weighted scoring, vendor selection, feature prioritization,
stakeholder alignment, the person who has to make the call.

**Vocabulary to avoid:** revolutionize, game-changer, disrupt, seamless,
leverage (as a verb), synergy, "AI-powered" as a selling point, "unlock",
"supercharge", "in today's fast-paced world", "it's no secret that", any
sentence that could open a LinkedIn post about hustle.

## 7. Target queries

The keyword plan is maintained separately in `seo/keyword-plan.md`. **When
that file exists, it overrides the seed list below.** Until then, use these
seeds, which come from the landing page's existing positioning.

| Series | Seed queries |
|---|---|
| Guides | `how to make a group decision`, `group decision making process`, `team decision making methods`, `how to get team buy-in on a decision`, `pairwise comparison method` |
| Templates | `decision matrix template`, `weighted decision matrix`, `vendor selection criteria template`, `feature prioritization framework`, `hiring decision matrix` |
| Compare | `group decision making software`, `team decision making tool`, `pairwise comparison tool`, `decision matrix alternative`, `best prioritization tools for product teams` |
| Product | `ChoiceBoard`, `ChoiceBoard pricing`, `ChoiceBoard features`, `ChoiceBoard vs [tool]` |
| Customers | `ChoiceBoard review`, `[industry] decision making tool`, `how [type of team] makes decisions` |
| Company | `ChoiceBoard`, `who makes ChoiceBoard`, `is ChoiceBoard free` |

Question-form queries (what AI Overviews, Perplexity, and "People also ask"
actually match). Use them as `h2` and FAQ questions, worded exactly the way
a manager would type them:

- "How do you make a decision as a group without endless meetings?"
- "What is a pairwise comparison and when should a team use one?"
- "How do you weight criteria in a decision matrix?"
- "Is voting or consensus better for team decisions?"
- "How do you get buy-in on a decision people disagree with?"
- "What is the best tool for vendor selection?"
- "How do product teams prioritize features fairly?"
- "What is group decision-making software?"
- "How is ChoiceBoard different from a decision matrix spreadsheet?"

Rules when a post targets a query:

- **One main query per post**, at the start of the `<title>`, in the `<h1>`,
  in the meta description, and in the first paragraph.
- Secondary queries become `<h2>` headings and FAQ questions.
- One post = one intent. Two intents = two posts, linked to each other.
- Never stuff. If the query reads unnaturally twice in one paragraph, once
  is enough.

Search Console and Bing Webmaster data are not available yet. When they are,
the keyword plan replaces the seeds with real queries and their volumes.

## 8. Intake — ask all of this before generating

Ask in one message and wait for the answers:

1. Post type: `article` / `video` / `story`.
2. Series (§5).
3. Working title and the angle in one sentence.
4. Target query from the keyword plan, or `none`.
5. Author: a named person (name, title, LinkedIn URL) or `The ChoiceBoard team`.
6. For video posts: YouTube ID, duration, chapters, and the full transcript.
7. Three hard facts or figures the post must contain, each with its source.
8. For customer stories: the customer's name, company, role, written
   permission to publish, and the quotes they approved.
9. OG / social image source: provided file, product screenshot, or generated card.
10. Call to action (default: free tier, see §14).

## 9. Per-article meta block

Every article carries an HTML comment at the top of `<head>`. The generator
creates it, you fill it in, the checker enforces it on indexed posts:

```html
<!-- choiceboard-meta
     type: article                       (article | video | story)
     series: guides
     query: how to make a group decision (or: none)
     author: The ChoiceBoard team        (or the person's full name)
     og-image: pending                   (pending | dedicated)
     published: 2026-09-07
     modified: 2026-09-07
-->
```

- `query` other than `none` → every word of the query must appear in the
  `<title>`, and the query should open it.
- `author` other than `The ChoiceBoard team` → a matching `Person` in JSON-LD
  and the name in the visible byline.
- `og-image: pending` blocks publication. There is no "default" option;
  every indexed post gets its own image.

## 10. Publishing workflow

1. **Intake** (§8), then create the skeleton as `noindex` from the template
   for the post type (§17). Slug: short, lowercase, hyphenated, the main
   query's key words, no stop words where avoidable
   (`group-decision-making-process`, not `the-ultimate-guide-to-…`).
2. **Read the live corpus** (§6) before writing a single sentence.
3. **Write the article** in the voice above. Fill the meta block. Apply the
   keyword rules if a query is targeted.
4. **Author.** Apply §11 if a person signs.
5. **`<head>`.** `<title>` 50–60 characters, description 140–160,
   canonical, full OG and Twitter set, ISO 8601 dates, JSON-LD (§12, §13),
   and exactly one Google Analytics snippet from §12.
6. **Video** (video and story posts): set the YouTube ID (facade + chapters
   + noscript + JSON-LD `embedUrl`), duration (`PT12M34S` and displayed
   `12:34`), thumbnail, and paste the **full transcript** into
   `<details class="transcript">`. Chapter `data-start` values must match
   the JSON-LD `Clip` entries.
7. **Images.** Produce the OG image and the social set (§15). Set
   `og:image`, `og:image:alt`, `twitter:image`, and the JSON-LD `image`.
   Set `og-image: dedicated`. Every `<img>` gets a descriptive `alt` that
   says what is shown, not "image" or "screenshot".
8. **Internal linking.** Add the post card on `/blog/` and on its series
   page (including the `ItemList` JSON-LD). Update "Read next" blocks on
   the two closest neighboring posts. Each post gets at least 2 incoming
   internal links and links out to 1–2 posts plus the relevant landing page
   section (`/#how-it-works`, `/#pricing`, `/#use-cases`).
9. **AI-search layer.** Regenerate the markdown alternates and
   `llms-full.txt` (§17).
10. **Check.** The checker must report 0 errors while the post is still
    `noindex` (§17).
11. **Social copy.** Write `social.md` next to the article (§16).
12. **Go-live gate.** Show the author the checker output and ask "Ready to
    publish?". Only after a yes, follow §19.

## 11. Author procedure (E-E-A-T)

A post signed by an identifiable person with relevant experience outranks
"The ChoiceBoard team" on advice queries, and AI assistants weight named
expertise when deciding what to cite.

When a person signs the post:

1. Add a `Person` node to the `@graph` and point the `BlogPosting` to it:

   ```json
   {
     "@type": "Person",
     "@id": "https://choiceboard.io/#person-firstname-lastname",
     "name": "Firstname Lastname",
     "jobTitle": "Founder, ChoiceBoard",
     "worksFor": { "@id": "https://choiceboard.io/#organization" },
     "sameAs": ["https://www.linkedin.com/in/…"]
   }
   ```

   ```json
   "author": { "@id": "https://choiceboard.io/#person-firstname-lastname" }
   ```

2. `<meta property="article:author" content="https://www.linkedin.com/in/…">`.
3. Visible byline: `<strong>Firstname Lastname</strong>` in `.byline`.
4. The `.authorcard` at the end of the post: name, one-line bio (role,
   relevant experience, one concrete credential), link to LinkedIn.
5. The blockquote `<footer>` carries the same name.
6. `author:` in the meta block is the same name, character for character.

When `The ChoiceBoard team` signs, leave the template's Organization author.

In all cases: cite primary sources with outgoing links (academic papers on
group decision-making, published frameworks, official documentation of
tools we compare against), and show accurate publication **and** update
dates.

## 12. `<head>` checklist (every article)

- **Analytics.** Google Analytics 4 measurement ID: `G-ZLZMXRHMBS`.
  Include the exact snippet below immediately after the opening `<head>`
  on every HTML page: landing pages, the blog hub, series pages, articles,
  video/story pages, drafts, and any future pages. Include it in every
  page template and generator so new pages inherit it. Load the script
  and call `gtag('config', 'G-ZLZMXRHMBS')` exactly once per page; never
  add a second installation through another script or tag manager.
  Markdown alternates, feeds, and other non-HTML files do not run the tag.

  ```html
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-ZLZMXRHMBS"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());

    gtag('config', 'G-ZLZMXRHMBS');
  </script>
  ```
- `<title>` (50–60 chars, main query first when targeted, ends with
  `| ChoiceBoard`)
- `<meta name="description">` (140–160 chars, answers the search intent in
  the first clause)
- `<link rel="canonical">` — `https://choiceboard.io/blog/<series>/<slug>/`
  with trailing slash
- `<meta name="robots">` — `noindex, nofollow` until go-live, then
  `index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1`
- `<meta name="theme-color" content="#4059D8">` (inherited from the site)
- `og:type=article`, `og:site_name=ChoiceBoard`, `og:locale=en_US`,
  `og:url`, `og:title`, `og:description`, `og:image` (1200×630, absolute
  URL), `og:image:width`, `og:image:height`, `og:image:type`, `og:image:alt`
- `article:published_time`, `article:modified_time` (ISO 8601 with offset),
  `article:author`, `article:section` (the series name), three `article:tag`
- `twitter:card=summary_large_image`, `twitter:site` (fill in once the X
  handle exists), `twitter:title`, `twitter:description`, `twitter:image`,
  `twitter:image:alt`
- `<link rel="alternate" type="application/rss+xml" href="/blog/feed.xml">`
- `<link rel="alternate" type="text/markdown" href="index.md">`
- Favicon and fonts inherited from the landing page (`index.html`). Do not
  add a second font family.

## 13. JSON-LD checklist

Use one `<script type="application/ld+json">` with an `@graph`:

- `Organization` (`@id` `https://choiceboard.io/#organization`, `name`,
  `url`, `logo` `https://choiceboard.io/logo.png`, `description` identical
  to the one in `index.html`, `sameAs` with every social profile once they
  exist)
- `WebSite` (`@id` `#website`, `publisher` → `#organization`)
- `BlogPosting`: `headline` (≤ 110 chars), `description`, `image`,
  `datePublished`, `dateModified`, `author`, `publisher`, `isPartOf`
  (`#website`), `articleSection`, `keywords`, `inLanguage` `en-US`,
  `wordCount` (real count ± 25%), `timeRequired`, `mainEntityOfPage`,
  `speakable` pointing to `.article-hero__head` and `.takeaways`
- `BreadcrumbList` (Home → Blog → Series → Post)
- `VideoObject` with `hasPart` `Clip` chapters (video and story posts)
- `FAQPage` identical word for word to the visible FAQ
- `Person` when a person signs (§11)
- `SoftwareApplication` only on product posts, and only as a reference to
  the one on the landing page (`@id` `#software`), never duplicated with
  different pricing

Validate with the Rich Results Test before go-live. Never put a claim in
JSON-LD that isn't visible on the page.

## 14. Calls to action

- **Default CTA:** free tier. The landing page includes a free Starter plan
  with 20 responses and no credit card required. **The signup URL does not exist yet.** Until it is
  recorded here, every CTA links to `/#pricing`. When the app URL is known,
  add it here and replace every CTA in one commit.
- **Secondary CTAs** by series: guides → the matching template post;
  templates → free tier; compare → `/#pricing`; product → free tier;
  customers → free tier; company → `/#how-it-works`.
- One primary CTA per post, placed after the reader has gotten value (never
  above the "Key takeaways" box). A second, softer mention in the closing
  paragraph is allowed.
- CTA markup uses the landing page's `.btn .btn-primary` / `.btn-ghost`
  classes so any future click tracking works site-wide.

## 15. Social images

Every published post ships with a dedicated visual set in
`images/blog/<slug>/`:

| File | Size | Used for |
|---|---|---|
| `og.png` | 1200×630 | `og:image`, LinkedIn, X, Slack unfurls |
| `linkedin-square.png` | 1080×1080 | LinkedIn carousel / square |
| `story.png` | 1080×1920 | Instagram and LinkedIn stories (optional) |

Image source is decided with the author every time (intake question 9):
a provided file, a product screenshot (framed on the site's `--cream`
background with the `--brand` accent), or a generated typographic card
(title + first "Key takeaways" bullet + series label, Manrope headline,
Inter body, brand colors from `index.html`'s `:root` tokens).

Text on cards is US English, sentence case, no exclamation marks. The
ChoiceBoard mark (`logo.svg`) appears once, small, bottom-left. The site's
`og-image.png` is the landing page's image only; never reuse it for a post.

## 16. Social copy (after the post is finished)

Once the article is final and the checker passes, write
`blog/<series>/<slug>/social.md` with three ready-to-paste posts in the
blog's voice. Each one teases the post and sends the reader to it. Never
summarize the whole post: one insight, one figure, or one question, then
the link.

```markdown
# Social — <post title>

URL: https://choiceboard.io/blog/<series>/<slug>/

## X
<≤ 280 characters including the URL; one insight; no hashtags or at most two>

## LinkedIn
<hook line that carries the insight (shown before "see more"), then 4–8
short lines with one concrete fact or figure, one line saying the rest is
in the post, the URL on its own line, then 3 hashtags on their own line>
#DecisionMaking #Leadership #ProductManagement

## Newsletter blurb
<2–3 sentences for an email digest: what the reader will be able to do
after reading, then a text link on "Read the post">
```

Rules:

- Same facts as the article, no new claims.
- The hook is a claim or a question, not a title. "Most team decisions are
  made by whoever talked last" beats "New post: group decision-making".
- Hashtags: pick three from `#DecisionMaking #Leadership
  #ProductManagement #Prioritization #VendorSelection #TeamAlignment`
  per post, matched to the series.
- Pair each post with the matching visual from `images/blog/<slug>/`.

## 17. Site structure and tooling

### Current state of the repo

The site is static HTML deployed via GitHub Pages (`CNAME` → `choiceboard.io`,
no deployment build step). As of September 7, 2026, the blog hub, six series
pages, article/video/story templates, and the five publishing tools below exist.
The hub, series pages, and templates remain `noindex`; no articles have been
published. See `tools/README.md` for operation and manual publication steps,
`seo/keyword-plan.md` for query ownership, and `seo/audit-2026-09-07.md` for
remaining editorial and account-dependent checks. The checker reports automated
errors separately from required human review; zero errors is not publication
approval.

```
index.html                     Landing page (SEO head, inline CSS, markup, inline JS)
CNAME, robots.txt, sitemap.xml GitHub Pages + crawler files
logo.svg, logo.png, og-image.png
──────────────── publishing foundation ────────────────
blog/index.html                Blog hub (featured post + card grid)
blog/<series>/index.html       Series page with ItemList JSON-LD
blog/<series>/<slug>/index.html  Article (noindex until go-live)
blog/<series>/<slug>/index.md    Markdown alternate (generated)
blog/<series>/<slug>/social.md   Social copy
blog/_templates/article/index.html
blog/_templates/video/index.html
blog/_templates/story/index.html
blog/feed.xml                  RSS 2.0
images/blog/<slug>/            Social image set
llms.txt                       Index for AI assistants (site root)
llms-full.txt                  Full text of every indexed post (generated)
seo/keyword-plan.md            The keyword plan (separate workstream)
seo/citation-log.md            AI citation checks (§18)
tools/                         Scripts below
```

### Tools (build these; keep the interface stable)

| Command | Role |
|---|---|
| `python3 tools/new-article.py <series> <slug> "Title" --type <article\|video\|story>` | creates a post from the template, `noindex`, with the meta block filled in and the §12 analytics snippet |
| `python3 tools/social-images.py <series> <slug> --source <generated\|image:PATH\|screenshot:PATH>` | OG image + social set, prints the head tags to paste |
| `python3 tools/build-llms.py` | regenerates every `index.md`, `llms.txt`, and `llms-full.txt` from indexed posts |
| `python3 tools/check-seo.py` | validates every rule in §12, §13, §20, and the crawler allowlist in `robots.txt`; also checks every HTML page and template for exactly one §12 analytics installation; 0 errors required |
| `tools/indexnow.sh <url…>` | submits published URLs to Bing / IndexNow |

Templates are `noindex` and must never be published or used as a style
reference. Edit a template only to change the structure for all future
posts.

### Landing page facts (for cross-linking and consistency)

- Design tokens live on `:root` in `index.html` (`--brand #3F5AD9`,
  `--accent #14967F`, `--ink`, `--navy`, `--cream`, radii, `--max 1180px`,
  Manrope headings, Inter body). Blog pages reuse them; never hard-code
  colors.
- Section anchors: `#top`, `#how-it-works`, `#features`, `#use-cases`,
  `#pricing`, `#faq`. Keep them stable; nav, footer, and blog links depend
  on them.
- Pricing: Starter $0, Pro $7, Team $29. If pricing changes on the landing
  page, grep every post for the old figure the same day.
- The placeholder testimonials were removed from the local landing page in the
  September 7 SEO foundation pass. Never restore or quote them as customer
  evidence, and never reference a customer that does not exist.
- The hero duel copy is the canonical example of the voice.

## 18. AI search engines and multi-model assistants

### What makes LLMs cite us (maintain on every post)

- `llms.txt` (index with a one-paragraph company description at the top)
  and `llms-full.txt` (full text) up to date, both reachable at the site
  root, `text/plain` or `text/markdown`, no redirect.
- One `index.md` per post, declared with `rel="alternate"` in the head.
- **"Key takeaways" box:** 4–5 self-contained factual statements, quotable
  as-is with no pronoun that points back to something else. This is what
  assistants lift.
- **Define each key term once**, in one sentence, near the top ("A pairwise
  comparison is…"). LLMs quote definitions verbatim.
- **Self-contained `h2` sections.** Assistants lift one passage, not a page.
  Restate the subject in the first sentence of each section instead of
  "this method" or "it".
- **Question headings** worded the way people ask (§7).
- **Numbers with a scope and a source**, dated. Engines cite pages that give
  a figure and say where it came from.
- **Full transcripts** in the HTML for every video.
- **Outgoing links** to primary sources. A page that cites is a page that
  gets cited.
- **Entity consistency.** The company description in `llms.txt`, the
  `Organization` JSON-LD, the landing page meta description, and every
  social profile bio say the same thing in substance. Fix drift as soon as
  it appears.

### Crawler policy — allow every retrieval bot, explicitly

Our objective is to be cited, so we **allow** retrieval bots (used to answer
a question), search-index bots, and training bots. Each is listed in
`robots.txt` with an explicit `Allow: /`, never left to the wildcard alone:
an explicit entry is a stronger signal for some engines, and an explicit
list makes an accidental block visible in a diff.

| Engine | User-agents to keep allowed | How it finds us |
|---|---|---|
| ChatGPT search, OpenAI | `OAI-SearchBot` (search index), `ChatGPT-User` (live fetch), `GPTBot` (training) | own index + Bing → IndexNow matters |
| Claude (Anthropic) | `Claude-SearchBot`, `Claude-User`, `ClaudeBot` | Brave index (no push API: clean crawl + sitemap) |
| Perplexity | `PerplexityBot`, `Perplexity-User` | own index + live fetch, favors fresh, dated pages |
| Google AI Overviews / AI Mode, Gemini | `Googlebot`, `Google-Extended` | Google index; `max-snippet:-1` required |
| Microsoft Copilot, Bing | `Bingbot` | Bing index → IndexNow |
| Apple Intelligence / Siri | `Applebot`, `Applebot-Extended` | Apple index |
| Meta AI | `Meta-ExternalAgent`, `Meta-ExternalFetcher` | own crawl + live fetch |
| DuckDuckGo AI, Amazon, Common Crawl, Mistral | `DuckAssistBot`, `Amazonbot`, `CCBot`, `MistralAI-User` | various; CCBot feeds many open models |

Rules:

- `robots.txt` lists each of these user-agents with `Allow: /`, keeps the
  sitemap line, and gains an `llms.txt` comment pointing to
  `https://choiceboard.io/llms.txt`.
- Never add a `Disallow` for one of them without the author's explicit
  decision, recorded in a commit message.
- Never block by user-agent at the hosting or CDN level either. Re-check
  after any hosting change (GitHub Pages today).
- `noindex` pages stay `noindex` for everyone; the crawler policy does not
  override the go-live gate.

### What each engine weighs (write for all of them at once)

- **Freshness and dates.** Perplexity and ChatGPT search prefer pages with
  a visible, recent date. Keep `dateModified` honest and update it on every
  substantive edit.
- **Passage-level answers.** AI Overviews, Perplexity, and Claude quote a
  paragraph. Write every `h2` section so that its first two sentences answer
  the heading's question.
- **Structured comparisons.** For compare posts, use a real `<table>` with
  a header row and a caption. Assistants extract tables cleanly and
  hallucinate from prose comparisons.
- **Numbered steps.** For guides, use an ordered list whose items begin
  with a verb. This is what "how do I…" answers are built from.
- **Brand queries.** Assistants answer "What is ChoiceBoard?" and "Is
  ChoiceBoard free?" from our site and from third parties. The FAQ on the
  landing page, `llms.txt`, and the Company series must agree.
- **Bing Webmaster Tools and Google Search Console.** Both must be verified
  with the sitemap submitted. Bing feeds ChatGPT search and Copilot. Record
  the verification method here once done.

### Citation check (after publication)

Search Console is the only engine that reports on us. For the others, test
by hand. One week after go-live, and again one month later, ask each
assistant the post's target query (or, for `query: none`, the first FAQ
question), with web search enabled where it is an option:

1. ChatGPT (search on), 2. Perplexity, 3. Claude (web search on),
4. Google AI Overviews / AI Mode, 5. Gemini, 6. Bing Copilot, 7. Grok.

Record the result in `seo/citation-log.md` (one line per engine and date:
cited / not cited, which page was cited, which competitor was cited
instead). When an engine cites a competitor or an older post of ours, fix
the post before anything else: sharpen the "Key takeaways" bullets, add the
missing figure, tighten the `h2` question, add the table. Then update
`dateModified`, regenerate the AI-search layer, and re-check.

## 19. Going live

Only after the author answered yes to "Ready to publish?":

1. Set `robots` to `index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1`.
2. Add the URL to `sitemap.xml` with `lastmod` = `dateModified`, an `<item>`
   to `blog/feed.xml`, and the post to `llms.txt`.
3. Run `python3 tools/build-llms.py` then `python3 tools/check-seo.py`
   (0 errors, now as an indexed page).
4. Commit with a short, plain message matching the repo's history
   (`add post: group decision-making process`). Push only if asked.
5. Once deployed, submit the URL to Bing / IndexNow:

   ```bash
   tools/indexnow.sh https://choiceboard.io/blog/<series>/<slug>/
   ```

   `HTTP 200` or `202` means accepted. The key file `<key>.txt` at the
   site root must stay deployed.
6. Google has no push API for posts: request indexing in Search Console
   (URL inspection → Request indexing).
7. Verify: Rich Results Test, LinkedIn Post Inspector for the OG preview,
   X card validator, and click every internal link on the live page.
8. One week later: run the citation check (§18) and log the result.

## 20. Template rules (do not break)

- A single `<h1>` per page; `h2`/`h3` hierarchy without skipping levels.
- "Key takeaways" (`.takeaways`) stays at the top of the article, before
  the first `h2`.
- Visible FAQ and JSON-LD `FAQPage` identical word for word, 3–6 questions.
- Transcript always in the HTML for video and story posts.
- ISO 8601 dates in `datetime`, OG, and JSON-LD.
- Canonical URLs with trailing slash, `https://choiceboard.io/…`.
- Every template includes the Google Analytics snippet from §12 exactly once.
- No external JavaScript beyond the video facade and the approved Google
  Analytics tag in §12. No third-party embeds
  that set cookies before consent.
- Every page keeps the site's progressive-enhancement rule: nothing is
  hidden without JS.

## 21. Maintenance

- On every page creation or edit, verify that the §12 Google Analytics
  snippet is present exactly once in `<head>`. When the measurement ID
  changes, update all HTML pages, templates, generators, and guidance together.

- Update `lastmod` (sitemap), `dateModified`, and the `modified:` line in
  the meta block at every substantive edit. Google and LLMs favor
  maintained content; stale dates cost citations.
- Quarterly: re-run the citation check on the ten highest-traffic posts and
  refresh any figure older than 18 months.
- When pricing, the CTA URL, or the positioning sentence changes, grep every
  post and `llms.txt` the same day.
- When a post is unpublished: `noindex`, remove from hub, series page,
  `ItemList`, sitemap, feed, `llms.txt`, and regenerate `llms-full.txt`.

## 22. Definition of done (one post)

- [ ] Intake answered; meta block complete; `og-image: dedicated`
- [ ] Voice matches the live corpus; refrain present; no banned vocabulary
- [ ] Main query in title, h1, description, first paragraph (or `query: none`)
- [ ] "Key takeaways", question-form `h2`s, FAQ, one CTA, one signed blockquote
- [ ] Every figure has a scope and a source; nothing invented
- [ ] `<head>` and JSON-LD checklists pass; Rich Results Test clean
- [ ] Google Analytics `G-ZLZMXRHMBS` loads and is configured exactly once
      in `<head>`; any new templates or generators include the same snippet
- [ ] Social image set produced; every `<img>` has descriptive alt text
- [ ] ≥ 2 incoming internal links, 1–2 outgoing post links, 1 landing-page link
- [ ] `index.md`, `llms.txt`, `llms-full.txt`, `feed.xml`, `sitemap.xml` updated
- [ ] `social.md` written
- [ ] Checker: 0 errors
- [ ] Author said "yes" to "Ready to publish?"
- [ ] IndexNow submitted; Search Console indexing requested
- [ ] Citation check scheduled (+1 week, +1 month) in `seo/citation-log.md`
