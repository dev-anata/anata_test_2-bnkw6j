# Terraform configuration for Data Processing Pipeline staging environment
# Provider version: hashicorp/google ~> 4.0
# Provider version: hashicorp/google-beta ~> 4.0

terraform {
  required_version = ">= 1.0.0"
  
  backend "gcs" {
    bucket = "terraform-state-${var.project_id}"
    prefix = "terraform/state/staging"
  }
}

# Configure providers
provider "google" {
  project = var.project_id
  region  = "us-central1"
}

provider "google-beta" {
  project = var.project_id
  region  = "us-central1"
}

# Local variables for staging environment
locals {
  staging_labels = {
    environment = "staging"
    managed_by  = "terraform"
    project     = "data-processing-pipeline"
  }

  staging_config = {
    gke_node_count          = 3
    cloud_run_min_instances = 2
    cloud_run_max_instances = 5
    api_rate_limit         = 500
    error_rate_threshold   = 0.02
    storage_retention_days = 30
  }
}

# GKE Cluster for staging
module "gke_cluster" {
  source = "../../modules/gke"

  cluster_name       = "data-pipeline-staging"
  region            = "us-central1"
  node_count        = local.staging_config.gke_node_count
  machine_type      = "n1-standard-2"
  kubernetes_version = "1.24"

  labels = local.staging_labels
}

# Cloud Storage for staging data
module "cloud_storage" {
  source = "../../modules/cloud-storage"

  bucket_names = [
    "data-pipeline-staging-raw",
    "data-pipeline-staging-processed"
  ]
  location      = "us-central1"
  storage_class = "STANDARD"

  lifecycle_rules = [{
    action = {
      type = "Delete"
    }
    condition = {
      age = local.staging_config.storage_retention_days
    }
  }]

  labels = local.staging_labels
}

# Cloud Run service for staging API
module "cloud_run" {
  source = "../../modules/cloud-run"

  service_name          = "data-pipeline-staging-api"
  region               = "us-central1"
  min_instances        = local.staging_config.cloud_run_min_instances
  max_instances        = local.staging_config.cloud_run_max_instances
  container_concurrency = 80

  labels = local.staging_labels
}

# Pub/Sub for staging task queue
module "pubsub" {
  source = "../../modules/pubsub"

  topic_names = [
    "data-pipeline-staging-tasks",
    "data-pipeline-staging-notifications"
  ]
  message_retention_duration = "604800s" # 7 days

  labels = local.staging_labels
}

# Firestore for staging metadata
module "firestore" {
  source = "../../modules/firestore"

  location_id   = "us-central1"
  database_type = "FIRESTORE_NATIVE"

  labels = local.staging_labels
}

# Security configurations for staging
resource "google_project_iam_binding" "staging_security" {
  project = var.project_id
  role    = "roles/viewer"

  members = [
    "serviceAccount:${var.project_id}@appspot.gserviceaccount.com",
  ]
}

# Network security for staging
resource "google_compute_security_policy" "staging_security_policy" {
  name = "staging-security-policy"

  rule {
    action   = "allow"
    priority = "1000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["0.0.0.0/0"]
      }
    }
    description = "Allow all traffic with rate limiting"

    rate_limit_options {
      conform_action = "allow"
      exceed_action = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count = local.staging_config.api_rate_limit
        interval_sec = 3600
      }
    }
  }
}

# Monitoring configuration for staging
resource "google_monitoring_alert_policy" "staging_alerts" {
  display_name = "Staging Error Rate Alert"
  combiner     = "OR"
  conditions {
    display_name = "Error Rate High"
    condition_threshold {
      filter          = "metric.type=\"custom.googleapis.com/error_rate\" resource.type=\"global\""
      duration        = "300s"
      comparison     = "COMPARISON_GT"
      threshold_value = local.staging_config.error_rate_threshold
    }
  }

  notification_channels = []  # Configure as needed
  user_labels = local.staging_labels
}

# Outputs
output "gke_cluster_endpoint" {
  value       = module.gke_cluster.cluster_endpoint
  description = "GKE cluster endpoint for staging"
  sensitive   = true
}

output "cloud_run_url" {
  value       = module.cloud_run.service_url
  description = "Cloud Run service URL for staging API"
}

output "storage_buckets" {
  value       = module.cloud_storage.bucket_names
  description = "Storage bucket names for staging environment"
}

output "pubsub_topics" {
  value       = module.pubsub.topic_names
  description = "Pub/Sub topic names for staging environment"
}