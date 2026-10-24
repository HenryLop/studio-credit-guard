"""CLI: python -m creditguard request|arm|record|ledger|status"""
import argparse
import sys

from creditguard import core


def main(argv=None):
    ap = argparse.ArgumentParser(prog="creditguard")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("request", help="prepare a paid run and show it to the user")
    r.add_argument("item")
    r.add_argument("--model", required=True)
    r.add_argument("--settings", default="")
    r.add_argument("--cost", type=float, required=True, help="credits per run, as quoted by the tool")
    r.add_argument("--runs", type=int, default=1)
    a = sub.add_parser("arm", help="arm ONE run of an approved request, right before the paid command")
    a.add_argument("request")
    a.add_argument("--quoted", type=float, help="the cost the tool shows right now")
    c = sub.add_parser("record", help="close an armed run: ok, failed, refunded")
    c.add_argument("request")
    c.add_argument("result", choices=["ok", "failed", "refunded"])
    sub.add_parser("ledger", help="print every run and the total spent")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "request":
            print(core.describe(core.make_request(args.item, args.model, args.settings, args.cost, args.runs)))
        elif args.cmd == "arm":
            r = core.arm(args.request, args.quoted)
            print("ARMED %s: %s credits, one run, valid %ds, then it locks again." % (r["id"], r["unit"], core.ARM_SECONDS))
        elif args.cmd == "record":
            core.record(args.request, args.result)
            print("recorded %s as %s" % (args.request, args.result))
        elif args.cmd == "ledger":
            for row in core.ledger_rows():
                print("%(when)s  %(request)-14s %(credits)6s  %(result)-8s %(item)s (%(model)s)" % row)
            print("total spent: %s credits" % core.spent())
    except core.GuardError as e:
        print("refused: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
