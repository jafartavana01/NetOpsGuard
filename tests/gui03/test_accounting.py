"""Protect existing parser/filter semantics while presentation changes."""
import sys, unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.services.accounting_log import _parse_line, filter_records, to_csv_row

class AccountingPresentationContract(unittest.TestCase):
    def setUp(self):
        self.rows=[_parse_line(f'2026-10-10 14:00:00 +0000 R1::operator::tty1::198.51.100.12::cmd::{result}::shell::show clock') for result in ('permit','deny','unrecognized','success')]
    def test_raw_results_are_preserved(self):
        self.assertEqual([r.result for r in self.rows],['permit','deny','unrecognized','success'])
        self.assertTrue(all(r.parsed for r in self.rows))
    def test_result_filter_remains_exact_case_insensitive(self):
        self.assertEqual([r.result for r in filter_records(self.rows,result='DENY')],['deny'])
        self.assertEqual(filter_records(self.rows,result='den'),[])
    def test_unknown_filter_is_literal_not_success_or_error_heuristic(self):
        self.assertEqual(filter_records(self.rows,result='unknown'),[])
    def test_combined_existing_filters(self):
        self.assertEqual(len(filter_records(self.rows,user='OPER',device='r1',source_ip='198.51',search='clock',device_group_device_names=['R1'],since=datetime(2026,10,10,13,tzinfo=timezone.utc),until=datetime(2026,10,10,15,tzinfo=timezone.utc))),4)
        self.assertEqual(filter_records(self.rows,device_group_device_names=[]),[])
    def test_csv_keeps_raw_result(self):
        self.assertIn('deny',to_csv_row(self.rows[1]))
    def test_unknown_timestamps_not_silently_discarded(self):
        row=_parse_line('R1::operator::tty1::198.51.100.12::cmd::deny::shell::show clock')
        self.assertIsNone(row.parsed_at)
        self.assertEqual(filter_records([row],since=datetime(2026,10,10,tzinfo=timezone.utc)),[row])

if __name__=='__main__': unittest.main(verbosity=2)
