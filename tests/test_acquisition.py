from io import BytesIO
from urllib.error import HTTPError, URLError
import unittest
from unittest.mock import patch

from tools.acquire_fixture import AcquisitionError, ENFORCEMENT_URL, NOTICE_URL, fetch


def http_error(code, body=b"error"):
    return HTTPError(ENFORCEMENT_URL, code, "test error", {}, BytesIO(body))


class AcquisitionTests(unittest.TestCase):
    def test_documented_no_results_is_separate_from_outage(self):
        error = http_error(404, b'{"error":{"code":"NOT_FOUND","message":"No matches found!"}}')
        with patch("tools.acquire_fixture.urlopen", side_effect=error), self.assertRaises(AcquisitionError) as result:
            fetch(ENFORCEMENT_URL)
        self.assertEqual(result.exception.state, "NO_RESULTS")

    def test_missing_notice_is_not_no_recalls(self):
        error = http_error(404, b'{"error":{"code":"NOT_FOUND","message":"No matches found!"}}')
        with patch("tools.acquire_fixture.urlopen", side_effect=error), self.assertRaises(AcquisitionError) as result:
            fetch(NOTICE_URL)
        self.assertEqual(result.exception.state, "UNAVAILABLE")

    def test_auth_query_and_unknown_errors_are_distinct(self):
        for code, state in ((401, "ACCESS_DENIED"), (403, "ACCESS_DENIED"), (400, "INVALID_QUERY"), (404, "UNAVAILABLE")):
            with self.subTest(code=code), patch("tools.acquire_fixture.urlopen", side_effect=http_error(code)), self.assertRaises(AcquisitionError) as result:
                fetch(ENFORCEMENT_URL)
            self.assertEqual(result.exception.state, state)

    def test_rate_limit_and_server_retries_are_bounded(self):
        for code in (429, 503):
            with self.subTest(code=code), patch("tools.acquire_fixture.urlopen", side_effect=[http_error(code) for _ in range(3)]) as request, patch("tools.acquire_fixture.time.sleep") as sleep, self.assertRaises(AcquisitionError) as result:
                fetch(ENFORCEMENT_URL)
            self.assertEqual(result.exception.state, "UNAVAILABLE")
            self.assertEqual(request.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])
            self.assertTrue(all(call.kwargs["timeout"] == 20 for call in request.call_args_list))

    def test_network_failure_preserves_unavailable(self):
        for error in (URLError("offline"), TimeoutError("timeout")):
            with self.subTest(error=error), patch("tools.acquire_fixture.urlopen", side_effect=error), self.assertRaises(AcquisitionError) as result:
                fetch(ENFORCEMENT_URL)
            self.assertEqual(result.exception.state, "UNAVAILABLE")

    def test_malformed_api_error_is_not_no_results(self):
        with patch("tools.acquire_fixture.urlopen", side_effect=http_error(404, b'{"error":[]}')), self.assertRaises(AcquisitionError) as result:
            fetch(ENFORCEMENT_URL)
        self.assertEqual(result.exception.state, "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
