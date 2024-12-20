# Core Terraform functionality
terraform {
  required_version = ">=1.0.0"
}

# Project Configuration Variables
variable "project_id" {
  description = "The Google Cloud Project ID where the storage buckets will be created"
  type        = string

  validation {
    condition     = length(var.project_id) > 0
    error_message = "Project ID must not be empty"
  }
}

variable "region" {
  description = "The GCP region where the storage buckets will be located"
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

# Storage Configuration Variables
variable "storage_class" {
  description = "The storage class for the buckets (STANDARD, NEARLINE, COLDLINE, ARCHIVE)"
  type        = string
  default     = "STANDARD"

  validation {
    condition     = contains(["STANDARD", "NEARLINE", "COLDLINE", "ARCHIVE"], var.storage_class)
    error_message = "Storage class must be one of: STANDARD, NEARLINE, COLDLINE, ARCHIVE"
  }
}

# Security Configuration Variables
variable "kms_key_name" {
  description = "The Cloud KMS key name used for bucket encryption"
  type        = string

  validation {
    condition     = can(regex("^projects/.+/locations/.+/keyRings/.+/cryptoKeys/.+$", var.kms_key_name))
    error_message = "KMS key name must be a valid Cloud KMS key path"
  }
}

variable "service_account" {
  description = "The service account email that will be granted access to the buckets"
  type        = string

  validation {
    condition     = can(regex("^.+@.+\\.iam\\.gserviceaccount\\.com$", var.service_account))
    error_message = "Service account must be a valid GCP service account email"
  }
}

# Data Lifecycle Variables
variable "retention_period_days" {
  description = "The retention period in days for the backup bucket"
  type        = number
  default     = 90

  validation {
    condition     = var.retention_period_days >= 1
    error_message = "Retention period must be at least 1 day"
  }
}

variable "enable_versioning" {
  description = "Whether to enable object versioning on the buckets"
  type        = bool
  default     = true
}

variable "lifecycle_rules" {
  description = "List of lifecycle rules for the buckets"
  type = list(object({
    action    = map(string)
    condition = map(string)
  }))
  default = []
}