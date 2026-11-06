#!/usr/bin/env python3
"""Score a tool's categorization against the benchmark labels.

    python3 cli/score.py predictions.csv
    python3 cli/score.py predictions.csv --split cold-test --json
    python3 cli/score.py predictions.csv --markdown > report.md

predictions.csv needs two columns: txn_id and account (an account number
from data/chart-of-accounts.csv). A transaction with no prediction counts
as wrong. Predicting 9999 (Ask the client) is right only where the label is
9999; anywhere else it is counted as a deferral, reported separately.

Part of https://github.com/ZeraBooks/transaction-categorization-benchmark
(ZeraBooks, https://www.zerabooks.com/ai-bookkeeping).
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
PL = {"revenue", "cost_of_sales", "expense", "other_income"}


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def score(pred_path, split=None):
    chart = {r["account"]: r for r in load("chart-of-accounts.csv")}
    labels = {r["txn_id"]: r for r in load("labels.csv")}
    txns = {r["txn_id"]: r for r in load("transactions.csv")}
    if split:
        scheme, part = split.split("-")
        keep = {r["txn_id"] for r in load("splits.csv") if r[scheme] == part}
        labels = {k: v for k, v in labels.items() if k in keep}
    with open(pred_path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not {"txn_id", "account"} <= set(reader.fieldnames or []):
            raise ValueError("predictions need txn_id and account columns")
        preds = {r["txn_id"].strip(): r["account"].strip() for r in reader}

    unknown_ids = sorted(set(preds) - set(txns))
    bad_accounts = sorted({a for a in preds.values() if a and a not in chart})
    total = len(labels)
    right = asked = missing = material = 0
    dollars_right = dollars_all = Decimal("0")
    by_diff, by_biz, by_group = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    tp, fp, fn = Counter(), Counter(), Counter()
    confusion = Counter()
    for tid, lab in labels.items():
        want = lab["account"]
        got = preds.get(tid, "")
        amt = abs(Decimal(txns[tid]["amount"]))
        dollars_all += amt
        ok = got == want
        if not got:
            missing += 1
        elif got == "9999" and want != "9999":
            asked += 1
        if ok:
            right += 1
            dollars_right += amt
            tp[want] += 1
        else:
            fn[want] += 1
            if got:
                fp[got] += 1
                confusion[(want, got)] += 1
                if got in chart and got != "9999" and want != "9999":
                    if (chart[want]["group"] in PL) != (chart[got]["group"] in PL):
                        material += 1
        for bucket, key in ((by_diff, lab["difficulty"]), (by_biz, txns[tid]["business_id"]), (by_group, chart[want]["group"])):
            bucket[key][0] += ok
            bucket[key][1] += 1

    per_account = {}
    f1s = []
    for acct in sorted(chart):
        support = tp[acct] + fn[acct]
        if not support:
            continue
        p = tp[acct] / (tp[acct] + fp[acct]) if tp[acct] + fp[acct] else 0.0
        r = tp[acct] / support
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        f1s.append(f1)
        per_account[acct] = {"name": chart[acct]["name"], "support": support, "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}

    def pct(a, b):
        return round(100 * a / b, 2) if b else 0.0

    return {
        "predictions_file": os.path.basename(pred_path),
        "split": split or "all",
        "transactions": total,
        "accuracy_pct": pct(right, total),
        "dollar_weighted_accuracy_pct": round(float(100 * dollars_right / dollars_all), 2) if dollars_all else 0.0,
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else 0.0,
        "missing_predictions": missing,
        "deferred_to_ask": asked,
        "material_errors": material,
        "material_error_rate_pct": pct(material, total),
        "by_difficulty": {k: {"accuracy_pct": pct(*v), "n": v[1]} for k, v in sorted(by_diff.items())},
        "by_business": {k: {"accuracy_pct": pct(*v), "n": v[1]} for k, v in sorted(by_biz.items())},
        "by_group": {k: {"accuracy_pct": pct(*v), "n": v[1]} for k, v in sorted(by_group.items())},
        "per_account": per_account,
        "top_confusions": [{"label": a, "label_name": chart[a]["name"], "predicted": b, "predicted_name": chart.get(b, {}).get("name", "not in chart"), "count": c}
                           for (a, b), c in confusion.most_common(15)],
        "unknown_txn_ids": unknown_ids[:20],
        "accounts_not_in_chart": bad_accounts,
    }


def markdown(r):
    out = [f"# Categorization score: {r['predictions_file']} ({r['split']} split)", "",
           "| Metric | Value |", "|---|---|",
           f"| Transactions | {r['transactions']} |", f"| Accuracy | {r['accuracy_pct']}% |",
           f"| Dollar-weighted accuracy | {r['dollar_weighted_accuracy_pct']}% |", f"| Macro F1 | {r['macro_f1']} |",
           f"| Material errors (P&L vs balance sheet) | {r['material_errors']} ({r['material_error_rate_pct']}%) |",
           f"| Deferred to Ask the client | {r['deferred_to_ask']} |", f"| Missing predictions | {r['missing_predictions']} |", "",
           "## By difficulty", "", "| Difficulty | n | Accuracy |", "|---|---|---|"]
    out += [f"| {k} | {v['n']} | {v['accuracy_pct']}% |" for k, v in r["by_difficulty"].items()]
    out += ["", "## Top confusions", "", "| Label | Predicted | Count |", "|---|---|---|"]
    out += [f"| {c['label']} {c['label_name']} | {c['predicted']} {c['predicted_name']} | {c['count']} |" for c in r["top_confusions"]]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Score categorization predictions against the benchmark.")
    ap.add_argument("predictions")
    ap.add_argument("--split", choices=["warm-dev", "warm-test", "cold-dev", "cold-test"])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true")
    g.add_argument("--markdown", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = score(a.predictions, a.split)
    except (OSError, ValueError, KeyError) as exc:
        print(f"could not score: {exc}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(r, indent=2))
    elif a.markdown:
        print(markdown(r), end="")
    else:
        print(f"{r['predictions_file']} on {r['split']} ({r['transactions']} transactions)")
        print(f"  accuracy {r['accuracy_pct']}%, dollar-weighted {r['dollar_weighted_accuracy_pct']}%, macro F1 {r['macro_f1']}")
        print(f"  material errors {r['material_errors']}, deferred to ask {r['deferred_to_ask']}, missing {r['missing_predictions']}")
        for k, v in r["by_difficulty"].items():
            print(f"  {k:14} {v['accuracy_pct']:6}%  (n={v['n']})")
        for c in r["top_confusions"][:5]:
            print(f"  {c['count']:4} x {c['label']} {c['label_name']} -> {c['predicted']} {c['predicted_name']}")
        if r["accounts_not_in_chart"]:
            print(f"  accounts not in the chart: {', '.join(r['accounts_not_in_chart'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
