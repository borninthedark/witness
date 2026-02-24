"""Certification metadata configuration for the Witness platform."""

from __future__ import annotations

from typing import Any

# ==========================================
# Certification Provider URLs
# ==========================================

LINUX_FOUNDATION_VERIFY_URL = (
    "https://training.linuxfoundation.org/certification/verify/"
)
AWS_VERIFY_URL = "https://cloudweb2.aws.org/Certifications/Search/"
AZURE_VERIFY_URL = "https://learn.microsoft.com/api/credentials/share/"
MICROSOFT_TRANSCRIPT_URL = (
    "https://learn.microsoft.com/en-us/users/borninthedark/transcript/"
    "7om9fqk41zlw36d?tab=credentials-tab"
)
AZURE_104_SHARE_URL = (
    "https://learn.microsoft.com/api/credentials/share/en-us/"
    "borninthedark/E2D4DED07F2F31D8?sharingId=DD5C0268D58AF2D"
)
CREDLY_BADGE_HOST = "https://www.credly.com"
CREDLY_BADGE_EMBED_SCRIPT = "https://cdn.credly.com/assets/utilities/embed.js"


# ==========================================
# Certification Metadata Registry
# ==========================================
#
# Structure:
# slug -> {
#     "title": str,           # Display name of the certification
#     "issuer": str,          # Organization that issued the cert
#     "verification_url": str # (optional) External verification URL
# }
#
# If verification_url is omitted, the system will use the internal
# verification page at /v/{slug}

CertMetadata = dict[str, Any]


CERT_METADATA: dict[str, CertMetadata] = {
    # ==========================================
    # Linux Foundation Certifications
    # ==========================================
    "ckad": {
        "title": "Certified Kubernetes Application Developer (CKAD)",
        "issuer": "The Linux Foundation",
        "verification_url": LINUX_FOUNDATION_VERIFY_URL,
        "badge": {
            "id": "986c4a0c-c9fb-4317-a68d-3b76956cb10a",
            "host": CREDLY_BADGE_HOST,
            "script": CREDLY_BADGE_EMBED_SCRIPT,
            "iframe_width": 150,
            "iframe_height": 270,
            "url": (
                f"{CREDLY_BADGE_HOST}/badges/"
                "986c4a0c-c9fb-4317-a68d-3b76956cb10a/public_url"
            ),
        },
    },
    "cka": {
        "title": "Certified Kubernetes Administrator (CKA)",
        "issuer": "The Linux Foundation",
        "verification_url": LINUX_FOUNDATION_VERIFY_URL,
        "badge": {
            "id": "3d19b5ae-319a-4207-bfcc-e59afb5d6d0c",
            "host": CREDLY_BADGE_HOST,
            "script": CREDLY_BADGE_EMBED_SCRIPT,
            "iframe_width": 150,
            "iframe_height": 270,
            "url": (
                f"{CREDLY_BADGE_HOST}/badges/"
                "3d19b5ae-319a-4207-bfcc-e59afb5d6d0c/public_url"
            ),
        },
    },
    "lfcs": {
        "title": "Linux Foundation Certified System Administrator (LFCS)",
        "issuer": "The Linux Foundation",
        "verification_url": LINUX_FOUNDATION_VERIFY_URL,
    },
    # ==========================================
    # AWS Certifications
    # ==========================================
    "aws-cloud-practitioner": {
        "title": "AWS Certified Cloud Practitioner",
        "issuer": "Amazon Web Services",
        "verification_url": AWS_VERIFY_URL,
        "assertion_url": (
            f"{CREDLY_BADGE_HOST}/badges/"
            "0c20975e-b9fd-4998-bc64-0a37e034fab2/public_url"
        ),
        "badge": {
            "id": "0c20975e-b9fd-4998-bc64-0a37e034fab2",
            "host": CREDLY_BADGE_HOST,
            "script": CREDLY_BADGE_EMBED_SCRIPT,
            "iframe_width": 150,
            "iframe_height": 270,
            "url": (
                f"{CREDLY_BADGE_HOST}/badges/"
                "0c20975e-b9fd-4998-bc64-0a37e034fab2/public_url"
            ),
        },
        "verification_methods": [
            {
                "label": "AWS Certification Verification",
                "description": (
                    "Open the AWS Certification Verification portal and search for "
                    "this certification to confirm it is active."
                ),
                "url": AWS_VERIFY_URL,
                "cta": "Open AWS Verification Portal",
            },
            {
                "label": "Credly Digital Badge",
                "description": (
                    "AWS Training & Certification also publishes this badge to Credly "
                    "with signature and issuance metadata."
                ),
                "url": (
                    f"{CREDLY_BADGE_HOST}/badges/"
                    "0c20975e-b9fd-4998-bc64-0a37e034fab2/public_url"
                ),
                "cta": "View on Credly",
            },
        ],
    },
    "aws-solutions-architect-associate": {
        "title": "AWS Certified Solutions Architect - Associate",
        "issuer": "Amazon Web Services",
        "verification_url": AWS_VERIFY_URL,
        "assertion_url": (
            f"{CREDLY_BADGE_HOST}/badges/"
            "c4bbb094-80e3-4c9d-be13-63ee2a345f1e/public_url"
        ),
        "badge": {
            "id": "c4bbb094-80e3-4c9d-be13-63ee2a345f1e",
            "host": CREDLY_BADGE_HOST,
            "script": CREDLY_BADGE_EMBED_SCRIPT,
            "iframe_width": 150,
            "iframe_height": 270,
            "url": (
                f"{CREDLY_BADGE_HOST}/badges/"
                "c4bbb094-80e3-4c9d-be13-63ee2a345f1e/public_url"
            ),
        },
        "verification_methods": [
            {
                "label": "AWS Certification Verification",
                "description": (
                    "Open the AWS Certification Verification portal and search for "
                    "Credential ID AWS-CSA-PL-001 to confirm the certification."
                ),
                "url": AWS_VERIFY_URL,
                "cta": "Open AWS Verification Portal",
                "reference": "Credential ID: AWS-CSA-PL-001",
            },
            {
                "label": "Credly Digital Badge",
                "description": (
                    "AWS Training & Certification also publishes this badge to Credly "
                    "with signature and issuance metadata."
                ),
                "url": (
                    f"{CREDLY_BADGE_HOST}/badges/"
                    "c4bbb094-80e3-4c9d-be13-63ee2a345f1e/public_url"
                ),
                "cta": "View on Credly",
            },
        ],
    },
    # ==========================================
    # Azure Certifications
    # ==========================================
    "az-104": {
        "title": "Microsoft Certified: Azure Administrator Associate",
        "issuer": "Microsoft",
        "verification_url": AZURE_104_SHARE_URL,
    },
    "az-305": {
        "title": "Microsoft Certified: Azure Solutions Architect Expert",
        "issuer": "Microsoft",
        "verification_url": MICROSOFT_TRANSCRIPT_URL,
    },
    "az-400": {
        "title": "Microsoft Certified: DevOps Engineer Expert",
        "issuer": "Microsoft",
        "verification_url": MICROSOFT_TRANSCRIPT_URL,
    },
    # ==========================================
    # HashiCorp Certifications (inactive)
    # ==========================================
    "terraform-associate": {
        "title": "HashiCorp Certified: Terraform Associate",
        "issuer": "HashiCorp",
        "verification_url": (
            f"{CREDLY_BADGE_HOST}/badges/"
            "bfcd13e0-1dd3-4110-a6e6-46162d6641c1/public_url"
        ),
        "assertion_url": (
            f"{CREDLY_BADGE_HOST}/badges/"
            "bfcd13e0-1dd3-4110-a6e6-46162d6641c1/public_url"
        ),
        "badge": {
            "id": "bfcd13e0-1dd3-4110-a6e6-46162d6641c1",
            "host": CREDLY_BADGE_HOST,
            "script": CREDLY_BADGE_EMBED_SCRIPT,
            "iframe_width": 150,
            "iframe_height": 270,
            "url": (
                f"{CREDLY_BADGE_HOST}/badges/"
                "bfcd13e0-1dd3-4110-a6e6-46162d6641c1/public_url"
            ),
        },
    },
}

INACTIVE_CERT_SLUGS: set[str] = {"terraform-associate", "cka"}

# Certs that should be visible with expired status on startup sync
EXPIRED_CERT_SLUGS: set[str] = {"terraform-associate", "cka"}

VERIFICATION_LABELS: dict[str, str] = {
    "The Linux Foundation": "The Linux Foundation Certification Verification Tool",
    "Amazon Web Services": "Verify via AWS Certification Portal",
    "Microsoft": "Microsoft Learn Credential Share",
}


# ==========================================
# Helper Functions
# ==========================================


def get_cert_metadata(slug: str | None) -> CertMetadata:
    """Return metadata for a slug, falling back to case-insensitive lookups."""
    if not slug:
        return {}
    slug_lower = slug.lower()
    if slug_lower in CERT_METADATA:
        return CERT_METADATA[slug_lower]
    return CERT_METADATA.get(slug, {})


def get_cert_providers() -> list[str]:
    """Get list of unique certification providers/issuers."""
    return sorted({meta["issuer"] for meta in CERT_METADATA.values()})


def get_certs_by_provider(provider: str) -> list[str]:
    """Get list of cert slugs for a specific provider."""
    return [slug for slug, meta in CERT_METADATA.items() if meta["issuer"] == provider]


def has_external_verification(slug: str) -> bool:
    """Check if a certification has external verification URL."""
    metadata = get_cert_metadata(slug)
    return bool(metadata.get("verification_url"))


def verification_label_for_slug(slug: str, issuer: str | None = None) -> str | None:
    """Resolve a human-friendly verification label for the slug/issuer."""
    metadata = get_cert_metadata(slug)
    provider = metadata.get("issuer") or issuer
    if not provider:
        return None
    return VERIFICATION_LABELS.get(provider, f"Verify via {provider}")
