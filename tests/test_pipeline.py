"""Integration checks on the built artefacts (run after `python run_pipeline.py`).

These assert business invariants rather than exact numbers, so they survive a reseed:
the MRR bridge closes, retention metrics are in sane ranges and the model beats a random ranking.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "saas.duckdb"

pytestmark = pytest.mark.skipif(not WH.exists(), reason="run `python run_pipeline.py` first")


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(WH), read_only=True)
    yield c
    c.close()


def test_mrr_bridge_closes_every_month(con):
    m = con.sql("select month, mrr, net_new_mrr from marts.fct_saas_metrics_monthly order by month").df()
    opening = m["mrr"].shift(fill_value=0)
    assert ((opening + m["net_new_mrr"] - m["mrr"]).abs() < 0.01).all()


def test_retention_metrics_in_plausible_ranges(con):
    last = con.sql("select * from marts.fct_saas_metrics_monthly order by month desc limit 1").df().iloc[0]
    assert 0.85 <= last["grr_ttm"] <= 1.0          # gross retention can never exceed 100 %
    assert last["nrr_ttm"] >= last["grr_ttm"]       # expansion only adds
    assert 0.002 <= last["logo_churn_rate"] <= 0.05
    ltv_cac = last["ltv"] / last["cac_per_customer"]
    assert 2 <= ltv_cac <= 15, ltv_cac


def test_every_account_month_has_one_movement(con):
    dup = con.sql("select account_id, month, count(*) n from intermediate.int_mrr_movements group by 1, 2 having n > 1").df()
    assert dup.empty


def test_churn_labels_never_peek_past_as_of(con):
    late = con.sql("""select count(*) from marts.fct_churn_features
                      where churned_next_3m is not null and month > date '2024-03-01'""").fetchall()[0][0]
    assert late == 0


def test_model_beats_random_and_is_calibrated_enough():
    m = json.loads((ROOT / "models" / "metrics.json").read_text())
    assert m["test_roc_auc"] > 0.75
    assert m["test_pr_auc"] > 3 * m["test_base_rate"]
    assert m["top_decile_lift"] > 3
    assert m["test_brier"] < m["test_base_rate"]     # better than always predicting the base rate's square-ish loss


def test_risk_book_only_scores_active_accounts(con):
    r = con.sql("""select d.status, count(*) n from ml.account_risk r join marts.dim_accounts d using (account_id)
                   group by 1""").df()
    assert set(r["status"]) == {"Active"}
