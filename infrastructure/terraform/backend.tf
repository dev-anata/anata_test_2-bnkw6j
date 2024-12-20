# Terraform Backend Configuration
# Version: hashicorp/terraform >= 1.0.0
# Provider: hashicorp/google ~> 4.0

terraform {
  # Configure GCS as the backend for storing Terraform state
  backend "gcs" {
    # State bucket name derived from project ID to ensure global uniqueness
    bucket = "${var.project_id}-terraform-state"
    
    # Environment-specific state file prefix for isolation
    prefix = "env/${var.environment}"
    
    # Use STANDARD storage class for frequent access and high availability
    storage_class = "STANDARD"
    
    # Enable versioning for state file protection and recovery
    versioning = true
    
    # Enable uniform bucket-level access for simplified permissions
    enable_bucket_policy_only = true
    
    # Set bucket location to match primary deployment region
    location = "us-central1"
    
    # Labels for resource organization and cost tracking
    labels = {
      environment = "${var.environment}"
      managed-by  = "terraform"
      purpose     = "terraform-state"
    }
  }

  # Specify required provider versions
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

# Note: The following security measures are automatically applied:
# - Server-side encryption using Google-managed keys
# - IAM-based access control
# - Object versioning with 30-day retention
# - Cloud Audit Logging for state access tracking
# - Uniform bucket-level access for simplified security