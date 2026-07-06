import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from launcher.process_manager import kill_process_tree


class ProcessTreeKillTest(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "taskkill process-tree behavior is Windows-specific")
    def test_kill_process_tree_stops_grandchild(self):
        with tempfile.TemporaryDirectory() as tmp:
            child = Path(tmp) / "child.py"
            parent = Path(tmp) / "parent.py"
            child.write_text("import time\ntime.sleep(120)\n", encoding="utf-8")
            parent.write_text(
                "import subprocess, sys, time\n"
                "p = subprocess.Popen([sys.executable, 'child.py'])\n"
                "print(p.pid, flush=True)\n"
                "time.sleep(120)\n",
                encoding="utf-8",
            )
            process = subprocess.Popen(
                [sys.executable, str(parent)],
                cwd=tmp,
                stdout=subprocess.PIPE,
                text=True,
            )
            assert process.stdout is not None
            grandchild_pid = int(process.stdout.readline().strip())

            self.assertTrue(kill_process_tree(process.pid))
            process.wait(timeout=10)
            if process.stdout:
                process.stdout.close()
            time.sleep(1)
            tasklist = subprocess.run(
                ["tasklist", "/FI", f"PID eq {grandchild_pid}"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertIn("No tasks are running", tasklist.stdout)


if __name__ == "__main__":
    unittest.main()

