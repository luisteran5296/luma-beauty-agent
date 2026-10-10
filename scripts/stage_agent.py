"""Copy the shared library into the scaffold Docker context before build/deploy."""
import shutil
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    source, target = root / 'beauty', root / 'agent' / 'beauty'
    shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
    print('Staged shared catalog library into agent/beauty')


if __name__ == '__main__':
    main()
