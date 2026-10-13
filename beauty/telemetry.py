"""Metadata-only OpenTelemetry and structured metrics; never export content."""
import contextvars
import json
import logging
import os
import time
import threading
import random
from collections import OrderedDict
from contextlib import contextmanager
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult, BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.sampling import ParentBased, Sampler, SamplingResult, Decision
from opentelemetry.trace import Status, StatusCode

request_id = contextvars.ContextVar('support_request_id', default='')
request_started = contextvars.ContextVar('request_started', default=0.)
FIELDS = frozenset({'event', 'operation', 'outcome', 'duration_seconds', 'first_status_seconds',
    'input_tokens', 'output_tokens', 'model_cost_usd', 'tool_calls', 'model_calls',
    'quota_conversations', 'quota_turns', 'cache_hit', 'error_type', 'revision', 'request_id'})
ATTRS = frozenset({'gen_ai.operation.name', 'gen_ai.request.model', 'gen_ai.response.model',
    'gen_ai.usage.input_tokens', 'gen_ai.usage.output_tokens', 'gen_ai.tool.name',
    'gen_ai.system', 'luma.operation', 'luma.outcome', 'luma.catalog_version', 'luma.cache_hit',
    'gcp.vertex.agent.name', 'gcp.vertex.agent.engine_id'})
RESOURCES = frozenset({'service.name', 'service.version', 'cloud.provider', 'cloud.account.id',
    'cloud.region', 'gcp.vertex.agent.engine_id', 'gcp.resource_type', 'gcp.resource_container',
    'gcp.resource.location', 'gcp.resource.reasoning_engine_id', 'cloud.platform', 'cloud.resource_id',
    'gcp.project_id', 'gen_ai.agent.name'})
logger = logging.getLogger('luma.metrics')
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.propagate = False
_provider = None
_service = None


def emit(event, **values):
    try:
        payload = {k: v for k, v in {'event': event, **values}.items() if k in FIELDS}
        payload['revision'] = os.getenv('K_REVISION', os.getenv('LUMA_REVISION', 'local'))
        payload['luma_service'] = 'agent' if _service=='luma-agent' or os.getenv('GOOGLE_CLOUD_AGENT_ENGINE_ID') else 'gateway'
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            project = os.getenv('GOOGLE_CLOUD_PROJECT', 'sitiosweb1')
            payload['logging.googleapis.com/trace'] = f'projects/{project}/traces/{context.trace_id:032x}'
            payload['logging.googleapis.com/spanId'] = f'{context.span_id:016x}'
            payload['logging.googleapis.com/trace_sampled'] = context.trace_flags.sampled
        if request_id.get():
            payload['request_id'] = request_id.get()
        logger.info(json.dumps(payload))
    except Exception:
        pass  # Observability cannot break an admitted shopping turn.


class RootSampler(Sampler):
    def should_sample(self, parent_context, trace_id, name, kind=None, attributes=None, links=None, trace_state=None):
        return SamplingResult(Decision.RECORD_AND_SAMPLE if (attributes or {}).get('luma.sampled', True) else Decision.DROP)

    def get_description(self):
        return 'Luma admitted-chat / sampled-browsing'


class SafeExporter(SpanExporter):
    """Defense in depth even when ADK/provider spans accidentally capture content."""
    def __init__(self, exporter):
        self.exporter = exporter

    def export(self, spans):
        safe = []
        for item in spans:
            attrs = {k: v for k, v in item.attributes.items() if k in ATTRS}
            if attrs.get('gen_ai.tool.name') not in (None, 'search_products', 'get_product'):
                attrs.pop('gen_ai.tool.name', None)
            name = item.name if item.name.startswith('luma.') else 'adk.' + str(attrs.get('gen_ai.operation.name', 'operation'))
            safe.append(ReadableSpan(name=name, context=item.context, parent=item.parent,
                resource=Resource({k: v for k, v in item.resource.attributes.items() if k in RESOURCES}),
                attributes=attrs, events=(), links=(), kind=item.kind,
                status=Status(item.status.status_code), start_time=item.start_time, end_time=item.end_time))
        try:
            return self.exporter.export(safe)
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self):
        try:
            self.exporter.shutdown()
        except Exception:
            pass


class AdmissionProcessor(SpanProcessor):
    """Bounded gateway tail admission: all admitted chats, 10% other requests.

    Private runtime descendants are already admitted and export immediately.
    Overflow drops telemetry only; conversation execution never depends on it.
    """
    def __init__(self, downstream, maximum_traces=128, maximum_spans=128, private_runtime=False):
        self.downstream = downstream
        self.maximum_traces, self.maximum_spans = maximum_traces, maximum_spans
        self.pending = OrderedDict()
        self.lock = threading.Lock()
        self.private_runtime = private_runtime

    def on_start(self, current, parent_context=None):
        self.downstream.on_start(current, parent_context=parent_context)

    def on_end(self, current):
        try:
            if self.private_runtime or current.resource.attributes.get('cloud.platform') == 'gcp_agent_engine':
                self.downstream.on_end(current)
                return
            if current.name == 'luma.request':
                with self.lock:
                    descendants = self.pending.pop(current.context.trace_id, [])
                if current.attributes.get('luma.admitted') or random.random() < .1:
                    for item in [*descendants, current]:
                        self.downstream.on_end(item)
            elif current.parent is None:
                self.downstream.on_end(current)  # startup/local diagnostic spans
            else:
                with self.lock:
                    items = self.pending.setdefault(current.context.trace_id, [])
                    if len(items) < self.maximum_spans:
                        items.append(current)
                    while len(self.pending) > self.maximum_traces:
                        self.pending.popitem(last=False)
        except Exception:
            pass

    def shutdown(self):
        self.downstream.shutdown()

    def force_flush(self, timeout_millis=30000):
        return self.downstream.force_flush(timeout_millis)


def setup(service):
    global _provider, _service
    _service = service
    os.environ['ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS'] = 'false'
    os.environ['OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT'] = 'NO_CONTENT'
    if _provider or os.getenv('GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY', '').lower() != 'true':
        return
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        project = project or 'sitiosweb1'
        session = AuthorizedSession(credentials)
        resource = {'service.name': service, 'service.version': os.getenv('K_REVISION', os.getenv('LUMA_REVISION', 'local')),
            'cloud.provider': 'gcp', 'cloud.account.id': project or 'sitiosweb1', 'cloud.region': 'us-central1'}
        engine = os.getenv('GOOGLE_CLOUD_AGENT_ENGINE_ID') or os.getenv('LUMA_AGENT_ENGINE_ID')
        if engine:
            engine = engine.rsplit('/', 1)[-1]
            resource.update({'service.name': engine, 'cloud.platform': 'gcp_agent_engine',
                'cloud.resource_id': f'//aiplatform.googleapis.com/projects/{project}/locations/us-central1/reasoningEngines/{engine}',
                'gcp.vertex.agent.engine_id': engine, 'gcp.resource_type': 'aiplatform.googleapis.com/ReasoningEngine',
                'gcp.resource_container': f'projects/{project}', 'gcp.resource.location': 'us-central1',
                'gcp.resource.reasoning_engine_id': engine.rsplit('/', 1)[-1]})
        provider = TracerProvider(resource=Resource(resource), sampler=ParentBased(RootSampler()))
        exporter = OTLPSpanExporter(endpoint='https://telemetry.googleapis.com/v1/traces', session=session,
            headers={'x-goog-user-project': project or 'sitiosweb1'}, timeout=5)
        provider.add_span_processor(AdmissionProcessor(BatchSpanProcessor(SafeExporter(exporter)),
            private_runtime=service=='luma-agent'))
        trace.set_tracer_provider(provider)
        _provider = provider
    except Exception as exc:
        emit('telemetry_setup', outcome='failed', error_type=type(exc).__name__)


@contextmanager
def span(operation, **attributes):
    started = time.monotonic()
    with trace.get_tracer('luma').start_as_current_span('luma.' + operation,
            attributes={'luma.operation': operation, **attributes}, record_exception=False,
            set_status_on_exception=False) as current:
        try:
            yield current
        except BaseException as exc:
            current.set_status(Status(StatusCode.ERROR))
            emit('operation', operation=operation, outcome='failed', duration_seconds=time.monotonic()-started,
                error_type=type(exc).__name__)
            raise
        else:
            emit('operation', operation=operation, outcome='ok', duration_seconds=time.monotonic()-started)


def shutdown():
    global _provider
    if _provider:
        try:
            _provider.shutdown()
        except Exception:
            pass
        # A global OpenTelemetry provider cannot be replaced in this process.
