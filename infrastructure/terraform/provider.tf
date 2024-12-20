# Provider Configuration for Data Processing Pipeline Infrastructure
# Version: 1.0.0
# This file configures the Google Cloud Platform providers (standard and beta) 
# with required authentication and project settings.

# Core Terraform Configuration Block
terraform {
  # Enforce minimum Terraform version for compatibility
  required_version = ">= 1.0.0"

  # Define required providers with specific versions
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 4.0"
    }
  }
}

# Primary Google Cloud Provider Configuration
provider "google" {
  # Project configuration
  project = var.project_id
  region  = var.region

  # Request configuration
  request_timeout = "60s"

  # Enable user project override for shared VPC and cross-project resources
  user_project_override = true

  # Default provider settings
  scopes = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
  ]
}

# Google Cloud Beta Provider Configuration
# Required for features in beta/preview
provider "google-beta" {
  # Project configuration (matching primary provider)
  project = var.project_id
  region  = var.region

  # Request configuration
  request_timeout = "60s"

  # Enable user project override for shared VPC and cross-project resources
  user_project_override = true

  # Default provider settings
  scopes = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
  ]
}