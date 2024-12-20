# Core Terraform and Provider Configuration
terraform {
  required_version = ">= 1.0.0"
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

# Project Configuration Variables
variable "project_id" {
  description = "GCP project ID for the deployment"
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Project ID must be between 6 and 30 characters, and contain only lowercase letters, numbers, and hyphens"
  }
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod"
  }
}

variable "region" {
  description = "Primary GCP region for resource deployment"
  type        = string
  default     = "us-central1"
}

# GKE Cluster Configuration
variable "gke_cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
  default     = "data-pipeline-cluster"
}

variable "gke_node_count" {
  description = "Number of nodes in the GKE cluster"
  type        = number
  default     = 3
}

# Storage Configuration
variable "storage_bucket_names" {
  description = "List of GCS bucket names for data storage"
  type        = list(string)
  validation {
    condition     = length(var.storage_bucket_names) > 0
    error_message = "At least one storage bucket name must be provided"
  }
}

# Cloud Run Configuration
variable "cloud_run_service_name" {
  description = "Name of the Cloud Run service for API"
  type        = string
  default     = "data-pipeline-api"
}

variable "cloud_run_min_instances" {
  description = "Minimum number of Cloud Run instances"
  type        = number
  default     = 1
}

variable "cloud_run_max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 10
}

# Pub/Sub Configuration
variable "pubsub_topic_names" {
  description = "List of Pub/Sub topic names for task queues"
  type        = list(string)
  validation {
    condition     = length(var.pubsub_topic_names) > 0
    error_message = "At least one Pub/Sub topic name must be provided"
  }
}

# Performance and Rate Limiting
variable "api_rate_limit" {
  description = "API rate limit per hour"
  type        = number
  default     = 1000
}

# Monitoring and Observability
variable "enable_monitoring" {
  description = "Enable comprehensive monitoring"
  type        = bool
  default     = true
}

variable "error_rate_threshold" {
  description = "Error rate threshold for alerts"
  type        = number
  default     = 0.01
}

# Data Management
variable "storage_retention_days" {
  description = "Data retention period in days"
  type        = number
  default     = 90
}

variable "backup_enabled" {
  description = "Enable automated backups"
  type        = bool
  default     = true
}

# Security Configuration
variable "ssl_policy" {
  description = "SSL policy for endpoints"
  type        = string
  default     = "MODERN"
  validation {
    condition     = contains(["COMPATIBLE", "MODERN", "RESTRICTED"], var.ssl_policy)
    error_message = "SSL policy must be one of: COMPATIBLE, MODERN, RESTRICTED"
  }
}