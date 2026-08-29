# Factors Page in Settings

## Short Description
### user
We are exposing to two comparison prompts on the options page. One is ostensibly user entered, the other agent generated. Both allow direct edits.

This was likely a poor statement in an earlier request, as only one was intended. 

Let's deprecate the first field, with the statement below, 'Optional legacy question. Used only if concise prompt blank.'

If the user wants to enter text manually, the can.

For the remaining field, change the initial grey placeholder text to say, 'Enter a clear single question, like, "Which requires less engineering resources"'

The previous field should be removed from the page and all logic for editing and use in the prompt streams. Legacy values can be left in the data store, but would be ignored.
[comment: created 2026-08-23T20:28:45.964Z | id factors-page-in-settings-34pzhx]

## Expanded Description
### agent
Consolidate the Factors/Settings options page from two editable comparison prompts (user-entered vs. agent-generated) to a single canonical prompt to fix an earlier over-exposure. Update the remaining field's empty-state placeholder to `Enter a clear single question, like, "Which requires less engineering resources"` and fully remove the legacy field from UI and prompt-stream logic; stored legacy values remain in the data store but are ignored.

*   **Scope - UI:** Remove/deprecate first/legacy prompt field from Factors/Settings page; retain single editable field with new grey placeholder text; if transitional deprecation kept, label it `Optional legacy question. Used only if concise prompt blank.`
*   **Scope - Logic:** Strip legacy field from editing handlers, validation, and all prompt assembly/stream injection; concise prompt becomes sole source for comparison question.
*   **Data compatibility:** No migration/deletion of legacy datastore values; reads ignored, writes disabled; ensure blank concise prompt does not silently fall back in final state.
*   **Key consideration:** Resolve contradictory brief (deprecate with fallback label vs. fully remove and ignore) and identify canonical field ID to keep.
*   **Open question:** Confirm placeholder exact casing/quotes and whether to keep legacy fallback temporarily for backward compatibility.

## Plan

## Build Summary

## Code Review Guide

## UI Review Guide

## History
- 2026-08-23T20:28:45.964Z created (source: user)
