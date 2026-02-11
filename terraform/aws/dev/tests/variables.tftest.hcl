# ================================================================
# AWS App Runner Variable Validation Tests
# Tests input variable constraints and defaults
# Run from terraform/dev: terraform test
# ================================================================

# ──────────────────────────────────────────────────────────────────
# Test: Required variables must be provided
# ──────────────────────────────────────────────────────────────────

run "required_variables_set" {
  command = plan

  variables {
    secret_key = "test-secret-key-12345"
  }

  assert {
    condition     = var.project != ""
    error_message = "Project name must be provided"
  }

  assert {
    condition     = var.environment != ""
    error_message = "Environment must be provided"
  }

  assert {
    condition     = var.aws_region != ""
    error_message = "AWS region must be provided"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: App Runner instance configuration
# ──────────────────────────────────────────────────────────────────

run "instance_cpu_valid" {
  command = plan

  variables {
    secret_key   = "test-secret"
    instance_cpu = "512"
  }

  assert {
    condition     = contains(["256", "512", "1024", "2048", "4096"], var.instance_cpu)
    error_message = "Instance CPU must be a valid App Runner CPU value"
  }
}

run "instance_memory_valid" {
  command = plan

  variables {
    secret_key      = "test-secret"
    instance_memory = "1024"
  }

  assert {
    condition     = can(tonumber(var.instance_memory))
    error_message = "Instance memory must be a valid number string"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: Scaling configuration
# ──────────────────────────────────────────────────────────────────

run "min_size_at_least_one" {
  command = plan

  variables {
    secret_key = "test-secret"
    min_size   = 1
  }

  assert {
    condition     = var.min_size >= 1
    error_message = "Min size should be at least 1 for App Runner"
  }
}

run "max_size_greater_than_min" {
  command = plan

  variables {
    secret_key = "test-secret"
    min_size   = 1
    max_size   = 5
  }

  assert {
    condition     = var.max_size >= var.min_size
    error_message = "Max size should be greater than or equal to min size"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: Port configuration
# ──────────────────────────────────────────────────────────────────

run "container_port_valid_range" {
  command = plan

  variables {
    secret_key     = "test-secret"
    container_port = 8000
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
    secret_key = "test-secret"
  }

  assert {
    condition     = var.environment == "dev"
    error_message = "Default environment should be 'dev'"
  }
}

run "aws_region_default" {
  command = plan

  variables {
    secret_key = "test-secret"
  }

  assert {
    condition     = var.aws_region == "us-east-1"
    error_message = "Default AWS region should be 'us-east-1'"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: Log retention compliance
# ──────────────────────────────────────────────────────────────────

run "log_retention_compliance" {
  command = plan

  variables {
    secret_key         = "test-secret"
    log_retention_days = 30
  }

  assert {
    condition     = var.log_retention_days >= 30
    error_message = "Log retention should be at least 30 days for compliance"
  }
}

# ──────────────────────────────────────────────────────────────────
# Test: Max concurrency
# ──────────────────────────────────────────────────────────────────

run "max_concurrency_valid" {
  command = plan

  variables {
    secret_key      = "test-secret"
    max_concurrency = 100
  }

  assert {
    condition     = var.max_concurrency >= 1 && var.max_concurrency <= 200
    error_message = "Max concurrency should be between 1 and 200"
  }
}
