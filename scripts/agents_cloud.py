"""Run official agents-cli using the explicitly authorized gcloud account."""
import os
from pathlib import Path
import sys
import google.auth
from beauty.cloud import GcloudCredentials

credential = GcloudCredentials.create()
credential._quota_project_id = 'sitiosweb1'
google.auth.default = lambda *args, **kwargs: (credential, 'sitiosweb1')
os.environ['GOOGLE_CLOUD_PROJECT'] = 'sitiosweb1'
os.environ['GOOGLE_CLOUD_QUOTA_PROJECT'] = 'sitiosweb1'
os.chdir(Path(__file__).resolve().parents[1] / 'agent')
from google.agents.cli.main import main
main()
