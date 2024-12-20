# Main Terraform configuration for Data Processing Pipeline
# Provider version: hashicorp/google ~> 4.0
# Provider version: hashicorp/google-beta ~> 4.0

terraform {
  required_version = ">= 1.0.0"
  
  backend "gcs" {
    bucket = "${var.project_id}-terraform-state"
    prefix = "terraform/state"
  }
}

# Local variables for resource naming and tagging
locals {
  common_labels = {
    project     = "data-processing-pipeline"
    environment = var.environment
    managed_by  = "terraform"
  }
  
  resource_prefix = "data-pipeline-${var.environment}"
}

# Enable required GCP APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "container.googleapis.com",      # GKE
    "run.googleapis.com",           # Cloud Run
    "pubsub.googleapis.com",        # Pub/Sub
    "firestore.googleapis.com",     # Firestore
    "storage.googleapis.com",       # Cloud Storage
    "monitoring.googleapis.com",    # Cloud Monitoring
    "logging.googleapis.com",       # Cloud Logging
    "cloudkms.googleapis.com"       # Cloud KMS
  ])
  
  project = var.project_id
  service = each.value
  
  disable_on_destroy = false
}

# GKE Cluster deployment
module "gke_cluster" {
  source = "./modules/gke"
  depends_on = [google_project_service.required_apis]
  
  cluster_name        = "${local.resource_prefix}-cluster"
  region             = var.region
  node_count         = var.gke_node_count
  machine_type       = "n1-standard-2"
  kubernetes_version = "1.24"
  
  labels = local.common_labels
}

# Cloud Storage configuration
module "cloud_storage" {
  source = "./modules/cloud-storage"
  depends_on = [google_project_service.required_apis]
  
  bucket_names   = var.storage_bucket_names
  location       = var.region
  storage_class  = "STANDARD"
  
  lifecycle_rules = [{
    action = {
      type = "Delete"
    }
    condition = {
      age = var.storage_retention_days
    }
  }]
  
  labels = local.common_labels
}

# Cloud Run service deployment
module "cloud_run" {
  source = "./modules/cloud-run"
  depends_on = [google_project_service.required_apis]
  
  service_name          = "${local.resource_prefix}-api"
  region               = var.region
  container_concurrency = 80
  min_instances        = var.cloud_run_min_instances
  max_instances        = var.cloud_run_max_instances
  
  labels = local.common_labels
}

# Pub/Sub configuration
module "pubsub" {
  source = "./modules/pubsub"
  depends_on = [google_project_service.required_apis]
  
  topic_names                 = var.pubsub_topic_names
  message_retention_duration  = "604800s"  # 7 days
  
  labels = local.common_labels
}

# Firestore configuration
module "firestore" {
  source = "./modules/firestore"
  depends_on = [google_project_service.required_apis]
  
  location_id   = var.region
  database_type = "FIRESTORE_NATIVE"
  
  labels = local.common_labels
}

# Monitoring and logging configuration
module "monitoring" {
  source = "./modules/monitoring"
  count  = var.enable_monitoring ? 1 : 0
  
  project_id          = var.project_id
  error_threshold     = var.error_rate_threshold
  notification_channels = []  # Configure as needed
  
  labels = local.common_labels
}

# VPC network configuration
resource "google_compute_network" "vpc" {
  name                    = "${local.resource_prefix}-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${local.resource_prefix}-subnet"
  ip_cidr_range = "10.0.0.0/20"
  region        = var.region
  network       = google_compute_network.vpc.id
  
  secondary_ip_range {
    range_name    = "gke-pods"
    ip_cidr_range = "10.1.0.0/16"
  }
  
  secondary_ip_range {
    range_name    = "gke-services"
    ip_cidr_range = "10.2.0.0/20"
  }
}

# Cloud KMS configuration for encryption
resource "google_kms_key_ring" "keyring" {
  name     = "${local.resource_prefix}-keyring"
  location = var.region
  project  = var.project_id
}

resource "google_kms_crypto_key" "key" {
  name     = "${local.resource_prefix}-key"
  key_ring = google_kms_key_ring.keyring.id
  
  rotation_period = "7776000s"  # 90 days
  
  lifecycle {
    prevent_destroy = true
  }
}

# Output values
output "gke_cluster_endpoint" {
  value       = module.gke_cluster.cluster_endpoint
  description = "GKE cluster endpoint"
  sensitive   = true
}

output "cloud_run_url" {
  value       = module.cloud_run.service_url
  description = "Cloud Run service URL"
}

output "storage_buckets" {
  value       = module.cloud_storage.bucket_names
  description = "Created storage bucket names"
}

output "pubsub_topics" {
  value       = module.pubsub.topic_names
  description = "Created Pub/Sub topic names"
}