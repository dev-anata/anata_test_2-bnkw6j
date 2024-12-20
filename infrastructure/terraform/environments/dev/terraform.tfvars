# Terraform variables for Data Processing Pipeline Development Environment
# Version: 1.0.0
# Provider versions:
# - hashicorp/google ~> 4.0
# - hashicorp/google-beta ~> 4.0

# Project Configuration
project_id = "data-pipeline-dev"
environment = "dev"
region = "us-central1"

# GKE Configuration
gke_cluster_name = "data-pipeline-dev-cluster"
gke_node_count = 2

# Storage Configuration
storage_bucket_names = [
  "data-pipeline-dev-raw",
  "data-pipeline-dev-processed"
]
storage_retention_days = 30
backup_enabled = false

# Cloud Run Configuration
cloud_run_service_name = "data-pipeline-dev-api"
cloud_run_min_instances = 1
cloud_run_max_instances = 5

# Pub/Sub Configuration
pubsub_topic_names = [
  "data-pipeline-dev-tasks",
  "data-pipeline-dev-notifications"
]

# API Configuration
api_rate_limit = 1000  # requests per hour
ssl_policy = "MODERN"

# Monitoring Configuration
enable_monitoring = true
error_rate_threshold = 0.02  # 2% error rate threshold for development