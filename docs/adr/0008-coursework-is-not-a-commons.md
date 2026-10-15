# ADR-0008: Coursework is not a commons

- Status: Accepted · 2026-10-15 · Felisa Wiley

**Context**: [your-protected-notes](https://github.com/jlumbroso/your-protected-notes)
is level 3 of the instrument series. The move is one idea: the server
learns who is asking. The notes prototype stores rows, so ownership is a
`user_id` column and guests keep a shared commons. This server stores
nothing. It reads one person's Canvas with `CANVAS_API_TOKEN`.

**Decision**: same three modes, different gate.

- No `Authorization` header, or the declared guest credential → guest.
- A valid Neon Auth JWT → user, keyed on `sub`, never on email as the identity.
- An invalid or expired token raises. It is never treated as a guest.

Guests do not see courses or assignments. There is no shared shelf to
preserve: this server never had public rows. A signed-in caller sees the
Canvas only when `OWNER_EMAIL` is unset, or when their email matches it.
Someone else who signs in gets a refusal that names both emails. That
refusal is not guest mode — calling them a guest would hide a real login
as anonymity.

**Roads not taken**: (A) show Canvas to every guest, the way notes show
the commons. Rejected: a Canvas token was never public. (B) one Neon row
per assignment, with `user_id`. Rejected: the coursework already lives in
Canvas; copying it into Postgres would make a second, stale list.
(C) a Canvas token per signed-in user. Not available. This deployment
holds one token.

**If wrong**: a course staff server with many viewers wants a list of
emails, not one `OWNER_EMAIL`. The gate is that one comparison.
