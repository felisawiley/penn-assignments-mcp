# ADR-0009: Attach the module, and the file beside the assignment

- Status: Accepted · 2026-10-29 · Felisa Wiley

**Context**: `assignments()` could name the work and link the assignment
page, and still leave the model unable to say which module it lives in or
which reading sits next to it. The module list and the file list are
already on Canvas. The week tools stay short on purpose (ADR-0006), and a
week check should not walk every module and every file.

**Decision**: only `assignments()` loads this context, once per course.
A module item of type Assignment (or Quiz, matched on `quiz_id`) places
the assignment. The line then links up to four files, pages, or external
URLs: same-module items with a similar title, then the two materials
placed just above it, then course files with a similar title. Locked or
hidden files are skipped. Nothing is downloaded, and quiz questions are
not requested. A course that hides modules or files still returns its
assignments, without the extra links. `due_this_week()` and
`academic_week()` do not call this path.

**If wrong**: if "the two items above" attaches the wrong reading, drop
that step and keep title matches only. If the extra Canvas calls make
`assignments()` too slow, fetch context for one named course at a time
and leave the all-courses call on the short form.
