"""Identical scenarios across repeat runs; first process turn is a cold proxy, not a cloud cold start."""
import argparse
import asyncio
import json
import math
import logging
import time
from contextvars import ContextVar
from unittest.mock import patch
from pathlib import Path
from agent.app.shopping import respond
from beauty.catalog import get_catalog
from beauty.telemetry import logger
from scripts.evaluate_shopping import SCENARIOS
from agent.app.agent import evidence as original_evidence


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values)*fraction)-1)] if values else None


async def run(args):
    records = []
    class Capture(logging.Handler):
        def emit(self, record): records.append(json.loads(record.getMessage()))
    original_handlers = logger.handlers[:]
    logger.handlers = [Capture()]
    logger.disabled = False
    startup = time.monotonic()
    catalog = get_catalog()
    startup_seconds = time.monotonic()-startup
    turns = []
    active_evidence = ContextVar('benchmark_evidence',default=None)
    def capture_evidence(product):
        ids = active_evidence.get()
        if ids is not None: ids.add(product.id)
        return original_evidence(product)
    semaphore = asyncio.Semaphore(args.concurrency)
    async def scenario(index, messages):
        history = []
        async with semaphore:
            for prompt in messages:
                started = time.monotonic()
                ids = set()
                active_evidence.set(ids)
                async for event in respond({'message':prompt,'history':history,'catalog_version':catalog.version}):
                    if event['type'] != 'result': continue
                    turns.append({'case':index,'prompt':prompt,'answer':event['answer'],
                        'seconds':time.monotonic()-started,'usage':event['usage'],
                        'evidence':[catalog.products[pid].public() for pid in sorted(ids)],
                        'product_ids':event['product_ids'],'model_calls':event['model_calls'],'tool_calls':event['tool_calls']})
                    history.extend([{'role':'user','text':prompt},{'role':'assistant','text':event['answer'],'product_ids':event['product_ids']}])
    # First scenario is run separately to identify process initialization overhead.
    with patch('agent.app.agent.evidence',capture_evidence):
        await scenario(0,SCENARIOS[0])
        await asyncio.gather(*(scenario(i,messages) for i,messages in enumerate(SCENARIOS[1:],1)))
    warm = [t['seconds'] for t in turns[1:]]
    report = {'catalog_version':catalog.version,'concurrency':args.concurrency,'turns':turns,
        'catalog_startup_seconds':startup_seconds,
        'process_first_turn_seconds':turns[0]['seconds'], 'warm_p50_seconds':percentile(warm,.5),
        'warm_p95_seconds':percentile(warm,.95), 'cloud_cold_start_measured':False,
        'warm_target_passed':percentile(warm,.95)<30}
    operations = sorted({r['operation'] for r in records if r.get('event')=='operation'})
    report['component_seconds'] = {op: {'calls':len(values), 'total':sum(values), 'p95':percentile(values,.95)}
        for op in operations if (values := [r['duration_seconds'] for r in records if r.get('event')=='operation' and r.get('operation')==op])}
    report['metadata_records'] = len(records)
    report['metadata_bytes'] = sum(len(json.dumps(r).encode()) for r in records)
    logger.handlers = original_handlers
    Path(args.output).write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='turns'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--concurrency',type=int,choices=[1,2],default=1)
    parser.add_argument('--output',default='reports/hardening-benchmark.json')
    asyncio.run(run(parser.parse_args()))
