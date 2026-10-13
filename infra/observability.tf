locals {
  luma_counters = {
    completed = "chat_completed"
    failed    = "chat_failed"
    internal  = "chat_failed"
    rejected  = "chat_rejected"
    guards    = "guard_failure"
    started   = "chat_started"
  }
  luma_distributions = {
    latency             = "duration_seconds"
    first_status        = "first_status_seconds"
    input_tokens        = "input_tokens"
    output_tokens       = "output_tokens"
    model_cost          = "model_cost_usd"
    quota_conversations = "quota_conversations"
    quota_turns         = "quota_turns"
    operation_latency   = "duration_seconds"
  }
}

resource "google_project_service" "observability" {
  for_each           = toset(["cloudtrace.googleapis.com", "telemetry.googleapis.com", "monitoring.googleapis.com", "logging.googleapis.com", "agentregistry.googleapis.com"])
  project            = local.project
  service            = each.value
  disable_on_destroy = false
}

resource "google_project_iam_member" "trace_writers" {
  for_each = { agent = google_service_account.agent.email, gateway = google_service_account.gateway.email }
  project  = local.project
  role     = "roles/telemetry.tracesWriter"
  member   = "serviceAccount:${each.value}"
}

resource "google_firestore_field" "session_expiration" {
  for_each   = toset(["beauty_store_sessions", "beauty_store_visitors"])
  project    = local.project
  database   = "(default)"
  collection = each.value
  field      = "expires_at"
  ttl_config {}
}

resource "google_logging_metric" "counts" {
  for_each = local.luma_counters
  project  = local.project
  name     = "luma_${each.key}"
  filter   = "jsonPayload.luma_service=${each.key == "guards" ? "(\"gateway\" OR \"agent\")" : "\"gateway\""} AND jsonPayload.event=\"${each.value}\"${each.key == "internal" ? " AND jsonPayload.outcome=\"internal\"" : ""}"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "distributions" {
  for_each        = local.luma_distributions
  project         = local.project
  name            = "luma_${each.key}"
  filter          = "jsonPayload.luma_service=(\"gateway\" OR \"agent\") AND ${each.key == "operation_latency" ? "jsonPayload.event=\"operation\"" : startswith(each.key, "quota_") ? "jsonPayload.event=\"quota\"" : each.key == "first_status" ? "jsonPayload.event=\"first_status\"" : "jsonPayload.event=\"chat_completed\""}"
  value_extractor = "EXTRACT(jsonPayload.${each.value})"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    dynamic "labels" {
      for_each = each.key == "operation_latency" ? ["operation"] : []
      content { key = labels.value }
    }
  }
  label_extractors = each.key == "operation_latency" ? { operation = "EXTRACT(jsonPayload.operation)" } : {}
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 40
      growth_factor      = 2
      scale              = 0.000001
    }
  }
}

resource "google_monitoring_uptime_check_config" "gateway" {
  project      = local.project
  display_name = "Luma gateway health"
  timeout      = "10s"
  period       = "300s"
  http_check {
    path         = "/health"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }
  monitored_resource {
    type   = "uptime_url"
    labels = { project_id = local.project, host = trimprefix(google_cloud_run_v2_service.gateway.uri, "https://") }
  }
}

resource "google_monitoring_dashboard" "luma" {
  project        = local.project
  dashboard_json = file("${path.module}/luma-dashboard.json")
  depends_on     = [google_logging_metric.counts, google_logging_metric.distributions]
}

resource "google_monitoring_alert_policy" "health" {
  project      = local.project
  display_name = "Luma: three failed five-minute health windows"
  combiner     = "OR"
  conditions {
    display_name = "Sustained failed health checks"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.gateway.uptime_check_id}\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "900s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_FRACTION_TRUE"
        cross_series_reducer = "REDUCE_MIN"
      }
      trigger { count = 1 }
    }
  }
}

resource "google_monitoring_alert_policy" "failures" {
  project      = local.project
  display_name = "Luma: three internal chat failures in 15 minutes"
  combiner     = "OR"
  conditions {
    display_name = "Failed streamed turns"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/luma_internal\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 2
      duration        = "0s"
      aggregations {
        alignment_period     = "900s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
      trigger { count = 1 }
    }
  }
}

resource "google_monitoring_alert_policy" "latency" {
  project      = local.project
  display_name = "Luma: completion p95 above 30s with 20 completed turns/hour"
  combiner     = "AND"
  conditions {
    display_name = "Slow p95"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/luma_latency\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 30
      duration        = "0s"
      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_PERCENTILE_95"
        cross_series_reducer = "REDUCE_MAX"
      }
      trigger { count = 1 }
    }
  }
  conditions {
    display_name = "Enough samples"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/luma_completed\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 19
      duration        = "0s"
      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
      trigger { count = 1 }
    }
  }
}

resource "google_monitoring_alert_policy" "quota" {
  for_each     = { conversations = 80, turns = 800 }
  project      = local.project
  display_name = "Luma: monthly ${each.key} above 80 percent"
  combiner     = "OR"
  conditions {
    display_name = "High quota usage"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/luma_quota_${each.key}\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = each.value
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_PERCENTILE_99"
        cross_series_reducer = "REDUCE_MAX"
      }
      trigger { count = 1 }
    }
  }
}
