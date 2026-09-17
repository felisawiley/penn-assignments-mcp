"""assignment-mcp — a sense of coursework for a model that has none.

Ask your Claude "what's due this week?" without this connected: it can't
know, because Canvas isn't in its context window. This server hands it a
read-only view of Canvas — courses, assignments, due dates — through the
same REST API Canvas's own web UI calls. See docs/adr/ for the reasoning.
"""
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP(
    "assignment-mcp",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
)

CANVAS_BASE_URL = os.environ.get("CANVAS_BASE_URL", "https://canvas.upenn.edu").rstrip("/")
CANVAS_API_TOKEN = os.environ.get("CANVAS_API_TOKEN", "")


def _client() -> httpx.Client:
    if not CANVAS_API_TOKEN:
        raise RuntimeError(
            "Set CANVAS_API_TOKEN — Canvas → Account → Settings → "
            "+ New Access Token. Set CANVAS_BASE_URL too if you're not on "
            "Penn's Canvas (default: https://canvas.upenn.edu)."
        )
    return httpx.Client(
        base_url=f"{CANVAS_BASE_URL}/api/v1",
        headers={"Authorization": f"Bearer {CANVAS_API_TOKEN}"},
        timeout=20,
    )


def _get_all(client: httpx.Client, path: str, **params: Any) -> list[dict]:
    """GET `path`, following Canvas's Link-header pagination to the end."""
    items: list[dict] = []
    url: str | None = path
    query: dict[str, Any] | None = {**params, "per_page": 100}
    while url:
        resp = client.get(url, params=query)
        resp.raise_for_status()
        items.extend(resp.json())
        url = resp.links.get("next", {}).get("url")
        query = None
    return items


def _active_courses(client: httpx.Client) -> list[dict]:
    return _get_all(
        client,
        "/courses",
        enrollment_state="active",
        **{"include[]": ["term", "teachers"]},
    )


def _resolve_courses(client: httpx.Client, course: str | None) -> list[dict]:
    courses = _active_courses(client)
    if course is None:
        return courses
    needle = course.strip().lower()
    matches = [
        c for c in courses
        if needle in (c.get("name") or "").lower()
        or needle in (c.get("course_code") or "").lower()
    ]
    if not matches:
        names = ", ".join(c["name"] for c in courses)
        raise ValueError(f"No active course matches {course!r}. Active courses: {names}")
    return matches


def _parse_due(due_at: str | None) -> datetime | None:
    if not due_at:
        return None
    return datetime.fromisoformat(due_at.replace("Z", "+00:00"))


def _course_assignments(client: httpx.Client, course: dict) -> list[dict]:
    raw = _get_all(client, f"/courses/{course['id']}/assignments", order_by="due_at")
    out = []
    for a in raw:
        if a.get("workflow_state") != "published":
            continue
        out.append({
            "course": course["name"],
            "name": a["name"],
            "due_at": _parse_due(a.get("due_at")),
            "points_possible": a.get("points_possible"),
        })
    return out


def _all_assignments(client: httpx.Client, course: str | None = None) -> list[dict]:
    assignments = []
    for c in _resolve_courses(client, course):
        assignments.extend(_course_assignments(client, c))
    distant_future = datetime.max.replace(tzinfo=timezone.utc)
    assignments.sort(key=lambda a: a["due_at"] or distant_future)
    return assignments


def _week_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Monday 00:00 to next Monday 00:00, in the server's local timezone."""
    local_now = now.astimezone()
    monday = (local_now - timedelta(days=local_now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday, monday + timedelta(days=7)


def _format_assignment(a: dict) -> str:
    when = a["due_at"].astimezone().strftime("%a %b %-d, %-I:%M %p") if a["due_at"] else "no due date"
    pts = f" ({a['points_possible']:g} pts)" if a.get("points_possible") else ""
    return f"- [{a['course']}] {a['name']} — due {when}{pts}"


@mcp.tool()
def canvas() -> str:
    """Basic course context: your active courses, their instructors, modules, and latest announcements."""
    with _client() as client:
        courses = _active_courses(client)
        if not courses:
            return "No active courses."
        context_codes = [f"course_{c['id']}" for c in courses]
        announcements = _get_all(
            client, "/announcements", **{"context_codes[]": context_codes}, active_only="true"
        )
        by_course_ann: dict[int, list[dict]] = defaultdict(list)
        for ann in announcements:
            cid = int(ann["context_code"].removeprefix("course_"))
            by_course_ann[cid].append(ann)

        blocks = []
        for c in courses:
            teachers = ", ".join(t["display_name"] for t in c.get("teachers", [])) or "unknown instructor"
            term = c.get("term", {}).get("name", "")
            modules = _get_all(client, f"/courses/{c['id']}/modules")
            module_lines = "\n".join(
                f"  - {m['name']} ({'published' if m.get('published') else 'unpublished'})"
                for m in modules[:10]
            ) or "  (none)"
            latest_ann = sorted(
                by_course_ann.get(c["id"], []), key=lambda a: a.get("posted_at") or "", reverse=True
            )[:2]
            ann_lines = "\n".join(f"  - {a['title']}" for a in latest_ann) or "  (none)"
            blocks.append(
                f"{c['name']} [{term}] — taught by {teachers}\n"
                f" Modules:\n{module_lines}\n"
                f" Recent announcements:\n{ann_lines}"
            )
        return "\n\n".join(blocks)


@mcp.tool()
def assignments(course: str | None = None) -> str:
    """All active (published) assignments, optionally filtered to one course by name or code."""
    with _client() as client:
        items = _all_assignments(client, course)
    if not items:
        return f"No active assignments{f' for {course}' if course else ''}."
    return "\n".join(_format_assignment(a) for a in items)


@mcp.tool()
def due_this_week() -> str:
    """Assignments due in the current Monday–Sunday academic week, earliest due date first."""
    now = datetime.now(timezone.utc)
    start, end = _week_bounds(now)
    with _client() as client:
        items = [a for a in _all_assignments(client) if a["due_at"] and start <= a["due_at"] < end]
    if not items:
        return "Nothing due this week."
    return "\n".join(_format_assignment(a) for a in items)


@mcp.tool()
def academic_week() -> str:
    """Synthesis of the current week: what's due, from which classes, what's coming next, and where the week is unusually heavy."""
    now = datetime.now(timezone.utc)
    start, end = _week_bounds(now)
    next_start, next_end = end, end + timedelta(days=7)
    with _client() as client:
        all_items = _all_assignments(client)
    this_week = [a for a in all_items if a["due_at"] and start <= a["due_at"] < end]
    next_week = [a for a in all_items if a["due_at"] and next_start <= a["due_at"] < next_end]

    lines = ["This week:"]
    lines.append("\n".join(_format_assignment(a) for a in this_week) if this_week else "  Nothing due.")

    heavy_days = [
        day.strftime("%A %b %-d") for day, n in
        Counter(a["due_at"].astimezone().date() for a in this_week).items() if n >= 2
    ]
    heavy_courses = [
        course for course, n in Counter(a["course"] for a in this_week).items() if n >= 2
    ]
    if heavy_days or heavy_courses:
        lines.append("\nUnusually heavy:")
        for d in heavy_days:
            lines.append(f"  - {d} has multiple assignments due")
        for c in heavy_courses:
            n = sum(1 for a in this_week if a["course"] == c)
            lines.append(f"  - {c} has {n} due this week")
    elif len(this_week) > len(next_week) + 1:
        lines.append(f"\nThis week ({len(this_week)} due) is heavier than next week ({len(next_week)} due).")

    lines.append("\nComing next week:")
    lines.append("\n".join(_format_assignment(a) for a in next_week) if next_week else "  Nothing posted yet.")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
