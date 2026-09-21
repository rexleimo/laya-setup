#!/usr/bin/env python3
"""Smoke test: load the local English checkpoint and ask it real questions."""
import os
import sys
import time

os.environ.setdefault("USE_TF", "0")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from laya_runtime import LayaRuntime  # noqa: E402

STATE = {
    "from": "user@acme.com",
    "subject": "Duplicate charge on invoice #4411",
    "body": (
        "Hi, we were billed twice for March. Please refund the duplicate today "
        "or we will cancel our plan."
    ),
}

QUESTIONS = {
    "department": {
        "type": "choice",
        "instructions": "Which team should handle this request?",
        "criteria": {
            "billing": "invoices, payments, refunds",
            "technical": "bugs, outages, system errors",
            "sales": "pricing, new contracts",
            "other": "everything else",
        },
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is this request?",
        "criteria": [
            "no time pressure",
            "needs attention soon",
            "blocking issue or hard deadline",
        ],
    },
    "churn_risk": {
        "type": "noul",
        "instructions": "Does the user threaten to cancel or leave?",
    },
    "refund_requested": {
        "type": "noul",
        "instructions": "Does the user explicitly request a refund?",
    },
}


def main():
    model_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "models", "laya")
    device = sys.argv[2] if len(sys.argv) > 2 else "auto"
    rt = LayaRuntime(model_dir=model_dir, device=device)
    print("device: %s" % rt.device)
    print("available checkpoints: %s" % (rt.available() or "<none>"))
    t0 = time.time()
    rt.load("english")
    print("model loaded in %.1fs" % (time.time() - t0))

    res = rt.predict(STATE, QUESTIONS)
    print("latency: %.1f ms" % res["latency_ms"])
    for qid, ans in res["answers"].items():
        print("  %-17s %s" % (qid, ans))
    ans = res["answers"]
    ok = (
        ans.get("department", {}).get("choice") == "billing"
        and ans.get("refund_requested", {}).get("noul", 0) > 0.5
        and ans.get("churn_risk", {}).get("noul", 0) > 0.3
    )
    print("selftest: %s" % ("PASS" if ok else "CHECK (answers above)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
