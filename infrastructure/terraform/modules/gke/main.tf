# Provider and version requirements
terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

# Local variables for environment-specific configurations
locals {
  # Cluster labels for resource management and tracking
  cluster_labels = {
    environment     = terraform.workspace
    managed-by     = "terraform"
    component      = "data-processing-pipeline"
    created-by     = "terraform"
    last-modified  = timestamp()
  }

  # Environment-specific node pool configurations
  node_pools = {
    development = {
      machine_type = "e2-standard-2"
      min_count    = 1
      max_count    = 3
    }
    staging = {
      machine_type = "e2-standard-4"
      min_count    = 2
      max_count    = 5
    }
    production = {
      machine_type = "e2-standard-8"
      min_count    = 3
      max_count    = 10
    }
  }
}

# Primary GKE cluster resource
resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  project  = var.project_id
  location = var.region
  
  # Network configuration
  network    = var.network
  subnetwork = var.subnetwork

  # Cluster version and initial configuration
  min_master_version = var.kubernetes_version
  remove_default_node_pool = true
  initial_node_count = 1

  # Workload identity configuration for enhanced security
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Maintenance window configuration for minimal disruption
  maintenance_policy {
    recurring_window {
      start_time = var.maintenance_start_time
      end_time   = var.maintenance_end_time
      recurrence = var.maintenance_recurrence
    }
  }

  # Network policy configuration for pod-to-pod communication
  network_policy {
    enabled  = true
    provider = "CALICO"
  }

  # Private cluster configuration for enhanced security
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block = "172.16.0.0/28"  # Master nodes CIDR
  }

  # Release channel configuration for version updates
  release_channel {
    channel = "REGULAR"
  }

  # Cluster add-ons configuration
  addons_config {
    http_load_balancing {
      disabled = false
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
    network_policy_config {
      disabled = false
    }
  }

  # IP allocation policy for VPC-native cluster
  ip_allocation_policy {
    cluster_ipv4_cidr_block  = "/16"
    services_ipv4_cidr_block = "/22"
  }

  # Cluster security configuration
  master_auth {
    client_certificate_config {
      issue_client_certificate = false
    }
  }
}

# Environment-specific node pool
resource "google_container_node_pool" "primary_nodes" {
  name       = "${var.cluster_name}-node-pool-${terraform.workspace}"
  location   = var.region
  cluster    = google_container_cluster.primary.name
  
  # Initial node count and autoscaling configuration
  initial_node_count = local.node_pools[terraform.workspace].min_count
  
  autoscaling {
    min_node_count = local.node_pools[terraform.workspace].min_count
    max_node_count = local.node_pools[terraform.workspace].max_count
  }

  # Node pool management configuration
  management {
    auto_repair  = true
    auto_upgrade = true
  }

  # Upgrade settings for minimal disruption
  upgrade_settings {
    max_surge       = 1
    max_unavailable = 0
  }

  # Node configuration
  node_config {
    machine_type = local.node_pools[terraform.workspace].machine_type
    disk_size_gb = var.disk_size_gb
    disk_type    = "pd-ssd"

    # Service account and OAuth scope configuration
    service_account = var.service_account
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Workload identity and metadata configuration
    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    # Node labels
    labels = local.cluster_labels

    # Metadata configuration
    metadata = {
      disable-legacy-endpoints = "true"
    }

    # Shielded instance configuration for enhanced security
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    # Tags for network management
    tags = ["gke-node", var.cluster_name]
  }

  # Depends on the cluster being created first
  depends_on = [
    google_container_cluster.primary
  ]
}

# Output the cluster endpoint and name
output "cluster_endpoint" {
  value       = google_container_cluster.primary.endpoint
  description = "The IP address of the cluster master"
}

output "cluster_name" {
  value       = google_container_cluster.primary.name
  description = "The name of the cluster"
}