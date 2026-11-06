# Bookkeeping transaction categorization benchmark

How accurate is AI bookkeeping at categorizing bank transactions? This benchmark measures it: 3,170 fictional small-business bank transactions from 12 businesses, each labelled with the account a bookkeeper would book it to, and a scorer that reports accuracy, dollar-weighted accuracy, per-account F1 and the errors that actually hurt (a transfer booked as revenue, a loan payment booked as an expense). It was made by [ZeraBooks](https://www.zerabooks.com/ai-bookkeeping), whose AI bookkeeping categorizes every transaction from the client's own history and asks when it isn't sure. Run any tool against it, ours included.

- Inputs: [`data/transactions.csv`](data/transactions.csv) and [`data/businesses.csv`](data/businesses.csv)
- Answer key: [`data/labels.csv`](data/labels.csv), with the reason for every label
- Chart of accounts: [`data/chart-of-accounts.csv`](data/chart-of-accounts.csv) (34 accounts)
- Scorer: [`cli/score.py`](cli/score.py) (Python 3.8+, standard library)
- Baselines: [`baselines/`](baselines/)
- Release zip: [latest](https://github.com/ZeraBooks/transaction-categorization-benchmark/releases/latest)

## What a tool gets and what it returns

A tool gets the bank line and the business it belongs to:

```csv
txn_id,business_id,date,description,amount
T00310,B02,2026-04-02,CHECKCARD 0402 HENRY SCHEIN INC 686038 87242852110,-1512.53
```

```csv
business_id,name,industry,entity_type,collects_sales_tax
B02,Okafor Family Dental PC,dental,professional corporation,no
```

It returns one account number per transaction:

```csv
txn_id,account
T00310,6360
```

Then:

```bash
python3 cli/score.py my-tool-predictions.csv --split cold-test
python3 cli/score.py my-tool-predictions.csv --split cold-test --markdown > report.md
python3 cli/score.py my-tool-predictions.csv --json
```

## Why it's built this way

Most of a bank statement is easy. Gusto is payroll, Comcast is internet. The rows that cost bookkeepers time, and that a categorization tool gets wrong, are the ones where the bank line alone doesn't decide the answer. The benchmark labels every row with how hard it is:

| Difficulty | Rows | What it means | Example |
|---|---|---|---|
| `easy` | 2,083 | The description decides it | `COMCAST BUSINESS` is phone and internet |
| `judgment` | 524 | A normal bookkeeping convention decides it | A $3,047.05 Apple Store purchase is equipment, not supplies, because it's over the $2,500 de minimis threshold |
| `needs_context` | 563 | The business decides it, or nobody can tell from the line | `SHELL OIL` is cost of revenue for a freight carrier and a vehicle expense for a dentist. `CHECK 1043` needs the check image. A Venmo to a person needs a question. |

So the same merchant gets different labels in different businesses, and some rows are labelled **9999 Ask the client**. A tool that guesses on those is wrong. A tool that asks is right.

## Splits

`data/splits.csv` has two splits. Report which one you used.

- **cold**: four service businesses (dental, CPA, agency, therapy) are dev; the other eight are test. Each test business is a new client in an industry the tool has no labels for. This is the honest test for a tool that's onboarding a new client.
- **warm**: a random 30% of every business is dev, 70% test. This is a tool that already knows the client.

## Metrics

| Metric | What it tells you |
|---|---|
| Accuracy | Share of transactions on the right account. Missing predictions count as wrong. |
| Dollar-weighted accuracy | The same, weighted by amount. A wrong $12,000 deposit matters more than a wrong $6 coffee. |
| Macro F1 | Average F1 across accounts, so rare accounts (sales tax, loans, owner draws) count as much as common ones. |
| Material errors | Wrong in a way that moves profit: a balance sheet item (transfer, loan, card payment, owner money, equipment) booked to the P&L, or the reverse. |
| Deferred to ask | Rows where the tool said 9999 but the label was an account. Not counted as material, but not right either. |
| By difficulty, business, group | Where the errors are. |
| Top confusions | The 15 most common label to prediction mistakes. |

## Baselines

Two simple baselines in [`baselines/merchant_lookup.py`](baselines/merchant_lookup.py), learned only from the dev split. They clean the bank wrapper off the description, keep the first two words as a merchant key and predict that key's most common dev label. The `--context` version keys on industry plus merchant.

| Baseline | Split | Accuracy | Dollar-weighted | Macro F1 | Material errors | needs_context accuracy |
|---|---|---|---|---|---|---|
| Merchant only | cold-test | 91.59% | 95.20% | 0.7515 | 28 | 76.79% |
| Merchant + industry | cold-test | 91.59% | 95.20% | 0.7515 | 28 | 76.79% |
| Merchant only | warm-test | 95.03% | 94.99% | 0.7814 | 6 | 92.20% |
| Merchant + industry | warm-test | 96.02% | 95.94% | 0.8472 | 6 | 94.88% |

Read the gap, not the headline. A lookup that has seen the client hits 96%. On new clients it drops to 77% on the rows that need context, and its most common mistakes are ingredients booked as office supplies and owner draws booked as transfers. Industry doesn't help on the cold split because the test industries aren't in dev, which is exactly the new-client problem. Rebuild them with `sh baselines/run_all.sh`.

No ZeraBooks score is published here. A vendor scoring itself on its own benchmark proves very little. If you run a tool, ZeraBooks or any other, keep the predictions file and the split with the result so anyone can re-score it.

## The data

All 12 businesses, their owners, amounts and dates are fictional: a bakery, a dental practice, a landscaper, a freight carrier, a CPA, an electrician, an online store, a creative agency, a coffee bar, a property manager, a counseling practice and a law firm, April to September 2026. Descriptions use real merchant names (Shell, Costco, Gusto, Henry Schein) because reading those is the job. Card purchases are wrapped the way three common bank styles print them, and one style cuts lines at 45 characters, as real exports do.

`scripts/generate_samples.py` builds everything from a fixed seed. The label and reason for every merchant pattern are in that script, so you can disagree with one and see exactly what it would change.

## Chart of accounts

34 accounts a small-business bookkeeper would recognize: revenue and refunds, cost of goods, subcontractors and fuel as cost of revenue, 22 operating expense accounts, and the balance sheet accounts that most often get booked as expenses by mistake (transfers, card payments, loan payments, sales tax, owner contributions and draws, equipment). Plus 9999 Ask the client. Map your tool's accounts onto these before scoring.

## Where ZeraBooks fits

[ZeraBooks AI bookkeeping](https://www.zerabooks.com/ai-bookkeeping) works from bank statements inside a double-entry [general ledger](https://www.zerabooks.com/general-ledger-software). It categorizes from each client's own reviewed history, so a Costco run lands in ingredients for the bakery and supplies for the law firm, and it asks you when a line can't be decided, which is what the 9999 rows test. You can undo anything it did. One plan, $79 a month billed annually or $149 month to month, with a 7-day trial.

## Tests

```bash
python3 scripts/generate_samples.py
python3 -m unittest discover -s tests -v
```

## License and citation

Code MIT ([`LICENSE`](LICENSE)). Data, labels and docs CC BY 4.0 ([`LICENSE-SAMPLES`](LICENSE-SAMPLES)). Cite with [`CITATION.cff`](CITATION.cff). `MANIFEST.json` and `checksums.txt` list every data file with its SHA-256, so a published score can name the exact version it used.

Labels follow common U.S. small-business bookkeeping practice. They aren't tax advice; your accountant may book some of these differently, and the reasons column says why each label was chosen.
