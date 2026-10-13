"""Audit staged public files without printing potential secret values.

This heuristic check complements manual review; it is not a complete secret scanner.
Run after git add and before commit/push.
"""
import re
import subprocess
import sys
from pathlib import PurePosixPath


def main():
    all_files = '--all' in sys.argv
    command = ['git','ls-files','-z'] if all_files else ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM', '-z']
    paths = subprocess.check_output(command).decode().split('\0')
    patterns = {
        'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
        'GitHub token': re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
        'Google access token': re.compile(r'ya29\.[A-Za-z0-9_-]{30,}'),
        'Google API key': re.compile(r'AIza[0-9A-Za-z_-]{35}'),
        'AWS access key': re.compile(r'AKIA[0-9A-Z]{16}'),
        'credential JSON': re.compile(r'"(?:private_key|client_secret)"\s*:\s*"[^"\s]{8,}'),
    }
    issues = []
    for path in filter(None, paths):
        parts = PurePosixPath(path).parts
        name = parts[-1]
        if (name.startswith('.env') and name != '.env.example') or any(
            value in parts for value in ['reports', '.venv', '.terraform', 'node_modules']
        ) or '.tfstate' in name or name.endswith(('.tfplan', '.tfvars', '.pem', '.key')) or name == 'deployment_metadata.json':
            issues.append((path, 'private/generated file'))
        if path.startswith('data/') and not name.endswith('template.csv'):
            issues.append((path, 'downloaded data'))
        content = subprocess.check_output(['git', 'show', ':' + path]).decode('utf-8', errors='replace')
        for label, pattern in patterns.items():
            if pattern.search(content):
                issues.append((path, label))
    for path, label in issues:
        print(f'{path}: {label} (value withheld)')
    if issues:
        raise SystemExit('Public-file audit failed; review findings before publishing.')
    print(f'Public-file audit passed for {sum(bool(path) for path in paths)} staged files.')


if __name__ == '__main__':
    main()
