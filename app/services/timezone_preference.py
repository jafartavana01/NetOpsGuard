"""Independent atomic application preference; no server-local timezone fallback."""
import json
import os
import tempfile
from pathlib import Path
from ..config import CONFIG_DIR
from .schedule_time import validate_zone

PATH = CONFIG_DIR / 'timezone.json'


def load():
    try:
        value = json.loads(PATH.read_text())['timezone']
        if not isinstance(value, str):
            raise ValueError('Invalid saved application timezone.')
        validate_zone(value)
        return value
    except FileNotFoundError:
        return 'UTC'
    # Corrupt preferences are reported, not silently treated as a saved choice.


def save(value):
    validate_zone(value)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.timezone-', dir=PATH.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump({'timezone': value}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, PATH)
    finally:
        Path(name).unlink(missing_ok=True)
