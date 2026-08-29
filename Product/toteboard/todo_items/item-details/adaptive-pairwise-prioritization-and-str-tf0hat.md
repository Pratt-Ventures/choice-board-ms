# Adaptive Pairwise Prioritization and Strengthened Analytics

## Short Description
### user
This is being done in one or more prompts with Grok 4.6 in the console to avoid time limits and answer questions.

In user use, we find the sort algorithm is too fragile. A single incorrect response has an outsized influence on the resultant order.
We do like the current grouping of questions into a block of questions with a single factor, or all factors only. In single factor mode, there is just groups of options in a general comparison. We also need a functioning 'undo' button as it is a common user expectation.

We are deprecating the sort-based processing, but will use the Ford-Jackson comparison step estimate, at the server, to set each group's size based on that maximum. Similar to the current implementation, we will send the list of items to compare, active factor if any, along with prior pair responses from the current participant. The question set will now always be exactly the predicted size.


In the group results table, projectvotegroupresult, the pairings include fields 'choice' and 'response' that appear to always be the same. If these serve no purpose, they can be removed. The table should also add columns for the requested number of pairings, number of pairings received in the group, and the total number of historical pairings provided for selection statistics with the group request. Some of these are for forensic convenience, rather than internal needs, though others may be used as described below.

It appears the group ids are presently written only when a group is completed. The new logic will require a group to be written when the package is prepared for the client. Include a new key field, a unique group token (e.g., secure, safe 10 url chars). This should be sent to the client and echoed back with the group's results and will help in the localstorage recovery below. We don't want to use the database id for this purpose, as its values are predictable.

We will also submit incomplete packages to the server to limit data loss if the user quits the session prematurely. The partial server update should occur after 5 entries or 90 seconds of idle time, whichever comes first, provided one or more answers have been captured. These time and count thresholds must be adjustable in new application settings in config/config_settings.py. Each partial update is cumulative from the client, so it updates the partial pairings list and receive count at the server. The client should also maintain the state of responses for the current group in local storage with the group ID tag mentioned above and sent along with the request and all responses. The client will restart partial groups with the longer of the response history from the browser or provided by the server. Generally, recovering on the same browser will be best; switching browsers will involve a partial rollback of the current group. 

We want to change from Select First vs Rank mode to Find Best, Find Top 3, Find Top Half, Rank All; Internally, it should be implemented as rank-all, or rank top-n, where n can be 1 to one half the number of options. Allowing a top-list favored goal, not just top-entry, will provide more use cases. This will affect question order based on the statistics and confidence calculations.

Pairs presented within a group are never repeated (in the group) as a pair; individual options (or factors in factor groups), are never repeated in successive pairs. Every alternative must appear at least once in the first group; later groups do not have this restriction. The valid alternatives are prioritized in order of increasing confidence of the top N, pulling away from the pack, or getting the best overall ranking from top-to-bottom in that mode.

A paper on the math and approach we would like to use, with illustrative math, is attached.  First, change the group logic to accommodate the new voting order and intermediate checkpoints. We will then update all statistics and related metrics. For backward compatibility, a ranked list of each group is still returned, along with the pairings, although the aggregate order in the reporting will be based on the complete set of pairings, not the estimated ranks in any of the groups.

Use the file in "docs_examples/Implementation Specification for Paired Adaptive question process.md" as the definitive math for reporting purposes, generated on the server and communicated via revised APIs for updated reporting. Use the pair prioritization proposal in the client to prioritize pair presentation within a group based on prior group and in-group pair presentation. Specific data structures or message types in that document are illustrative, a combination of adapting existing flows and structures for equivalent outcome with modifications to provide full capability is needed.

Plan for the UI pairwise selection, then the server statistics generation updates, then the visualization updates in the client in several phases. Add features and options in the visualation reports and dashboard to add value with enriched statistics. 

Ask any clarification questions and recognize this is just above draft form and should be enhanced in execution to make the best decision-support product.
[comment: updated 2026-08-19T11:09:28.747Z | id adaptive-pairwise-prioritization-and-str-tf0hat]

## Expanded Description

## Plan

## Build Summary

## Code Review Guide

## UI Review Guide

## History
- 2026-08-19T04:18:18.377Z created (source: user)
