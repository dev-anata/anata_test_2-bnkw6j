# Google Cloud Storage Module
# Terraform ~> 4.0

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

# Raw Data Storage Bucket
# Stores unprocessed data from web scraping and OCR tasks
resource "google_storage_bucket" "raw_data_bucket" {
  name                        = "${var.project_id}-raw-data-${var.environment}"
  project                     = var.project_id
  location                    = var.region
  storage_class              = var.storage_class
  uniform_bucket_level_access = true
  
  versioning {
    enabled = var.enable_versioning
  }
  
  encryption {
    default_kms_key_name = var.kms_key_name
  }
  
  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_rules
    content {
      action {
        type = lifecycle_rule.value.action["type"]
        storage_class = lookup(lifecycle_rule.value.action, "storage_class", null)
      }
      condition {
        age                   = lookup(lifecycle_rule.value.condition, "age", null)
        created_before        = lookup(lifecycle_rule.value.condition, "created_before", null)
        with_state           = lookup(lifecycle_rule.value.condition, "with_state", null)
        matches_storage_class = lookup(lifecycle_rule.value.condition, "matches_storage_class", null)
        num_newer_versions    = lookup(lifecycle_rule.value.condition, "num_newer_versions", null)
      }
    }
  }

  logging {
    log_bucket = "${var.project_id}-logs-${var.environment}"
  }

  labels = {
    environment = var.environment
    data_type   = "raw"
    managed_by  = "terraform"
  }
}

# Processed Data Storage Bucket
# Stores structured and processed data
resource "google_storage_bucket" "processed_data_bucket" {
  name                        = "${var.project_id}-processed-data-${var.environment}"
  project                     = var.project_id
  location                    = var.region
  storage_class              = var.storage_class
  uniform_bucket_level_access = true
  
  versioning {
    enabled = var.enable_versioning
  }
  
  encryption {
    default_kms_key_name = var.kms_key_name
  }
  
  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_rules
    content {
      action {
        type = lifecycle_rule.value.action["type"]
        storage_class = lookup(lifecycle_rule.value.action, "storage_class", null)
      }
      condition {
        age                   = lookup(lifecycle_rule.value.condition, "age", null)
        created_before        = lookup(lifecycle_rule.value.condition, "created_before", null)
        with_state           = lookup(lifecycle_rule.value.condition, "with_state", null)
        matches_storage_class = lookup(lifecycle_rule.value.condition, "matches_storage_class", null)
        num_newer_versions    = lookup(lifecycle_rule.value.condition, "num_newer_versions", null)
      }
    }
  }

  logging {
    log_bucket = "${var.project_id}-logs-${var.environment}"
  }

  labels = {
    environment = var.environment
    data_type   = "processed"
    managed_by  = "terraform"
  }
}

# Backup Storage Bucket
# Stores data backups with enhanced retention policies
resource "google_storage_bucket" "backup_bucket" {
  name                        = "${var.project_id}-backups-${var.environment}"
  project                     = var.project_id
  location                    = var.region
  storage_class              = var.storage_class
  uniform_bucket_level_access = true
  
  versioning {
    enabled = true # Always enabled for backup bucket
  }
  
  retention_policy {
    retention_period = var.retention_period_days * 24 * 60 * 60
    is_locked        = true
  }
  
  encryption {
    default_kms_key_name = var.kms_key_name
  }
  
  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_rules
    content {
      action {
        type = lifecycle_rule.value.action["type"]
        storage_class = lookup(lifecycle_rule.value.action, "storage_class", null)
      }
      condition {
        age                   = lookup(lifecycle_rule.value.condition, "age", null)
        created_before        = lookup(lifecycle_rule.value.condition, "created_before", null)
        with_state           = lookup(lifecycle_rule.value.condition, "with_state", null)
        matches_storage_class = lookup(lifecycle_rule.value.condition, "matches_storage_class", null)
        num_newer_versions    = lookup(lifecycle_rule.value.condition, "num_newer_versions", null)
      }
    }
  }

  logging {
    log_bucket = "${var.project_id}-logs-${var.environment}"
  }

  labels = {
    environment = var.environment
    data_type   = "backup"
    managed_by  = "terraform"
  }
}

# IAM Bindings for Raw Data Bucket
resource "google_storage_bucket_iam_member" "raw_data_bucket_iam" {
  bucket = google_storage_bucket.raw_data_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.service_account}"

  condition {
    title       = "raw_data_access"
    description = "Allows read access to raw data"
    expression  = "resource.type == 'storage.googleapis.com/Object'"
  }
}

# IAM Bindings for Processed Data Bucket
resource "google_storage_bucket_iam_member" "processed_data_bucket_iam" {
  bucket = google_storage_bucket.processed_data_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.service_account}"

  condition {
    title       = "processed_data_access"
    description = "Allows read access to processed data"
    expression  = "resource.type == 'storage.googleapis.com/Object'"
  }
}

# IAM Bindings for Backup Bucket
resource "google_storage_bucket_iam_member" "backup_bucket_iam" {
  bucket = google_storage_bucket.backup_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.service_account}"

  condition {
    title       = "backup_access"
    description = "Allows read access to backups"
    expression  = "resource.type == 'storage.googleapis.com/Object'"
  }
}

# Output values for use in other modules
output "raw_data_bucket" {
  description = "Raw data bucket details"
  value = {
    name = google_storage_bucket.raw_data_bucket.name
    url  = google_storage_bucket.raw_data_bucket.url
  }
}

output "processed_data_bucket" {
  description = "Processed data bucket details"
  value = {
    name = google_storage_bucket.processed_data_bucket.name
    url  = google_storage_bucket.processed_data_bucket.url
  }
}

output "backup_bucket" {
  description = "Backup bucket details"
  value = {
    name = google_storage_bucket.backup_bucket.name
    url  = google_storage_bucket.backup_bucket.url
  }
}