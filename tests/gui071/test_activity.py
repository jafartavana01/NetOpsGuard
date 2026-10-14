"""Real-format authorization lines and actual health aggregation; no daemon/DB claim."""
import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app.services import accounting_log as log
from app.api.routes_accounting import accounting_health

NOW = datetime(2026, 10, 13, 20, 15, tzinfo=timezone.utc)
def record(stamp, result='permit', command='show version'):
    return log._auth_parse_line(f'{stamp}\tR1\tops\ttty1\t192.0.2.1\t15\t{result}\tshell\t{command}')
def at(delta=0, offset=0, result='permit', command='show version'):
    stamp=(NOW+timedelta(hours=delta)).astimezone(timezone(timedelta(minutes=offset)))
    return record(stamp.strftime('%Y-%m-%d %H:%M:%S %z'),result,command)
class ActivityTests(unittest.TestCase):
    def test_real_format_recent(self):
        r=at(-1); self.assertTrue(r.parsed); self.assertEqual(sum(x['count'] for x in log.compute_hourly_activity([r],now=NOW)),1)
    def test_half_hour_offset(self):
        rows=log.compute_hourly_activity([at(-1,210)],now=NOW)
        self.assertEqual(next(x['count'] for x in rows if x['hour']==NOW.replace(hour=19,minute=0).isoformat()),1)
    def test_quarter_hour_offset(self):
        self.assertEqual(sum(x['count'] for x in log.compute_hourly_activity([at(-1,345)],now=NOW)),1)
    def test_negative_offset(self):
        self.assertEqual(log.compute_hourly_activity([at(-1,-210)],now=NOW),log.compute_hourly_activity([at(-1)],now=NOW))
    def test_window_boundary(self):
        selected,w=log.activity_window([at(-24),at(-24.01),at(.01)],now=NOW)
        self.assertEqual(len(selected),1);self.assertEqual(w['outside_window'],2)
    def test_empty(self):
        self.assertTrue(all(x['count']==0 for x in log.compute_hourly_activity([],now=NOW)))
    def test_old_sample(self):
        rows,w=log.activity_window([at(-25)],now=NOW);self.assertEqual(rows,[]);self.assertEqual(w['outside_window'],1)
    def test_malformed_timestamp(self):
        rows,w=log.activity_window([record('2026-99-13 20:15:00 +0000')],now=NOW)
        self.assertEqual(rows,[]);self.assertEqual(w['unknown_timestamp'],1)
    def test_missing_timestamp(self):
        r=log._auth_parse_line('R1\tops\ttty1\t192.0.2.1\t15\tdeny\tshell\tshow clock')
        self.assertEqual(log.activity_window([r],now=NOW)[1]['unknown_timestamp'],1)
    def test_malformed_line(self):
        self.assertEqual(log.activity_window([log._auth_parse_line('unreadable')],now=NOW)[0],[])
    def test_login_excluded(self):
        self.assertEqual(sum(x['count'] for x in log.compute_hourly_activity([at(-1,command='')],now=NOW)),0)
    def test_non_permit_not_assumed_deny(self):
        selected,_=log.activity_window([at(-1,result=x) for x in ['permit','deny','error','']],now=NOW)
        stats=log.compute_health_and_failure_stats(selected)
        self.assertEqual((stats['permit_count'],stats['non_permit_count']),(1,2))
        self.assertEqual(sum(x['count'] for x in log.compute_hourly_activity(selected,now=NOW)),4)
    def test_real_file_reader_excludes_login_and_keeps_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'authorization.log'
            path.write_text(at(-1,210).raw_line+'\n'+at(-1,command='').raw_line+'\n'+'malformed line\n')
            with patch.object(log,'AUTH_LOG_PATH',path): rows=log.read_auth_records(limit=2000)
        self.assertEqual(len(rows),1)
        self.assertEqual(sum(x['count'] for x in log.compute_hourly_activity(rows,now=NOW)),1)
    def test_endpoint_same_window_for_counts_and_buckets(self):
        current=datetime.now(timezone.utc)
        records=[record((current-timedelta(minutes=5)).astimezone(timezone(timedelta(minutes=210))).strftime('%Y-%m-%d %H:%M:%S %z')),record((current-timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S %z'),'deny')]
        with patch.object(log,'read_auth_records',return_value=records): result=accounting_health(limit=2000,hours=24,_admin=None)
        self.assertEqual(result['permit_count'],1);self.assertEqual(result['non_permit_count'],0)
        self.assertEqual(sum(x['count'] for x in result['hourly_activity']),1)
        self.assertEqual(result['activity_window']['outside_window'],1)
if __name__=='__main__':unittest.main(verbosity=2)
