"""Two simple baselines, learned from a dev split and scored on its test split.

    python3 baselines/merchant_lookup.py --train cold > baselines/cold-merchant-only.csv
    python3 baselines/merchant_lookup.py --train cold --context > baselines/cold-merchant-plus-industry.csv
    python3 baselines/merchant_lookup.py --train warm > baselines/warm-merchant-only.csv
    python3 baselines/merchant_lookup.py --train warm --context > baselines/warm-merchant-plus-industry.csv
    python3 cli/score.py baselines/cold-merchant-only.csv --split cold-test

merchant-only: clean the bank wrapper off the description, keep the first
two words as a merchant key, and predict the label that key had most often
in the dev split. Unseen merchants get Revenue for money in and Office
supplies for money out. This is roughly what "remember what this vendor was
last time" rules do.

--context: the same, but the key is (industry, merchant), falling back to
merchant-only. It's the cheapest way to show how much the business itself
decides the answer.
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRAP = re.compile(r"^(CARD PURCHASE \d\d/\d\d |CHECKCARD \d{4} |PURCHASE AUTHORIZED ON \d\d/\d\d )")


def merchant(desc):
    d = WRAP.sub("", desc.upper())
    words = [w for w in re.split(r"[\s*#_]+", d) if w and not any(c.isdigit() for c in w)]
    return " ".join(words[:2])


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", action="store_true")
    ap.add_argument("--train", choices=["warm", "cold"], default="cold", help="which split's dev rows to learn from")
    a = ap.parse_args(argv)
    txns = load("transactions.csv")
    labels = {r["txn_id"]: r["account"] for r in load("labels.csv")}
    dev = {r["txn_id"] for r in load("splits.csv") if r[a.train] == "dev"}
    industry = {r["business_id"]: r["industry"] for r in load("businesses.csv")}
    by_m, by_im = defaultdict(Counter), defaultdict(Counter)
    for t in txns:
        if t["txn_id"] in dev:
            m = merchant(t["description"])
            by_m[m][labels[t["txn_id"]]] += 1
            by_im[(industry[t["business_id"]], m)][labels[t["txn_id"]]] += 1
    w = csv.writer(sys.stdout, lineterminator="\r\n")
    w.writerow(["txn_id", "account"])
    for t in txns:
        m = merchant(t["description"])
        key = (industry[t["business_id"]], m)
        if a.context and by_im.get(key):
            guess = by_im[key].most_common(1)[0][0]
        elif by_m.get(m):
            guess = by_m[m].most_common(1)[0][0]
        else:
            guess = "4000" if float(t["amount"]) > 0 else "6250"
        w.writerow([t["txn_id"], guess])


if __name__ == "__main__":
    main()
