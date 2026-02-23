"""Secrets Manager rotation Lambda for application secrets.

Implements the 4-step rotation protocol:
  1. createSecret — generate new SECRET_KEY, preserve DATABASE_URL
  2. setSecret    — no-op (no external system to update)
  3. testSecret   — verify the pending secret version is retrievable
  4. finishSecret — promote AWSPENDING to AWSCURRENT
"""

from __future__ import annotations

import json
import secrets

import boto3


def lambda_handler(event: dict, context: object) -> None:
    arn = event["SecretId"]
    token = event["ClientRequestToken"]
    step = event["Step"]

    client = boto3.client("secretsmanager")
    metadata = client.describe_secret(SecretId=arn)

    if not metadata.get("RotationEnabled"):
        raise ValueError(f"Secret {arn} is not enabled for rotation")

    versions = metadata.get("VersionIdsToStages", {})
    if token not in versions:
        raise ValueError(
            f"Secret version {token} has no stage for rotation of secret {arn}"
        )

    if "AWSCURRENT" in versions.get(token, []):
        return  # Already current, nothing to do

    if "AWSPENDING" not in versions.get(token, []):
        raise ValueError(
            f"Secret version {token} not set as AWSPENDING for rotation of secret {arn}"
        )

    if step == "createSecret":
        _create_secret(client, arn, token, versions)
    elif step == "setSecret":
        pass  # No external system to update
    elif step == "testSecret":
        _test_secret(client, arn, token)
    elif step == "finishSecret":
        _finish_secret(client, arn, token, versions)
    else:
        raise ValueError(f"Invalid step parameter: {step}")


def _create_secret(
    client: boto3.client,
    arn: str,
    token: str,
    versions: dict,
) -> None:
    """Generate a new SECRET_KEY while preserving DATABASE_URL."""
    try:
        client.get_secret_value(
            SecretId=arn, VersionId=token, VersionStage="AWSPENDING"
        )
        return  # Already created
    except client.exceptions.ResourceNotFoundException:
        pass

    current = client.get_secret_value(SecretId=arn, VersionStage="AWSCURRENT")
    current_dict = json.loads(current["SecretString"])

    new_secret = {
        "SECRET_KEY": secrets.token_urlsafe(64),
        "DATABASE_URL": current_dict.get(
            "DATABASE_URL", "sqlite:////app/data/fitness.db"
        ),
    }

    client.put_secret_value(
        SecretId=arn,
        ClientRequestToken=token,
        SecretString=json.dumps(new_secret),
        VersionStages=["AWSPENDING"],
    )


def _test_secret(client: boto3.client, arn: str, token: str) -> None:
    """Verify the pending secret version is retrievable and valid JSON."""
    response = client.get_secret_value(
        SecretId=arn, VersionId=token, VersionStage="AWSPENDING"
    )
    secret_dict = json.loads(response["SecretString"])

    if "SECRET_KEY" not in secret_dict:
        raise ValueError("Rotated secret missing SECRET_KEY")
    if "DATABASE_URL" not in secret_dict:
        raise ValueError("Rotated secret missing DATABASE_URL")


def _finish_secret(
    client: boto3.client,
    arn: str,
    token: str,
    versions: dict,
) -> None:
    """Promote AWSPENDING to AWSCURRENT."""
    current_version = None
    for version_id, stages in versions.items():
        if "AWSCURRENT" in stages:
            if version_id == token:
                return  # Already current
            current_version = version_id
            break

    client.update_secret_version_stage(
        SecretId=arn,
        VersionStage="AWSCURRENT",
        MoveToVersionId=token,
        RemoveFromVersionId=current_version,
    )
    client.update_secret_version_stage(
        SecretId=arn,
        VersionStage="AWSPENDING",
        RemoveFromVersionId=token,
    )
