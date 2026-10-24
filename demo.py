"""One-command demo of the whole gate, against the real hooks and CLI.

    python demo.py
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ["CREDIT_STATE_DIR"] = tempfile.mkdtemp(prefix="creditguard-demo-")
PY = sys.executable


def cli(*args):
    p = subprocess.run([PY, "-m", "creditguard", *args], cwd=ROOT, capture_output=True, text=True)
    return (p.stdout + p.stderr).strip()


def hook(mode, event):
    p = subprocess.run([PY, os.path.join(ROOT, "creditguard", "hooks.py"), mode],
                       input=json.dumps(event), capture_output=True, text=True)
    return p.stdout.strip()


def gen():
    out = hook("guard", {"tool_name": "Bash", "tool_input": {"command": "studio generate create --model video-x"}})
    return "DENIED (locked)" if "deny" in out else "ran (credits spent)"


print("1. agent tries to generate with nothing armed ->", gen())
print("2. agent files a request:")
print("   " + cli("request", "intro clip", "--model", "video-x", "--settings", "720p 5s", "--cost", "12").replace("\n", "\n   "))
print("3. agent tries to arm before the user says go ->", cli("arm", os.listdir(os.environ["CREDIT_STATE_DIR"]) and
      json.load(open(os.path.join(os.environ["CREDIT_STATE_DIR"], "requests.json")))[0]["id"]))
rid = json.load(open(os.path.join(os.environ["CREDIT_STATE_DIR"], "requests.json")))[0]["id"]
print("4. user types 'go 99' (wrong count) ->", hook("approve", {"prompt": "go 99"}))
print("5. user types 'go 12' ->", hook("approve", {"prompt": "go 12"}))
print("6. price changed on the tool, agent arms at 20 ->", cli("arm", rid, "--quoted", "20"))
print("7. agent arms at the approved price ->", cli("arm", rid, "--quoted", "12"))
print("8. the generate command ->", gen())
print("9. a retry of the same command ->", gen())
print("10. record the result:", cli("record", rid, "ok"))
print(cli("ledger"))
