# ================================================================
# Data Ingest Module — DynamoDB + Lambda + EventBridge
# ================================================================
# Decouples external API data ingestion from request handling.
# Lambda functions run on schedules to fetch NASA, NIST, and
# space data into a single-table DynamoDB store.
# ================================================================

data "aws_caller_identity" "current" {}

locals {
  table_name      = "${var.project}-${var.environment}-data-store"
  function_prefix = "${var.project}-${var.environment}"

  lambda_functions = {
    ingest_nasa = {
      handler     = "handler.lambda_handler"
      timeout     = 120
      description = "Ingest NASA APOD, NEO, Exoplanet, Mars Rover data"
      schedule    = var.nasa_schedule
      environment = {
        DYNAMODB_TABLE = local.table_name
        NASA_API_KEY   = var.nasa_api_key
        ENVIRONMENT    = var.environment
      }
    }
    ingest_nist = {
      handler     = "handler.lambda_handler"
      timeout     = 120
      description = "Ingest NIST NVD CVE data"
      schedule    = var.nist_schedule
      environment = {
        DYNAMODB_TABLE = local.table_name
        NIST_API_KEY   = var.nist_api_key
        ENVIRONMENT    = var.environment
      }
    }
    ingest_space = {
      handler     = "handler.lambda_handler"
      timeout     = 120
      description = "Ingest CelesTrak TLE and NOAA Space Weather"
      schedule    = var.space_schedule
      environment = {
        DYNAMODB_TABLE = local.table_name
        ENVIRONMENT    = var.environment
      }
    }
  }
}

# ================================================================
# DynamoDB Table (single-table design)
# ================================================================

resource "aws_dynamodb_table" "data_store" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "source"
  range_key    = "sort_key"

  attribute {
    name = "source"
    type = "S"
  }

  attribute {
    name = "sort_key"
    type = "S"
  }

  attribute {
    name = "data_type"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  # GSI1: Cross-source time-range queries
  global_secondary_index {
    name            = "GSI1-DataType-Timestamp"
    hash_key        = "data_type"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # TTL for auto-cleanup
  ttl {
    attribute_name = "expiry_epoch"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  # Enable DynamoDB Streams for embed-sync Lambda
  stream_enabled   = var.enable_embed_sync
  stream_view_type = var.enable_embed_sync ? "NEW_AND_OLD_IMAGES" : null

  tags = merge(var.tags, {
    Name = local.table_name
  })
}

# ================================================================
# SQS Dead Letter Queue (shared by all Lambda functions)
# ================================================================

resource "aws_sqs_queue" "lambda_dlq" {
  name                              = "${local.function_prefix}-lambda-dlq"
  message_retention_seconds         = 1209600 # 14 days
  kms_master_key_id                 = var.kms_key_arn
  kms_data_key_reuse_period_seconds = 300

  tags = var.tags
}

# ================================================================
# Lambda Execution Role (shared)
# ================================================================

resource "aws_iam_role" "lambda_exec" {
  name = "${local.function_prefix}-lambda-exec"

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

resource "aws_iam_role_policy" "lambda_dynamo" {
  name = "dynamodb-access"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBWrite"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
        ]
        Resource = [
          aws_dynamodb_table.data_store.arn,
          "${aws_dynamodb_table.data_store.arn}/index/*",
        ]
      },
      {
        Sid    = "KMSDecrypt"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
        ]
        Resource = [var.kms_key_arn]
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_xray" {
  name = "xray-tracing"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
        ]
        Resource = ["*"]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_dlq" {
  name = "dlq-send"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = [aws_sqs_queue.lambda_dlq.arn]
      }
    ]
  })
}

# ================================================================
# CloudWatch Log Groups (one per function)
# ================================================================

resource "aws_cloudwatch_log_group" "lambda" {
  for_each = local.lambda_functions

  name              = "/aws/lambda/${local.function_prefix}-${each.key}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

# ================================================================
# Lambda Functions
# ================================================================

data "archive_file" "shared" {
  type        = "zip"
  source_dir  = "${path.module}/../../../../lambda/shared"
  output_path = "${path.module}/../../../../.build/lambda/shared.zip"
}

resource "aws_lambda_layer_version" "shared" {
  layer_name          = "${local.function_prefix}-shared"
  filename            = data.archive_file.shared.output_path
  source_code_hash    = data.archive_file.shared.output_base64sha256
  compatible_runtimes = [var.lambda_runtime]

  compatible_architectures = [var.lambda_architecture]
}

data "archive_file" "functions" {
  for_each = local.lambda_functions

  type        = "zip"
  source_dir  = "${path.module}/../../../../lambda/functions/${each.key}"
  output_path = "${path.module}/../../../../.build/lambda/${each.key}.zip"
}

resource "aws_lambda_function" "ingest" {
  for_each = local.lambda_functions

  function_name = "${local.function_prefix}-${each.key}"
  description   = each.value.description
  role          = aws_iam_role.lambda_exec.arn

  filename         = data.archive_file.functions[each.key].output_path
  source_code_hash = data.archive_file.functions[each.key].output_base64sha256
  handler          = each.value.handler
  runtime          = var.lambda_runtime
  architectures    = [var.lambda_architecture]
  timeout          = each.value.timeout
  memory_size      = var.lambda_memory_mb

  reserved_concurrent_executions = var.lambda_reserved_concurrency
  kms_key_arn                    = var.kms_key_arn

  layers = [aws_lambda_layer_version.shared.arn]

  tracing_config {
    mode = "Active"
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }

  environment {
    variables = each.value.environment
  }

  depends_on = [aws_cloudwatch_log_group.lambda]

  tags = var.tags
}

# ================================================================
# EventBridge Scheduler — IAM Role
# ================================================================

resource "aws_iam_role" "scheduler" {
  name = "${local.function_prefix}-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  name = "lambda-invoke"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = [for fn in aws_lambda_function.ingest : fn.arn]
      }
    ]
  })
}

# ================================================================
# EventBridge Schedules
# ================================================================

resource "aws_scheduler_schedule_group" "ingest" {
  name = "${local.function_prefix}-ingest"

  tags = var.tags
}

resource "aws_scheduler_schedule" "ingest" {
  for_each = local.lambda_functions

  name       = "${local.function_prefix}-${each.key}"
  group_name = aws_scheduler_schedule_group.ingest.name

  schedule_expression = each.value.schedule
  kms_key_arn         = var.kms_key_arn

  flexible_time_window {
    mode                      = "FLEXIBLE"
    maximum_window_in_minutes = 15
  }

  target {
    arn      = aws_lambda_function.ingest[each.key].arn
    role_arn = aws_iam_role.scheduler.arn

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
  }
}

# ================================================================
# Embed Sync Lambda (DynamoDB Streams → Azure AI Search)
# ================================================================

data "archive_file" "embed_sync" {
  count = var.enable_embed_sync ? 1 : 0

  type        = "zip"
  source_dir  = "${path.module}/../../../../lambda/functions/embed_sync"
  output_path = "${path.module}/../../../../.build/lambda/embed_sync.zip"
}

resource "aws_cloudwatch_log_group" "embed_sync" {
  count = var.enable_embed_sync ? 1 : 0

  name              = "/aws/lambda/${local.function_prefix}-embed-sync"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

resource "aws_lambda_function" "embed_sync" {
  count = var.enable_embed_sync ? 1 : 0

  function_name = "${local.function_prefix}-embed-sync"
  description   = "Sync DynamoDB items to Azure AI Search via embeddings"
  role          = aws_iam_role.lambda_exec.arn

  filename         = data.archive_file.embed_sync[0].output_path
  source_code_hash = data.archive_file.embed_sync[0].output_base64sha256
  handler          = "handler.lambda_handler"
  runtime          = var.lambda_runtime
  architectures    = [var.lambda_architecture]
  timeout          = 300
  memory_size      = var.lambda_memory_mb

  reserved_concurrent_executions = var.lambda_reserved_concurrency
  kms_key_arn                    = var.kms_key_arn

  layers = [aws_lambda_layer_version.shared.arn]

  tracing_config {
    mode = "Active"
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }

  environment {
    variables = {
      DYNAMODB_TABLE        = local.table_name
      AZURE_OPENAI_ENDPOINT = var.azure_openai_endpoint
      AZURE_OPENAI_KEY      = var.azure_openai_key
      AZURE_SEARCH_ENDPOINT = var.azure_search_endpoint
      AZURE_SEARCH_KEY      = var.azure_search_key
      ENVIRONMENT           = var.environment
    }
  }

  depends_on = [aws_cloudwatch_log_group.embed_sync]

  tags = var.tags
}

resource "aws_lambda_event_source_mapping" "embed_sync" {
  count = var.enable_embed_sync ? 1 : 0

  event_source_arn  = aws_dynamodb_table.data_store.stream_arn
  function_name     = aws_lambda_function.embed_sync[0].arn
  starting_position = "LATEST"
  batch_size        = 10

  maximum_batching_window_in_seconds = 30

  filter_criteria {
    filter {
      pattern = jsonencode({
        eventName = ["INSERT", "MODIFY"]
      })
    }
  }
}

# DynamoDB Streams read permission for embed-sync
resource "aws_iam_role_policy" "lambda_streams" {
  count = var.enable_embed_sync ? 1 : 0

  name = "dynamodb-streams"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeStream",
          "dynamodb:GetRecords",
          "dynamodb:GetShardIterator",
          "dynamodb:ListStreams",
        ]
        Resource = "${aws_dynamodb_table.data_store.arn}/stream/*"
      }
    ]
  })
}
