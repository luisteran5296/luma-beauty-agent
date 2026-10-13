"""Generate the versioned Cloud Monitoring dashboard; no cloud writes."""
import json
from pathlib import Path


def chart(title, metric, aligner='ALIGN_SUM', operation=None):
    filter_value = f'metric.type="logging.googleapis.com/user/luma_{metric}"'
    if operation:
        filter_value += f' AND metric.label.operation="{operation}"'
    return {'title': title, 'xyChart': {'dataSets': [{'timeSeriesQuery': {'timeSeriesFilter': {
        'filter': filter_value, 'aggregation': {'alignmentPeriod': '300s', 'perSeriesAligner': aligner}}},
        'plotType': 'LINE'}], 'yAxis': {'scale': 'LINEAR'}}}


def dashboard():
    widgets = [chart('Completed turns', 'completed'), chart('Internal failures / cancelled streams', 'failed'),
        chart('Completion p50 (seconds)', 'latency', 'ALIGN_PERCENTILE_50'),
        chart('Completion p95 (seconds)', 'latency', 'ALIGN_PERCENTILE_95'),
        chart('First status p95 (seconds)', 'first_status', 'ALIGN_PERCENTILE_95'),
        chart('Input tokens per turn', 'input_tokens', 'ALIGN_MEAN'),
        chart('Output tokens per turn', 'output_tokens', 'ALIGN_MEAN'),
        chart('Estimated model USD per turn (not billing)', 'model_cost', 'ALIGN_MEAN'),
        chart('Monthly conversations, sampled high-water level', 'quota_conversations', 'ALIGN_PERCENTILE_99'),
        chart('Monthly turns, sampled high-water level', 'quota_turns', 'ALIGN_PERCENTILE_99'),
        chart('Grounding guards', 'guards'), chart('Expected chat rejections', 'rejected')]
    widgets += [chart(f'{operation} p95 (seconds)', 'operation_latency', 'ALIGN_PERCENTILE_95', operation)
        for operation in ['model', 'embedding', 'retrieval', 'token_count', 'credentials', 'history_persistence']]
    for name in ['cpu', 'memory']:
        widgets.append({'title': f'Gateway {name} utilization', 'xyChart': {'dataSets': [{'timeSeriesQuery': {
            'timeSeriesFilter': {'filter': f'metric.type="run.googleapis.com/container/{name}/utilizations" AND resource.type="cloud_run_revision" AND resource.label.service_name="beauty-store-api"',
            'aggregation': {'alignmentPeriod': '300s', 'perSeriesAligner': 'ALIGN_PERCENTILE_95'}}}, 'plotType': 'LINE'}]}})
    for name in ['cpu/allocation_time', 'memory/allocation_time', 'request_count', 'request_latencies']:
        widgets.append({'title': f'Agent Runtime {name}', 'xyChart': {'dataSets': [{'timeSeriesQuery': {
            'timeSeriesFilter': {'filter': f'metric.type="aiplatform.googleapis.com/reasoning_engine/{name}" AND resource.label.reasoning_engine_id="4860633318019825664"',
            'aggregation': {'alignmentPeriod': '300s', 'perSeriesAligner':
                'ALIGN_PERCENTILE_95' if name=='request_latencies' else 'ALIGN_SUM'}}}, 'plotType': 'LINE'}]}})
    widgets.append({'title': 'Correlated turn metrics (token totals / cost inputs in structured JSON)',
        'logsPanel': {'filter': 'jsonPayload.event="chat_completed"', 'resourceNames': ['projects/sitiosweb1']}})
    return {'displayName': 'Luma agent · performance, reliability, security and cost',
        'gridLayout': {'columns': '2', 'widgets': widgets}}


if __name__ == '__main__':
    Path('infra/luma-dashboard.json').write_text(json.dumps(dashboard(), indent=2)+'\n')
