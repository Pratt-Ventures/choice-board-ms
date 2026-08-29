# Explicit Questions Tracking

## Short Description
### user
In the Expand and Build process, we'd like to separate the responses into primary response, as today, and a separate area, tracked, displayed, and edited distinctly, of "QUESTIONS."

The proposed solution is to adjust the prompts with something like, 'Response with the overall and summary information first and any questions subsequently. If questions or clarifications are needed to refine scope or choose an approach, list the questions, with recommend answers, at the end of the response, after a fixed marker '----- QUESTIONS AND RECOMMENDATIONS -----'  

This will be done for expand and plan only. The prompts will be adjusted to request this in a clear and precise manner. The responses will be parsed and the qeustion portion, when present will be placed in a new node field for expand questions and plan questions, respectively. These will be editable fields on the primary node, showing beneath the plan response. The prior questions sections, when present, will be appended in the prompt chains for subsequent requests.

In the legend above the expand and plan questions text boxes, add an indication if the values have been edited by the user (show edited by user {} at this time). Take the user name and user id from the user configuration settings.

Review and ensure all prompts are adjusted and refined to accomodate this. However, the question areas are optional responses and should not make subsequent prompts larger when they are unused.
[comment: created 2026-08-21T13:21:35.809Z | id explicit-questions-tracking-3r6n5j]

## Expanded Description

## Plan

## Build Summary

## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T13:21:35.809Z created (source: user)
