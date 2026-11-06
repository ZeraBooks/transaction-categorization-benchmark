import contextlib
import csv
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))
import score  # noqa: E402


def rows(name):
    return list(csv.DictReader(open(os.path.join(ROOT, "data", name), encoding="utf-8")))


class Data(unittest.TestCase):
    def test_every_label_is_in_the_chart(self):
        chart = {r["account"] for r in rows("chart-of-accounts.csv")}
        for r in rows("labels.csv"):
            self.assertIn(r["account"], chart, r["txn_id"])
            self.assertIn(r["difficulty"], {"easy", "judgment", "needs_context"})
            self.assertTrue(r["reason"])

    def test_inputs_labels_and_splits_line_up(self):
        t, l, s = rows("transactions.csv"), rows("labels.csv"), rows("splits.csv")
        self.assertEqual([r["txn_id"] for r in t], [r["txn_id"] for r in l])
        self.assertEqual([r["txn_id"] for r in t], [r["txn_id"] for r in s])
        self.assertEqual(len({r["txn_id"] for r in t}), len(t))
        self.assertGreater(len(t), 3000)

    def test_labels_are_not_in_the_inputs(self):
        self.assertNotIn("account", rows("transactions.csv")[0])

    def test_cold_split_holds_out_whole_businesses(self):
        t = {r["txn_id"]: r["business_id"] for r in rows("transactions.csv")}
        dev = {t[r["txn_id"]] for r in rows("splits.csv") if r["cold"] == "dev"}
        test = {t[r["txn_id"]] for r in rows("splits.csv") if r["cold"] == "test"}
        self.assertEqual(dev & test, set())


class Scorer(unittest.TestCase):
    def write(self, d, mapping):
        p = os.path.join(d, "p.csv")
        with open(p, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["txn_id", "account"])
            w.writerows(mapping.items())
        return p

    def test_perfect_predictions_score_100(self):
        with tempfile.TemporaryDirectory() as d:
            r = score.score(self.write(d, {x["txn_id"]: x["account"] for x in rows("labels.csv")}))
            self.assertEqual(r["accuracy_pct"], 100.0)
            self.assertEqual(r["macro_f1"], 1.0)
            self.assertEqual(r["material_errors"], 0)

    def test_missing_predictions_count_as_wrong(self):
        with tempfile.TemporaryDirectory() as d:
            labels = rows("labels.csv")
            half = {x["txn_id"]: x["account"] for x in labels[: len(labels) // 2]}
            r = score.score(self.write(d, half))
            self.assertEqual(r["missing_predictions"], len(labels) - len(half))
            self.assertAlmostEqual(r["accuracy_pct"], 100 * len(half) / len(labels), places=1)

    def test_material_error_when_transfer_called_revenue(self):
        with tempfile.TemporaryDirectory() as d:
            labels = rows("labels.csv")
            pred = {x["txn_id"]: x["account"] for x in labels}
            transfers = [x["txn_id"] for x in labels if x["account"] == "1000"]
            for tid in transfers:
                pred[tid] = "4000"
            r = score.score(self.write(d, pred))
            self.assertEqual(r["material_errors"], len(transfers))
            self.assertEqual(r["top_confusions"][0]["label"], "1000")

    def test_asking_is_deferral_not_material(self):
        with tempfile.TemporaryDirectory() as d:
            pred = {x["txn_id"]: "9999" for x in rows("labels.csv")}
            r = score.score(self.write(d, pred))
            self.assertEqual(r["material_errors"], 0)
            self.assertGreater(r["deferred_to_ask"], 0)

    def test_baselines_score_and_cli_runs(self):
        p = os.path.join(ROOT, "baselines", "cold-merchant-only.csv")
        r = score.score(p, "cold-test")
        self.assertGreater(r["accuracy_pct"], 50)
        self.assertLess(r["accuracy_pct"], 100)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(score.main([p, "--split", "cold-test", "--markdown"]), 0)


if __name__ == "__main__":
    unittest.main()
