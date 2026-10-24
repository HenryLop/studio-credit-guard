import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CREDIT_STATE_DIR"] = tempfile.mkdtemp(prefix="creditguard-test-")
from creditguard import core, hooks  # noqa: E402

GEN = {"tool_name": "Bash", "tool_input": {"command": "studio generate create --model m"}}


def reset():
    d = core.state_dir()
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))


class Tests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_locked_by_default(self):
        self.assertIsNotNone(hooks.guard_decision(GEN))

    def test_other_commands_pass(self):
        self.assertIsNone(hooks.guard_decision({"tool_name": "Bash", "tool_input": {"command": "ls"}}))

    def test_full_flow_and_relock(self):
        r = core.make_request("clip", "m", "720p", 12)
        with self.assertRaises(core.GuardError):
            core.arm(r["id"])  # not approved yet
        self.assertIn("Approved", core.approve_from_prompt("go 12"))
        core.arm(r["id"], 12)
        self.assertIsNone(hooks.guard_decision(GEN))      # the armed run goes through
        self.assertIsNotNone(hooks.guard_decision(GEN))   # and it relocks
        with self.assertRaises(core.GuardError):
            core.arm(r["id"])                              # one run per request

    def test_wrong_count_approves_nothing(self):
        core.make_request("clip", "m", "720p", 12)
        self.assertIn("Nothing approved", core.approve_from_prompt("go 13"))

    def test_negated_go(self):
        core.make_request("clip", "m", "720p", 12)
        self.assertIsNone(core.approve_from_prompt("do not go 12"))

    def test_price_change_needs_new_request(self):
        r = core.make_request("clip", "m", "720p", 12)
        core.approve_from_prompt("go 12")
        with self.assertRaises(core.GuardError):
            core.arm(r["id"], quoted_cost=15)

    def test_arm_expires(self):
        r = core.make_request("clip", "m", "720p", 12)
        core.approve_from_prompt("go 12")
        core.arm(r["id"], now=time.time() - 3600)
        self.assertIsNotNone(hooks.guard_decision(GEN))

    def test_ledger_and_total(self):
        r = core.make_request("clip", "m", "720p", 12)
        core.approve_from_prompt("go 12")
        core.arm(r["id"])
        core.record(r["id"], "ok")
        self.assertEqual(core.spent(), 12)
        core.record_fail = None
        self.assertEqual(core.ledger_rows()[0]["result"], "ok")

    def test_budget_cap(self):
        core.BUDGET = 20
        try:
            core.make_request("a", "m", "s", 12)
            r = core.make_request("b", "m", "s", 5)
            self.assertTrue(r)
            core.approve_from_prompt("go 5")
            core.arm(r["id"])
            core.record(r["id"], "ok")
            with self.assertRaises(core.GuardError):
                core.make_request("c", "m", "s", 20)
        finally:
            core.BUDGET = 0


if __name__ == "__main__":
    unittest.main()
