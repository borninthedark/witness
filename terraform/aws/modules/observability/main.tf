# ================================================================
# Observability Module - CloudWatch Logs, Dashboards, Alarms
# ================================================================

# ================================================================
# CloudWatch Log Group for App Runner
# ================================================================

module "app_log_group" {
  source  = "terraform-aws-modules/cloudwatch/aws//modules/log-group"
  version = "5.7.2"

  name              = "/aws/apprunner/${var.project}-${var.environment}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

# ================================================================
# CloudWatch Metric Alarms
# ================================================================

module "app_runner_alarms" {
  source  = "terraform-aws-modules/cloudwatch/aws//modules/metric-alarm"
  version = "5.7.2"

  alarm_name          = "${var.project}-${var.environment}-5xx-errors"
  alarm_description   = "App Runner 5xx errors exceed threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = var.error_threshold

  metric_name = "5xxStatusResponses"
  namespace   = "AWS/AppRunner"
  period      = 300
  statistic   = "Sum"

  dimensions = {
    ServiceName = "${var.project}-${var.environment}"
  }

  alarm_actions = var.alarm_sns_topic_arn != null ? [var.alarm_sns_topic_arn] : []

  tags = var.tags
}

module "app_runner_latency_alarm" {
  source  = "terraform-aws-modules/cloudwatch/aws//modules/metric-alarm"
  version = "5.7.2"

  alarm_name          = "${var.project}-${var.environment}-high-latency"
  alarm_description   = "App Runner P99 latency exceeds threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = var.latency_threshold_ms

  metric_name        = "RequestLatency"
  namespace          = "AWS/AppRunner"
  period             = 300
  extended_statistic = "p99"

  dimensions = {
    ServiceName = "${var.project}-${var.environment}"
  }

  alarm_actions = var.alarm_sns_topic_arn != null ? [var.alarm_sns_topic_arn] : []

  tags = var.tags
}

# ================================================================
# CloudWatch Dashboard
# ================================================================

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project}-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/AppRunner", "RequestCount", "ServiceName", "${var.project}-${var.environment}", { stat = "Sum" }],
            [".", "5xxStatusResponses", ".", ".", { stat = "Sum", color = "#d62728" }],
            [".", "4xxStatusResponses", ".", ".", { stat = "Sum", color = "#ff7f0e" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Request Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/AppRunner", "RequestLatency", "ServiceName", "${var.project}-${var.environment}", { stat = "p50" }],
            ["...", { stat = "p90" }],
            ["...", { stat = "p99" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Latency (p50/p90/p99)"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/AppRunner", "ActiveInstances", "ServiceName", "${var.project}-${var.environment}", { stat = "Average" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Active Instances"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/AppRunner", "CPUUtilization", "ServiceName", "${var.project}-${var.environment}", { stat = "Average" }],
            [".", "MemoryUtilization", ".", ".", { stat = "Average" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "CPU / Memory Utilization"
          period  = 300
        }
      }
    ]
  })
}
