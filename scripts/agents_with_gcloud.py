"""Run agents-cli with the explicitly selected, keyless gcloud identity.

Local release tooling only. Does not alter ADC files or persist access tokens.
"""
import os
from pathlib import Path
import google.auth
from beauty.cloud import GcloudCredentials


def main():
    if not os.getenv('GCLOUD_ACCOUNT'):
        raise SystemExit('Set GCLOUD_ACCOUNT explicitly for release operations')
    selected = GcloudCredentials.create()
    # Both the CLI and its Agent Platform SDK resolve ADC in this process.
    # Bind that lookup to the requested identity without changing machine ADC.
    google.auth.default = lambda *args, **kwargs: (selected, 'sitiosweb1')
    os.chdir(Path(__file__).resolve().parents[1] / 'agent')
    from google.agents.cli.main import main as cli
    cli()


if __name__ == '__main__': main()
