# Node editor update

## Short Description
### user
Where 'View Plan' is shown add a 'Review/Edit Plan' between the prompt and response indicators. Make it a three column presentation. The other types (build, code review, ui review) will have the middle column empty, as their output is not used in subesquent steps.
[comment: updated 2026-08-21T01:29:16.753Z | id node-editor-update-335l22]

## Expanded Description
### agent
Add a Review/Edit Plan control in the node editor wherever View Plan appears, placed between the prompt and response indicators in a three-column layout. Plan-type nodes use the middle column for Review/Edit Plan; build, code review, and UI review keep that column empty because their output is not consumed by later steps. Preserve existing View Plan behavior and keep empty middle columns aligned so the prompt and response indicators stay consistent across node types.

- Scope: three-column chrome around prompt / Review/Edit Plan / response; only plan nodes populate the middle column.
- Match existing View Plan styling, placement, and interaction patterns.
- Empty middle column for non-plan types should still reserve space so columns line up.
- Confirm Review/Edit Plan opens the same plan surface as View Plan vs a distinct edit mode.
- Open: whether the middle column is hidden vs empty-but-spaced on non-plan nodes.
[comment: expanded description edited 2026-08-21T01:29:16.753Z]


## Plan

## Build Summary

## Code Review Guide

## UI Review Guide

## History
- 2026-08-20T20:11:37.163Z expand completed (e-20260820-0001)
- 2026-08-20T20:11:01.318Z created (source: user)
