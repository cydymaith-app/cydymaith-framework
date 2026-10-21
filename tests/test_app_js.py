"""Runs the browser script tests (tests/app.test.js) under Node, so one command runs every test.

Without Node the tests are skipped on a developer machine. CI sets REQUIRE_NODE=1, so a missing Node there is a failure.
"""
import os
import pathlib
import shutil
import subprocess
import unittest

TESTS = pathlib.Path(__file__).resolve().parent


class BrowserScriptTests(unittest.TestCase):
    def test_app_js_passes_its_tests(self):
        node = shutil.which("node")
        if node is None:
            if os.environ.get("REQUIRE_NODE"):
                self.fail("Node is required (REQUIRE_NODE is set) but was not found")
            self.skipTest("Node is not installed")
        files = sorted(str(p) for p in TESTS.glob("*.test.js"))
        self.assertTrue(files, "no tests/*.test.js files found")
        result = subprocess.run([node, "--test", *files], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout[-3000:] + result.stderr[-1000:])


if __name__ == "__main__":
    unittest.main()
