# ================================================================
# Production Environment Values
# ================================================================
# HCP Terraform workspace: witness-prod
# Sensitive vars set in HCP Terraform workspace variables:
#   - secret_key
#   - anthropic_api_key (optional — enables Captain's Log + Astrometrics AI)
#   - nasa_api_key      (optional — DEMO_KEY used when unset)
# ================================================================

project     = "witness"
environment = "prod"
aws_region  = "us-east-1"

# Networking
vpc_cidr        = "10.0.0.0/16"
azs             = ["us-east-1a", "us-east-1b"]
private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

# App Runner
image_tag       = "latest"
container_port  = 8000
log_level       = "INFO"
instance_cpu    = "1024"
instance_memory = "2048"
auto_deploy     = false
min_size        = 2
max_size        = 5
max_concurrency = 100

# Observability (longer retention for production)
log_retention_days = 90

# CodePipeline (disabled - HCP Terraform VCS handles this)
enable_codepipeline = false

tags = {
  CostCenter  = "production"
  Criticality = "high"
}
