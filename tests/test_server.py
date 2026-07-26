import io
import json
import unittest
from types import SimpleNamespace

from quill.server import (
    AUTOMATIC_IGNORE_TTL_SECONDS,
    EXPLICIT_IGNORE_TTL_SECONDS,
    QuillServer,
    _Handler,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class MeetingIgnoreTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.server = QuillServer(clock=self.clock)
        self.server.status = lambda: {"state": "idle"}
        self.tab_id = 42
        self.first_url = "https://meet.google.com/abc-defg-hij?authuser=0"
        self.second_url = "https://meet.google.com/xyz-abcd-efg"

    def test_explicit_ignore_is_scoped_to_meeting_and_expires(self):
        self.server.ignore(self.tab_id, self.first_url, automatic=False)

        self.assertEqual(
            self.server.meeting_detected(self.tab_id, self.first_url),
            {"prompt": False},
        )
        self.assertEqual(
            self.server.meeting_detected(self.tab_id, self.second_url),
            {"prompt": True},
        )

        self.clock.advance(EXPLICIT_IGNORE_TTL_SECONDS)
        self.assertEqual(
            self.server.meeting_detected(self.tab_id, self.first_url),
            {"prompt": True},
        )

    def test_automatic_dismissal_is_only_a_short_cooldown(self):
        self.server.ignore(self.tab_id, self.first_url, automatic=True)

        self.assertEqual(
            self.server.meeting_detected(self.tab_id, self.first_url),
            {"prompt": False},
        )
        self.clock.advance(AUTOMATIC_IGNORE_TTL_SECONDS - 1)
        self.assertEqual(
            self.server.meeting_detected(self.tab_id, self.first_url),
            {"prompt": False},
        )
        self.clock.advance(1)
        self.assertEqual(
            self.server.meeting_detected(self.tab_id, self.first_url),
            {"prompt": True},
        )
        self.assertLess(
            AUTOMATIC_IGNORE_TTL_SECONDS,
            EXPLICIT_IGNORE_TTL_SECONDS,
        )

    def test_automatic_dismissal_cannot_shorten_an_explicit_ignore(self):
        self.server.ignore(self.tab_id, self.first_url, automatic=False)
        self.clock.advance(1)
        self.server.ignore(self.tab_id, self.first_url, automatic=True)
        self.clock.advance(AUTOMATIC_IGNORE_TTL_SECONDS)

        self.assertEqual(
            self.server.meeting_detected(self.tab_id, self.first_url),
            {"prompt": False},
        )

    def test_clearing_tab_removes_all_of_its_suppressions(self):
        self.server.ignore(self.tab_id, self.first_url, automatic=False)
        self.server.ignore(self.tab_id, self.second_url, automatic=False)
        self.server.clear_tab(self.tab_id)

        self.assertEqual(
            self.server.meeting_detected(self.tab_id, self.first_url),
            {"prompt": True},
        )
        self.assertEqual(
            self.server.meeting_detected(self.tab_id, self.second_url),
            {"prompt": True},
        )

    def post(self, path, body):
        raw_body = json.dumps(body).encode()
        handler = object.__new__(_Handler)
        handler.path = path
        handler.server = SimpleNamespace(quill=self.server)
        handler.headers = {"Content-Length": str(len(raw_body))}
        handler.rfile = io.BytesIO(raw_body)
        responses = []
        handler._send = lambda payload, status=200: responses.append(
            (status, payload)
        )
        handler.do_POST()
        self.assertEqual(len(responses), 1)
        return responses[0]

    def test_http_routes_reproduce_same_tab_different_meeting_scenario(self):
        first_detection = {
            "platform": "google-meet",
            "url": self.first_url,
            "tabId": self.tab_id,
        }
        self.assertEqual(
            self.post("/meeting/detected", first_detection),
            (200, {"prompt": True}),
        )
        self.assertEqual(
            self.post(
                "/meeting/ignore",
                {
                    "tabId": self.tab_id,
                    "url": self.first_url,
                    "automatic": False,
                },
            ),
            (200, {"ok": True}),
        )
        self.assertEqual(
            self.post("/meeting/detected", first_detection),
            (200, {"prompt": False}),
        )
        self.assertEqual(
            self.post(
                "/meeting/detected",
                {
                    **first_detection,
                    "url": self.second_url,
                },
            ),
            (200, {"prompt": True}),
        )


if __name__ == "__main__":
    unittest.main()
