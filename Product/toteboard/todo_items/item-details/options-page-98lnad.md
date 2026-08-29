# Options Page

## Short Description
### user
The options page should add a 'Generate Missing Compare Prompts (n)' - similar to the same feature on the Factors page.  The behavior would be about the same. The (n) is the number of empty ~"Compare Prompt 2-5 words" present. Place after the 'import from template' and 'save as template' options in the same visual row.
[comment: created 2026-08-23T20:32:15.598Z | id options-page-98lnad]

## Expanded Description
### agent
Add a `Generate Missing Compare Prompts (n)` button to the Options page mirroring the existing Factors page feature, where `n` is the live count of empty Compare Prompt fields (expected 2-5 words each). Place it in the same visual row immediately after the `Import from Template` and `Save as Template` controls with consistent styling, disabling/hiding when `n=0`. Clicking triggers generation for only the empty prompts, reusing the Factors-page prompt/LLM flow and updating the fields in place.

*   **Scope:** Add button to Options page action row after import/save template; compute `n` as count of empty/whitespace-only Compare Prompt inputs; wire to existing generate-missing-prompts handler/service used by Factors page.
*   **Behavior parity:** Generate only for empty prompts, preserve non-empty values, validate generated output is 2-5 words, show loading/disabled state during generation and handle partial failures per-field.
*   **UI/UX:** Label dynamically as `Generate Missing Compare Prompts (n)`; disabled (or hidden) when `n=0`; match button variant/size/spacing of adjacent template buttons; responsive wrapping for narrow widths.
*   **Key consideration:** Reuse shared generation logic to avoid duplication — confirm prompt template, model params, and error handling are identical to Factors page; ensure no toteboard/board storage schema change.
*   **Open question:** Should generation run sequentially vs. parallel and how to surface per-prompt errors/toast vs. inline validation?

## Plan

## Build Summary

## Code Review Guide

## UI Review Guide

## History
- 2026-08-23T20:32:15.598Z created (source: user)
