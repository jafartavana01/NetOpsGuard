"""Offline installed application metadata, independent of daemon build metadata."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def metadata():
    try:
        version = (ROOT / 'VERSION').read_text().strip()
        if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version):
            raise ValueError('Invalid version')
    except (OSError, ValueError):
        version = 'unavailable'
    commit = None
    try:
        info = json.loads((ROOT / 'installed_release.json').read_text())
        if info.get('version') == version and re.fullmatch(r'[0-9a-f]{40}', info.get('commit', '')):
            commit = info['commit']
    except (OSError, ValueError, TypeError):
        pass
    return {'application': 'NetOpsGuard', 'version': version, 'commit': commit}
