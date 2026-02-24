# ================================================================
# App Runner Module - ECR + Secrets Manager + App Runner
# ================================================================

data "aws_region" "current" {}

# ================================================================
# ECR Repository
# ================================================================

module "ecr" {
  source  = "terraform-aws-modules/ecr/aws"
  version = "3.2.0"

  repository_name = "${var.project}-${var.environment}"

  repository_image_tag_mutability = "MUTABLE"
  repository_encryption_type      = "KMS"
  repository_kms_key              = var.kms_key_arn

  repository_image_scan_on_push = true

  repository_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Remove untagged after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      }
    ]
  })

  tags = var.tags
}

# ================================================================
# Secrets Manager
# ================================================================

resource "aws_secretsmanager_secret" "app" {
  name        = "${var.project}/${var.environment}/app"
  description = "Application secrets for ${var.project} ${var.environment}"
  kms_key_id  = var.kms_key_arn

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    SECRET_KEY   = var.secret_key
    DATABASE_URL = var.database_url
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# ================================================================
# Secrets Manager Rotation Lambda
# ================================================================

data "archive_file" "rotate_secret" {
  type        = "zip"
  source_dir  = "${path.module}/../../../../lambda/functions/rotate_secret"
  output_path = "${path.module}/../../../../.build/lambda/rotate_secret.zip"
}

resource "aws_cloudwatch_log_group" "rotate_secret" {
  name              = "/aws/lambda/${var.project}-${var.environment}-rotate-secret"
  retention_in_days = 365
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

resource "aws_sqs_queue" "rotate_secret_dlq" {
  name                              = "${var.project}-${var.environment}-rotate-secret-dlq"
  message_retention_seconds         = 1209600
  kms_master_key_id                 = var.kms_key_arn
  kms_data_key_reuse_period_seconds = 300

  tags = var.tags
}

resource "aws_iam_role" "rotate_secret" {
  name = "${var.project}-${var.environment}-rotate-secret"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "rotate_secret_basic" {
  role       = aws_iam_role.rotate_secret.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "rotate_secret" {
  name = "secrets-rotation"
  role = aws_iam_role.rotate_secret.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:DescribeSecret",
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecretVersionStage",
        ]
        Resource = [aws_secretsmanager_secret.app.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetRandomPassword"]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
        ]
        Resource = [var.kms_key_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = [aws_sqs_queue.rotate_secret_dlq.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
        ]
        Resource = ["*"]
      },
    ]
  })
}

resource "aws_lambda_function" "rotate_secret" {
  function_name = "${var.project}-${var.environment}-rotate-secret"
  description   = "Rotate application secrets"
  role          = aws_iam_role.rotate_secret.arn

  filename         = data.archive_file.rotate_secret.output_path
  source_code_hash = data.archive_file.rotate_secret.output_base64sha256
  handler          = "handler.lambda_handler"
  runtime          = "python3.13"
  architectures    = ["arm64"]
  timeout          = 60

  kms_key_arn                    = var.kms_key_arn
  reserved_concurrent_executions = 1

  tracing_config {
    mode = "Active"
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.rotate_secret_dlq.arn
  }

  environment {
    variables = {
      ENVIRONMENT = var.environment
    }
  }

  depends_on = [aws_cloudwatch_log_group.rotate_secret]

  tags = var.tags
}

resource "aws_lambda_permission" "secrets_manager" {
  statement_id  = "AllowSecretsManagerInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rotate_secret.function_name
  principal     = "secretsmanager.amazonaws.com"
  source_arn    = aws_secretsmanager_secret.app.arn
}

resource "aws_secretsmanager_secret_rotation" "app" {
  secret_id           = aws_secretsmanager_secret.app.id
  rotation_lambda_arn = aws_lambda_function.rotate_secret.arn

  rotation_rules {
    automatically_after_days = 45
  }
}

# ================================================================
# App Runner IAM - Access Role (ECR pull)
# ================================================================

resource "aws_iam_role" "apprunner_access" {
  name = "${var.project}-${var.environment}-apprunner-access"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr" {
  role       = aws_iam_role.apprunner_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# ================================================================
# App Runner IAM - Instance Role (runtime)
# ================================================================

resource "aws_iam_role" "apprunner_instance" {
  name = "${var.project}-${var.environment}-apprunner-instance"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "apprunner_secrets" {
  name = "secrets-access"
  role = aws_iam_role.apprunner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [aws_secretsmanager_secret.app.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = [var.kms_key_arn]
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${data.aws_region.current.id}.amazonaws.com"
          }
        }
      }
    ]
  })
}

# ================================================================
# App Runner IAM - DynamoDB Read (conditional)
# ================================================================

resource "aws_iam_role_policy" "apprunner_dynamodb" {
  count = var.enable_data_ingest ? 1 : 0

  name = "dynamodb-read"
  role = aws_iam_role.apprunner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:BatchGetItem",
        ]
        Resource = [
          var.dynamodb_table_arn,
          "${var.dynamodb_table_arn}/index/*",
        ]
      }
    ]
  })
}

# ================================================================
# App Runner IAM - S3 Media Upload (conditional)
# ================================================================

# Least-privilege S3 policy for App Runner media uploads:
# - PutObject + GetObject scoped to exact bucket ARN (object-level)
# - ListBucket scoped to exact bucket ARN (bucket-level)
# - No DeleteObject — media deletion handled via lifecycle/admin console only
# - No wildcard resources — prevents lateral access to other S3 buckets
resource "aws_iam_role_policy" "apprunner_media_s3" {
  count = var.enable_media ? 1 : 0

  name = "media-s3-upload"
  role = aws_iam_role.apprunner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
        ]
        Resource = ["${var.media_bucket_arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [var.media_bucket_arn]
      },
    ]
  })
}

# ================================================================
# App Runner VPC Connector
# ================================================================

resource "aws_apprunner_vpc_connector" "main" {
  count = length(var.private_subnet_ids) > 0 ? 1 : 0

  vpc_connector_name = "${var.project}-${var.environment}"
  subnets            = var.private_subnet_ids
  security_groups    = [aws_security_group.apprunner[0].id]

  tags = var.tags
}

# checkov:skip=CKV2_AWS_5: SG attached to App Runner via VPC connector resource
resource "aws_security_group" "apprunner" {
  count = length(var.private_subnet_ids) > 0 ? 1 : 0

  name        = "${var.project}-${var.environment}-apprunner"
  description = "App Runner VPC connector"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS to AWS services and external APIs"
  }

  egress {
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "DNS resolution"
  }

  egress {
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "DNS resolution (TCP fallback)"
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-apprunner"
  })
}

# ================================================================
# App Runner Service
# ================================================================

module "app_runner" {
  source  = "terraform-aws-modules/app-runner/aws"
  version = "1.2.2"

  service_name = "${var.project}-${var.environment}"

  # ECR source
  source_configuration = {
    authentication_configuration = {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }
    image_repository = {
      image_identifier      = "${module.ecr.repository_url}:${var.image_tag}"
      image_repository_type = "ECR"
      image_configuration = {
        port = tostring(var.container_port)
        runtime_environment_variables = merge(
          {
            ENVIRONMENT      = var.environment == "dev" ? "development" : "production"
            LOG_LEVEL        = var.log_level
            PYTHONUNBUFFERED = "1"
            DATABASE_URL     = var.database_url
            SECRET_KEY       = var.secret_key
            ADMIN_USERNAME   = var.admin_username
            ADMIN_PASSWORD   = var.admin_password
          },
          var.nasa_api_key != "" ? { NASA_API_KEY = var.nasa_api_key } : {},
          var.dynamodb_table_name != "" ? {
            USE_DATA_STORE      = "true"
            DYNAMODB_TABLE_NAME = var.dynamodb_table_name
          } : {},
          var.media_bucket_name != "" ? {
            MEDIA_BUCKET_NAME = var.media_bucket_name
            MEDIA_CDN_DOMAIN  = var.media_cdn_domain
          } : {},
        )
      }
    }
    auto_deployments_enabled = var.auto_deploy
  }

  instance_configuration = {
    cpu               = var.instance_cpu
    memory            = var.instance_memory
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  health_check_configuration = {
    protocol            = "HTTP"
    path                = "/healthz"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.main.arn

  observability_configuration = var.enable_xray ? {
    observability_configuration_arn = aws_apprunner_observability_configuration.main[0].arn
    observability_enabled           = true
  } : null

  network_configuration = {
    egress_configuration = length(var.private_subnet_ids) > 0 ? {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.main[0].arn
    } : null

    ingress_configuration = {
      is_publicly_accessible = true
    }
  }

  tags = var.tags
}

# ================================================================
# Auto Scaling Configuration
# ================================================================

resource "aws_apprunner_auto_scaling_configuration_version" "main" {
  auto_scaling_configuration_name = "${var.project}-${var.environment}"

  max_concurrency = var.max_concurrency
  max_size        = var.max_size
  min_size        = var.min_size

  tags = var.tags
}

# ================================================================
# X-Ray Observability
# ================================================================

resource "aws_apprunner_observability_configuration" "main" {
  count = var.enable_xray ? 1 : 0

  observability_configuration_name = "${var.project}-${var.environment}"

  trace_configuration {
    vendor = "AWSXRAY"
  }

  tags = var.tags
}

# ================================================================
# WAFv2 Web ACL
# ================================================================

resource "aws_wafv2_web_acl" "main" {
  count = var.enable_waf ? 1 : 0

  name  = "${var.project}-${var.environment}-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "aws-common-rules"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-${var.environment}-common-rules"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-known-bad-inputs"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-${var.environment}-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-sqli"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-${var.environment}-sqli"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project}-${var.environment}-waf"
    sampled_requests_enabled   = true
  }

  tags = var.tags
}

resource "aws_wafv2_web_acl_association" "main" {
  count = var.enable_waf ? 1 : 0

  resource_arn = module.app_runner.service_arn
  web_acl_arn  = aws_wafv2_web_acl.main[0].arn
}

resource "aws_cloudwatch_log_group" "waf" {
  count = var.enable_waf ? 1 : 0

  name              = "aws-waf-logs-${var.project}-${var.environment}"
  retention_in_days = 365
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

resource "aws_wafv2_web_acl_logging_configuration" "main" {
  count = var.enable_waf ? 1 : 0

  log_destination_configs = [aws_cloudwatch_log_group.waf[0].arn]
  resource_arn            = aws_wafv2_web_acl.main[0].arn
}
