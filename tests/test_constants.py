from __future__ import annotations

from typing import Any

from fitness.constants import (
    AZURE_104_SHARE_URL,
    MICROSOFT_TRANSCRIPT_URL,
    get_cert_metadata,
    verification_label_for_slug,
)


def test_get_cert_metadata_is_case_insensitive() -> None:
    meta_upper: dict[str, Any] = get_cert_metadata("CKA")
    meta_lower: dict[str, Any] = get_cert_metadata("cka")
    assert meta_upper == meta_lower
    assert meta_upper["issuer"] == "The Linux Foundation"


def test_verification_label_defaults_to_provider() -> None:
    label = verification_label_for_slug("ckad")
    assert label is not None and "Linux Foundation" in label
    # Fallback to issuer parameter when slug unknown
    fallback_label = verification_label_for_slug("unknown-cert", issuer="Custom Issuer")
    assert fallback_label == "Verify via Custom Issuer"


def test_aws_metadata_includes_badge_and_verification_steps() -> None:
    meta: dict[str, Any] = get_cert_metadata("aws-solutions-architect-associate")
    badge = meta.get("badge")
    assert badge is not None
    assert badge["id"] == "c4bbb094-80e3-4c9d-be13-63ee2a345f1e"
    methods = meta.get("verification_methods")
    assert methods is not None and len(methods) >= 1
    assert any(
        "cloudweb2.aws.org" in method["url"] for method in methods if "url" in method
    )


def test_ckad_metadata_includes_badge_embed() -> None:
    meta: dict[str, Any] = get_cert_metadata("ckad")
    badge = meta.get("badge")
    assert badge is not None
    assert badge["id"] == "986c4a0c-c9fb-4317-a68d-3b76956cb10a"
    assert badge["host"].startswith("https://www.credly.com")


def test_cka_metadata_includes_badge_embed() -> None:
    meta: dict[str, Any] = get_cert_metadata("cka")
    badge = meta.get("badge")
    assert badge is not None
    assert badge["id"] == "3d19b5ae-319a-4207-bfcc-e59afb5d6d0c"
    assert badge["script"].endswith("embed.js")


def test_az400_metadata_uses_microsoft_and_share_link() -> None:
    meta: dict[str, Any] = get_cert_metadata("az-400")
    assert meta["issuer"] == "Microsoft"
    assert meta["verification_url"] == MICROSOFT_TRANSCRIPT_URL


def test_az305_metadata_uses_microsoft_and_share_link() -> None:
    meta: dict[str, Any] = get_cert_metadata("az-305")
    assert meta["issuer"] == "Microsoft"
    assert meta["verification_url"] == MICROSOFT_TRANSCRIPT_URL


def test_az104_metadata_points_to_transcript() -> None:
    meta: dict[str, Any] = get_cert_metadata("az-104")
    assert meta["issuer"] == "Microsoft"
    assert meta["verification_url"] == AZURE_104_SHARE_URL


def test_terraform_associate_metadata_includes_badge_and_hashicorp() -> None:
    meta: dict[str, Any] = get_cert_metadata("terraform-associate")
    assert meta["issuer"] == "HashiCorp"
    badge = meta.get("badge")
    assert badge is not None
    assert badge["id"] == "bfcd13e0-1dd3-4110-a6e6-46162d6641c1"
