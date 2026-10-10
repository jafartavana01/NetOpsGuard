"""Ensure expected-failure reporting cannot hide broken test infrastructure."""
import io
import unittest
from run import SecurityResult

class ExpectedFailureBoundaryTests(unittest.TestCase):
    def test_runtime_error_is_not_security_xfail(self):
        """Protect test infrastructure: a harness exception fails the security gate."""
        class Broken(unittest.TestCase):
            @unittest.expectedFailure
            def runTest(self): raise RuntimeError('fixture failure')
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=SecurityResult).run(Broken())
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.expectedFailures), 0)
    def test_unexpected_success_requires_review(self):
        """Protect test infrastructure: a fixed or accidentally weakened XFAIL cannot pass silently."""
        class Fixed(unittest.TestCase):
            @unittest.expectedFailure
            def runTest(self): self.assertTrue(True)
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=SecurityResult).run(Fixed())
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.unexpectedSuccesses), 1)
