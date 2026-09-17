# ADR-0001: Canvas's course REST API, not the Planner API; week = Mon–Sun

- Status: Accepted · 2026-09-17 · Felisa Wiley

**Options considered for `assignments`/`due_this_week`**: (A) per-course
`/courses/:id/assignments` · (B) the cross-course `/planner/items` endpoint.

**Decision: A.** Rationale: Planner items are stubs (title, date, a link) —
fine for a to-do list, but `canvas()` and `assignments()` want the real
assignment object (points, description, submission type) so the model can
reason about the work, not just its existence. The cost is one HTTP call per
active course instead of one call total; acceptable at the class-sized
number of courses a student carries. If wrong: course count grows past a
handful → switch the aggregation in `_all_assignments` to `/planner/items`
and re-fetch full assignment objects only for what's actually due soon.

**Decision: an academic week is Monday 00:00 to Sunday 24:00**, in the
server process's local timezone — not Canvas's, not UTC. Rationale: matches
how a student actually plans ("this week" starts Monday); the alternative
(Sunday-start) is a US calendar convention but not an academic one. If this
server runs somewhere with a different timezone than the student, due times
will be off by that offset — acceptable for now; fixed by pinning the
process's `TZ` env var if it ever matters.

**Auth**: `CANVAS_API_TOKEN` is a personal access token, read from the
environment only — never written to code or committed. This token grants
read access to a real account, so it's treated as a hard boundary: no
logging it, no baking it into a URL, no default value.
