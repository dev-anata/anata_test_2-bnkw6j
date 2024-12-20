# Output definitions for the cloud-storage module
# These outputs expose essential information about created GCS buckets
# for use by other modules and the root configuration

# Raw Data Bucket Outputs
output "raw_data_bucket_name" {
  description = "The name of the raw data storage bucket"
  value       = google_storage_bucket.raw_data_bucket.name
}

output "raw_data_bucket_url" {
  description = "The URL of the raw data storage bucket"
  value       = google_storage_bucket.raw_data_bucket.url
}

# Processed Data Bucket Outputs
output "processed_data_bucket_name" {
  description = "The name of the processed data storage bucket"
  value       = google_storage_bucket.processed_data_bucket.name
}

output "processed_data_bucket_url" {
  description = "The URL of the processed data storage bucket"
  value       = google_storage_bucket.processed_data_bucket.url
}

# Backup Bucket Outputs
output "backup_bucket_name" {
  description = "The name of the backup storage bucket"
  value       = google_storage_bucket.backup_bucket.name
}

output "backup_bucket_url" {
  description = "The URL of the backup storage bucket"
  value       = google_storage_bucket.backup_bucket.url
}

# IAM Configuration Outputs
output "raw_data_bucket_iam" {
  description = "The IAM configuration for the raw data bucket"
  value = {
    bucket = google_storage_bucket_iam_member.raw_data_bucket_iam.bucket
    role   = google_storage_bucket_iam_member.raw_data_bucket_iam.role
    member = google_storage_bucket_iam_member.raw_data_bucket_iam.member
  }
}

output "processed_data_bucket_iam" {
  description = "The IAM configuration for the processed data bucket"
  value = {
    bucket = google_storage_bucket_iam_member.processed_data_bucket_iam.bucket
    role   = google_storage_bucket_iam_member.processed_data_bucket_iam.role
    member = google_storage_bucket_iam_member.processed_data_bucket_iam.member
  }
}

output "backup_bucket_iam" {
  description = "The IAM configuration for the backup bucket"
  value = {
    bucket = google_storage_bucket_iam_member.backup_bucket_iam.bucket
    role   = google_storage_bucket_iam_member.backup_bucket_iam.role
    member = google_storage_bucket_iam_member.backup_bucket_iam.member
  }
}

# Storage Configuration Outputs
output "storage_configuration" {
  description = "Common storage configuration for all buckets"
  value = {
    project_id        = var.project_id
    region           = var.region
    environment      = var.environment
    storage_class    = var.storage_class
    kms_key_name     = var.kms_key_name
    enable_versioning = var.enable_versioning
  }
}