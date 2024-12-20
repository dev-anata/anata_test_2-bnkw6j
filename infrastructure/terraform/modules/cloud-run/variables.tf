# Core Terraform and provider version requirements
terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"  # version ~> 4.0
      version = "~> 4.0"
    }
  }
}

# Service Configuration Variables
variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string
  
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,62}[a-z0-9]$", var.service_name))
    error_message = "Service name must be between 4 and 64 characters, and contain only lowercase letters, numbers, and hyphens"
  }
}

variable "project_id" {
  description = "GCP project ID where the Cloud Run service will be deployed"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run service deployment"
  type        = string
  default     = "us-central1"
}

variable "container_image" {
  description = "Container image URL for the Cloud Run service"
  type        = string
}

# Scaling Configuration Variables
variable "min_instances" {
  description = "Minimum number of service instances to maintain for high availability"
  type        = number
  default     = 1

  validation {
    condition     = var.min_instances >= 1 && var.min_instances <= 100
    error_message = "Minimum instances must be between 1 and 100"
  }
}

variable "max_instances" {
  description = "Maximum number of service instances to scale to under load"
  type        = number
  default     = 10

  validation {
    condition     = var.max_instances >= var.min_instances && var.max_instances <= 1000
    error_message = "Maximum instances must be greater than or equal to minimum instances and not exceed 1000"
  }
}

# Resource Configuration Variables
variable "cpu_limit" {
  description = "CPU limit for each service instance to meet performance requirements"
  type        = string
  default     = "1000m"

  validation {
    condition     = can(regex("^[0-9]+m$", var.cpu_limit))
    error_message = "CPU limit must be specified in millicores (e.g., 1000m)"
  }
}

variable "memory_limit" {
  description = "Memory limit for each service instance to ensure optimal performance"
  type        = string
  default     = "512Mi"

  validation {
    condition     = can(regex("^[0-9]+(Mi|Gi)$", var.memory_limit))
    error_message = "Memory limit must be specified in Mi or Gi units"
  }
}

variable "timeout_seconds" {
  description = "Maximum request timeout in seconds to maintain API responsiveness"
  type        = number
  default     = 300

  validation {
    condition     = var.timeout_seconds >= 1 && var.timeout_seconds <= 900
    error_message = "Timeout must be between 1 and 900 seconds"
  }
}

# Security Configuration Variables
variable "service_account_email" {
  description = "Service account email for the Cloud Run service authentication"
  type        = string
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated access to the service (defaults to false for security)"
  type        = bool
  default     = false
}

# Network Configuration Variables
variable "vpc_connector" {
  description = "VPC connector name for private network connectivity"
  type        = string
  default     = null
}

# Runtime Configuration Variables
variable "environment_variables" {
  description = "Environment variables for configuring the Cloud Run service runtime"
  type        = map(string)
  default     = {}
}

# Resource Organization Variables
variable "labels" {
  description = "Labels to apply to the Cloud Run service for resource organization"
  type        = map(string)
  default     = {}
}