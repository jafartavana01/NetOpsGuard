"""Dependency-free isolated suite. JSON inventory optional; no production imports."""
import argparse
import json
import sys
import unittest
from pathlib import Path

class SecurityResult(unittest.TextTestResult):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.records = []
    def record(self, test, outcome, detail=''):
        self.records.append(dict(test=test.id(), outcome=outcome,
                                 description=test.shortDescription(), detail=detail))
    def addSuccess(self, test):
        super().addSuccess(test); self.record(test, 'PASS')
    def addExpectedFailure(self, test, err):
        # unittest normally hides ANY exception under expectedFailure. Harness/import/type
        # errors must be real errors. Only failed security assertions qualify here.
        if not issubclass(err[0], AssertionError):
            self.addError(test, err)
            return
        super().addExpectedFailure(test, err)
        self.record(test, 'XFAIL', str(err[1]))
    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test); self.record(test, 'XPASS')
    def addFailure(self, test, err):
        super().addFailure(test, err); self.record(test, 'FAIL', str(err[1]))
    def addError(self, test, err):
        super().addError(test, err); self.record(test, 'ERROR', str(err[1]))
    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.record(test, 'SKIP', reason)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', type=Path, help='Write results/classification inventory to this path')
    parser.add_argument('--no-xfail', action='store_true', help='Expose security failures directly; expected nonzero on baseline')
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern='test_*.py')
    if args.no_xfail:
        def unwrap(suite):
            for item in suite:
                if isinstance(item, unittest.TestSuite): unwrap(item)
                else:
                    fn = getattr(type(item), item._testMethodName)
                    if getattr(fn, '__unittest_expecting_failure__', False):
                        fn.__unittest_expecting_failure__ = False
        unwrap(suite)
    result = unittest.TextTestRunner(verbosity=2, resultclass=SecurityResult).run(suite)
    if args.json:
        args.json.write_text(json.dumps(dict(tests=result.testsRun, records=result.records), indent=2) + '\n')
    sys.exit(0 if result.wasSuccessful() else 1)
