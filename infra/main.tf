terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 7.0" }
  }
}
provider "google" {
  project = "sitiosweb1"
  region  = "us-central1"
  billing_project = "sitiosweb1"
  user_project_override = true
}
variable "create_firestore" {
  type        = bool
  default     = false
  description = "Set true only after confirming that no Firestore/Datastore database exists."
}
variable "billing_account" { type = string }
variable "gateway_image" { type = string }
variable "runtime_resource" { type = string }
variable "catalog_version" { type = string }
variable "hosting_origin" { type = string }
locals {
  project = "sitiosweb1"
  bucket  = "sitiosweb1-beauty-store-catalog"
}
resource "google_project_service" "apis" {
  for_each           = toset(["firestore.googleapis.com", "identitytoolkit.googleapis.com", "firebase.googleapis.com", "firebasehosting.googleapis.com", "run.googleapis.com", "aiplatform.googleapis.com", "storage.googleapis.com", "artifactregistry.googleapis.com", "billingbudgets.googleapis.com"])
  project            = local.project
  service            = each.value
  disable_on_destroy = false
}
resource "google_service_account" "agent" {
  account_id   = "beauty-store-agent"
  display_name = "Beauty store agent"
}
resource "google_service_account" "gateway" {
  account_id   = "beauty-store-api"
  display_name = "Beauty store public gateway"
}
resource "google_project_iam_member" "agent_vertex" {
  project = local.project
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent.email}"
}
resource "google_project_iam_member" "gateway_vertex" {
  project = local.project
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.gateway.email}"
}
resource "google_project_iam_member" "gateway_firestore" {
  project = local.project
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.gateway.email}"
}
resource "google_project_iam_member" "agent_firestore" {
  project = local.project
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.agent.email}"
}
resource "google_project_iam_member" "agent_api_usage" {
  project = local.project
  role = "roles/serviceusage.serviceUsageConsumer"
  member = "serviceAccount:${google_service_account.agent.email}"
}
resource "google_project_iam_member" "gateway_api_usage" {
  project = local.project
  role = "roles/serviceusage.serviceUsageConsumer"
  member = "serviceAccount:${google_service_account.gateway.email}"
}
resource "google_project_iam_member" "agent_trace" {
  project = local.project
  role = "roles/cloudtrace.agent"
  member = "serviceAccount:${google_service_account.agent.email}"
}
resource "google_storage_bucket" "catalog" {
  name                        = local.bucket
  location                    = "US-CENTRAL1"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
}
resource "google_storage_bucket_iam_member" "readers" {
  for_each = { agent = google_service_account.agent.email, gateway = google_service_account.gateway.email }
  bucket   = google_storage_bucket.catalog.name
  role     = "roles/storage.objectViewer"
  member   = "serviceAccount:${each.value}"
}
resource "google_firestore_database" "store" {
  count           = var.create_firestore ? 1 : 0
  project         = local.project
  name            = "(default)"
  location_id     = "us-central1"
  type            = "FIRESTORE_NATIVE"
  deletion_policy = "ABANDON"
  depends_on      = [google_project_service.apis]
}
resource "google_artifact_registry_repository" "store" {
  location      = "us-central1"
  repository_id = "beauty-store"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}
resource "google_cloud_run_v2_service" "gateway" {
  name                = "beauty-store-api"
  location            = "us-central1"
  deletion_protection = true
  template {
    service_account                  = google_service_account.gateway.email
    max_instance_request_concurrency = 8
    timeout                          = "100s"
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = var.gateway_image
      resources {
        limits   = { cpu = "1", memory = "512Mi" }
        cpu_idle = true
      }
      env {
        name  = "ENVIRONMENT"
        value = "production"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = local.project
      }
      env {
        name  = "CATALOG_BACKEND"
        value = "firestore"
      }
      env {
        name  = "AGENT_RUNTIME_RESOURCE"
        value = var.runtime_resource
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.hosting_origin
      }
    }
  }
  depends_on = [google_project_service.apis, google_project_iam_member.gateway_firestore, google_project_iam_member.gateway_vertex]
}
resource "google_cloud_run_v2_service_iam_member" "public" {
  location = google_cloud_run_v2_service.gateway.location
  name     = google_cloud_run_v2_service.gateway.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
data "google_project" "store" { project_id = local.project }
resource "google_billing_budget" "store" {
  billing_account = var.billing_account
  display_name    = "Beauty store project MXN180 alerts"
  budget_filter { projects = ["projects/${data.google_project.store.number}"] }
  amount {
    specified_amount {
      currency_code = "MXN"
      units         = "180"
    }
  }
  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 0.8 }
  threshold_rules { threshold_percent = 1.0 }
}
output "gateway_url" { value = google_cloud_run_v2_service.gateway.uri }
output "agent_service_account" { value = google_service_account.agent.email }
output "catalog_bucket" { value = google_storage_bucket.catalog.name }
