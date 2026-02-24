"""Static analysis tests for Terraform modules.

Prevents misconfigurations that are hard to catch during plan/apply,
such as combining multiple TXT record values into a single Route 53
record resource (which breaks DNS validation for ProtonMail, SPF, etc.).
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DNS_MODULE = PROJECT_ROOT / "terraform" / "aws" / "modules" / "dns" / "main.tf"

# Matches: resource "aws_route53_record" "name" { ... }
_RESOURCE_BLOCK_RE = re.compile(
    r'resource\s+"aws_route53_record"\s+"(\w+)"\s*\{', re.MULTILINE
)


def _extract_record_blocks(content: str) -> list[tuple[str, str]]:
    """Return (resource_name, block_body) for each aws_route53_record."""
    blocks = []
    for match in _RESOURCE_BLOCK_RE.finditer(content):
        name = match.group(1)
        start = match.end()
        depth = 1
        pos = start
        while pos < len(content) and depth > 0:
            if content[pos] == "{":
                depth += 1
            elif content[pos] == "}":
                depth -= 1
            pos += 1
        blocks.append((name, content[start:pos]))
    return blocks


def _get_type(block_body: str) -> str | None:
    """Extract the type attribute from a resource block."""
    m = re.search(r'type\s*=\s*"(\w+)"', block_body)
    return m.group(1) if m else None


def _count_records_entries(block_body: str) -> int | None:
    """Count literal string entries in a records = [...] list.

    Returns None if no records attribute found (e.g. alias blocks).
    Only counts top-level quoted strings; ignores variables/expressions.
    """
    m = re.search(r"records\s*=\s*\[([^\]]*)\]", block_body, re.DOTALL)
    if not m:
        return None
    inner = m.group(1)
    return len(re.findall(r'"[^"]*"', inner))


def test_txt_records_have_single_value():
    """Each TXT aws_route53_record must contain exactly one value.

    Combining multiple TXT values (e.g. SPF + ProtonMail verification)
    into one record resource causes Route 53 to merge them, which breaks
    DNS validation for services that expect a standalone TXT record.
    """
    assert DNS_MODULE.exists(), f"DNS module not found at {DNS_MODULE}"
    content = DNS_MODULE.read_text()
    blocks = _extract_record_blocks(content)

    violations = []
    for name, body in blocks:
        if _get_type(body) != "TXT":
            continue
        count = _count_records_entries(body)
        if count is not None and count > 1:
            violations.append(
                f"aws_route53_record.{name} has {count} values in records "
                f"(each TXT record must be a separate resource)"
            )

    assert not violations, (
        "TXT records must not combine multiple values:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


# ================================================================
# Module path constants
# ================================================================

MEDIA_MODULE = PROJECT_ROOT / "terraform" / "aws" / "modules" / "media" / "main.tf"
APP_RUNNER_MODULE = (
    PROJECT_ROOT / "terraform" / "aws" / "modules" / "app-runner" / "main.tf"
)
BOOTSTRAP_MODULE = PROJECT_ROOT / "terraform" / "aws" / "bootstrap" / "main.tf"


# ================================================================
# Media Module — S3 + CloudFront Security Tests
# ================================================================


def test_media_s3_bucket_blocks_public_access():
    """Media S3 bucket must block all public access.

    CloudFront OAC is the sole reader; no direct public access should
    be possible. All four public-access-block settings must be true.
    """
    assert MEDIA_MODULE.exists(), f"Media module not found at {MEDIA_MODULE}"
    content = MEDIA_MODULE.read_text()

    for setting in (
        "block_public_acls",
        "block_public_policy",
        "ignore_public_acls",
        "restrict_public_buckets",
    ):
        pattern = rf"{setting}\s*=\s*true"
        assert re.search(pattern, content), (
            f"Media S3 bucket missing '{setting} = true' — "
            f"all public access must be blocked"
        )


def test_media_cloudfront_uses_oac():
    """Media module must use CloudFront Origin Access Control (OAC).

    OAC replaces the legacy OAI and provides sigv4-based access to S3,
    preventing direct bucket access from the internet.
    """
    assert MEDIA_MODULE.exists(), f"Media module not found at {MEDIA_MODULE}"
    content = MEDIA_MODULE.read_text()

    assert re.search(r'resource\s+"aws_cloudfront_origin_access_control"', content), (
        "Media module must define an aws_cloudfront_origin_access_control resource "
        "to secure S3 origin access"
    )


def test_media_s3_policy_denies_delete():
    """Media S3 bucket policy must include a Deny for s3:DeleteObject.

    Media is append-mostly; deletion should be handled via lifecycle
    rules or admin console, not application-level API calls.
    """
    assert MEDIA_MODULE.exists(), f"Media module not found at {MEDIA_MODULE}"
    content = MEDIA_MODULE.read_text()

    # The bucket policy should contain both a Deny effect and s3:DeleteObject action
    # HCL keys inside jsonencode() may or may not be quoted
    has_deny = re.search(r'"?Effect"?\s*=\s*"Deny"', content)
    has_delete_object = re.search(r'"?Action"?\s*=\s*"s3:DeleteObject"', content)

    assert has_deny and has_delete_object, (
        "Media S3 bucket policy must contain a Deny statement for s3:DeleteObject "
        "to prevent accidental or unauthorized media deletion"
    )


def test_media_cloudfront_https_only():
    """All CloudFront cache behaviors must redirect HTTP to HTTPS.

    Serving media over plain HTTP exposes content to interception.
    Every viewer_protocol_policy must be 'redirect-to-https'.
    """
    assert MEDIA_MODULE.exists(), f"Media module not found at {MEDIA_MODULE}"
    content = MEDIA_MODULE.read_text()

    policies = re.findall(r'viewer_protocol_policy\s*=\s*"([^"]+)"', content)
    assert len(policies) > 0, (
        "No viewer_protocol_policy found in CloudFront distribution"
    )
    for policy in policies:
        assert policy == "redirect-to-https", (
            f"CloudFront viewer_protocol_policy is '{policy}' — "
            f"must be 'redirect-to-https'"
        )


def test_media_cloudfront_tls_minimum():
    """CloudFront must enforce at least TLSv1.2.

    Older TLS versions have known vulnerabilities; the minimum
    protocol version must contain 'TLSv1.2'.
    """
    assert MEDIA_MODULE.exists(), f"Media module not found at {MEDIA_MODULE}"
    content = MEDIA_MODULE.read_text()

    match = re.search(r'minimum_protocol_version\s*=\s*"([^"]+)"', content)
    assert match, "No minimum_protocol_version found in CloudFront viewer_certificate"
    assert "TLSv1.2" in match.group(1), (
        f"minimum_protocol_version is '{match.group(1)}' — "
        f"must contain 'TLSv1.2' or higher"
    )


# ================================================================
# App Runner Module — Egress + S3 Policy Tests
# ================================================================


def test_apprunner_egress_no_unrestricted():
    """App Runner security group must not allow unrestricted egress.

    Using protocol = "-1" (all traffic) in egress rules bypasses the
    principle of least privilege. Only HTTPS (443/tcp) and DNS
    (53/udp, 53/tcp) should be permitted.
    """
    assert APP_RUNNER_MODULE.exists(), (
        f"App Runner module not found at {APP_RUNNER_MODULE}"
    )
    content = APP_RUNNER_MODULE.read_text()

    # Look for protocol = "-1" inside security group egress blocks
    assert not re.search(r'protocol\s*=\s*"-1"', content), (
        'App Runner security group has protocol = "-1" (all traffic) in egress — '
        "egress must be restricted to HTTPS (443/tcp) and DNS (53/udp+tcp) only"
    )


def test_apprunner_media_s3_policy_no_delete():
    """App Runner S3 media policy must not grant s3:DeleteObject.

    The application should only upload (PutObject) and read (GetObject)
    media. Deletion is restricted to lifecycle rules and admin console.
    """
    assert APP_RUNNER_MODULE.exists(), (
        f"App Runner module not found at {APP_RUNNER_MODULE}"
    )
    content = APP_RUNNER_MODULE.read_text()

    # Extract the apprunner_media_s3 policy block
    match = re.search(
        r'resource\s+"aws_iam_role_policy"\s+"apprunner_media_s3"\s*\{',
        content,
    )
    assert match, "apprunner_media_s3 IAM policy not found in app-runner module"

    # Extract the full block
    start = match.end()
    depth = 1
    pos = start
    while pos < len(content) and depth > 0:
        if content[pos] == "{":
            depth += 1
        elif content[pos] == "}":
            depth -= 1
        pos += 1
    policy_block = content[start:pos]

    assert "s3:DeleteObject" not in policy_block, (
        "App Runner media S3 policy contains s3:DeleteObject — "
        "only PutObject and GetObject should be permitted"
    )


# ================================================================
# App Runner Module — Boolean Count Pattern Tests
# ================================================================
#
# Pattern: Conditional resources must use boolean variables for count,
# NOT computed string checks like `var.some_arn != ""`.
#
# Why: Terraform evaluates `count` during the plan phase. If the
# expression depends on a resource attribute that won't be known until
# apply (e.g. an ARN from a counted module), the plan fails with:
#
#   Error: Invalid count argument
#   The "count" value depends on resource attributes that cannot be
#   determined until apply.
#
# Fix: Pass a plan-time-known `bool` variable (e.g. `enable_media`)
# from the root module alongside the computed ARN, and use the bool
# for the count expression:
#
#   count = var.enable_media ? 1 : 0      # ✓ plan-time known
#   count = var.media_bucket_arn != "" ? 1 : 0  # ✗ computed at apply
#


def _extract_count_expression(
    content: str, resource_type: str, resource_name: str
) -> str | None:
    """Extract the count expression from a Terraform resource block.

    Returns the RHS of `count = <expr>` or None if the resource is not found.
    """
    pattern = rf'resource\s+"{resource_type}"\s+"{resource_name}"\s*\{{'
    match = re.search(pattern, content)
    if not match:
        return None

    # Find the block body
    start = match.end()
    depth = 1
    pos = start
    while pos < len(content) and depth > 0:
        if content[pos] == "{":
            depth += 1
        elif content[pos] == "}":
            depth -= 1
        pos += 1
    block = content[start:pos]

    # Extract count = ...
    count_match = re.search(r"count\s*=\s*(.+)", block)
    return count_match.group(1).strip() if count_match else None


def test_apprunner_media_s3_uses_boolean_count():
    """App Runner media S3 policy must use a boolean variable for count.

    Using `var.media_bucket_arn != ""` fails at plan time because the ARN
    is computed from a counted module. The count must use `var.enable_media`.
    """
    content = APP_RUNNER_MODULE.read_text()
    expr = _extract_count_expression(
        content, "aws_iam_role_policy", "apprunner_media_s3"
    )

    assert expr is not None, "apprunner_media_s3 resource not found"
    assert "var.enable_media" in expr, (
        f"apprunner_media_s3 count uses '{expr}' — "
        f"must use 'var.enable_media ? 1 : 0' (plan-time boolean)"
    )
    assert "media_bucket_arn" not in expr, (
        f"apprunner_media_s3 count depends on computed ARN: '{expr}' — "
        f"use 'var.enable_media' boolean instead"
    )


def test_apprunner_dynamodb_uses_boolean_count():
    """App Runner DynamoDB policy must use a boolean variable for count.

    Using `var.dynamodb_table_arn != ""` fails at plan time because the ARN
    is computed from a counted module. The count must use `var.enable_data_ingest`.
    """
    content = APP_RUNNER_MODULE.read_text()
    expr = _extract_count_expression(
        content, "aws_iam_role_policy", "apprunner_dynamodb"
    )

    assert expr is not None, "apprunner_dynamodb resource not found"
    assert "var.enable_data_ingest" in expr, (
        f"apprunner_dynamodb count uses '{expr}' — "
        f"must use 'var.enable_data_ingest ? 1 : 0' (plan-time boolean)"
    )
    assert "dynamodb_table_arn" not in expr, (
        f"apprunner_dynamodb count depends on computed ARN: '{expr}' — "
        f"use 'var.enable_data_ingest' boolean instead"
    )


# ================================================================
# Bootstrap Module — KMS + S3 Scoping Tests
# ================================================================


def test_bootstrap_s3_scoped_to_project_prefix():
    """Bootstrap S3 policy must scope resources to the project prefix.

    Using bare '*' as a resource ARN would grant access to ALL S3
    buckets in the account. The policy must use '${var.project}-*'
    to limit scope to project-owned buckets only.
    """
    assert BOOTSTRAP_MODULE.exists(), (
        f"Bootstrap module not found at {BOOTSTRAP_MODULE}"
    )
    content = BOOTSTRAP_MODULE.read_text()

    # Find the S3Buckets statement in tfc_governance policy
    match = re.search(
        r'"S3Buckets".*?Resource\s*=\s*\[(.*?)\]',
        content,
        re.DOTALL,
    )
    assert match, "S3Buckets statement not found in bootstrap module"

    resource_block = match.group(1)
    assert "${var.project}-" in resource_block, (
        "Bootstrap S3 policy Resource must use '${var.project}-*' prefix — "
        "found unscoped resource ARN"
    )
    # Ensure there is no bare wildcard resource (just "arn:aws:s3:::*")
    bare_wildcard = re.findall(r'"arn:aws:s3:::\*"', resource_block)
    assert len(bare_wildcard) == 0, (
        "Bootstrap S3 policy has bare wildcard 'arn:aws:s3:::*' resource — "
        "must be scoped to '${var.project}-*'"
    )


def test_bootstrap_kms_has_viaservice_condition():
    """Bootstrap KMS encryption policy must include kms:ViaService condition.

    Data-plane KMS operations (Encrypt, Decrypt, GenerateDataKey) should
    only be allowed when invoked via specific AWS services, preventing
    direct KMS API abuse.
    """
    assert BOOTSTRAP_MODULE.exists(), (
        f"Bootstrap module not found at {BOOTSTRAP_MODULE}"
    )
    content = BOOTSTRAP_MODULE.read_text()

    # Find the KMSEncryption statement
    match = re.search(
        r'"KMSEncryption".*?Condition\s*=\s*\{(.*?)\}\s*\}',
        content,
        re.DOTALL,
    )
    assert match, "KMSEncryption statement with Condition not found in bootstrap module"

    condition_block = match.group(1)
    assert "kms:ViaService" in condition_block, (
        "Bootstrap KMS encryption policy missing 'kms:ViaService' condition — "
        "data-plane operations must be scoped to specific AWS services"
    )


# ================================================================
# Bootstrap IAM — Resource-to-Action Coverage Tests
# ================================================================
#
# These tests verify the bootstrap IAM policies contain the IAM
# actions required to manage every AWS resource type used in the
# project's Terraform modules.
#
# When a new resource type is added to a module, the corresponding
# IAM action must be added here AND to the bootstrap policy. This
# catches "AccessDenied" errors before they hit CI/CD.
# ================================================================

MODULES_DIR = PROJECT_ROOT / "terraform" / "aws" / "modules"

# Map of AWS resource types (used in modules) to the IAM actions
# required to create/manage them. Each entry lists the critical
# write action(s) that must exist in bootstrap.
#
# To add a new resource:
#   1. Add the resource type + required action(s) here
#   2. Add the IAM action to the appropriate bootstrap policy
#   3. Run `pytest tests/test_terraform.py -k iam` to verify
_RESOURCE_IAM_ACTIONS: dict[str, list[str]] = {
    # ── App Runner ──
    "aws_apprunner_auto_scaling_configuration_version": ["apprunner:Create*"],
    "aws_apprunner_observability_configuration": ["apprunner:Create*"],
    "aws_apprunner_vpc_connector": ["apprunner:Create*"],
    "aws_apprunner_custom_domain_association": ["apprunner:AssociateCustomDomain"],
    # ── WAFv2 ──
    "aws_wafv2_web_acl": ["wafv2:CreateWebACL"],
    "aws_wafv2_web_acl_association": ["wafv2:AssociateWebACL"],
    "aws_wafv2_web_acl_logging_configuration": ["wafv2:PutLoggingConfiguration"],
    # ── CloudFront ──
    "aws_cloudfront_distribution": ["cloudfront:CreateDistribution"],
    "aws_cloudfront_origin_access_control": ["cloudfront:CreateOriginAccessControl"],
    "aws_cloudfront_response_headers_policy": [
        "cloudfront:CreateResponseHeadersPolicy"
    ],
    # ── ACM ──
    "aws_acm_certificate": ["acm:RequestCertificate"],
    # ── SQS ──
    "aws_sqs_queue": ["sqs:CreateQueue"],
    # ── S3 (non-module resources) ──
    "aws_s3_bucket_cors_configuration": ["s3:PutBucketCors"],
    "aws_s3_bucket_logging": ["s3:PutBucketLogging"],
    "aws_s3_bucket_ownership_controls": ["s3:PutBucketOwnershipControls"],
    # ── Lambda ──
    "aws_lambda_function": ["lambda:CreateFunction"],
    # ── DynamoDB ──
    "aws_dynamodb_table": ["dynamodb:CreateTable"],
    # ── Scheduler ──
    "aws_scheduler_schedule": ["scheduler:CreateSchedule"],
    "aws_scheduler_schedule_group": ["scheduler:CreateScheduleGroup"],
    # ── SNS ──
    "aws_sns_topic": ["sns:CreateTopic"],
    # ── GuardDuty ──
    "aws_guardduty_detector": ["guardduty:CreateDetector"],
    # ── CloudTrail ──
    "aws_cloudtrail": ["cloudtrail:CreateTrail"],
    # ── Security Hub ──
    "aws_securityhub_account": ["securityhub:EnableSecurityHub"],
    # ── Budgets ──
    "aws_budgets_budget": ["budgets:CreateBudgetAction"],
}


def _extract_all_iam_actions(content: str) -> set[str]:
    """Extract all IAM action strings from bootstrap policy HCL."""
    return set(re.findall(r'"([a-z][a-z0-9-]*:[A-Za-z*]+)"', content))


def _action_matches(required: str, granted: set[str]) -> bool:
    """Check if a required action is satisfied by the granted set.

    Supports wildcard matching: 'apprunner:Create*' in the granted
    set matches a required action of 'apprunner:CreateService'.
    Also handles the reverse: if the required action has a wildcard.
    """
    if required in granted:
        return True
    # Check if any granted wildcard covers the required action
    req_service, req_action = required.split(":", 1)
    for action in granted:
        if ":" not in action:
            continue
        svc, act = action.split(":", 1)
        if svc != req_service:
            continue
        if act.endswith("*") and req_action.startswith(act[:-1]):
            return True
        if req_action.endswith("*") and act.startswith(
            req_service + ":" + req_action[:-1]
        ):
            return True
    return False


def _find_resource_types_in_modules() -> set[str]:
    """Scan our module .tf files for AWS resource type declarations.

    Excludes .terraform/ directories which contain downloaded third-party
    module code (e.g. terraform-aws-modules/*) — those resources are
    managed internally by the upstream modules, not by our IAM policies.
    """
    types = set()
    for tf_file in MODULES_DIR.rglob("*.tf"):
        if ".terraform" in tf_file.parts:
            continue
        for m in re.finditer(r'resource\s+"(aws_\w+)"', tf_file.read_text()):
            types.add(m.group(1))
    return types


def test_bootstrap_iam_covers_all_resource_actions():
    """Bootstrap IAM policies must grant actions for every mapped resource.

    Verifies that each resource type in _RESOURCE_IAM_ACTIONS has
    its required IAM action(s) present in the bootstrap policy file.
    Fails with a clear message listing missing actions and which
    bootstrap policy to update.
    """
    content = BOOTSTRAP_MODULE.read_text()
    granted = _extract_all_iam_actions(content)

    missing = []
    for resource_type, actions in _RESOURCE_IAM_ACTIONS.items():
        for action in actions:
            if not _action_matches(action, granted):
                missing.append(f"  {resource_type} → {action}")

    assert not missing, (
        "Bootstrap IAM policies are missing actions required "
        "by module resources:\n"
        + "\n".join(missing)
        + "\n\nAdd the missing actions to the appropriate "
        "bootstrap policy in terraform/aws/bootstrap/main.tf"
    )


def test_all_module_resources_have_iam_mapping():
    """Every AWS resource type in modules must be mapped in the test.

    When a new `resource "aws_*"` is added to any module, a
    corresponding entry must be added to _RESOURCE_IAM_ACTIONS
    so the IAM coverage test can verify bootstrap permissions.

    Resources from third-party modules (e.g. terraform-aws-modules/*)
    are managed internally by those modules and excluded.
    """
    module_types = _find_resource_types_in_modules()

    # Resource types that don't need explicit IAM mapping:
    # - Generic resources managed by broader IAM statements
    # - Resources whose IAM actions are covered by wildcard grants
    exempted = {
        # EC2/VPC — covered by ec2:* wildcard block in tfc_core
        "aws_security_group",
        "aws_vpc_endpoint",
        # IAM — covered by iam:Create*/Delete* in tfc_governance
        "aws_iam_role",
        "aws_iam_role_policy",
        "aws_iam_role_policy_attachment",
        "aws_iam_policy",
        # CloudWatch — covered by logs:* block in tfc_core
        "aws_cloudwatch_log_group",
        "aws_cloudwatch_dashboard",
        # Route 53 — covered by route53:* block in tfc_core
        "aws_route53_record",
        # Config — covered by config:Put* in tfc_governance
        "aws_config_config_rule",
        "aws_config_configuration_recorder",
        "aws_config_configuration_recorder_status",
        "aws_config_delivery_channel",
        # GuardDuty features — covered by guardduty:* grant
        "aws_guardduty_detector_feature",
        # Secrets Manager — covered by sm:Create* in tfc_core
        "aws_secretsmanager_secret",
        "aws_secretsmanager_secret_version",
        "aws_secretsmanager_secret_rotation",
        # Lambda permission — covered by lambda:AddPermission
        "aws_lambda_permission",
        "aws_lambda_event_source_mapping",
        "aws_lambda_layer_version",
        # ACM validation — read-only, no extra action needed
        "aws_acm_certificate_validation",
        # SNS policy/subscription — covered by sns:* grant
        "aws_sns_topic_policy",
        "aws_sns_topic_subscription",
        # S3 sub-resources covered by s3:Put* grants
        "aws_s3_bucket",
        "aws_s3_bucket_acl",
        "aws_s3_bucket_lifecycle_configuration",
        "aws_s3_bucket_policy",
        "aws_s3_bucket_public_access_block",
        "aws_s3_bucket_server_side_encryption_configuration",
        "aws_s3_bucket_versioning",
        # CodeStar/CodeBuild/CodePipeline covered by existing
        "aws_codebuild_project",
        "aws_codepipeline",
    }

    unmapped = module_types - set(_RESOURCE_IAM_ACTIONS) - exempted
    assert not unmapped, (
        "Module resource types missing from _RESOURCE_IAM_ACTIONS "
        "and not exempted:\n"
        + "\n".join(f"  - {t}" for t in sorted(unmapped))
        + "\n\nAdd each to _RESOURCE_IAM_ACTIONS with required "
        "IAM actions, or add to the exempted set with a comment."
    )
