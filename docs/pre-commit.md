# Pre-commit Hooks

Witness uses [pre-commit](https://pre-commit.com/) to enforce code quality **before**
changes reach the repository. The [shift-left](https://en.wikipedia.org/wiki/Shift-left_testing) strategy catches formatting, linting,
security, and infrastructure issues at commit time so CI focuses on integration testing
and deployment.

## Setup

```bash
uv run pre-commit install              # enable hooks
uv run pre-commit run --all-files      # run everything once
```

## Hook Reference

### File Hygiene (pre-commit-hooks v4.5.0)

| Hook | Purpose |
|------|---------|
| `trailing-whitespace` | Strip trailing whitespace |
| `end-of-file-fixer` | Ensure files end with a newline |
| `check-yaml` | Validate YAML syntax (multi-document allowed) |
| `check-json` | Validate JSON syntax |
| `check-toml` | Validate TOML syntax |
| `check-added-large-files` | Block files > 1 MB |
| `check-merge-conflict` | Detect unresolved merge markers |
| `check-case-conflict` | Detect filenames that differ only by case |
| `detect-private-key` | Block accidental key commits |
| `mixed-line-ending` | Normalize to LF line endings |

### Python Formatting + Linting

| Hook | Version | Notes |
|------|---------|-------|
| [ruff](https://docs.astral.sh/ruff/) | 0.14.4 | Lint (`--fix`) + format + import sorting; config in `pyproject.toml` |
| [pylint](https://pylint.readthedocs.io/) | 3.2.6 | Errors only (`--errors-only`), config in `.pylintrc` |
| [mypy](https://mypy.readthedocs.io/) | 1.8.0 | Type-checks `fitness/constants.py`; missing imports ignored |

### Security

| Hook | Version | Notes |
|------|---------|-------|
| [bandit](https://bandit.readthedocs.io/) | 1.7.6 | Scans `fitness/`, `tools/`, `tests/`; low-low severity; config in `pyproject.toml` |

### Markup and Shell

| Hook | Version | Notes |
|------|---------|-------|
| [yamllint](https://yamllint.readthedocs.io/) | 1.33.0 | 120-char line warning, document-start disabled |
| [shellcheck](https://www.shellcheck.net/) | 0.10.0.1 | Shell script linting |
| [markdownlint](https://github.com/igorshubovych/markdownlint-cli) | 0.41.0 | Config in `.markdownlint.yml` |

### Terraform (pre-commit-terraform v1.96.3)

| Hook | Notes |
|------|-------|
| `terraform_fmt` | Canonical formatting for all `.tf` files |
| `terraform_validate` | Syntax validation (excludes `dev/`, `prod/`, `bootstrap/` roots) |
| `terraform_tflint` | Naming conventions, deprecated interpolation, unused declarations |
| `terraform_checkov` | Checkov security scan; config in `.checkov.yml` (shared with CI) |

### Custom Local Hooks

| Hook | Trigger | Purpose |
|------|---------|---------|
| `jsonnet-validate` | `deploy/jsonnet/*.jsonnet` | Validate Jsonnet templates |
| `security-reports` | All commits | Generate security audit reports via `tools/generate-security-reports.py` |
| `check-dry` | Python files | DRY enforcement scoped to `fitness/` (functions-only mode) |
| `update-readme` | `docs/**/*.md`, `tests/README.md`, `tools/update_readme.py`, `coverage.json` | Regenerate `README.md` from template |
| `pytest` | Python files | Run test suite (no coverage, strict markers) |

## Design Decisions

- **Shift left:** Lint, format, security scan, and Checkov IaC analysis at commit time.
  CI runs integration tests and deployment only, avoiding duplicate checks.
- **Checkov shared config:** `.checkov.yml` is used by both the pre-commit hook and
  GitHub Actions (`worf.yml`), keeping skip lists consistent across local and CI.
- **DRY scoped to `fitness/`:** Test files have natural duplication (fixtures, assertions)
  that would trigger false positives. The `--path fitness` flag excludes tests.
- **`unset VIRTUAL_ENV`:** Local hooks that invoke `uv run` unset this variable to
  suppress environment mismatch warnings when pre-commit runs in its own venv.
- **Terraform validate excludes roots:** Environment roots (`dev/`, `prod/`, `bootstrap/`)
  require backend init and are validated in CI instead.

## Related Config Files

| File | Purpose |
|------|---------|
| `.checkov.yml` | Checkov skip list and framework config (shared with CI) |
| `.pylintrc` | Pylint config |
| `.markdownlint.yml` | Markdownlint rules |
| `pyproject.toml` | Ruff and Bandit config (`[tool.ruff]`, `[tool.bandit]` sections) |
