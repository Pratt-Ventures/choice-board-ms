# Complete Enable_user_communication

## Short Description
### user
The original request appears partial. Wiring of optional feature has been completed, at least to point of binding databases and providing basic endpoints.

The following prompt, externally submitted, requests follow-up and finalization:

We started this user commuication feature some time ago, with the prompt and information here:
We are adding dialogs to submit a suggestion and report a bug. This will only be available for logged in users.  These options will be added the current session pulldown in the upper right area. Another option is 'Check Submission Status' - These should be immediatly above the About entry.

These will each submit to a new endpoint we will create in this request. The dialog will ask for a title/summary and a brief description.  

Ensure the client settings indicate if this feature is enabled and available on the server. If not, the option on the user session menu will not be presented.

For bug reports, these are the recommend fields, including an option to paste or upload a screen shot.
Summary *
What happened? *
What did you expect to happen?
Steps to reproduce
Impact: Minor / Moderate / Blocking
Optionally Attach screenshot or file

For suggestions, 
Suggestion *
What would this help you accomplish?
Area of the product
Importance: Nice to have / Important / Very important
Optional Attachment

We will create two new databases that captures user submissions. 

These will follow the patterns used by other sqlmodel tables defined in the application. In addition to reasonable named fields from the above, they will each have an integer id, a customer_id, a user_id, acknowledge receipt date, acknowledge receipt user, acknowledge note text, response date, response user, response note text, resolution date, resolution user, resolution note text, creation date (use standard naming from code), modify date, soft deletion date.

A session services group for 'User Communication' will be added. This group will have submit requests for each these, bug reports and suggestions, for any user. Users will be limited to a configured, MAX_REPORTS_PER_DAY, defaulting to 10, in a rolling 24 hour period. If they exceed that, the new submission will be stored, and a warning returned that they've reached the daily submission limit for that type. If they exceed the configured limit by 1, the added submission is captured in the variable area of a log_entry and the user is given an error response, stating the request was discarded due to daily submission limits. In each response, also include the number of rows of the type in the trailing 24 hours and the maximum allowed (not including the buffer). This should be shown to the user that submission n of x (per day) has been submitted.

All of the related requests will be mirrored for each type. These include retrieve submissions request will retrieve all submissions of the type, bug or suggestion, for a customer if customer admin, or specific user otherwise.  

An administrative retrieve all submissions for system admins, for each type, with offset and limit fields, will be used to provide a paginated view for admins in most recent first order. 

Each type will also have a modify service, available only to system admins, that allows setting the relevant dates to current time for each of the actions (acknowledge, response, resolution) and notes for each. Notes can be entered independent of setting the date.

Each type will have a soft-delete service, that sets the deletion date, and is available to any user to soft-delete their own submissions prior to any of the relavent actions or updates from an admin. The system admin can soft delete any item.

The retrieve my submissions requests are used to provide a table view, scrollable if needed, for end users, that list recent submissions by date, clipped initial words from summary or suggestion, and dates for acknowledge, response, and resolution, when available. If notes are available for acknowledge, response or resolution, they are shown near the respective dates with circled i that will provide a stable hover over with the appropriate note text. The single page in the user interface shows suggestions first, if any, and the the bug report listing below. If either is not found, it states 'No active suggestions found' or 'No active bug reports found'

For system admins only, add a left menu area entry for 'System Admin' This leads to a page, that will have two links initially. One for the suggestion box, one for bug reports. These will provide paginated lists, most recent first, by submission date, linked customer name, linked user name, front part of summary or suggestion, and the dates for each action (or NA if none). A rightmost column shows Edit/Delete and if clicked will show a box overlayed with full details vertically and options to set or clear the three dates and edit the three text response fields. The bottom of the dialog has the option to cancel, delete, or save. Delete should ask are you sure.

This lays out the basic behavior, the rest services that will be needed, and user interface instructions. Fill in necessary or clearly beneficial extensions, arrange aesthetically strong pages, consistent with the style guide and other pages, add be sure to add appropriate tests of functionality and security.

If common code can be used to create the baseline, for any database table, service, or user interface elements, that is preferred.
Expanded by agent with: 
Logged-in users get session-menu items immediately above About for Report Bug, Submit Suggestion, and Check Submission Status, shown only when client settings say the server feature is enabled. Two SQLModel tables persist submissions (form fields plus customer/user ids, ack/response/resolution dates-users-notes, created/modified, soft-delete). A User Communication service group mirrors submit, retrieve (own or customer-admin), admin paginated retrieve, admin modify, and owner/admin soft-delete for both types, with a rolling 24h MAX_REPORTS_PER_DAY (default 10): store+warn at the limit, discard+log_entry at limit+1, and every response includes n of x for the UI.

- Scope: feature flag, session menu, submit dialogs (bug: summary*, what happened*, expected, steps, impact, attachment; suggestion: suggestion*, goal, area, importance, attachment), status page (suggestions then bugs, clipped text, dates, circled-i note hovers, empty states), System Admin nav + paginated lists + edit/delete overlay, tests for function and authz.
- Prefer shared table/service/UI baselines over duplicated type-specific code.
- Rate-limit buffer is one extra stored row; the next attempt is discarded and logged; counts exclude the buffer from the published max.
- Users may soft-delete only their own items before any admin action; system admins can delete any; notes can change without setting dates.
- Open: attachment storage (inline vs file service), exact client-settings key, whether customer admins see all customer submissions on the status page, and confirm/clear semantics for admin date fields. 
The above was mostly completed subsequently refined. It is activated by ACTIVATE_CUSTOMER_COMMUNICATION and is on in this project.

The UI experience suggested, which appears to not be implemented, should be changed to add a 'System Admin' label at the bottom of the left menu and then add items for Review Bug Reports and Review Suggestions.
The user should have a Submit Bug/Suggestion on their session menu. This leads to a page where they choose the type of report. Also, the user should have a 'my reports' option below the Submit requests which is one page showing the status of bugs in most recent first order, then a section for suggestions, in most recent first order.
If either section is empty, it reports, 'No reports on file' appropriate to the type. A link to Create a Bug Report and Create a Suggestion should also be placed on that page in the appropriate section.

Examine existing code for its present state. Utilize what is helpful, remove what is partially complete or not useful in this feature space. Server changes can only be made in the framework, under /src/pvf. This is isolated from the broader application. Client changes are made in the nuxt client in the cleanest way available.
[comment: created 2026-08-19T12:11:45.350Z | id complete-enable-user-communication-mffi5x]

## Expanded Description

## Plan

## Build Summary

## Code Review Guide

## UI Review Guide

## History
- 2026-08-19T12:11:45.350Z created (source: user)
