# ADR-0007: Render runs on Eastern time

- Status: Accepted · 2026-10-15 · Felisa Wiley

**Context**: ADR-0005 defines the academic week in the server process's
local timezone. That matched a laptop set to US Eastern. Render's free
tier runs UTC. A Sunday 11:59 PM deadline in Philadelphia is already Monday
in UTC, so a cutoff computed in UTC places it in the next week. That is the
same miss already fixed once locally, when the Monday boundary was still
computed in UTC.

**Decision**: `render.yaml` sets `TZ=America/New_York` on `assignment-mcp`.
Python's local time then follows Eastern, including the daylight switch, and
the heading on `due_this_week()` names the week and the zone abbreviation
so a wrong zone is visible. Local `uv run` still uses the machine zone; set
`TZ` the same way if the machine is not already Eastern.

**If wrong**: a course that is not on Penn time wants a different `TZ`.
Change the env var. The week math does not hard-code a zone.
