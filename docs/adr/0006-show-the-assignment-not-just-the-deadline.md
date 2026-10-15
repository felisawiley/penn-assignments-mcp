# ADR-0006: Show the assignment, not just the deadline

- Status: Accepted · 2026-10-15 · Felisa Wiley

**Context**: ADR-0005 chose `/courses/:id/assignments` over the Planner API
because the assignment object carries points, description, and submission
type. The first server fetched that object and then kept only the name, the
due date, and the points. A week view built from that could say something
was due and still leave the model unable to say what the work was, how to
turn it in, or whether it was already in.

**Decision**: `assignments()` keeps those fields. The description is reduced
to plain text and cut off so one syllabus page cannot fill the context.
The Canvas link is on every line. Submission state (`submitted`, `graded`,
`missing`, `late`, and the rest Canvas returns) is printed when it changes
what you'd do next; a plain unsubmitted assignment stays unmarked. The week
tools stay the short form: course, name, due, points, status, link.
`assignments()` adds how you submit and the short description.

**If wrong**: if the short description is still too long, or the status
labels lie for a quiz, trim `_plain` or stop requesting `include[]=submission`.
The week boundary does not depend on this.
