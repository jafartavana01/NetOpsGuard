import unittest
from datetime import datetime, date, timezone, timedelta
from app.services.schedule_time import occurrence, due_slot, next_slot, validate_zone
from app.services.scheduled_audit import should_run_now
from app.schemas.ncm import NcmScheduleRequest
from app.schemas.security_audit import AuditScheduleUpdateRequest

UTC=timezone.utc
class TimeTests(unittest.TestCase):
    def test_tehran_midnight(self):
        self.assertEqual(occurrence(date(2026,10,15),'00:15','Asia/Tehran'),datetime(2026,10,14,20,45,tzinfo=UTC))
    def test_legacy_utc(self):
        self.assertEqual(occurrence(date(2026,10,15),'02:00'),datetime(2026,10,15,2,tzinfo=UTC))
    def test_dst_gap_skipped(self):
        self.assertIsNone(occurrence(date(2026,3,8),'02:30','America/New_York'))
        self.assertEqual(next_slot('02:30',datetime(2026,3,7,8,tzinfo=UTC),'America/New_York'),datetime(2026,3,9,6,30,tzinfo=UTC))
    def test_dst_fold_first_only(self):
        self.assertEqual(occurrence(date(2026,11,1),'01:30','America/New_York'),datetime(2026,11,1,5,30,tzinfo=UTC))
        self.assertEqual(next_slot('01:30',datetime(2026,11,1,5,30,tzinfo=UTC),'America/New_York'),datetime(2026,11,2,6,30,tzinfo=UTC))
    def test_due_second_fold_same_claim(self):
        a=due_slot('01:30',datetime(2026,11,1,5,31,tzinfo=UTC),'America/New_York')
        b=due_slot('01:30',datetime(2026,11,1,6,31,tzinfo=UTC),'America/New_York')
        self.assertEqual(a,b)
    def test_non_hour_dst_gap(self):
        self.assertIsNone(occurrence(date(2026,10,4),'02:15','Australia/Lord_Howe'))
    def test_date_line_skipped_day(self):
        self.assertIsNone(occurrence(date(2011,12,30),'12:00','Pacific/Apia'))
    def test_invalid_times(self):
        for t in ['25:00','02:99','2:00','oops',None]:
            with self.assertRaises(ValueError):due_slot(t,datetime.now(UTC))
    def test_invalid_zones(self):
        for z in ['','../UTC','ServerLocal','Not/AZone']:
            with self.assertRaises(ValueError):validate_zone(z)
    def test_sqlite_naive_same_as_pg_aware(self):
        now=datetime(2026,10,15,1)
        self.assertEqual(due_slot('02:00',now),due_slot('02:00',now.replace(tzinfo=UTC)))
    def test_audit_legacy_before_time_unchanged(self):
        self.assertFalse(should_run_now('02:00',None,datetime(2026,10,15,1,tzinfo=UTC)))
    def test_audit_legacy_naive_checkpoint(self):
        self.assertFalse(should_run_now('02:00',datetime(2026,10,15,2),datetime(2026,10,15,3,tzinfo=UTC)))
    def test_audit_zoned_restart_does_not_repeat(self):
        now=datetime(2026,10,15,1,tzinfo=UTC);slot=due_slot('02:00',now,'Asia/Tehran')
        self.assertTrue(should_run_now('02:00',None,now,'Asia/Tehran'))
        self.assertFalse(should_run_now('02:00',slot.replace(tzinfo=None),now,'Asia/Tehran'))
    def test_api_omission_is_distinct_from_explicit_conversion(self):
        s=NcmScheduleRequest(name='daily',daily_run_time='02:00')
        self.assertIsNone(s.schedule_timezone);self.assertNotIn('schedule_timezone',s.model_fields_set)
        s=NcmScheduleRequest(name='daily',daily_run_time='02:00',schedule_timezone='Asia/Tehran')
        self.assertEqual(s.schedule_timezone,'Asia/Tehran')
    def test_both_apis_reject_invalid_zone(self):
        for cls,kw in [(NcmScheduleRequest,{'name':'a'}),(AuditScheduleUpdateRequest,{'enabled':False})]:
            with self.assertRaises(ValueError):cls(daily_run_time='02:00',schedule_timezone='bad',**kw)

    def test_manual_legacy_audit_still_consumes_today(self):
        from types import SimpleNamespace as NS
        from app.services.scheduled_audit import next_due
        now=datetime(2026,10,15,1,tzinfo=UTC)
        settings=NS(enabled=True,daily_run_time='02:00',schedule_timezone=None,last_slot=now,last_run_at=now)
        self.assertFalse(should_run_now('02:00',now,now+timedelta(hours=2)))
        self.assertEqual(next_due(settings,now),datetime(2026,10,16,2,tzinfo=UTC))
