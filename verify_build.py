import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXE = ROOT / "dist" / "AI Note Taker.exe"


def kill_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True, text=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def pid_using_port(port: int) -> str:
    if os.name != "nt":
        return ""
    try:
        output = subprocess.check_output(["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""
    needle = f":{port}"
    for line in output.splitlines():
        if needle in line and "LISTENING" in line:
            return line.split()[-1]
    return ""


def main() -> int:
    if not EXE.exists():
        print(f"Missing built executable: {EXE}")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="ai-note-taker-verify-"))
    logs = tmp / "AI Note Taker" / "logs" / "ai-note-taker.err.log"
    env = os.environ.copy()
    env["APPDATA"] = str(tmp)
    existing_pid = pid_using_port(8000)

    process = subprocess.Popen([str(EXE)], cwd=str(Path.home()), env=env)
    try:
        deadline = time.time() + 45
        while time.time() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/healthz", timeout=2) as response:
                    if response.status == 200:
                        print("Build verification passed: AI Note Taker is reachable.")
                        return 0
            except Exception:
                pass
            if process.poll() is not None:
                print(f"AI Note Taker launcher exited with code {process.returncode}")
                if logs.exists():
                    print(logs.read_text(encoding="utf-8", errors="replace"))
                return 1
            time.sleep(0.4)
        print("AI Note Taker was not reachable in time.")
        if logs.exists():
            print(logs.read_text(encoding="utf-8", errors="replace"))
        return 1
    finally:
        kill_tree(process.pid)
        server_pid = pid_using_port(8000)
        if server_pid and server_pid != existing_pid:
            kill_tree(int(server_pid))
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
