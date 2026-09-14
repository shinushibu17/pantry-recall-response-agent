import importlib.util
import unittest
from unittest.mock import Mock, patch

HAS_BOTO = importlib.util.find_spec("boto3") is not None
if HAS_BOTO:
    from botocore.exceptions import ClientError, EndpointConnectionError
    from pantry_recall.aws_access import check_access, error_details


@unittest.skipUnless(HAS_BOTO, "Install locked boto3 dependencies with uv sync")
class AwsAccessTests(unittest.TestCase):
    def test_missing_credentials_never_means_model_access_denied(self):
        session = Mock(region_name="us-east-1")
        session.get_credentials.return_value = None
        with patch("pantry_recall.aws_access.session_for", return_value=session), patch.dict("os.environ", {}, clear=True):
            result = check_access()
        self.assertEqual(result["status"], "CREDENTIALS_MISSING")
        self.assertFalse(result["model_invocation_verified"])
        session.client.assert_not_called()

    def test_ready_requires_successful_runtime_request(self):
        session = Mock(region_name="us-east-1")
        session.client.return_value.converse.return_value = {"usage": {"inputTokens": 5, "outputTokens": 1}}
        with patch("pantry_recall.aws_access.session_for", return_value=session):
            result = check_access()
        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["model_invocation_verified"])
        session.client.return_value.converse.assert_called_once()

    def test_denied_expired_and_network_failures_are_distinct_and_redacted(self):
        for code, status in (("AccessDeniedException", "ACCESS_DENIED"), ("ExpiredToken", "CREDENTIALS_EXPIRED"), ("ValidationException", "MODEL_OR_REQUEST_INVALID")):
            with self.subTest(code=code):
                error = ClientError({"Error": {"Code": code, "Message": "private credential-provider output"}}, "Converse")
                result = error_details(error)
                self.assertEqual(result["status"], status)
                self.assertNotIn("private", str(result))
        self.assertEqual(error_details(EndpointConnectionError(endpoint_url="https://example.invalid"))["status"], "UNAVAILABLE")
