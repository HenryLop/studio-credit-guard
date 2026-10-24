"""Claude Code hooks.

    python creditguard/hooks.py approve   # UserPromptSubmit: the human types "go 12"
    python creditguard/hooks.py guard     # PreToolUse: deny generate commands unless armed
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from creditguard import core  # noqa: E402


def guard_decision(event):
    cmd = (event.get("tool_input") or {}).get("command", "")
    if event.get("tool_name") not in ("Bash", "PowerShell") or not core.is_generate(cmd):
        return None
    if core.consume_arm():
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": (
            "BLOCKED: this spends credits and nothing is armed. Create a request "
            "(creditguard request ...), show it to the user, wait for them to type 'go <credits>', "
            "then run (creditguard arm <id>) right before this command. One arm covers one run.")}}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    if mode == "approve":
        msg = core.approve_from_prompt(event.get("prompt") or "")
        if msg:
            print(msg)
    elif mode == "guard":
        out = guard_decision(event)
        if out:
            print(json.dumps(out))


if __name__ == "__main__":
    main()
