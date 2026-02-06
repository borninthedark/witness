# ================================================================
# Security Module - KMS + CloudTrail + Config + IAM
# ================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ================================================================
# KMS Key (shared CMK for ECR, Secrets Manager, CloudTrail)
# ================================================================

module "kms" {
  source  = "terraform-aws-modules/kms/aws"
  version = "4.2.0"

  description             = "${var.project}-${var.environment} encryption key"
  deletion_window_in_days = var.kms_deletion_window
  enable_key_rotation     = true

  aliases = ["${var.project}/${var.environment}"]

  key_administrators = [
    data.aws_caller_identity.current.arn
  ]

  key_service_roles_for_autoscaling = []

  key_statements = [
    {
      sid    = "AllowCloudTrailEncrypt"
      effect = "Allow"
      principals = [
        {
          type        = "Service"
          identifiers = ["cloudtrail.amazonaws.com"]
        }
      ]
      actions   = ["kms:GenerateDataKey*", "kms:DescribeKey"]
      resources = ["*"]
      conditions = [
        {
          test     = "StringEquals"
          variable = "aws:SourceAccount"
          values   = [data.aws_caller_identity.current.account_id]
        }
      ]
    },
    {
      sid    = "AllowCloudWatchLogsEncrypt"
      effect = "Allow"
      principals = [
        {
          type        = "Service"
          identifiers = ["logs.${data.aws_region.current.id}.amazonaws.com"]
        }
      ]
      actions = [
        "kms:Encrypt*",
        "kms:Decrypt*",
        "kms:ReEncrypt*",
        "kms:GenerateDataKey*",
        "kms:Describe*"
      ]
      resources = ["*"]
      conditions = [
        {
          test     = "ArnEquals"
          variable = "kms:EncryptionContext:aws:logs:arn"
          values   = ["arn:aws:logs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:log-group:*"]
        }
      ]
    }
  ]

  tags = var.tags
}

# ================================================================
# CloudTrail S3 Bucket
# ================================================================

module "cloudtrail_bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "5.10.0"

  bucket        = "${var.project}-${var.environment}-cloudtrail-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.environment == "dev"

  # Block all public access
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  versioning = {
    enabled = true
  }

  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        sse_algorithm     = "aws:kms"
        kms_master_key_id = module.kms.key_arn
      }
      bucket_key_enabled = true
    }
  }

  lifecycle_rule = [
    {
      id     = "transition-to-ia"
      status = "Enabled"
      transition = [
        {
          days          = 90
          storage_class = "STANDARD_IA"
        }
      ]
      expiration = {
        days = 365
      }
    }
  ]

  attach_policy = true
  policy        = data.aws_iam_policy_document.cloudtrail_bucket.json

  tags = var.tags
}

data "aws_iam_policy_document" "cloudtrail_bucket" {
  statement {
    sid    = "AWSCloudTrailAclCheck"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions   = ["s3:GetBucketAcl"]
    resources = ["arn:aws:s3:::${var.project}-${var.environment}-cloudtrail-${data.aws_caller_identity.current.account_id}"]
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  statement {
    sid    = "AWSCloudTrailWrite"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions   = ["s3:PutObject"]
    resources = ["arn:aws:s3:::${var.project}-${var.environment}-cloudtrail-${data.aws_caller_identity.current.account_id}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

# ================================================================
# CloudTrail
# ================================================================

resource "aws_cloudwatch_log_group" "cloudtrail" {
  name              = "/aws/cloudtrail/${var.project}-${var.environment}"
  retention_in_days = var.log_retention_days
  kms_key_id        = module.kms.key_arn

  tags = var.tags
}

resource "aws_iam_role" "cloudtrail_cloudwatch" {
  name = "${var.project}-${var.environment}-cloudtrail-cw"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "cloudtrail_cloudwatch" {
  name = "cloudwatch-logs"
  role = aws_iam_role.cloudtrail_cloudwatch.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
      }
    ]
  })
}

resource "aws_cloudtrail" "main" {
  name                          = "${var.project}-${var.environment}"
  s3_bucket_name                = module.cloudtrail_bucket.s3_bucket_id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true
  kms_key_id                    = module.kms.key_arn

  cloud_watch_logs_group_arn = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
  cloud_watch_logs_role_arn  = aws_iam_role.cloudtrail_cloudwatch.arn

  tags = var.tags
}

# ================================================================
# AWS Config
# ================================================================

resource "aws_config_configuration_recorder" "main" {
  count = var.enable_config ? 1 : 0

  name     = "${var.project}-${var.environment}"
  role_arn = aws_iam_role.config[0].arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }
}

resource "aws_config_delivery_channel" "main" {
  count = var.enable_config ? 1 : 0

  name           = "${var.project}-${var.environment}"
  s3_bucket_name = module.cloudtrail_bucket.s3_bucket_id
  s3_key_prefix  = "config"

  depends_on = [aws_config_configuration_recorder.main]
}

resource "aws_config_configuration_recorder_status" "main" {
  count = var.enable_config ? 1 : 0

  name       = aws_config_configuration_recorder.main[0].name
  is_enabled = true

  depends_on = [aws_config_delivery_channel.main]
}

resource "aws_iam_role" "config" {
  count = var.enable_config ? 1 : 0

  name = "${var.project}-${var.environment}-config"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "config" {
  count = var.enable_config ? 1 : 0

  role       = aws_iam_role.config[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

resource "aws_iam_role_policy" "config_s3" {
  count = var.enable_config ? 1 : 0

  name = "s3-delivery"
  role = aws_iam_role.config[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetBucketAcl"
        ]
        Resource = [
          module.cloudtrail_bucket.s3_bucket_arn,
          "${module.cloudtrail_bucket.s3_bucket_arn}/*"
        ]
      }
    ]
  })
}
