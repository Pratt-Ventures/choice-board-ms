PowerChoice Notes:
- Document scripts and processes
 cd client && npm run dev -- starts the nuxt active @ 3000
 scripts/nuxt/update_static_client.sh updates the static_client area

QUESTIONS FOR PowerChoice:
 
 
TODO LIST FOR Power Choice:
- need table for alternative choices (id, customer id, customer project id, choice title, choice description, added_by_user_id, create/modify/soft delete date) (need review)

- Need tables for sharing and share tracking and related services

- local email sender

- implement robust sharing capability, varying security verification, varying action and view potential


- private projects within the customer (visible to self and read-only to admins)

- projects can be locked, preventing further votes, views remain open.

- need table for alternative factors (id, customer id, customer project id, factor title, factor description, factor improvement direction, added_by_user_id, create/modify/soft delete date)

- build an admin interface for service operations into the client, exposed only if admin and also secured by appropriate endpoints

- change log to use postgres native json fields
- ensure idempotencies of reported votes

- customer registration request with env configured trial code (not stripe initiated) should be incorporated into expiration tests during login (done plus configured grace period days)

- ensure primary login is tested against primary trial expiration date and account expiration date properly (these are implemented with respective grace period days)

- what does an expired user do if they can't login?  may need to catch specific failure modes
  (user/pw were validated, so we provide specific string for cause)

- api key - keep, but not needed for now

- always allow primary account login, return primary subscription expired indication on the dashboard and disable further actions. Existing data remains visible


- need jwt proper expiration

- make sure live mode is set / tested properly throughout and highlight issues on dashboard

- ensure that activated customers with no transaction history are highlighted in dashboard somewhere

