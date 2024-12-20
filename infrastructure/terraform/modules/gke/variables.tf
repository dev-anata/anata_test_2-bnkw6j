terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

# Cluster name variable with validation
variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.cluster_name))
    error_message = "Cluster name must be between 6 and 30 characters, containing only lowercase letters, numbers, and hyphens"
  }
}

# Project ID variable with validation
variable "project_id" {
  description = "GCP project ID where the GKE cluster will be created"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Project ID must be between 6 and 30 characters, containing only lowercase letters, numbers, and hyphens"
  }
}

# Region variable with default value
variable "region" {
  description = "GCP region for the GKE cluster"
  type        = string
  default     = "us-central1"
}

# Network configuration variables
variable "network" {
  description = "VPC network name for the GKE cluster"
  type        = string
  default     = "default"
}

variable "subnetwork" {
  description = "VPC subnetwork name for the GKE cluster"
  type        = string
  default     = "default"
}

# Kubernetes version variable
variable "kubernetes_version" {
  description = "Kubernetes version for the GKE cluster"
  type        = string
  default     = "1.27"
}

# Node pool configuration variables
variable "machine_type" {
  description = "Machine type for GKE nodes per environment"
  type        = map(string)
  default = {
    dev     = "e2-standard-2"
    staging = "e2-standard-4"
    prod    = "e2-standard-8"
  }
}

variable "min_node_count" {
  description = "Minimum number of nodes per environment"
  type        = map(number)
  default = {
    dev     = 1
    staging = 2
    prod    = 3
  }
}

variable "max_node_count" {
  description = "Maximum number of nodes per environment"
  type        = map(number)
  default = {
    dev     = 3
    staging = 5
    prod    = 10
  }
}

variable "disk_size_gb" {
  description = "Size of the disk attached to each node"
  type        = number
  default     = 100
}

# Service account configuration
variable "service_account" {
  description = "Service account email for GKE nodes"
  type        = string
}

# Maintenance window configuration
variable "maintenance_start_time" {
  description = "Start time for maintenance window in RFC3339 format"
  type        = string
  default     = "2023-01-01T00:00:00Z"
}

variable "maintenance_end_time" {
  description = "End time for maintenance window in RFC3339 format"
  type        = string
  default     = "2023-01-01T04:00:00Z"
}

variable "maintenance_recurrence" {
  description = "RFC5545 RRULE for cluster maintenance window"
  type        = string
  default     = "FREQ=WEEKLY;BYDAY=SA,SU"
}