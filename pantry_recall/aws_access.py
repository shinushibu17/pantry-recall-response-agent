"""Check local authentication and actually invoke the configured Bedrock model."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path


DEFAULT_REGION = "us-east-1"
DEFAULT_MODEL = "amazon.nova-pro-v1:0"


def session_for(profile: str | None = None, region: str | None = None):
    import boto3

    # Local CLI: don't probe EC2 metadata on a volunteer's laptop.
    os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
    session = boto3.Session(profile_name=profile, region_name=region or os.getenv("AWS_REGION"))
    if session.region_name is None:
        session = boto3.Session(profile_name=profile, region_name=DEFAULT_REGION)
    return session


def client_config():
    from botocore.config import Config

    return Config(connect_timeout=5, read_timeout=45,
                  retries={"mode": "standard", "total_max_attempts": 2})


def agent_model_options(model_id: str) -> dict:
    """Bounded generation; Nova tool-use settings follow AWS troubleshooting guidance."""
    options = {"streaming": False, "temperature": 0, "max_tokens": 3072}
    if model_id in ("amazon.nova-lite-v1:0", "amazon.nova-pro-v1:0"):
        options["additional_request_fields"] = {"inferenceConfig": {"topK": 1}}
    return options


def error_details(error: Exception) -> dict:
    """Don't serialize SDK exceptions: they can contain credential-provider output."""
    from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

    if isinstance(error, ProfileNotFound):
        return {"status": "PROFILE_MISSING", "next_step": "Run aws login --profile pantry-recall --region us-east-1."}
    if isinstance(error, NoCredentialsError):
        return {"status": "CREDENTIALS_MISSING", "next_step": "Configure a local AWS profile, then pass --profile NAME."}
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code", "Unknown")
        if code == "ModelErrorException":
            return {"status": "MODEL_OUTPUT_ERROR", "aws_error_code": code,
                    "next_step": "The model failed to produce a valid response. Check tool-use decoding and output-token limits; this is not a credential or permission diagnosis."}
        states = {
            "AccessDeniedException": "ACCESS_DENIED", "AccessDenied": "ACCESS_DENIED",
            "ExpiredTokenException": "CREDENTIALS_EXPIRED", "ExpiredToken": "CREDENTIALS_EXPIRED",
            "UnrecognizedClientException": "CREDENTIALS_INVALID",
            "InvalidClientTokenId": "CREDENTIALS_INVALID",
            "ValidationException": "MODEL_OR_REQUEST_INVALID",
            "ResourceNotFoundException": "MODEL_NOT_FOUND",
            "ThrottlingException": "THROTTLED",
        }
        return {"status": states.get(code, "AWS_ERROR"), "aws_error_code": code,
                "next_step": "Check this model's region and InvokeModel permission; re-login if credentials expired."}
    return {"status": "UNAVAILABLE", "error_type": type(error).__name__,
            "next_step": "Check network access and local AWS login configuration. No model-access conclusion was established."}


def check_access(profile: str | None = None, region: str | None = None,
                 model_id: str = DEFAULT_MODEL) -> dict:
    from botocore.exceptions import NoCredentialsError

    report = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "profile": profile or os.getenv("AWS_PROFILE", "default"),
              "region": region, "model_id": model_id, "model_invocation_verified": False}
    try:
        session = session_for(profile, region)
        report["region"] = session.region_name
        bearer = bool(os.getenv("AWS_BEARER_TOKEN_BEDROCK"))
        if not bearer and session.get_credentials() is None:
            raise NoCredentialsError()
        if not bearer:
            session.client("sts", config=client_config()).get_caller_identity()
        report["authentication"] = "bedrock_bearer_token" if bearer else "aws_credential_chain"
        response = session.client("bedrock-runtime", config=client_config()).converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "Reply with READY."}]}],
            inferenceConfig={"maxTokens": 8, "temperature": 0},
        )
        report.update(status="READY", model_invocation_verified=True,
                      usage=response.get("usage", {}), request_id=response.get("ResponseMetadata", {}).get("RequestId"))
    except Exception as error:
        report.update(error_details(error))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile")
    parser.add_argument("--region")
    parser.add_argument("--model-id", default=os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL))
    parser.add_argument("--output", type=Path, default=Path("outputs/aws-access.json"))
    args = parser.parse_args()
    report = check_access(args.profile, args.region, args.model_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["model_invocation_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
