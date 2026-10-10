import argparse
import json
from pathlib import Path


def estimate(conversations, turns=10, input_tokens=5000, output_tokens=600, seconds=10, free_tier=True):
    requests = conversations * turns
    compute_hours = requests * seconds / 3600
    memory_hours = compute_hours * 4
    model = requests * (input_tokens * .25 + output_tokens * 1.5) / 1_000_000
    runtime = max(0, compute_hours - (50 if free_tier else 0)) * .085 + max(0, memory_hours - (100 if free_tier else 0)) * .009
    return {'conversations': conversations, 'model_usd': round(model, 4), 'runtime_usd': round(runtime, 4),
            'model_and_runtime_usd': round(model + runtime, 4), 'compute_hours': round(compute_hours, 3), 'memory_gib_hours': round(memory_hours, 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--usage-report', help='JSON with successful_turns, input_tokens, output_tokens, total_seconds')
    args = parser.parse_args()
    assumptions = {'input_tokens': 5000, 'output_tokens': 600, 'seconds': 10}
    basis = 'Planning assumptions; use --usage-report for measured evaluation costs'
    if args.usage_report:
        report = json.loads(Path(args.usage_report).read_text())
        count = report['successful_turns']
        if not count:
            raise SystemExit('No successful turns to measure')
        assumptions = {'input_tokens': report['input_tokens']/count, 'output_tokens': report['output_tokens']/count, 'seconds': report['total_seconds']/count}
        basis = 'Measured successful evaluation turns; failed attempts may add cost'
    result = {'checked_on': '2026-10-09', 'basis': basis, 'assumptions_per_message': assumptions,
              'with_available_free_tier': [estimate(n, **assumptions) for n in (0, 100, 1000, 10000)],
              'without_available_free_tier': [estimate(n, free_tier=False, **assumptions) for n in (0,100,1000)],
              'bounded_model_maximum_1000_turns_usd': round(1000*(12000*.25+1800*1.5)/1_000_000,2),
              'exclusions': ['Cloud Run gateway', 'hosting bandwidth', 'storage and embeddings', 'build and registry', 'logging', 'tax', 'existing project services']}
    Path('reports').mkdir(exist_ok=True)
    Path('reports/cost-estimate.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
