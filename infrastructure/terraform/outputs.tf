# Output definitions for Data Processing Pipeline infrastructure components
# These outputs expose essential information about deployed GCP resources
# Version: 1.0

# Storage Buckets
output "raw_data_bucket_name" {
  description = "Name of the GCS bucket for storing raw data from web scraping and OCR tasks"
  value       = module.cloud_storage.raw_data_bucket_name
  sensitive   = false
}

output "processed_data_bucket_name" {
  description = "Name of the GCS bucket for storing processed and structured data"
  value       = module.cloud_storage.processed_data_bucket_name
  sensitive   = false
}

output "backup_bucket_name" {
  description = "Name of the GCS bucket for storing system backups and archives"
  value       = module.cloud_storage.backup_bucket_name
  sensitive   = false
}

# GKE Cluster
output "gke_cluster_endpoint" {
  description = "GKE cluster endpoint URL for kubectl and API access"
  value       = module.gke.cluster_endpoint
  sensitive   = true # Endpoint contains sensitive connection information
}

# Cloud Run Service
output "cloud_run_api_url" {
  description = "Cloud Run service URL for API access"
  value       = module.cloud_run.api_service_url
  sensitive   = false
}

# Pub/Sub Topic
output "task_topic_id" {
  description = "Pub/Sub topic ID for distributed task processing"
  value       = module.pubsub.task_topic_id
  sensitive   = false
}

# Firestore Database
output "firestore_database_id" {
  description = "Firestore database ID for system metadata storage"
  value       = module.firestore.database_id
  sensitive   = false
}