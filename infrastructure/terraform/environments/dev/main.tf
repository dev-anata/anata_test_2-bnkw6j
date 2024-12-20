# Development environment configuration for Data Processing Pipeline
# Provider version: hashicorp/google ~> 4.0
# Provider version: hashicorp/google-beta ~> 4.0

terraform {
  required_version = ">= 1.0.0"
  
  backend "gcs" {
    bucket = "terraform-state-data-pipeline-dev"
    prefix = "terraform/state/dev"
  }
}

# Configure providers
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Local variables for resource naming and tagging
locals {
  common_labels = {
    project     = "data-processing-pipeline"
    environment = "dev"
    managed_by  = "terraform"
  }
  
  resource_prefix = "data-pipeline-dev"
}

# Import root module for core infrastructure
module "root_module" {
  source = "../../"

  # Project configuration
  project_id  = var.project_id
  environment = "dev"
  region      = "us-central1"

  # GKE development configuration
  gke_cluster = {
    cluster_name       = "${local.resource_prefix}-cluster"
    node_count        = 1  # Minimal nodes for dev
    machine_type      = "n1-standard-2"
    kubernetes_version = "1.24"
  }

  # Cloud Storage development configuration
  cloud_storage = {
    bucket_names = [
      "raw-data-dev",
      "processed-data-dev",
      "ocr-output-dev"
    ]
    location      = "us-central1"
    storage_class = "STANDARD"
    lifecycle_rules = [{
      action = {
        type = "Delete"
      }
      condition = {
        age = 30  # Shorter retention for dev environment
      }
    }]
  }

  # Cloud Run development configuration
  cloud_run = {
    service_name          = "${local.resource_prefix}-api"
    region               = "us-central1"
    container_concurrency = 80
    min_instances        = 0  # Scale to zero in dev
    max_instances        = 10
  }

  # Pub/Sub development configuration
  pubsub = {
    topic_names = [
      "scraping-tasks-dev",
      "ocr-tasks-dev"
    ]
    message_retention_duration = "604800s"  # 7 days retention
  }

  # Firestore development configuration
  firestore = {
    location_id   = "us-central1"
    database_type = "FIRESTORE_NATIVE"
  }

  # Development-specific settings
  enable_monitoring     = true
  error_rate_threshold  = 0.05  # Higher error threshold for dev
  api_rate_limit       = 1000
  backup_enabled       = false  # Disable backups in dev
  ssl_policy          = "MODERN"

  # Common labels
  labels = local.common_labels
}

# Development-specific outputs
output "dev_gke_cluster_endpoint" {
  value       = module.root_module.gke_cluster_endpoint
  description = "Development GKE cluster endpoint"
  sensitive   = true
}

output "dev_cloud_run_url" {
  value       = module.root_module.cloud_run_url
  description = "Development Cloud Run service URL"
}

output "dev_storage_buckets" {
  value       = module.root_module.storage_buckets
  description = "Development storage bucket names"
}

output "dev_pubsub_topics" {
  value       = module.root_module.pubsub_topics
  description = "Development Pub/Sub topic names"
}

# Development environment validation
locals {
  validate_dev_config = {
    single_region_check = var.region == "us-central1" ? true : file("ERROR: Development environment must be in us-central1")
    minimal_nodes_check = module.root_module.gke_cluster.node_count <= 1 ? true : file("ERROR: Development environment should use minimal nodes")
  }
}