# ================================================================
# Networking Module - VPC via terraform-aws-modules/vpc/aws
# ================================================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "6.6.0"

  name = "${var.project}-${var.environment}-vpc"
  cidr = var.vpc_cidr

  azs             = var.azs
  private_subnets = var.private_subnets
  public_subnets  = var.public_subnets

  enable_nat_gateway     = true
  single_nat_gateway     = var.single_nat_gateway
  one_nat_gateway_per_az = !var.single_nat_gateway

  enable_dns_hostnames = true
  enable_dns_support   = true

  # VPC Flow Logs
  enable_flow_log                                 = true
  create_flow_log_cloudwatch_log_group            = true
  create_flow_log_cloudwatch_iam_role             = true
  flow_log_cloudwatch_log_group_retention_in_days = var.flow_log_retention_days
  flow_log_cloudwatch_log_group_kms_key_id        = var.kms_key_arn

  tags = var.tags

  private_subnet_tags = {
    "Tier" = "private"
  }

  public_subnet_tags = {
    "Tier" = "public"
  }
}
