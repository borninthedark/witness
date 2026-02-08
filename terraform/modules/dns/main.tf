# ================================================================
# DNS Module — App Runner Custom Domain
# ================================================================
# Creates:
#   1. Custom domain association on the App Runner service
#      (handles ACM certificate provisioning automatically)
#   2. Route 53 CNAME records for certificate validation
#   3. Route 53 CNAME record for traffic routing
# ================================================================

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

  zone_id = var.hosted_zone_id
  name    = tolist(aws_apprunner_custom_domain_association.this.certificate_validation_records)[count.index].name
  type    = tolist(aws_apprunner_custom_domain_association.this.certificate_validation_records)[count.index].type
  ttl     = 300
  records = [tolist(aws_apprunner_custom_domain_association.this.certificate_validation_records)[count.index].value]
}

# ================================================================
# Traffic Routing CNAME Record
# ================================================================

resource "aws_route53_record" "app" {
  zone_id = var.hosted_zone_id
  name    = "${var.subdomain}.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = [aws_apprunner_custom_domain_association.this.dns_target]
}

# ================================================================
# Proton Mail
# ================================================================

resource "aws_route53_record" "spf" {
  zone_id = var.hosted_zone_id
  name    = ""
  type    = "TXT"
  ttl     = 3600

  multivalue_answer_routing_policy = true
  set_identifier                   = "spf"

  records = ["v=spf1 include:_spf.protonmail.ch ~all"]
}

resource "aws_route53_record" "protonmail_verification" {
  count = var.protonmail_verification_code != "" ? 1 : 0

  zone_id = var.hosted_zone_id
  name    = ""
  type    = "TXT"
  ttl     = 3600

  multivalue_answer_routing_policy = true
  set_identifier                   = "protonmail-verification"

  records = ["protonmail-verification=${var.protonmail_verification_code}"]
}

resource "aws_route53_record" "mx" {
  zone_id = var.hosted_zone_id
  name    = ""
  type    = "MX"
  ttl     = 3600

  records = [
    "10 mail.protonmail.ch",
    "20 mailsec.protonmail.ch",
  ]
}

resource "aws_route53_record" "dmarc" {
  zone_id = var.hosted_zone_id
  name    = "_dmarc"
  type    = "TXT"
  ttl     = 3600

  records = [
    "v=DMARC1; p=quarantine",
  ]
}

resource "aws_route53_record" "dkim" {
  count = 3

  zone_id = var.hosted_zone_id
  name    = "protonmail${count.index == 0 ? "" : count.index + 1}._domainkey"
  type    = "CNAME"
  ttl     = 3600

  records = [
    "protonmail${count.index == 0 ? "" : count.index + 1}.domainkey.d4rmgptbr32blnyq5244uir2hdftatqu3gnrefujosfqqnfrim5na.domains.proton.ch.",
  ]
}
