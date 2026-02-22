# ================================================================
# Production Environment - AWS App Runner
# ================================================================
# HCP Terraform VCS workflow: workspace "witness-prod"
# Working directory: terraform/aws/prod
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
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Workspace   = "witness-prod"
    }
  }
}

# ================================================================
# Security (KMS, CloudTrail, Config)
# ================================================================

module "security" {
  source = "../modules/security"

  project              = var.project
  environment          = var.environment
  kms_deletion_window  = 30
  log_retention_days   = var.log_retention_days
  enable_config        = true
  enable_guardduty     = true
  enable_security_hub  = true
  alarm_email          = var.alarm_email
  monthly_budget_limit = var.monthly_budget_limit

  tags = var.tags
}

# ================================================================
# Networking (VPC)
# ================================================================

module "networking" {
  source = "../modules/networking"

  project     = var.project
  environment = var.environment
  vpc_cidr    = var.vpc_cidr
  azs         = var.azs

  private_subnets    = var.private_subnets
  public_subnets     = var.public_subnets
  single_nat_gateway = false

  flow_log_retention_days    = var.log_retention_days
  kms_key_arn                = module.security.kms_key_arn
  enable_interface_endpoints = true

  tags = var.tags
}

# ================================================================
# App Runner (ECR + Secrets Manager + App Runner)
# ================================================================

module "app_runner" {
  source = "../modules/app-runner"

  project     = var.project
  environment = var.environment
  kms_key_arn = module.security.kms_key_arn

  image_tag      = var.image_tag
  container_port = var.container_port
  log_level      = var.log_level
  secret_key     = var.secret_key
  database_url   = var.database_url
  admin_username = var.admin_username
  admin_password = var.admin_password
  nasa_api_key   = var.nasa_api_key

  instance_cpu    = var.instance_cpu
  instance_memory = var.instance_memory
  auto_deploy     = var.auto_deploy

  min_size        = var.min_size
  max_size        = var.max_size
  max_concurrency = var.max_concurrency

  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids

  dynamodb_table_name = var.enable_data_ingest ? module.data_ingest[0].dynamodb_table_name : ""
  dynamodb_table_arn  = var.enable_data_ingest ? module.data_ingest[0].dynamodb_table_arn : ""

  media_bucket_name = var.enable_media ? module.media[0].media_bucket_name : ""
  media_bucket_arn  = var.enable_media ? module.media[0].media_bucket_arn : ""
  media_cdn_domain  = var.enable_media ? module.media[0].media_cdn_domain : ""

  enable_waf  = true
  enable_xray = true

  tags = var.tags
}

# ================================================================
# DNS (Route 53 + App Runner Custom Domain)
# ================================================================

module "dns" {
  source = "../modules/dns"

  domain_name            = var.domain_name
  subdomain              = "staging"
  hosted_zone_id         = var.hosted_zone_id
  app_runner_service_arn = module.app_runner.service_arn
}

# ================================================================
# Observability (CloudWatch)
# ================================================================

module "observability" {
  source = "../modules/observability"

  project     = var.project
  environment = var.environment
  aws_region  = var.aws_region
  kms_key_arn = module.security.kms_key_arn

  log_retention_days   = var.log_retention_days
  error_threshold      = 5
  latency_threshold_ms = 3000
  alarm_sns_topic_arn  = module.security.sns_topic_arn

  tags = var.tags
}

# ================================================================
# Media CDN (S3 + CloudFront)
# ================================================================

module "media" {
  source = "../modules/media"
  count  = var.enable_media ? 1 : 0

  project        = var.project
  environment    = var.environment
  domain_name    = var.domain_name
  hosted_zone_id = var.hosted_zone_id
  app_runner_url = replace(module.app_runner.service_url, "https://", "")

  tags = var.tags
}

# ================================================================
# Data Ingest (DynamoDB + Lambda + EventBridge)
# ================================================================

module "data_ingest" {
  source = "../modules/data-ingest"
  count  = var.enable_data_ingest ? 1 : 0

  project     = var.project
  environment = var.environment
  kms_key_arn = module.security.kms_key_arn

  nasa_api_key   = var.nasa_api_key
  nist_api_key   = var.nist_api_key
  nasa_schedule  = "rate(6 hours)"
  nist_schedule  = "rate(4 hours)"
  space_schedule = "rate(1 hour)"

  enable_point_in_time_recovery = true
  enable_embed_sync             = var.enable_embed_sync
  azure_openai_endpoint         = var.azure_openai_endpoint
  azure_openai_key              = var.azure_openai_key
  azure_search_endpoint         = var.azure_search_endpoint
  azure_search_key              = var.azure_search_key
  log_retention_days            = var.log_retention_days

  tags = var.tags
}

# ================================================================
# CodePipeline (optional)
# ================================================================

module "codepipeline" {
  source = "../modules/codepipeline"
  count  = var.enable_codepipeline ? 1 : 0

  project     = var.project
  environment = var.environment
  kms_key_arn = module.security.kms_key_arn

  terraform_version       = "1.14.2"
  repository_id           = var.repository_id
  branch_name             = "main"
  codestar_connection_arn = var.codestar_connection_arn

  tags = var.tags
}
