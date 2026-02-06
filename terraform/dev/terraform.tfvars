# ================================================================
# Dev Environment Values
# ================================================================
# HCP Terraform workspace: witness-dev
# Sensitive vars set in HCP Terraform workspace variables:
#   - secret_key
# ================================================================

project     = "witness"
environment = "dev"
aws_region  = "us-east-1"

# Networking
vpc_cidr        = "10.0.0.0/16"
azs             = ["us-east-1a", "us-east-1b"]
private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

# App Runner
image_tag       = "dev"
container_port  = 8000
log_level       = "DEBUG"
instance_cpu    = "512"
instance_memory = "1024"
auto_deploy     = true
min_size        = 1
max_size        = 2
max_concurrency = 100

# Observability
log_retention_days = 30

# CodePipeline (disabled - HCP Terraform VCS handles this)
enable_codepipeline = false

tags = {
  CostCenter = "development"
}
