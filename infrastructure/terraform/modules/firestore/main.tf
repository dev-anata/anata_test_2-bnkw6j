# Configure Terraform and required providers
terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

# Local variables for resource naming and tagging
locals {
  resource_prefix = "${var.environment}-firestore"
  
  common_labels = {
    environment           = var.environment
    managed-by           = "terraform"
    module               = "firestore"
    service              = "data-processing-pipeline"
    created-by           = "terraform"
    creation-timestamp   = timestamp()
    backup-enabled       = var.point_in_time_recovery ? "true" : "false"
    deletion-protection  = var.database_deletion_protection ? "enabled" : "disabled"
  }
}

# Create App Engine application (required for Firestore)
resource "google_app_engine_application" "main" {
  project       = var.project_id
  location_id   = var.region
  database_type = "CLOUD_FIRESTORE"
  auth_domain   = "${var.project_id}.firebaseapp.com"
  serving_status = "SERVING"
}

# Create Firestore database instance
resource "google_firestore_database" "main" {
  project  = var.project_id
  name     = "(default)"
  location_id = var.region
  type     = "FIRESTORE_NATIVE"
  
  # Configure database features based on input variables
  concurrency_mode = var.concurrency_mode
  app_engine_integration_mode = "ENABLED"
  
  # Security configurations
  deletion_protection = var.database_deletion_protection
  point_in_time_recovery_enablement = var.point_in_time_recovery ? "POINT_IN_TIME_RECOVERY_ENABLED" : "POINT_IN_TIME_RECOVERY_DISABLED"
  
  # Apply common labels
  labels = local.common_labels

  # Ensure App Engine application exists before creating Firestore
  depends_on = [
    google_app_engine_application.main
  ]

  lifecycle {
    prevent_destroy = true # Additional safety measure for production data
  }
}

# Output values for use in other modules
output "database_id" {
  description = "The ID of the Firestore database"
  value       = google_firestore_database.main.id
}

output "database_name" {
  description = "The name of the Firestore database"
  value       = google_firestore_database.main.name
}

output "database_location" {
  description = "The location of the Firestore database"
  value       = google_firestore_database.main.location_id
}

output "app_engine_id" {
  description = "The ID of the App Engine application"
  value       = google_app_engine_application.main.id
}

output "database_concurrency_mode" {
  description = "The concurrency mode of the Firestore database"
  value       = google_firestore_database.main.concurrency_mode
}

output "point_in_time_recovery_status" {
  description = "The point-in-time recovery status of the Firestore database"
  value       = google_firestore_database.main.point_in_time_recovery_enablement
}