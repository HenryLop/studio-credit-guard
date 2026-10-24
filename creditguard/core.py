"""Requests, approvals, the single-use arm, and the ledger.

Files under CREDIT_STATE_DIR (default ~/.creditguard):
  requests.json   written by `request` / `arm`
  approvals.json  written ONLY by the UserPromptSubmit hook (a human typed "go N")
  armed.json      one run is armed; the PreToolUse hook consumes it
  ledger.csv      one row per run with its cost
"""
import csv
import datetime as dt
import json
import os
import re
import time

ARM_SECONDS = int(os.environ.get("CREDIT_ARM_SECONDS", "300"))
APPROVAL_SECONDS = int(os.environ.get("CREDIT_APPROVAL_SECONDS", "900"))
BUDGET = float(os.environ.get("CREDIT_BUDGET", "0") or 0)  # 0 = no budget cap
GENERATE = re.compile(os.environ.get("CREDIT_GENERATE_PATTERN",
                                     r"\bgenerate\s+create\b|\bgenerate[-_]video\b|\bgenerate[-_]image\b"), re.I)


class GuardError(Exception):
    pass


def state_dir():
    d = os.environ.get("CREDIT_STATE_DIR") or os.path.join(os.path.expanduser("~"), ".creditguard")
    os.makedirs(d, exist_ok=True)
    return d


def _path(name):
    return os.path.join(state_dir(), name)


def read(name, default):
    try:
        with open(_path(name), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write(name, data):
    with open(_path(name), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)


# --- ledger ----------------------------------------------------------------
LEDGER_COLS = ["when", "request", "item", "model", "settings", "credits", "result"]


def ledger_rows():
    try:
        with open(_path("ledger.csv"), newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def ledger_append(row):
    new = not os.path.exists(_path("ledger.csv"))
    with open(_path("ledger.csv"), "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LEDGER_COLS)
        if new:
            w.writeheader()
        w.writerow({c: row.get(c, "") for c in LEDGER_COLS})


def spent():
    return sum(float(r["credits"] or 0) for r in ledger_rows() if r["result"] != "refunded")


# --- the flow --------------------------------------------------------------
def make_request(item, model, settings, unit_cost, count=1):
    total = round(float(unit_cost) * int(count), 2)
    if BUDGET and spent() + total > BUDGET:
        raise GuardError("over budget: %s spent + %s requested > %s" % (spent(), total, BUDGET))
    reqs = read("requests.json", [])
    rid = "r%s" % dt.datetime.now().strftime("%m%d%H%M%S")
    n = 1
    while any(r["id"] == rid for r in reqs):
        n += 1
        rid = "r%s-%d" % (dt.datetime.now().strftime("%m%d%H%M%S"), n)
    reqs.append({"id": rid, "item": item, "model": model, "settings": settings, "unit": float(unit_cost),
                 "runs": int(count), "total": total, "armed": 0, "created": time.time()})
    write("requests.json", reqs)
    return reqs[-1]


def describe(r):
    return ("REQUEST %s: %s with %s (%s): %d run(s) x %s = %s credits.\n"
            "To approve, the user types:  go %s"
            % (r["id"], r["item"], r["model"], r["settings"], r["runs"], r["unit"], r["total"],
               int(r["total"]) if r["total"] == int(r["total"]) else r["total"]))


def approve_from_prompt(prompt, now=None):
    """UserPromptSubmit: 'go N' approves the pending request whose total is N."""
    now = time.time() if now is None else now
    m = re.search(r"(?<![\w\"'`])go\s+(\d+(?:\.\d+)?)\b", prompt, re.I)
    if not m or re.search(r"\b(no|never|don'?t|not)\b[^.;!?]{0,30}$", prompt[:m.start()], re.I):
        return None
    credits = float(m.group(1))
    reqs = read("requests.json", [])
    pending = [r for r in reqs if r["armed"] < r["runs"] and abs(r["total"] - credits) < 0.01
               and not any(a["request"] == r["id"] for a in read("approvals.json", []))]
    if not pending:
        return "No pending request costs %s credits. Nothing approved." % credits
    r = pending[-1]
    aps = read("approvals.json", [])
    aps.append({"request": r["id"], "credits": credits, "until": now + APPROVAL_SECONDS})
    write("approvals.json", aps)
    return "Approved %s (%s credits). Arm it right before the run." % (r["id"], credits)


def approved(rid, now=None):
    now = time.time() if now is None else now
    return any(a["request"] == rid and a["until"] > now for a in read("approvals.json", []))


def arm(rid, quoted_cost=None, now=None):
    """Arm exactly one run of an approved request. quoted_cost = what the tool shows right now."""
    now = time.time() if now is None else now
    reqs = read("requests.json", [])
    r = next((x for x in reqs if x["id"] == rid), None)
    if not r:
        raise GuardError("no such request: %s" % rid)
    if not approved(rid, now):
        raise GuardError("the user has not approved %s (they must type: go %s)" % (rid, r["total"]))
    if r["armed"] >= r["runs"]:
        raise GuardError("%s already used its %d run(s); a new run is a new request" % (rid, r["runs"]))
    if quoted_cost is not None and abs(float(quoted_cost) - r["unit"]) > 0.01:
        raise GuardError("the tool now quotes %s, approved was %s per run: price or settings changed, "
                         "make a new request" % (quoted_cost, r["unit"]))
    r["armed"] += 1
    write("requests.json", reqs)
    write("armed.json", {"request": rid, "until": now + ARM_SECONDS, "used": False})
    ledger_append({"when": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "request": rid, "item": r["item"],
                   "model": r["model"], "settings": r["settings"], "credits": r["unit"], "result": "armed"})
    return r


def consume_arm(now=None):
    """PreToolUse: True if a live, unused arm existed (and is now spent: the guard relocks)."""
    now = time.time() if now is None else now
    a = read("armed.json", None)
    if not a or a.get("used") or a["until"] <= now:
        return False
    a["used"] = True
    write("armed.json", a)
    return True


def record(rid, result):
    rows = ledger_rows()
    for r in rows:
        if r["request"] == rid and r["result"] == "armed":
            r["result"] = result
            break
    else:
        raise GuardError("no armed run recorded for %s" % rid)
    with open(_path("ledger.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LEDGER_COLS)
        w.writeheader()
        w.writerows(rows)


def is_generate(command):
    return bool(GENERATE.search(command or ""))
