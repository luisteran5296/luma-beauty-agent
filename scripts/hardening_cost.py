"""Conservative incremental estimate; never a billing cap or allowance assertion."""
import json
from pathlib import Path


def main():
    measurement = json.loads(Path('reports/hardening-components.json').read_text())
    preflight = json.loads(Path('reports/cloud-preflight.json').read_text())
    measured_bytes = measurement['metadata_bytes']/len(measurement['turns'])
    log_gib, metric_mib, spans = .1, 12, 50000
    paid_metadata = log_gib*.5 + metric_mib*.258 + spans*.2/1e6
    uptime_executions = 6*30*24*12
    report = {'as_of':'2026-10-13','currency':'USD','monthly_turn_cap':1000,
        'measured_agent_metadata_bytes_per_turn':measured_bytes,
        'reserved_logs_gib':log_gib,'reserved_metrics_mib':metric_mib,'reserved_spans':spans,
        'metadata_cost_if_account_allowances_exhausted':round(paid_metadata,3),
        'existing_project_uptime_checks':preflight.get('existing_uptime_checks'),
        'observed_uptime_executions_month_to_date':preflight.get('observed_uptime_executions_month_to_date'),
        'new_uptime_executions_monthly':uptime_executions,'uptime_free_project_allowance':1000000,
        'uptime_cost_if_project_allowance_exhausted':uptime_executions*.30/1000,
        'additional_compute_storage_firestore_reserve_usd':.75,
        'expected_incremental_monthly_usd':[0,4],
        'one_off_synthetic_evaluation_reserve_usd':[.25,2],
        'shared_account_allowance_availability_verified':False,
        'actual_candidate_cloud_ingestion_measured':False,
        'sources':['https://cloud.google.com/products/observability/pricing'],
        'notes':['Assumes uptime fits project free allowance; zero existing active checks discovered.',
            'Account-wide trace/metric free usage unverified; estimate includes paid metadata.',
            'Modest browsing; unusual traffic, taxes and unrelated services excluded.',
            'Reconcile after rollout; $5 is a target, not a billing cap.']}
    Path('reports/hardening-cost.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__ == '__main__': main()
