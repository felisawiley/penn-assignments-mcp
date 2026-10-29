# ADR-0011: Ask what is fixed outside class

- Status: Accepted · 2026-10-29 · Felisa Wiley

**Context**: A ranking of assignments can fill every hour and still be a
bad plan. Sleep, a job, people, and an empty evening are not on Canvas.
They are also not all on one calendar. A person may have a school Google
account, a personal Google account, and Outlook, and still want Tuesday
night left blank even though no event says so.

**Decision**: `priorities()` does not become a plan until `outside` is
passed. Empty `outside` tells the model to ask two things: what is already
fixed this week, and which hours should stay empty. The answer is repeated
back and treated as blocked. The server does not read calendars and does
not store calendar tokens next to the Canvas token. A calendar, if one is
connected in the chat, is read by that connection, once per account, then
merged and shown. Only the blocks the person confirms are passed in
`outside`. Anything the calendars do not know still has to be asked.
Schoolwork is not placed on top of a confirmed block, and empty hours stay
empty.

**If wrong**: if confirming a merged week by hand is too much, accept a
busy list from each connected account without a second reading, and still
ask which hours should stay empty. Do not guess those hours from the
course load.
