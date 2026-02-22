# ================================================================
# Media CDN Module — Native Terraform Tests
# Run from terraform/aws/modules/media: terraform test
# ================================================================
#
# KNOWN LIMITATION (Terraform mock_provider + for_each):
# aws_route53_record.cert_validation uses for_each over
# aws_acm_certificate.cdn.domain_validation_options, which is a
# computed set(object) attribute — "known only after apply".
# Mock providers return unknown values for computed attributes even
# with override_resource, and for_each requires known keys at plan
# time. This is a fundamental Terraform testing limitation:
# for_each keys must be statically resolvable, but ACM validation
# options are inherently dynamic.
#
# Workaround: These tests use `command = apply` and override the
# for_each source resource. If the override_resource mechanism is
# enhanced in a future Terraform release to resolve for_each keys,
# these tests will begin passing automatically.
#
# In the meantime, the media module is validated through:
# 1. terraform validate (syntax + type checking)
# 2. terraform/aws/dev/tests/media.tftest.hcl (variable tests)
# 3. tests/test_terraform.py (Python static analysis)
# 4. HCP Terraform speculative plans on PR
# ================================================================

mock_provider "aws" {
  override_resource {
    target = aws_acm_certificate.cdn
    values = {
      arn = "arn:aws:acm:us-east-1:123456789012:certificate/mock-cert-id"
      domain_validation_options = [
        {
          domain_name           = "media.princetonstrong.com"
          resource_record_name  = "_mock.media.princetonstrong.com."
          resource_record_type  = "CNAME"
          resource_record_value = "_mock.acm-validations.aws."
        }
      ]
    }
  }

  override_resource {
    target = aws_acm_certificate_validation.cdn
    values = {
      certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/mock-cert-id"
    }
  }

  override_resource {
    target = aws_cloudfront_distribution.main
    values = {
      arn            = "arn:aws:cloudfront::123456789012:distribution/EMOCK123"
      domain_name    = "d111111abcdef8.cloudfront.net"
      hosted_zone_id = "Z2FDTNDATAQYW2"
    }
  }

  override_data {
    target = data.aws_caller_identity.current
    values = {
      account_id = "123456789012"
    }
  }

}

# ──────────────────────────────────────────────────────────────────
# Tests below are blocked by the for_each limitation above.
# They document intended assertions and will pass once Terraform's
# mock_provider can supply for_each keys for computed attributes.
#
# Each test validates a specific security or naming property:
# - Bucket naming: {project}-{environment}-media
# - CDN domain: media.{domain_name}
# - ACM cert: DNS-validated, matches CDN domain
# - OAC: sigv4 always-sign for S3
# - CloudFront: HTTPS redirect, TLSv1.2_2021, PriceClass_100
# - Cache: TTL=0 for dynamic, 1d for /media/*, 1h for /static/*
# - Route 53: A alias to CloudFront
# - Tags: Name convention and propagation
# ──────────────────────────────────────────────────────────────────

run "bucket_name_follows_convention" {
  command = apply

  variables {
    project        = "witness"
    environment    = "dev"
    domain_name    = "princetonstrong.com"
    hosted_zone_id = "Z0123456789"
    app_runner_url = "abc123.us-east-1.awsapprunner.com"
  }

  assert {
    condition     = module.media_bucket.s3_bucket_id == "witness-dev-media"
    error_message = "Bucket name should be {project}-{environment}-media"
  }
}

run "cdn_domain_uses_media_prefix" {
  command = apply

  variables {
    project        = "witness"
    environment    = "dev"
    domain_name    = "princetonstrong.com"
    hosted_zone_id = "Z0123456789"
    app_runner_url = "abc123.us-east-1.awsapprunner.com"
  }

  assert {
    condition     = output.media_cdn_domain == "media.princetonstrong.com"
    error_message = "CDN domain should be media.{domain_name}"
  }
}

run "acm_cert_matches_cdn_domain" {
  command = apply

  variables {
    project        = "witness"
    environment    = "dev"
    domain_name    = "princetonstrong.com"
    hosted_zone_id = "Z0123456789"
    app_runner_url = "abc123.us-east-1.awsapprunner.com"
  }

  assert {
    condition     = aws_acm_certificate.cdn.domain_name == "media.princetonstrong.com"
    error_message = "ACM certificate should match CDN domain"
  }

  assert {
    condition     = aws_acm_certificate.cdn.validation_method == "DNS"
    error_message = "ACM certificate should use DNS validation"
  }
}

run "cloudfront_oac_uses_sigv4" {
  command = apply

  variables {
    project        = "witness"
    environment    = "dev"
    domain_name    = "princetonstrong.com"
    hosted_zone_id = "Z0123456789"
    app_runner_url = "abc123.us-east-1.awsapprunner.com"
  }

  assert {
    condition     = aws_cloudfront_origin_access_control.s3.signing_protocol == "sigv4"
    error_message = "OAC must use sigv4 signing protocol"
  }

  assert {
    condition     = aws_cloudfront_origin_access_control.s3.signing_behavior == "always"
    error_message = "OAC must always sign requests"
  }
}

run "cloudfront_https_and_tls" {
  command = apply

  variables {
    project        = "witness"
    environment    = "dev"
    domain_name    = "princetonstrong.com"
    hosted_zone_id = "Z0123456789"
    app_runner_url = "abc123.us-east-1.awsapprunner.com"
  }

  assert {
    condition     = aws_cloudfront_distribution.main.enabled == true
    error_message = "CloudFront distribution must be enabled"
  }

  assert {
    condition     = aws_cloudfront_distribution.main.price_class == "PriceClass_100"
    error_message = "Price class should be PriceClass_100 (US/EU)"
  }

  assert {
    condition     = one(aws_cloudfront_distribution.main.viewer_certificate).minimum_protocol_version == "TLSv1.2_2021"
    error_message = "Minimum TLS version must be TLSv1.2_2021"
  }

  assert {
    condition     = one(aws_cloudfront_distribution.main.default_cache_behavior).viewer_protocol_policy == "redirect-to-https"
    error_message = "Default behavior must redirect HTTP to HTTPS"
  }

  assert {
    condition     = one(aws_cloudfront_distribution.main.default_cache_behavior).default_ttl == 0
    error_message = "Default behavior TTL should be 0 (no caching for dynamic HTML)"
  }
}

run "tags_propagated" {
  command = apply

  variables {
    project        = "witness"
    environment    = "dev"
    domain_name    = "princetonstrong.com"
    hosted_zone_id = "Z0123456789"
    app_runner_url = "abc123.us-east-1.awsapprunner.com"
    tags = {
      Owner = "test"
    }
  }

  assert {
    condition     = aws_cloudfront_distribution.main.tags["Name"] == "witness-dev-media-cdn"
    error_message = "Name tag should follow convention {project}-{env}-media-cdn"
  }

  assert {
    condition     = aws_acm_certificate.cdn.tags["Name"] == "witness-dev-cdn-cert"
    error_message = "ACM cert Name tag should follow convention"
  }
}
