"""Conservative audit comparison, independent of HTTP and scoring algorithms."""
from collections import defaultdict
from dataclasses import dataclass
import json
import math
import re
import uuid

from .audit_evidence import config_hash, finding_key, findings_digest


class ComparisonError(ValueError):
    pass


@dataclass
class Assessment:
    run: object
    findings: list
    provenance: object = None

    @property
    def identity(self):
        recorded = self.provenance.device_identity if self.provenance else None
        current = str(self.run.device_id) if self.run.device_id else None
        if recorded and current and recorded != current:
            return None
        identity = recorded or current
        try:
            return str(uuid.UUID(identity)) if identity else None
        except (ValueError, TypeError, AttributeError):
            return None

    @property
    def manifest(self):
        try:
            value = json.loads(self.provenance.manifest) if self.provenance else {}
            return value if isinstance(value, dict) else {}
        except (ValueError, TypeError):
            return {}

    def problem(self):
        if self.run.status != 'completed':
            return 'Audit did not complete successfully.'
        m = self.manifest
        if m.get('format') != 1 or not all(k in m for k in ('engine', 'policy', 'scope', 'config_hash', 'findings_hash', 'score')):
            return 'Recorded assessment provenance is unavailable; historical evidence cannot establish comparability.'
        if (any(not isinstance(m[k], str) or not re.fullmatch(r'[0-9a-f]{64}', m[k])
                for k in ('engine', 'policy', 'config_hash', 'findings_hash'))
                or not isinstance(m['scope'], list) or not all(isinstance(v, str) and v for v in m['scope'])
                or not isinstance(m.get('reasons'), list)):
            return 'Recorded assessment provenance is malformed.'
        if m.get('complete') is not True or m.get('reasons'):
            return 'Required configuration evidence or assessment coverage is incomplete.'
        if (not self.run.raw_config or config_hash(self.run.raw_config) != m['config_hash']
                or self.run.config_snapshot_hash != m['config_hash']
                or findings_digest(self.findings) != m['findings_hash']):
            return 'Recorded evidence does not match the execution manifest.'
        if any(f.status not in {'pass', 'fail', 'na', 'warn', 'manual_review'} for f in self.findings):
            return 'Assessment contains an error or unsupported observation status.'
        return None

    def grouped(self):
        groups = defaultdict(list)
        for f in self.findings:
            groups[finding_key(f)].append(f)
        for rows in groups.values():
            rows.sort(key=lambda f: str(f.id))
        return groups


def incompatibility(old, new):
    for a in (old, new):
        if reason := a.problem():
            return reason
    a, b = old.manifest, new.manifest
    if a['engine'] != b['engine'] or a['policy'] != b['policy']:
        return 'Check definitions or assessment policy changed.'
    if a['scope'] != b['scope']:
        return 'Assessment scope changed (including removed or renamed interfaces).'
    return None


def validate_pair(old, new):
    if old.run.id == new.run.id:
        raise ComparisonError('Choose two distinct audit executions.')
    if not old.identity or not new.identity:
        raise ComparisonError('Reliable device identity is unavailable for this historical or unattached audit.')
    if old.identity != new.identity:
        raise ComparisonError('Audit comparison requires the same device identity; display names are not identities.')
    # SQLite drops timezone metadata. All persisted audit instants use UTC.
    from datetime import timezone
    def utc(v):
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
    if utc(new.run.started_at) < utc(old.run.started_at):
        raise ComparisonError('The newer audit must not precede the previous audit.')


def score_comparison(old, new):
    try:
        validate_pair(old, new)
    except ComparisonError as exc:
        return None, str(exc)
    if reason := incompatibility(old, new):
        return None, reason
    before, after = old.grouped(), new.grouped()
    if (not before or set(before) != set(after)
            or any(not k[0] or not k[1] for k in before)
            or any(len(v) != 1 for v in [*before.values(), *after.values()])):
        return None, 'Finding coverage differs or contains duplicate identities.'
    for key in before:
        a, b = before[key][0].status, after[key][0].status
        if a != b and not ({a, b} <= {'pass', 'fail'}):
            return None, 'Control applicability or manual assessment coverage changed.'
    scores = [a.run.overall_score for a in (old, new)]
    if any(v is None or not math.isfinite(v) for v in scores):
        return None, 'One or both scores are unavailable.'
    if any(a.manifest['score'] != a.run.overall_score for a in (old, new)):
        return None, 'Recorded score does not match the execution manifest.'
    return round(scores[1] - scores[0], 1), None


def compare(old, new):
    validate_pair(old, new)
    before, after = old.grouped(), new.grouped()
    common_problem = incompatibility(old, new)
    new_problem = new.problem()
    items = []
    for key in sorted(set(before) | set(after)):
        previous, current = before.get(key, []), after.get(key, [])
        statuses = {f.status for f in previous + current}
        if not statuses.intersection({'fail', 'manual_review'}):
            continue
        a = previous[0].status if len(previous) == 1 else None
        b = current[0].status if len(current) == 1 else None
        category = 'indeterminate'
        if len(previous) > 1 or len(current) > 1 or not key[0] or not key[1]:
            reason = 'Finding identity is ambiguous; duplicate records have been retained.'
        elif new_problem:
            reason = new_problem
        elif b == 'manual_review':
            category, reason = 'manual_review', 'Awaiting manual review; no remediation is confirmed.'
            if common_problem:
                reason += ' ' + common_problem
        elif b == 'fail' and (not previous or a not in {'pass', 'fail'} or (a == 'pass' and common_problem)):
            category, reason = 'first_observed', 'Confirmed failure without a comparable prior pass or failure.'
        elif common_problem:
            reason = common_problem
        elif a == 'fail' and b == 'pass':
            category, reason = 'resolved', 'The same control explicitly passed in a complete, comparable assessment.'
        elif a == 'fail' and b == 'fail':
            category, reason = 'persistent', 'The same control failed in both comparable assessments.'
        elif a == 'pass' and b == 'fail':
            category, reason = 'new', 'Confirmed regression from a comparable passing assessment.'
        elif not current:
            reason = 'Check was not evaluated in the newer audit; absence is not remediation.'
        else:
            reason = 'Current result is not a confirmed comparable pass (not applicable, warning, or unavailable).'
        items.append(dict(category=category, reason=reason, key=key, previous=previous, current=current))
    delta, score_reason = score_comparison(old, new)
    return dict(items=items, score_delta=delta, score_reason=score_reason,
                warnings=[common_problem] if common_problem else [])


def load_assessments(db, runs):
    """Two batch queries, including for activity/dashboard comparisons."""
    from ..models.audit_run import AuditAssessment, AuditFinding
    ids = [r.id for r in runs]
    provenance = {p.audit_run_id: p for p in db.query(AuditAssessment).filter(AuditAssessment.audit_run_id.in_(ids)).all()}
    findings = defaultdict(list)
    for f in db.query(AuditFinding).filter(AuditFinding.audit_run_id.in_(ids)).all():
        findings[f.audit_run_id].append(f)
    return {r.id: Assessment(r, findings[r.id], provenance.get(r.id)) for r in runs}
