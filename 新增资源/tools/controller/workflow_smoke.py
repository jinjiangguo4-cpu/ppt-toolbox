"""Hosted integration test with a synthetic baseline and an isolated Git remote."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parents[3]
with TemporaryDirectory() as folder:
    baseline = Path(folder)/"baseline.json"
    baseline.write_text(json.dumps([{"id":f"baseline-{i}", "library":"test"} for i in range(3002)]))
    subprocess.run([sys.executable, str(Path(__file__).with_name("verify_controller.py")),
                    str(root), str(baseline)], check=True)
