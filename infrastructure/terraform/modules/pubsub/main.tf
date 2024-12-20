# Data Processing Pipeline - Pub/Sub Infrastructure Module
# Terraform configuration for Google Cloud Pub/Sub resources
# Provider version: hashicorp/google ~> 4.0

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

# Main task distribution topic
resource "google_pubsub_topic" "task_topic" {
  name                       = var.task_topic_name
  project                    = var.project_id
  message_retention_duration = var.message_retention_duration
  
  # Enable message ordering for maintaining task sequence
  message_storage_policy {
    allowed_persistence_regions = [
      var.region
    ]
  }
  
  labels = merge(var.labels, {
    purpose = "task-distribution"
  })
}

# Dead Letter Queue (DLQ) topic for failed message handling
resource "google_pubsub_topic" "dead_letter_topic" {
  name    = "${var.task_topic_name}-dlq"
  project = var.project_id
  
  message_storage_policy {
    allowed_persistence_regions = [
      var.region
    ]
  }
  
  labels = merge(var.labels, {
    purpose = "dead-letter-queue"
  })
}

# Subscription for web scraping tasks
resource "google_pubsub_subscription" "scraping_subscription" {
  name    = "scraping-subscription"
  topic   = google_pubsub_topic.task_topic.name
  project = var.project_id

  # Configure acknowledgment deadline based on task type
  ack_deadline_seconds = var.subscription_ack_deadline_seconds["scraping"]

  # Message retention for unacknowledged messages
  message_retention_duration = var.subscription_message_retention

  # Configure exponential backoff retry policy
  retry_policy {
    minimum_backoff = var.retry_policy.minimum_backoff
    maximum_backoff = var.retry_policy.maximum_backoff
    maximum_doublings = var.retry_policy.maximum_doublings
  }

  # Dead letter policy for handling failed messages
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter_topic.id
    max_delivery_attempts = var.max_delivery_attempts
  }

  # Enable message ordering for sequential processing
  enable_message_ordering = true

  labels = merge(var.labels, {
    subscription-type = "scraping"
    purpose          = "web-scraping"
  })
}

# Subscription for OCR processing tasks
resource "google_pubsub_subscription" "ocr_subscription" {
  name    = "ocr-subscription"
  topic   = google_pubsub_topic.task_topic.name
  project = var.project_id

  # Configure acknowledgment deadline based on task type
  ack_deadline_seconds = var.subscription_ack_deadline_seconds["ocr"]

  # Message retention for unacknowledged messages
  message_retention_duration = var.subscription_message_retention

  # Configure exponential backoff retry policy
  retry_policy {
    minimum_backoff = var.retry_policy.minimum_backoff
    maximum_backoff = var.retry_policy.maximum_backoff
    maximum_doublings = var.retry_policy.maximum_doublings
  }

  # Dead letter policy for handling failed messages
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter_topic.id
    max_delivery_attempts = var.max_delivery_attempts
  }

  # Enable message ordering for sequential processing
  enable_message_ordering = true

  labels = merge(var.labels, {
    subscription-type = "ocr"
    purpose          = "document-processing"
  })
}

# IAM policy for the task topic
resource "google_pubsub_topic_iam_policy" "task_topic_policy" {
  project = var.project_id
  topic   = google_pubsub_topic.task_topic.name
  policy_data = data.google_iam_policy.pubsub_topic_policy.policy_data
}

# IAM policy data for Pub/Sub topic
data "google_iam_policy" "pubsub_topic_policy" {
  binding {
    role = "roles/pubsub.publisher"
    members = [
      "serviceAccount:${var.project_id}@appspot.gserviceaccount.com",
    ]
  }

  binding {
    role = "roles/pubsub.subscriber"
    members = [
      "serviceAccount:${var.project_id}@appspot.gserviceaccount.com",
    ]
  }
}

# IAM policy for the DLQ topic
resource "google_pubsub_topic_iam_policy" "dlq_topic_policy" {
  project = var.project_id
  topic   = google_pubsub_topic.dead_letter_topic.name
  policy_data = data.google_iam_policy.pubsub_dlq_policy.policy_data
}

# IAM policy data for DLQ topic
data "google_iam_policy" "pubsub_dlq_policy" {
  binding {
    role = "roles/pubsub.publisher"
    members = [
      "serviceAccount:${var.project_id}@appspot.gserviceaccount.com",
    ]
  }
}