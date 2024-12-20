# Production GCP Project Configuration
# Version: 1.0.0
# Provider Requirements:
# - hashicorp/google ~> 4.0
# - hashicorp/google-beta ~> 4.0

# Project and Environment Identification
project_id  = "data-pipeline-prod"
environment = "prod"

# Regional Configuration
# Primary region for production deployment with multi-region capabilities
region = "us-central1"

# Google Kubernetes Engine (GKE) Configuration
# Production cluster with high availability and auto-scaling
gke_cluster_name = "data-pipeline-prod-cluster"
gke_node_count   = 5  # Base node count for production workload

# Cloud Storage Configuration
# Separate buckets for different data processing stages
storage_bucket_names = [
  "data-pipeline-prod-raw",       # Raw data storage
  "data-pipeline-prod-processed", # Processed data storage
  "data-pipeline-prod-archive"    # Archived data storage
]

# Cloud Run Configuration
# High-availability setup with auto-scaling capabilities
cloud_run_service_name  = "data-pipeline-prod-api"
cloud_run_min_instances = 3   # Ensures high availability
cloud_run_max_instances = 20  # Handles peak load conditions

# Pub/Sub Topics Configuration
# Message queues for different task types
pubsub_topic_names = [
  "data-pipeline-prod-scraping-tasks", # Web scraping task queue
  "data-pipeline-prod-ocr-tasks",      # OCR processing task queue
  "data-pipeline-prod-dlq"             # Dead letter queue for failed tasks
]

# API Configuration
# Production rate limiting and security settings
api_rate_limit = 1000  # Requests per hour per client
ssl_policy     = "RESTRICTED"  # Strict SSL/TLS policy

# Monitoring and Alerting Configuration
enable_monitoring     = true
error_rate_threshold = 0.001  # 0.1% error rate threshold

# Data Management Configuration
storage_retention_days = 90  # Compliance with data retention policies
backup_enabled        = true  # Automated backup for disaster recovery