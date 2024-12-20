# Output definitions for the Google Cloud Pub/Sub module
# Terraform version: >= 1.0.0
# Provider: hashicorp/google ~> 4.0

# Main task topic outputs
output "task_topic_id" {
  description = "The unique identifier of the main task distribution topic"
  value       = google_pubsub_topic.task_topic.id
}

output "task_topic_name" {
  description = "The name of the main task distribution topic"
  value       = google_pubsub_topic.task_topic.name
}

# Task subscription outputs
output "scraping_subscription_id" {
  description = "The unique identifier of the web scraping task subscription"
  value       = google_pubsub_subscription.scraping_subscription.id
}

output "ocr_subscription_id" {
  description = "The unique identifier of the OCR processing task subscription"
  value       = google_pubsub_subscription.ocr_subscription.id
}

# Dead letter queue outputs
output "dead_letter_topic_id" {
  description = "The unique identifier of the dead letter queue topic"
  value       = google_pubsub_topic.dead_letter_topic.id
}