"""Execution-time provenance. No historical evidence is inferred or rewritten."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def config_hash(raw):
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


@lru_cache(maxsize=1)
def engine_revision():
    root = Path(__file__).resolve().parents[1] / 'security_center'
    files = sorted(p for p in root.rglob('*') if p.suffix in {'.py', '.json'})
    return digest([(str(p.relative_to(root)), hashlib.sha256(p.read_bytes()).hexdigest()) for p in files])


def capture(raw, policy, errors):
    # These are necessary capture-envelope checks, not device attestation.
    # Uploads are administrator-supplied evidence for the explicitly selected device.
    reasons = list(errors)
    if not re.search(r'^version\s+\S+', raw, re.M) or not re.search(r'^hostname\s+\S+', raw, re.M):
        reasons.append('configuration_header_missing')
    if not re.search(r'^end\s*$', raw, re.M):
        reasons.append('configuration_end_missing')
    if re.search(r'--\s*More\s*--|^\s*%\s*(?:Invalid|Error|Incomplete|Ambiguous)|\x00', raw, re.M | re.I):
        reasons.append('configuration_capture_error')
    return dict(format=1, engine=engine_revision(), policy=digest(policy), config_hash=config_hash(raw),
                complete=not reasons, reasons=sorted(set(reasons)),
                scope=sorted(set(re.findall(r'^interface\s+(.+?)\s*$', raw, re.M))))


def finding_key(f):
    return (f.domain or '', f.check_id or '', f.interface_name or '', f.correlation_id or '')


def findings_digest(rows):
    values = [(finding_key(f), f.status, f.severity, f.title, f.evidence, f.evidence_label,
               f.detail, f.recommendation, f.fix_command) for f in rows]
    return digest(sorted(values, key=lambda v: json.dumps(v, sort_keys=True)))
