# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Instead, please report them privately via [GitHub Security Advisories](https://github.com/borninthedark/witness/security/advisories/new).

### What to include

- Description of the vulnerability
- Steps to reproduce
- Affected component (application code, Terraform, container, CI/CD)
- Severity assessment (if known)

### What to expect

- **Acknowledgement** within 48 hours
- **Status update** within 7 days with an initial assessment
- **Fix timeline** depends on severity:
  - Critical/High: patch targeted within 7 days
  - Medium/Low: addressed in the next regular release
- You will be credited in the fix commit unless you prefer to remain anonymous

### Scope

The following are in scope:

- Application code (`fitness/`)
- Terraform infrastructure (`terraform/`)
- CI/CD workflows (`.github/workflows/`)
- Container configuration (`container/Dockerfile`)
- Dependencies listed in `pyproject.toml`

### Out of scope

- Denial of service against the live site
- Social engineering
- Findings from automated scanners without a demonstrated impact

## Security Controls

This project implements the following security measures:

- **WAFv2** with AWS managed rule groups (OWASP Top 10, SQLi, known bad inputs)
- **GuardDuty** threat detection with S3 data event monitoring
- **CloudTrail** API audit logging with KMS-encrypted S3 storage
- **Security Hub** compliance dashboard (prod)
- **AWS Config** managed rules for continuous compliance (prod)
- **KMS** customer-managed keys for all at-rest encryption
- **CSP/HSTS** headers with nonce support
- **CSRF** double-submit cookie protection
- **Rate limiting** via slowapi on sensitive endpoints
- **Trivy, Checkov, tfsec** scanning in CI
- **Cosign** container image signing
