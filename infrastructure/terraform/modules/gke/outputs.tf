# Output definitions for the GKE module
# Provider version requirements inherited from main.tf
terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

# Basic cluster information
output "cluster_name" {
  description = "Name of the GKE cluster"
  value       = google_container_cluster.primary.name
}

output "cluster_endpoint" {
  description = "Endpoint for accessing the Kubernetes cluster"
  value       = google_container_cluster.primary.endpoint
}

output "cluster_ca_certificate" {
  description = "Public certificate authority of the cluster"
  value       = google_container_cluster.primary.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "cluster_location" {
  description = "GCP region where the cluster is deployed"
  value       = google_container_cluster.primary.location
}

# Node pool information
output "node_pool_name" {
  description = "Name of the GKE node pool"
  value       = google_container_node_pool.primary_nodes.name
}

# Identity and security configuration
output "workload_identity_config" {
  description = "Workload Identity configuration for GKE cluster"
  value       = google_container_cluster.primary.workload_identity_config[0].workload_pool
}

# Additional cluster details for integration purposes
output "network_config" {
  description = "Network configuration details of the cluster"
  value = {
    network    = google_container_cluster.primary.network
    subnetwork = google_container_cluster.primary.subnetwork
  }
}

output "node_pool_config" {
  description = "Configuration details of the node pool"
  value = {
    machine_type = google_container_node_pool.primary_nodes.node_config[0].machine_type
    disk_size_gb = google_container_node_pool.primary_nodes.node_config[0].disk_size_gb
    disk_type    = google_container_node_pool.primary_nodes.node_config[0].disk_type
  }
}

output "cluster_version" {
  description = "The Kubernetes version of the cluster master"
  value       = google_container_cluster.primary.master_version
}

output "cluster_ipv4_cidr" {
  description = "The IP address range of the Kubernetes pods in this cluster"
  value       = google_container_cluster.primary.ip_allocation_policy[0].cluster_ipv4_cidr_block
}

output "services_ipv4_cidr" {
  description = "The IP address range of the Kubernetes services in this cluster"
  value       = google_container_cluster.primary.ip_allocation_policy[0].services_ipv4_cidr_block
}

output "maintenance_window" {
  description = "Maintenance window configuration of the cluster"
  value = {
    recurring_window = google_container_cluster.primary.maintenance_policy[0].recurring_window
  }
}