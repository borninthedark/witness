# ================================================================
# Media CDN Module - S3 + CloudFront + OAC + ACM + Route 53
# ================================================================

locals {
  bucket_name = "${var.project}-${var.environment}-media"
  cdn_domain  = "media.${var.domain_name}"
}

# ================================================================
# ACM Certificate (us-east-1 required for CloudFront)
# ================================================================

resource "aws_acm_certificate" "cdn" {
  domain_name       = local.cdn_domain
  validation_method = "DNS"

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-cdn-cert"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.cdn.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = var.hosted_zone_id
}

resource "aws_acm_certificate_validation" "cdn" {
  certificate_arn         = aws_acm_certificate.cdn.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# ================================================================
# S3 Bucket (media storage)
# ================================================================

module "media_bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "5.10.0"

  bucket = local.bucket_name

  # Block all public access — CloudFront OAC is the only reader
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  # Versioning + encryption
  versioning = {
    enabled = true
  }

  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        sse_algorithm = "AES256"
      }
    }
  }

  # Lifecycle — transition to STANDARD_IA after 90 days
  lifecycle_rule = [
    {
      id      = "transition-to-ia"
      enabled = true

      transition = [
        {
          days          = 90
          storage_class = "STANDARD_IA"
        }
      ]
    }
  ]

  # CORS for browser-based access
  cors_rule = [
    {
      allowed_headers = ["*"]
      allowed_methods = ["GET", "HEAD"]
      allowed_origins = ["https://engage.${var.domain_name}"]
      max_age_seconds = 3600
    }
  ]

  # S3 bucket policy — two statements:
  # 1. AllowCloudFrontOAC: Grants s3:GetObject to CloudFront service principal,
  #    conditioned on SourceArn matching THIS distribution only. This is the only
  #    way objects are served publicly (no public bucket access).
  # 2. DenyObjectDeletion: Prevents any principal outside the owning account from
  #    deleting objects. Media is append-mostly; cleanup via lifecycle rules.
  attach_policy = true
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontOAC"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "arn:aws:s3:::${local.bucket_name}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.main.arn
          }
        }
      },
      {
        Sid    = "DenyObjectDeletion"
        Effect = "Deny"
        Principal = {
          AWS = "*"
        }
        Action   = "s3:DeleteObject"
        Resource = "arn:aws:s3:::${local.bucket_name}/*"
        Condition = {
          StringNotEquals = {
            "aws:PrincipalAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = var.tags
}

data "aws_caller_identity" "current" {}

# ================================================================
# CloudFront Origin Access Control (OAC)
# ================================================================

resource "aws_cloudfront_origin_access_control" "s3" {
  name                              = "${var.project}-${var.environment}-media-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ================================================================
# CloudFront Access Log Bucket
# ================================================================

resource "aws_s3_bucket" "cdn_logs" {
  bucket = "${var.project}-${var.environment}-cdn-logs"

  tags = var.tags
}

resource "aws_s3_bucket_logging" "cdn_logs" {
  bucket = aws_s3_bucket.cdn_logs.id

  target_bucket = aws_s3_bucket.cdn_logs.id
  target_prefix = "self-access-logs/"
}

resource "aws_s3_bucket_ownership_controls" "cdn_logs" {
  #checkov:skip=CKV2_AWS_65:CloudFront standard logging requires log-delivery-write ACL
  bucket = aws_s3_bucket.cdn_logs.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "cdn_logs" {
  depends_on = [aws_s3_bucket_ownership_controls.cdn_logs]

  bucket = aws_s3_bucket.cdn_logs.id
  acl    = "log-delivery-write"
}

resource "aws_s3_bucket_public_access_block" "cdn_logs" {
  bucket = aws_s3_bucket.cdn_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cdn_logs" {
  bucket = aws_s3_bucket.cdn_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "cdn_logs" {
  bucket = aws_s3_bucket.cdn_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "cdn_logs" {
  bucket = aws_s3_bucket.cdn_logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# ================================================================
# CloudFront Response Headers Policy (security headers)
# ================================================================

resource "aws_cloudfront_response_headers_policy" "security" {
  name = "${var.project}-${var.environment}-security-headers"

  security_headers_config {
    content_type_options {
      override = true
    }

    frame_options {
      frame_option = "DENY"
      override     = true
    }

    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }

    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }

    xss_protection {
      mode_block = true
      protection = true
      override   = true
    }
  }
}

# ================================================================
# CloudFront WAFv2 Web ACL (CLOUDFRONT scope — us-east-1)
# ================================================================

resource "aws_wafv2_web_acl" "cdn" {
  name  = "${var.project}-${var.environment}-cdn-waf"
  scope = "CLOUDFRONT"

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
      metric_name                = "${var.project}-${var.environment}-cdn-common"
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
      metric_name                = "${var.project}-${var.environment}-cdn-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project}-${var.environment}-cdn-waf"
    sampled_requests_enabled   = true
  }

  tags = var.tags
}

# ================================================================
# CloudFront Distribution (dual-origin: S3 media + App Runner)
# ================================================================

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  http_version        = "http2and3"
  comment             = "${var.project}-${var.environment} media CDN"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  aliases             = [local.cdn_domain]
  web_acl_id          = aws_wafv2_web_acl.cdn.arn

  # Origin 1: S3 media bucket (OAC)
  origin {
    domain_name              = module.media_bucket.s3_bucket_bucket_regional_domain_name
    origin_id                = "s3-media"
    origin_access_control_id = aws_cloudfront_origin_access_control.s3.id
  }

  # Origin 2: App Runner (existing app for static assets)
  origin {
    domain_name = var.app_runner_url
    origin_id   = "app-runner"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  logging_config {
    include_cookies = false
    bucket          = aws_s3_bucket.cdn_logs.bucket_domain_name
    prefix          = "cloudfront/"
  }

  # Default behavior → App Runner (dynamic HTML, no cache)
  default_cache_behavior {
    target_origin_id           = "app-runner"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id

    forwarded_values {
      query_string = true
      headers      = ["Host", "Origin"]

      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  # /media/* → S3 (long cache, immutable media)
  ordered_cache_behavior {
    path_pattern               = "/media/*"
    target_origin_id           = "s3-media"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 86400    # 1 day
    max_ttl     = 31536000 # 1 year
  }

  # /static/* → App Runner (cache-busted assets)
  ordered_cache_behavior {
    path_pattern               = "/static/*"
    target_origin_id           = "app-runner"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id

    forwarded_values {
      query_string = true # cache-busting ?v=

      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600     # 1 hour
    max_ttl     = 31536000 # 1 year
  }

  # TLS
  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.cdn.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction {
      restriction_type = "whitelist"
      locations        = ["US", "PR", "VI", "GU", "AS", "MP", "CA", "GB", "IE", "DE", "FR"]
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-media-cdn"
  })
}

# ================================================================
# CDN WAF Logging
# ================================================================

resource "aws_cloudwatch_log_group" "cdn_waf" {
  name              = "aws-waf-logs-${var.project}-${var.environment}-cdn"
  retention_in_days = 365
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

resource "aws_wafv2_web_acl_logging_configuration" "cdn" {
  log_destination_configs = [aws_cloudwatch_log_group.cdn_waf.arn]
  resource_arn            = aws_wafv2_web_acl.cdn.arn
}

# ================================================================
# Route 53 A Record → CloudFront
# ================================================================

resource "aws_route53_record" "cdn" {
  zone_id = var.hosted_zone_id
  name    = local.cdn_domain
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}
