# ================================================================
# Bootstrap Module Provider Requirements
# ================================================================
# Local state only — this is NOT managed by HCP Terraform.
# Run once locally with temporary AWS credentials.
# ================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.28.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Purpose   = "hcp-terraform-oidc-bootstrap"
    }
  }
}
