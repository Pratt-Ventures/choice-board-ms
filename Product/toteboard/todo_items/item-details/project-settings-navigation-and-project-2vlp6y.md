# Project settings navigation and project overview

## Short Description
### user
When on the Edit Project Settings page, there is no clear way to get back to the particular project. 

On project overview - change the page title at the top from 'Project' to 'Project - Overview'
Change the action bar list, containing 'start comparing', and so on to the following order:
'Project Settings', 'Make a Copy'; 'Invite People'; 'Start Comparing' and 'View Results'.

These buttons each have their current function.

On the Edit settings page,
Change the page title from 'Project' to 'Project - Edit Settings'

In the tab navigation, add an item at the left that shows a left arrow next to 'Overview' and provide a back to project overview function.

Change the oder of actions on the project summ
[comment: created 2026-08-19T16:48:05.424Z | id project-settings-navigation-and-project-2vlp6y]

## Expanded Description
### agent
Improve project overview and Edit Project Settings navigation so users can always return to the specific project and find actions in a consistent order. On overview, retitle the page “Project - Overview” and reorder the action bar to Project Settings, Make a Copy, Invite People, Start Comparing, and View Results without changing each button’s current behavior. On Edit Settings, retitle the page “Project - Edit Settings” and add a left-most tab with a left arrow plus “Overview” that navigates back to that project’s overview; apply the same action-order change on the project summary where it still differs.

- Scope: overview title, overview action-bar order, edit-settings title, new Overview back tab, matching summary action order.
- Keep existing handlers, permissions, and destinations for all current buttons.
- Overview back link must target the same project, not a generic projects list.
- Match existing tab/action-bar patterns (arrow, labels, responsive wrap).
- Confirm whether “project summ” is the same action bar or a second control set.
- Confirm tab insert is left of existing settings tabs and does not replace Save/Cancel.
[comment: expand completed 2026-08-19T17:00:46.330Z | via executor-opencode | entryId e-20260819-0004 | artifacts: ./project-settings-navigation-and-project-2vlp6y/2026-08-19T16-59-57-001Z-expand-udo3f1.request.md, ./project-settings-navigation-and-project-2vlp6y/2026-08-19T16-59-57-001Z-expand-udo3f1.response.md, ./project-settings-navigation-and-project-2vlp6y/2026-08-19T16-59-57-001Z-expand-udo3f1.trace.log, ./project-settings-navigation-and-project-2vlp6y/2026-08-19T16-59-57-001Z-expand-udo3f1.result.json]


## Plan

## Build Summary
### agent
I'll locate the project overview and edit-settings pages, then apply the title, action-bar, and Overview-back-tab changes.I'll read the layout, overview, and edit pages to apply titles, action order, and the Overview back tab.I'll update titles, reorder the overview actions, and add the Overview back tab. Checking git status and commit style first.Simplifying the Overview tab to a real route link so it doesn't fight the wizard `v-model`.Rebuilding the published UI next so FastAPI serves these navigation changes.**Build summary**

Overview and Edit Settings now have distinct top-bar titles, a same-project Overview back tab on settings, and a consistent action order. Project summary is a metrics card only — the list overflow menu already matched. Version `0.7.54`. Static client rebuilt. No CHANGELOG.md.

**Touch points**
- `client/layouts/default.vue:208-213` — titles `Project - Overview` / `Project - Edit Settings`
- `client/pages/projects/[id]/index.vue:27-47` — action order: Settings, Copy, Invite, Compare, Results
- `client/pages/projects/[id]/edit.vue:17-28` — left Overview tab (`/projects/:id`)
- `client/pages/projects/[id]/edit.vue:633-637`, `867-870` — back-tab guard + navigate
- `src/config/config_settings.py:17` — `0.7.54`

**Commit** `ce4fa1aa6a079c0b2b0e39e8c42e766a761fec21`  
Clarify project overview and settings navigation
[comment: build completed 2026-08-19T17:26:27.626Z | via executor-opencode | entryId e-20260819-0007 | artifacts: ./project-settings-navigation-and-project-2vlp6y/2026-08-19T17-18-01-065Z-build-c47sda.request.md, ./project-settings-navigation-and-project-2vlp6y/2026-08-19T17-18-01-065Z-build-c47sda.response.md, ./project-settings-navigation-and-project-2vlp6y/2026-08-19T17-18-01-065Z-build-c47sda.trace.log, ./project-settings-navigation-and-project-2vlp6y/2026-08-19T17-18-01-065Z-build-c47sda.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-19T17:26:27.626Z build completed (e-20260819-0007)
- 2026-08-19T17:00:46.330Z expand completed (e-20260819-0004)
- 2026-08-19T16:48:05.424Z created (source: user)
