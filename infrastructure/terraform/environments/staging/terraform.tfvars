# Core Configuration
# -----------------
# Project and environment identifiers
project_id = "data-pipeline-staging"
environment = "staging"
region = "us-central1"

# GKE Configuration
# ----------------
# Staging cluster with production-like setup but reduced capacity
gke_cluster_name = "data-pipeline-staging-cluster"
gke_node_count = 3  # Reduced capacity compared to production

# Storage Configuration
# --------------------
# GCS buckets for staging data with appropriate naming
storage_bucket_names = [
  "data-pipeline-staging-raw",
  "data-pipeline-staging-processed"
]
storage_retention_days = 30  # Shorter retention for staging

# Cloud Run Configuration
# ----------------------
# API service with balanced capacity for staging workloads
cloud_run_service_name = "data-pipeline-staging-api"
cloud_run_min_instances = 2  # Minimum instances for high availability
cloud_run_max_instances = 5  # Maximum instances for cost control

# Pub/Sub Configuration
# --------------------
# Message queues for task processing
pubsub_topic_names = [
  "staging-scraping-tasks",
  "staging-ocr-tasks"
]

# Performance and Security Configuration
# ------------------------------------
# Reduced rate limits and relaxed thresholds for staging
api_rate_limit = 500  # Requests per hour
error_rate_threshold = 0.02  # 2% error rate threshold
ssl_policy = "MODERN"  # Strong but compatible SSL policy

# Monitoring and Backup Configuration
# ---------------------------------
# Full monitoring enabled for staging validation
enable_monitoring = true
backup_enabled = true  # Enable backups for data safety