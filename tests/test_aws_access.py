import importlib.util
import unittest
from unittest.mock import Mock, patch

HAS_BOTO = importlib.util.find_spec("boto3") is not None
if HAS_BOTO:
    from botocore.exceptions import ClientError, EndpointConnectionError
    from pantry_recall.aws_access import check_access, error_details


@unittest.skipUnless(HAS_BOTO, "Install locked boto3 dependencies with uv sync")
class AwsAccessTests(unittest.TestCase):
    def test_web_invokes_and_reports_the_configured_model(self):
        from pantry_recall.web import live_agent
        from pantry_recall.aws_access import DEFAULT_MODEL
        for configured in (None, "amazon.nova-lite-v1:0", "amazon.nova-pro-v1:0"):
            with self.subTest(model=configured), patch.dict("os.environ", {"BEDROCK_MODEL_ID": configured} if configured else {}, clear=True), \
                    patch("strands.models.BedrockModel") as adapter, \
                    patch("pantry_recall.aws_access.session_for", return_value=Mock(region_name="us-east-1")), \
                    patch("pantry_recall.agent.run_agent", return_value={}) as run, \
                    patch("pantry_recall.web.FollowUp"):
                report = live_agent(Mock())
                expected = configured or DEFAULT_MODEL
                self.assertEqual(adapter.call_args.kwargs["model_id"], expected)
                self.assertEqual(report["model_id"], expected)
                self.assertIs(run.call_args.args[0], adapter.return_value)
                self.assertEqual(adapter.call_args.kwargs["max_tokens"], 3072)
                self.assertEqual(adapter.call_args.kwargs["additional_request_fields"], {"inferenceConfig": {"topK": 1}})

    def test_model_output_failure_does_not_request_new_permissions(self):
        error = ClientError({"Error": {"Code": "ModelErrorException", "Message": "private provider output"}}, "Converse")
        result = error_details(error)
        self.assertEqual(result["status"], "MODEL_OUTPUT_ERROR")
        self.assertNotIn("private", str(result))
        self.assertIn("not a credential or permission diagnosis", result["next_step"])

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
