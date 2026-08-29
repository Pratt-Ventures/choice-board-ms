# UI Reference Guide — how to talk about the PowerChoice Pro interface

Companion to [`terminology_dictionary.md`](./terminology_dictionary.md) (which defines **product nouns** — Project, Option, Factor, Compare…).
This guide defines the **interface vocabulary**: what to call each area and element when writing prompts, tickets, PRs, or reviews.
Interactive version with visuals: **[`ui_reference_annotated.html`](./ui_reference_annotated.html)** — hover any numbered zone.

---

## 1. How to reference anything

Use a location path from largest to smallest, then quote visible label text:

```
<Screen> › <Region> › <Element> "visible label"
```

Examples:

- `Projects screen › Toolbar › Search field`
- `Project Overview › Page header › Action row › "Start comparing" button`
- `Sharing screen › Share card › Overflow menu › Delete`
- `Edit Project › Tabs › Options tab`

Rules:

1. **Quote exact visible text** for anything with a label — it is unambiguous across translations and redesigns.
2. Name the **element type** (button, chip, field…), not its look ("the blue thing").
3. One **primary action** per view (filled button); everything else is secondary. Refer to them as *primary / secondary / tertiary* actions.
4. If you can't name an element, give **region + nearest labeled neighbor + quoted text**: *"top-right of the toolbar, next to Refresh"*.

## 2. Page frame (present on every signed-in screen)

| Term | What it is |
|---|---|
| **Side navigation** (nav drawer) | Left rail: brand block on top, grouped nav lists (**nav section labels**: Workspace, Account, System Admin), workspace card pinned at bottom |
| **Nav item / active nav item** | One entry in side navigation; *active* = current screen |
| **Top bar** | Horizontal bar above content: contextual page title + subtitle (left); theme toggle icon button and **user menu** avatar button (right) |
| **User menu** | Dropdown opened from the top-bar avatar (Profile, Settings, Sign out…) |
| **Content area** | Everything below the top bar; pages render here inside a max-width page container |
| **System banner** | Full-width notice at the very top of the content area (e.g., new app-version prompt) |

## 3. On-page elements (in typical top-to-bottom order)

| Term | What it is | Say it like |
|---|---|---|
| **Back link** | Text link returning up one level ("← Projects"), above the title |
| **Page header** | Block with **eyebrow** (small caps kicker), **title**, **subtitle**; optional **action row** of buttons aligned right |
| **Callout banner** | Large highlighted strip with headline, blurb, and CTA(s) (e.g., spotlight project on Projects screen) |
| **Inline alert** | Compact tinted message inside the flow (info/warning/error); persistent until context changes |
| **Stat card** (KPI tile) | Small card: label, big value, caption detail; usually a row of 3–4 |
| **Toolbar** (list controls) | Row directly above a list: section heading, **search field**, filters, **view toggle**, refresh |
| **View toggle** | Segmented control switching list presentation (cards ⇄ table) |
| **Card grid** | Responsive tiles; each **card** may hold chips, meta rows, progress, actions |
| **Data table** | Dense tabular alternative view of the same records |
| **Status chip** | Small colored pill conveying state (*Ready*, *Collecting input*, *Input closed*) or category (*Pick one*, share type). Not clickable, not a button |
| **Meta row** | Line of small icon+text facts inside a card (options · factors · participants · comparisons) |
| **Progress bar** | Thin horizontal fill showing completion; often paired with a % caption |
| **Overflow menu** ("kebab") | ⋯ icon button revealing an action menu on cards/rows |
| **Row actions** | Buttons at the end of a table row (often just the overflow menu) |
| **Empty state** | Icon + headline + helper sentence + CTA shown when a list has nothing to show |
| **Ranking list** | Results rows: rank number, option title, score bar, range indicator |
| **Range bar** | Slim uncertainty band visual under results (rank/importance ranges) |

## 4. Forms

| Term | What it is |
|---|---|
| **Text field / Text area** | Single-line input / multi-line input, both with floating label |
| **Select** (dropdown) | Pick-one field opening a menu |
| **Segmented control** (button group) | Exclusive choice rendered as joined buttons (e.g., Decision mode) |
| **Switch** | On/off toggle for a setting (e.g., "Close input") |
| **Date picker** | Calendar popover launched from a date field/menu |
| **Helper text** | Caption below a field explaining it |
| **Validation error** | Red message replacing helper text when input fails |
| **Tabs** | Switch between panels in place without navigation (Edit Project: Project / Options / Factors / Review) |
| **Accordion** (collapsible panel) | Header that expands/collapses detail in place (e.g., Access log on share cards) |
| **Stepper** | Sequential wizard steps — **we don't use these**; multi-step setup is done with Tabs |

## 5. Overlays & feedback (don't mix these up)

| Term | Behavior | Use for |
|---|---|---|
| **Dialog** (modal) | Centered overlay with title, body, action row; blocks until closed; has ✕ close icon button | Confirmations, create/edit forms |
| **Snackbar** (toast) | Transient message, bottom-right, auto-dismisses (~4 s), Close action | Success/error feedback after actions |
| **Inline alert** | Stays in the flow where it is relevant | Contextual warnings/info while browsing |
| **System banner** | Top-of-page, app-wide condition | Version mismatch prompts |
| **Loading bar** | Indeterminate linear bar at top of content while fetching; buttons show inline spinners | Async operations |
| **Tooltip** | Small hover hint attached to an element (rare; mostly `title` attributes) | Extra clarification |

## 6. Quick disambiguation

- **Chip ≠ button.** Chips display state; buttons act. Never say "Delete chip".
- **Menu ≠ dialog.** Menus list quick actions; dialogs collect input or confirmation.
- **Banner ≠ snackbar.** Banners persist in place; snackbars vanish.
- **Icon button** = button containing only an icon (theme toggle, ✕, ⋯). Name the icon if unlabeled ("✕ close button", "kebab menu button").
- **Tabs switch views; links navigate.**
- **Switch = immediate setting; checkbox = selection.**

## 7. Button hierarchy

| Variant | Look | Meaning |
|---|---|---|
| Primary | Filled brand color | The one main action of the view ("Create Project") |
| Secondary | Tinted/tonal or outlined | Supporting actions ("Invite people", "Make a copy") |
| Tertiary | Text-only / icon | Low-emphasis actions ("Refresh", "Cancel") |
| Destructive | Error-red filled or red text item in a menu | Deletes/closes; confirm via dialog |

---

*When this guide and a screenshot disagree, quote the visible label and note the screen — wording wins over styling.*
