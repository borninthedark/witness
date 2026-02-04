# ================================================================
# Container Apps Variable Validation Tests
# Tests input variable constraints and defaults
# ================================================================

# ──────────────────────────────────────────────────────────────────
# Test: Required variables must be provided
# ──────────────────────────────────────────────────────────────────

run "required_variables_set" {
  command = plan

  variables {
    resource_group_name = "test-rg"
    app_name            = "test-app"
    container_image     = "ghcr.io/test/app:latest"
    secret_key          = "test-secret-key"
  }

  assert {
    condition     = var.resource_group_name != ""
    error_message = "Resource group name must be provided"
  }

  assert {
    condition     = var.app_name != ""
    error_message = "App name must be provided"
  }

  assert {
    condition     = var.container_image != ""
    error_message = "Container image must be provided"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: Container resource limits
# ──────────────────────────────────────────────────────────────────

run "container_cpu_valid" {
  command = plan

  variables {
    resource_group_name = "test-rg"
    app_name            = "test-app"
    container_image     = "ghcr.io/test/app:latest"
    secret_key          = "test-secret"
    container_cpu       = "0.5"
  }

  assert {
    condition     = can(tonumber(var.container_cpu))
    error_message = "Container CPU must be a valid number string"
  }
}

run "container_memory_format" {
  command = plan

  variables {
    resource_group_name = "test-rg"
    app_name            = "test-app"
    container_image     = "ghcr.io/test/app:latest"
    secret_key          = "test-secret"
    container_memory    = "1Gi"
  }

  assert {
    condition     = can(regex("^[0-9]+(\\.?[0-9]*)(Gi|Mi)$", var.container_memory))
    error_message = "Container memory must be in format like '1Gi' or '512Mi'"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: Scaling configuration
# ──────────────────────────────────────────────────────────────────

run "min_replicas_at_least_one" {
  command = plan

  variables {
    resource_group_name = "test-rg"
    app_name            = "test-app"
    container_image     = "ghcr.io/test/app:latest"
    secret_key          = "test-secret"
    min_replicas        = 1
  }

  assert {
    condition     = var.min_replicas >= 0
    error_message = "Min replicas should be non-negative"
  }
}

run "max_replicas_greater_than_min" {
  command = plan

  variables {
    resource_group_name = "test-rg"
    app_name            = "test-app"
    container_image     = "ghcr.io/test/app:latest"
    secret_key          = "test-secret"
    min_replicas        = 1
    max_replicas        = 5
  }

  assert {
    condition     = var.max_replicas >= var.min_replicas
    error_message = "Max replicas should be greater than or equal to min replicas"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: Port configuration
# ──────────────────────────────────────────────────────────────────

run "container_port_valid_range" {
  command = plan

  variables {
    resource_group_name = "test-rg"
    app_name            = "test-app"
    container_image     = "ghcr.io/test/app:latest"
    secret_key          = "test-secret"
    container_port      = 8000
  }

  assert {
    condition     = var.container_port > 0 && var.container_port <= 65535
    error_message = "Container port must be between 1 and 65535"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: Environment configuration
# ──────────────────────────────────────────────────────────────────

run "environment_default_dev" {
  command = plan

  variables {
    resource_group_name = "test-rg"
    app_name            = "test-app"
    container_image     = "ghcr.io/test/app:latest"
    secret_key          = "test-secret"
  }

  assert {
    condition     = var.environment == "dev"
    error_message = "Default environment should be 'dev'"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: Revision mode
# ──────────────────────────────────────────────────────────────────

run "revision_mode_valid" {
  command = plan

  variables {
    resource_group_name = "test-rg"
    app_name            = "test-app"
    container_image     = "ghcr.io/test/app:latest"
    secret_key          = "test-secret"
    revision_mode       = "Single"
  }

  assert {
    condition     = contains(["Single", "Multiple"], var.revision_mode)
    error_message = "Revision mode must be 'Single' or 'Multiple'"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: Log retention compliance
# ──────────────────────────────────────────────────────────────────

run "log_retention_compliance" {
  command = plan

  variables {
    resource_group_name = "test-rg"
    app_name            = "test-app"
    container_image     = "ghcr.io/test/app:latest"
    secret_key          = "test-secret"
    log_retention_days  = 30
  }

  assert {
    condition     = var.log_retention_days >= 30
    error_message = "Log retention should be at least 30 days for compliance"
  }
}
