# Terraform configuration for Google Cloud Run service deployment
# Provider version: ~> 4.0

terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

# Environment-specific configuration for auto-scaling
locals {
  environment_config = {
    dev = {
      min_instances = 0  # Development environment can scale to zero
      max_instances = 2  # Limited scaling for cost control
    }
    staging = {
      min_instances = 1  # Maintain minimum availability
      max_instances = 5  # Moderate scaling for testing
    }
    prod = {
      min_instances = 2  # High availability requirement
      max_instances = 10 # Scale to handle production load
    }
  }

  # Default labels for resource organization
  default_labels = {
    environment = var.environment
    managed_by  = "terraform"
    service     = var.service_name
  }
}

# Cloud Run service resource configuration
resource "google_cloud_run_service" "cloud_run_service" {
  name     = var.service_name
  location = var.region
  project  = var.project_id

  template {
    metadata {
      annotations = {
        # Auto-scaling configuration
        "autoscaling.knative.dev/minScale" = local.environment_config[var.environment].min_instances
        "autoscaling.knative.dev/maxScale" = local.environment_config[var.environment].max_instances
        
        # VPC connectivity settings
        "run.googleapis.com/vpc-access-connector" = var.vpc_connector
        "run.googleapis.com/vpc-access-egress"    = "all-traffic"
        
        # Container startup and execution configurations
        "run.googleapis.com/execution-environment" = "gen2"
        "run.googleapis.com/startup-cpu-boost"     = "true"
      }
      labels = merge(local.default_labels, var.labels)
    }

    spec {
      service_account_name = var.service_account_email
      timeout_seconds     = var.timeout_seconds

      containers {
        image = var.container_image
        
        resources {
          limits = {
            cpu    = var.cpu_limit
            memory = var.memory_limit
          }
        }

        # Environment configuration
        dynamic "env" {
          for_each = merge(
            {
              ENVIRONMENT = var.environment
              PROJECT_ID  = var.project_id
            },
            var.environment_variables
          )
          content {
            name  = env.key
            value = env.value
          }
        }

        # Container port configuration
        ports {
          name           = "http1"
          container_port = 8080
        }

        # Health check configuration
        startup_probe {
          http_get {
            path = "/health"
            port = 8080
          }
          initial_delay_seconds = 10
          timeout_seconds      = 5
          period_seconds      = 15
          failure_threshold   = 3
        }

        liveness_probe {
          http_get {
            path = "/health"
            port = 8080
          }
          initial_delay_seconds = 15
          period_seconds       = 30
          timeout_seconds      = 5
          failure_threshold    = 3
        }
      }

      # Container concurrency configuration
      container_concurrency = 80
    }
  }

  # Traffic configuration
  traffic {
    percent         = 100
    latest_revision = true
  }

  # Ensure updates are handled gracefully
  lifecycle {
    ignore_changes = [
      template[0].metadata[0].annotations["client.knative.dev/user-image"],
      template[0].metadata[0].annotations["run.googleapis.com/client-name"],
      template[0].metadata[0].annotations["run.googleapis.com/client-version"],
    ]
  }
}

# IAM configuration for service invocation
resource "google_cloud_run_service_iam_member" "cloud_run_invoker" {
  location = var.region
  project  = var.project_id
  service  = google_cloud_run_service.cloud_run_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.service_account_email}"
}

# Optional: Public access configuration if allowed
resource "google_cloud_run_service_iam_member" "public_access" {
  count    = var.allow_unauthenticated ? 1 : 0
  location = var.region
  project  = var.project_id
  service  = google_cloud_run_service.cloud_run_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}