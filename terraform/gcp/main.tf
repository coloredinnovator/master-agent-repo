# ============================================
# HERMES ECOSYSTEM — Google Cloud Platform
# ============================================
# This Terraform configuration provisions the
# entire GCP infrastructure for the Hermes agent.
# Designed to pass Cloud Inspector audits.
# ============================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "hermes-terraform-state"
    prefix = "gcp"
  }
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ==========================================
# Enable Required APIs
# ==========================================
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "container.googleapis.com",
    "artifactregistry.googleapis.com",
    "sqladmin.googleapis.com",
  ])
  project = var.project_id
  service = each.value

  disable_dependent_services = false
  disable_on_destroy         = false
}

# ==========================================
# Service Account (Least Privilege)
# ==========================================
resource "google_service_account" "hermes" {
  account_id   = "hermes-agent-sa"
  display_name = "Hermes Agent Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "hermes_roles" {
  for_each = toset([
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/storage.objectAdmin",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.hermes.email}"
}

# ==========================================
# Cloud Storage Bucket
# ==========================================
resource "google_storage_bucket" "cleanup" {
  name                        = "${var.project_id}-hermes-cleanup"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ==========================================
# BigQuery Dataset
# ==========================================
resource "google_bigquery_dataset" "hermes" {
  dataset_id                 = "hermes_data"
  friendly_name              = "Hermes Agent Data"
  location                   = var.region
  delete_contents_on_destroy = false

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ==========================================
# Artifact Registry (Docker Images)
# ==========================================
resource "google_artifact_registry_repository" "hermes" {
  location      = var.region
  repository_id = "hermes-images"
  format        = "DOCKER"

  labels = {
    environment = var.environment
  }

  depends_on = [google_project_service.apis]
}

# ==========================================
# Cloud Run Service
# ==========================================
resource "google_cloud_run_v2_service" "hermes" {
  name     = "hermes-agent"
  location = var.region

  template {
    service_account = google_service_account.hermes.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.hermes.repository_id}/hermes-agent:latest"

      ports {
        container_port = 8080
      }

      env {
        name  = "PORT"
        value = "8080"
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.cleanup.name
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "LLM_PROVIDER"
        value = "ollama"
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 10
        period_seconds        = 3
        failure_threshold     = 10
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        period_seconds = 30
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
  }

  depends_on = [google_project_service.apis]
}

# ==========================================
# Cloud Run IAM (Public or Private)
# ==========================================
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  name     = google_cloud_run_v2_service.hermes.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers" # Change to specific SA for private access
}

# ==========================================
# Monitoring Alert Policy
# ==========================================
resource "google_monitoring_alert_policy" "hermes_errors" {
  display_name = "Hermes Agent Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run 5xx Error Rate"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"hermes-agent\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"5xx\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = []
}

# ==========================================
# Outputs
# ==========================================
output "cloud_run_url" {
  value = google_cloud_run_v2_service.hermes.uri
}

output "bucket_name" {
  value = google_storage_bucket.cleanup.name
}

output "bigquery_dataset" {
  value = google_bigquery_dataset.hermes.dataset_id
}

output "service_account_email" {
  value = google_service_account.hermes.email
}
