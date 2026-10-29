# ADR-0010: Rank open work on separate axes

- Status: Accepted · 2026-10-29 · Felisa Wiley

**Context**: "What should I do first?" can mean the soonest deadline, the
largest point value, the shortest task, the longest task, the weakest
course grade, or the semester as a whole. Folding those into one score
hides which reason won. Canvas stores due dates, points, and the current
and final course score. It does not store how long an assignment takes,
and it does not store credit hours on the course object this server reads.

**Decision**: `priorities()` returns six lists, and only open work (not
submitted, graded, pending review, or excused). Due soonest breaks a same-day
tie toward more points. Most points lists an assignment with no point value
last. A duration is included only when the assignment text states one
("45 minutes", "2 hours", "half an hour"). Points are never treated as
minutes. Each course line is Canvas's current score. The semester line is
the unweighted mean of those current scores, and it says so. A course with
no posted score is left out of the mean. The final score is shown beside
the current score when the two differ, because Canvas computes final by
counting ungraded work as zero.

**If wrong**: if a stated-time phrase is too often a false match, narrow
`_minutes_mentioned` instead of guessing a duration. If credit weights
become available from the registrar, weight the semester mean then. Do not
blend the six lists into one rank.
