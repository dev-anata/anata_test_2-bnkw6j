# Terraform configuration for Cloud Run module outputs
# Provider version: ~> 4.0

terraform {
  required_version = ">= 1.0.0"
}

# Service endpoint URL for external access and service discovery
output "service_url" {
  description = "The fully-qualified URL of the deployed Cloud Run service endpoint for external access and service discovery"
  value       = google_cloud_run_service.cloud_run_service.status[0].url
}

# Unique service identifier for resource referencing
output "service_id" {
  description = "The unique identifier of the Cloud Run service for resource referencing and integration"
  value       = google_cloud_run_service.cloud_run_service.id
}

# Service name for resource identification
output "service_name" {
  description = "The name of the deployed Cloud Run service for resource identification and monitoring"
  value       = google_cloud_run_service.cloud_run_service.name
}

# Deployment region for geographic routing
output "service_location" {
  description = "The GCP region where the service is deployed for geographic routing and disaster recovery"
  value       = google_cloud_run_service.cloud_run_service.location
}

# Latest revision name for deployment tracking
output "latest_revision_name" {
  description = "The name of the latest revision for deployment tracking and zero-downtime updates"
  value       = google_cloud_run_service.cloud_run_service.status[0].latest_created_revision_name
}

# Service status for health monitoring
output "service_status" {
  description = "The current status of the Cloud Run service for health monitoring and deployment validation"
  value       = google_cloud_run_service.cloud_run_service.status[0].conditions
}

# Traffic allocation information for deployment management
output "traffic_allocation" {
  description = "The current traffic allocation configuration for managing zero-downtime deployments"
  value       = google_cloud_run_service.cloud_run_service.traffic
}

# Service IAM configuration for security auditing
output "service_iam" {
  description = "The IAM configuration of the Cloud Run service for security auditing and access control"
  value = {
    invoker_member = "serviceAccount:${var.service_account_email}"
    public_access  = var.allow_unauthenticated
  }
}

# Resource utilization configuration for capacity planning
output "resource_config" {
  description = "The resource configuration of the Cloud Run service for capacity planning and scaling"
  value = {
    cpu_limit    = var.cpu_limit
    memory_limit = var.memory_limit
    min_instances = local.environment_config[var.environment].min_instances
    max_instances = local.environment_config[var.environment].max_instances
  }
}