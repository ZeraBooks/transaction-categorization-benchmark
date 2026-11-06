#!/bin/sh
# Rebuild the four baseline prediction files and print their scores.
set -e
cd "$(dirname "$0")/.."
for train in cold warm; do
  python3 baselines/merchant_lookup.py --train $train > baselines/$train-merchant-only.csv
  python3 baselines/merchant_lookup.py --train $train --context > baselines/$train-merchant-plus-industry.csv
  python3 cli/score.py baselines/$train-merchant-only.csv --split $train-test
  python3 cli/score.py baselines/$train-merchant-plus-industry.csv --split $train-test
done
