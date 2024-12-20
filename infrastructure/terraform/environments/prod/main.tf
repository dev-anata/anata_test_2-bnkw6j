# Production Environment Terraform Configuration
# Provider version: hashicorp/google ~> 4.0
# Provider version: hashicorp/google-beta ~> 4.0

terraform {
  required_version = ">= 1.0.0"

  # Configure GCS backend for production state
  backend "gcs" {
    bucket = "terraform-state-${var.project_id}"
    prefix = "terraform/state/prod"
  }
}

# Configure required providers
provider "google" {
  region = "us-central1"
  zones  = ["us-central1-a", "us-central1-b", "us-central1-c"]
  project = var.project_id
}

provider "google-beta" {
  region = "us-central1"
  zones  = ["us-central1-a", "us-central1-b", "us-central1-c"]
  project = var.project_id
}

# Production environment specific settings
locals {
  prod_settings = {
    # GKE cluster settings for high availability
    gke_node_count = 5
    gke_machine_type = "n2-standard-4"
    
    # Cloud Run settings for auto-scaling
    cloud_run_min_instances = 3
    cloud_run_max_instances = 20
    
    # Storage settings for data durability
    storage_class = "MULTI_REGIONAL"
    
    # Production features
    backup_enabled = true
    enable_monitoring = true
    
    # Production performance settings
    api_rate_limit = 5000
    error_rate_threshold = 0.001
  }
}

# Root module configuration for production environment
module "root" {
  source = "../../"

  # Project configuration
  project_id = var.project_id
  environment = "prod"
  region = "us-central1"

  # GKE cluster configuration
  gke_cluster_name = "data-pipeline-prod"
  gke_node_count = local.prod_settings.gke_node_count
  gke_machine_type = local.prod_settings.gke_machine_type

  # Storage configuration
  storage_bucket_names = [
    "data-pipeline-prod-raw",
    "data-pipeline-prod-processed"
  ]

  # Cloud Run configuration
  cloud_run_service_name = "data-pipeline-api-prod"
  cloud_run_min_instances = local.prod_settings.cloud_run_min_instances
  cloud_run_max_instances = local.prod_settings.cloud_run_max_instances

  # Pub/Sub configuration
  pubsub_topic_names = [
    "data-pipeline-prod-tasks",
    "data-pipeline-prod-dlq"
  ]

  # Performance and monitoring settings
  api_rate_limit = local.prod_settings.api_rate_limit
  enable_monitoring = local.prod_settings.enable_monitoring
  error_rate_threshold = local.prod_settings.error_rate_threshold

  # Data management settings
  storage_retention_days = 365  # 1 year retention for production
  backup_enabled = local.prod_settings.backup_enabled

  # Security settings
  ssl_policy = "RESTRICTED"  # Most secure SSL policy for production
}