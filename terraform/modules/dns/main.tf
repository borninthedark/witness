# ================================================================
# DNS Module — App Runner Custom Domain
# ================================================================
# Creates:
#   1. Custom domain association on the App Runner service
#      (handles ACM certificate provisioning automatically)
#   2. Route 53 CNAME records for certificate validation
#   3. Route 53 CNAME record for traffic routing
# ================================================================

data "aws_route53_zone" "main" {
  name = var.domain_name
}

# ================================================================
# App Runner Custom Domain Association
# ================================================================

resource "aws_apprunner_custom_domain_association" "this" {
  service_arn = var.app_runner_service_arn
  domain_name = "${var.subdomain}.${var.domain_name}"
}

# ================================================================
# Certificate Validation CNAME Records
# ================================================================
# App Runner always returns exactly 3 validation CNAME records,
# but the value isn't known until apply. Hardcode the count to
# avoid the "count depends on resource attributes" error.
# ================================================================

resource "aws_route53_record" "validation" {
  count = 3

  zone_id = data.aws_route53_zone.main.zone_id
  name    = tolist(aws_apprunner_custom_domain_association.this.certificate_validation_records)[count.index].name
  type    = tolist(aws_apprunner_custom_domain_association.this.certificate_validation_records)[count.index].type
  ttl     = 300
  records = [tolist(aws_apprunner_custom_domain_association.this.certificate_validation_records)[count.index].value]
}

# ================================================================
# Traffic Routing CNAME Record
# ================================================================

resource "aws_route53_record" "app" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "${var.subdomain}.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = [aws_apprunner_custom_domain_association.this.dns_target]
}
