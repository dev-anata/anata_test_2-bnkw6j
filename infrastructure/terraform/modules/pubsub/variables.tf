# Core Terraform and provider configuration
# hashicorp/terraform >= 1.0.0
# hashicorp/google ~> 4.0
terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

# Project configuration variables
variable "project_id" {
  description = "GCP project ID where Pub/Sub resources will be created"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Project ID must be between 6 and 30 characters, and contain only lowercase letters, numbers, and hyphens"
  }
}

variable "region" {
  description = "GCP region for Pub/Sub resource deployment"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment identifier"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod"
  }
}

# Topic configuration variables
variable "task_topic_name" {
  description = "Name of the main Pub/Sub topic for task distribution"
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-_.~+%]{2,254}$", var.task_topic_name))
    error_message = "Topic name must be between 3 and 255 characters and match the required pattern"
  }
}

variable "message_retention_duration" {
  description = "Duration to retain unacknowledged messages in the topic"
  type        = string
  default     = "604800s" # 7 days
}

# Subscription configuration variables
variable "subscription_ack_deadline_seconds" {
  description = "Acknowledgment deadline in seconds for each subscription type"
  type        = map(number)
  default = {
    scraping   = 600  # 10 minutes for web scraping tasks
    ocr        = 900  # 15 minutes for OCR processing
    processing = 300  # 5 minutes for general processing
    monitoring = 60   # 1 minute for monitoring tasks
  }
}

variable "subscription_message_retention" {
  description = "Duration to retain undelivered messages in subscriptions"
  type        = string
  default     = "604800s" # 7 days
}

# Retry and error handling configuration
variable "retry_policy" {
  description = "Retry policy configuration for message delivery"
  type = object({
    minimum_backoff    = string
    maximum_backoff    = string
    maximum_doublings  = number
  })
  default = {
    minimum_backoff   = "10s"
    maximum_backoff   = "600s"  # 10 minutes
    maximum_doublings = 5
  }
}

variable "max_delivery_attempts" {
  description = "Maximum delivery attempts before message is sent to dead letter queue"
  type        = number
  default     = 5

  validation {
    condition     = var.max_delivery_attempts >= 5 && var.max_delivery_attempts <= 100
    error_message = "Maximum delivery attempts must be between 5 and 100"
  }
}

variable "enable_message_ordering" {
  description = "Enable message ordering for task processing sequence"
  type        = bool
  default     = true
}

# Dead Letter Queue configuration
variable "dead_letter_topic_name" {
  description = "Name of the dead letter topic for failed messages"
  type        = string
  default     = "dlq-failed-tasks"
}

# Resource labeling
variable "labels" {
  description = "Labels to apply to all Pub/Sub resources"
  type        = map(string)
  default = {
    managed-by = "terraform"
    component  = "task-queue"
  }
}