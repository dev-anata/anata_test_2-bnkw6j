# Core Terraform version constraint
terraform {
  required_version = ">=1.0.0"
}

# Project configuration variables
variable "project_id" {
  description = "The Google Cloud project ID where Firestore will be created"
  type        = string

  validation {
    condition     = length(var.project_id) > 0
    error_message = "Project ID must not be empty"
  }
}

variable "region" {
  description = "The region where Firestore will be deployed"
  type        = string

  validation {
    condition     = can(regex("^[a-z]+-[a-z]+\\d+$", var.region))
    error_message = "Region must be a valid GCP region name"
  }
}

variable "environment" {
  description = "The deployment environment (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod"
  }
}

# Firestore configuration variables
variable "database_deletion_protection" {
  description = "Whether deletion protection is enabled for the Firestore database"
  type        = bool
  default     = true
}

variable "point_in_time_recovery" {
  description = "Whether point-in-time recovery is enabled for the Firestore database"
  type        = bool
  default     = true
}

variable "concurrency_mode" {
  description = "The concurrency mode for the Firestore database (OPTIMISTIC or PESSIMISTIC)"
  type        = string
  default     = "OPTIMISTIC"

  validation {
    condition     = contains(["OPTIMISTIC", "PESSIMISTIC"], var.concurrency_mode)
    error_message = "Concurrency mode must be either OPTIMISTIC or PESSIMISTIC"
  }
}