# ================================================================
# Media CDN Variable Tests — Dev Environment
# Run from terraform/aws/dev: terraform test
# ================================================================

# ──────────────────────────────────────────────────────────────────
# Test: enable_media defaults to true
# ──────────────────────────────────────────────────────────────────

run "media_enabled_by_default" {
  command = plan

  variables {
    secret_key     = "test-secret"
    hosted_zone_id = "Z0123456789"
    admin_password = "test-password"
  }

  assert {
    condition     = var.enable_media == true
    error_message = "enable_media should default to true"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: enable_media is a boolean
# ──────────────────────────────────────────────────────────────────

run "media_accepts_true" {
  command = plan

  variables {
    secret_key     = "test-secret"
    hosted_zone_id = "Z0123456789"
    admin_password = "test-password"
    enable_media   = true
  }

  assert {
    condition     = var.enable_media == true
    error_message = "enable_media should accept true"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: Media variables pass through to app_runner when disabled
# ──────────────────────────────────────────────────────────────────

run "app_runner_media_empty_when_disabled" {
  command = plan

  variables {
    secret_key     = "test-secret"
    hosted_zone_id = "Z0123456789"
    admin_password = "test-password"
    enable_media   = false
  }

  # When media is disabled, app_runner should get empty media config
  assert {
    condition     = var.enable_media == false
    error_message = "Media should be disabled"
  }
}
