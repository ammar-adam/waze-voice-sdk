"""The Vercel functions in api/, run under Node against an in-memory Redis.

The tests themselves are JavaScript (tests/api/functions.test.js), because the
functions are. This runs them as part of the Python suite, and skips cleanly
on a machine without Node.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is not installed")
class FunctionTests(unittest.TestCase):
    def test_track_and_stats(self) -> None:
        assert NODE is not None
        result = subprocess.run(
            [NODE, "--test", str(ROOT / "tests" / "api" / "functions.test.js")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
