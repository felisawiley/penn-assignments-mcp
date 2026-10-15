"""Week boundary and assignment formatting. No Canvas token required."""
import os
import time
import unittest
from datetime import datetime, timezone

os.environ["TZ"] = "America/New_York"
time.tzset()

import server


class WeekBoundsTest(unittest.TestCase):
    def test_sunday_night_eastern_stays_in_this_week(self):
        # Monday 12 Oct 2026, 3pm EDT. Sunday 11:59pm EDT is already Monday in UTC.
        now = datetime(2026, 10, 12, 19, 0, tzinfo=timezone.utc)
        start, end = server._week_bounds(now)
        sunday_night = datetime(2026, 10, 19, 3, 59, tzinfo=timezone.utc)
        next_monday = datetime(2026, 10, 19, 4, 0, tzinfo=timezone.utc)
        self.assertLessEqual(start, sunday_night)
        self.assertLess(sunday_night, end)
        self.assertFalse(start <= next_monday < end)

    def test_heading_names_the_local_week(self):
        start, end = server._week_bounds(datetime(2026, 10, 15, 16, 0, tzinfo=timezone.utc))
        self.assertEqual(server._week_heading(start, end), "Mon Oct 12 – Sun Oct 18 (EDT)")


class FormatTest(unittest.TestCase):
    def test_detailed_line_keeps_the_work(self):
        description = server._plain("<p>Write <b>300</b> words.</p>")
        self.assertEqual(description, "Write 300 words.")
        item = {
            "course": "CIS 7000",
            "name": "Reading response",
            "due_at": datetime(2026, 10, 19, 3, 59, tzinfo=timezone.utc),
            "points_possible": 10,
            "html_url": "https://canvas.upenn.edu/courses/1/assignments/2",
            "description": description,
            "submission_types": ["online_text_entry"],
            "submission": {"workflow_state": "submitted", "missing": False, "late": True},
        }
        text = server._format_assignment(item, detailed=True)
        self.assertIn("[CIS 7000] Reading response", text)
        self.assertIn("Sun Oct 18, 11:59 PM", text)
        self.assertIn("(10 pts)", text)
        self.assertIn("text entry", text)
        self.assertIn("submitted, late", text)
        self.assertIn("https://canvas.upenn.edu/courses/1/assignments/2", text)
        self.assertIn("Write 300 words.", text)
        self.assertNotIn("<p>", text)

    def test_missing_unsubmitted_is_marked(self):
        self.assertEqual(
            server._status_label({"workflow_state": "unsubmitted", "missing": True, "late": False}),
            "missing",
        )

    def test_plain_text_drops_markup_and_truncates(self):
        raw = "<script>alert(1)</script><p>Hello&nbsp;there</p>" + (" word" * 80)
        text = server._plain(raw, limit=40)
        self.assertNotIn("alert", text)
        self.assertNotIn("<", text)
        self.assertTrue(text.endswith("…"))
        self.assertLessEqual(len(text), 40)


class _Req:
    def __init__(self, headers):
        self.headers = headers


class _RC:
    def __init__(self, request):
        self.request = request


class Ctx:
    def __init__(self, authorization=None, request=...):
        if request is ...:
            headers = {}
            if authorization is not None:
                headers["authorization"] = authorization
            request = _Req(headers)
        self.request_context = _RC(request)


class IdentityTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("OWNER_EMAIL", None)
        server.JWKS_URL = None

    def test_absent_token_is_guest(self):
        self.assertEqual(server.current_identity(Ctx(request=None)), (None, None))

    def test_declared_guest_credential_is_guest(self):
        ctx = Ctx(authorization="Bearer guest-no-shelf")
        self.assertEqual(server.current_identity(ctx), (None, None))
        refusal = server._canvas_access(None, None)
        self.assertIn("guest", refusal.lower())

    def test_garbled_token_is_not_a_guest(self):
        server.JWKS_URL = "https://example.invalid/jwks.json"
        with self.assertRaises(Exception):
            server.current_identity(Ctx(authorization="Bearer not-a-jwt"))

    def test_owner_pin_refuses_someone_else(self):
        os.environ["OWNER_EMAIL"] = "me@upenn.edu"
        self.assertIsNone(server._canvas_access("sub", "Me@upenn.edu"))
        refusal = server._canvas_access("sub", "other@upenn.edu")
        self.assertIn("other@upenn.edu", refusal)
        self.assertIn("me@upenn.edu", refusal)
        self.assertNotIn("guest", refusal.lower())

    def test_without_owner_pin_any_signed_in_user_is_allowed(self):
        os.environ.pop("OWNER_EMAIL", None)
        self.assertIsNone(server._canvas_access("sub", "anyone@upenn.edu"))


if __name__ == "__main__":
    unittest.main()
