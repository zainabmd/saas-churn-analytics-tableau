"""Churn-risk model: XGBoost on the dbt feature mart, out-of-time validation, SHAP drivers.

Reads  marts.fct_churn_features (one row per paying account-month, label = churned within 3 months)
Writes models/churn_xgb.json, models/metrics.json and three model tables back into the warehouse
(schema `ml`) that the Tableau extract step publishes:
  ml.account_risk       latest-month churn probability, risk tier, ARR at risk, top-3 SHAP drivers
  ml.churn_drivers      global mean |SHAP| per feature + direction
  ml.model_performance  decile lift / capture and calibration on the untouched test window

Split (strictly by time, no account leakage across the label horizon):
  train  <= 2023-09   validation 2023-10 .. 2023-12 (early stopping)   test 2024-01 .. 2024-03
Final model is refit on train+validation with the early-stopped tree count, then scores 2024-06.
"""
from __future__ import annotations

import json
import sys
from datetime import date

import duckdb
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from src.config import CHURN_HORIZON_MONTHS, MODELS, WAREHOUSE, get_logger

log = get_logger("churn")

LABEL = f"churned_next_{CHURN_HORIZON_MONTHS}m"
TRAIN_END, VALID_END, TEST_END = date(2023, 9, 1), date(2023, 12, 1), date(2024, 3, 1)
NUMERIC = ["mrr", "seats", "seat_utilisation", "features_adopted", "logins_per_seat", "utilisation_change_3m",
           "logins_trend_3m", "mrr_change_3m", "tenure_months", "tickets_90d", "severe_tickets_90d", "csat_90d",
           "last_nps", "payment_issues_6m", "months_to_renewal"]
CATEGORICAL = ["company_size", "industry", "region", "acquisition_channel", "contract_type"]
FEATURES = NUMERIC + CATEGORICAL
# Business-readable names used in Tableau tooltips and the drivers chart
PRETTY = {
    "mrr": "MRR", "seats": "Seats", "seat_utilisation": "Seat utilisation", "features_adopted": "Features adopted",
    "logins_per_seat": "Logins per seat", "utilisation_change_3m": "Utilisation change (3m)",
    "logins_trend_3m": "Login trend (3m)", "mrr_change_3m": "MRR change (3m)", "tenure_months": "Tenure (months)",
    "tickets_90d": "Support tickets (90d)", "severe_tickets_90d": "Severe tickets (90d)", "csat_90d": "CSAT (90d)",
    "last_nps": "Last NPS score", "payment_issues_6m": "Payment issues (6m)", "months_to_renewal": "Months to renewal",
    "company_size": "Company size", "industry": "Industry", "region": "Region",
    "acquisition_channel": "Acquisition channel", "contract_type": "Contract type",
}
PARAMS = dict(objective="binary:logistic", eval_metric="aucpr", tree_method="hist", enable_categorical=True,
              max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=20,
              reg_lambda=2.0, n_estimators=2000, early_stopping_rounds=100, random_state=11)


def load(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.sql("select * from marts.fct_churn_features").df()
    if df.empty:
        raise RuntimeError("marts.fct_churn_features is empty - run `dbt build` first")
    df["month"] = pd.to_datetime(df["month"]).dt.date
    for c in CATEGORICAL:
        df[c] = df[c].astype("category")
    return df


def risk_tier(p: np.ndarray) -> np.ndarray:
    return np.select([p >= 0.30, p >= 0.15, p >= 0.07], ["Critical", "High", "Medium"], "Low")


def decile_table(y: np.ndarray, p: np.ndarray, mrr: np.ndarray) -> pd.DataFrame:
    d = pd.DataFrame({"y": y, "p": p, "mrr": mrr})
    d["decile"] = pd.qcut(d["p"].rank(method="first", ascending=False), 10, labels=range(1, 11)).astype(int)
    g = d.groupby("decile").agg(accounts=("y", "size"), churners=("y", "sum"), avg_pred=("p", "mean"),
                                churned_mrr=("mrr", lambda s: float(s[d.loc[s.index, "y"] == 1].sum())))
    g["churn_rate"] = g["churners"] / g["accounts"]
    g["lift"] = g["churn_rate"] / d["y"].mean()
    g["cum_capture"] = g["churners"].cumsum() / d["y"].sum()
    g["cum_mrr_capture"] = g["churned_mrr"].cumsum() / max(g["churned_mrr"].sum(), 1e-9)
    return g.reset_index()


def main() -> int:
    con = duckdb.connect(str(WAREHOUSE))
    df = load(con)
    labelled = df[df[LABEL].notna()].copy()
    train = labelled[labelled["month"] <= TRAIN_END]
    valid = labelled[(labelled["month"] > TRAIN_END) & (labelled["month"] <= VALID_END)]
    test = labelled[(labelled["month"] > VALID_END) & (labelled["month"] <= TEST_END)]
    as_of = df["month"].max()
    score = df[df["month"] == as_of].copy()
    log.info("rows  train %s · valid %s · test %s · score (%s) %s", f"{len(train):,}", f"{len(valid):,}",
             f"{len(test):,}", as_of, f"{len(score):,}")
    for name, part in [("train", train), ("valid", valid), ("test", test)]:
        if part.empty or part[LABEL].nunique() < 2:
            raise RuntimeError(f"{name} split has no positive/negative mix - check the date windows")

    pos_weight = float((train[LABEL] == 0).sum() / max((train[LABEL] == 1).sum(), 1))
    # 1) early stopping on the validation window
    m1 = xgb.XGBClassifier(**PARAMS, scale_pos_weight=np.sqrt(pos_weight))
    m1.fit(train[FEATURES], train[LABEL], eval_set=[(valid[FEATURES], valid[LABEL])], verbose=False)
    n_trees = int(m1.best_iteration) + 1
    p_valid = m1.predict_proba(valid[FEATURES])[:, 1]

    # 2) refit on train + valid with the chosen tree count; the test window stays untouched
    fit_df = pd.concat([train, valid])
    params = {k: v for k, v in PARAMS.items() if k not in ("n_estimators", "early_stopping_rounds")}
    model = xgb.XGBClassifier(**params, n_estimators=n_trees, scale_pos_weight=np.sqrt(pos_weight))
    model.fit(fit_df[FEATURES], fit_df[LABEL], verbose=False)
    p_test = model.predict_proba(test[FEATURES])[:, 1]
    y_test = test[LABEL].to_numpy().astype(int)

    dec = decile_table(y_test, p_test, test["mrr"].to_numpy())
    metrics = {
        "as_of_month": str(as_of), "horizon_months": CHURN_HORIZON_MONTHS, "trees": n_trees,
        "valid_roc_auc": round(roc_auc_score(valid[LABEL], p_valid), 4),
        "valid_pr_auc": round(average_precision_score(valid[LABEL], p_valid), 4),
        "test_roc_auc": round(roc_auc_score(y_test, p_test), 4),
        "test_pr_auc": round(average_precision_score(y_test, p_test), 4),
        "test_base_rate": round(float(y_test.mean()), 4),
        "test_brier": round(brier_score_loss(y_test, p_test), 4),
        "top_decile_lift": round(float(dec.loc[0, "lift"]), 2),
        "top_2_deciles_capture": round(float(dec.loc[1, "cum_capture"]), 4),
        "top_2_deciles_mrr_capture": round(float(dec.loc[1, "cum_mrr_capture"]), 4),
    }
    log.info("test ROC-AUC %.3f · PR-AUC %.3f (base %.3f) · top-decile lift %.1fx · top-20%% capture %.0f%%",
             metrics["test_roc_auc"], metrics["test_pr_auc"], metrics["test_base_rate"],
             metrics["top_decile_lift"], 100 * metrics["top_2_deciles_capture"])

    # calibration on the test window (10 equal-count bins)
    cal = pd.DataFrame({"p": p_test, "y": y_test})
    cal["bin"] = pd.qcut(cal["p"].rank(method="first"), 10, labels=range(1, 11)).astype(int)
    cal = cal.groupby("bin").agg(predicted=("p", "mean"), observed=("y", "mean"), accounts=("y", "size")).reset_index()

    # 3) score the as-of snapshot and explain it
    score["churn_probability"] = model.predict_proba(score[FEATURES])[:, 1]
    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(score[FEATURES])
    sv = np.asarray(sv)
    order = np.argsort(-sv, axis=1)          # features pushing risk UP the most
    for k in range(3):
        score[f"driver_{k + 1}"] = [PRETTY[FEATURES[j]] for j in order[:, k]]
        score[f"driver_{k + 1}_impact"] = sv[np.arange(len(score)), order[:, k]].round(4)
    score["risk_tier"] = risk_tier(score["churn_probability"].to_numpy())
    score["arr"] = score["mrr"] * 12
    score["arr_at_risk"] = score["arr"] * score["churn_probability"]

    drivers = pd.DataFrame({
        "feature": [PRETTY[f] for f in FEATURES],
        "feature_key": FEATURES,
        "mean_abs_shap": np.abs(sv).mean(axis=0),
        # share of accounts for which this feature raises churn risk
        "share_raising_risk": (sv > 0).mean(axis=0),
        "kind": ["Behaviour" if f in NUMERIC[:9] else "Support & billing" if f in NUMERIC[9:] else "Firmographic"
                 for f in FEATURES],
    }).sort_values("mean_abs_shap", ascending=False)
    drivers["rank"] = np.arange(1, len(drivers) + 1)

    perf = dec.assign(kind="decile").rename(columns={"decile": "bucket"})
    perf = pd.concat([perf, cal.rename(columns={"bin": "bucket"}).assign(kind="calibration")], ignore_index=True)

    risk_cols = ["account_id", "month", "mrr", "arr", "seats", "seat_utilisation", "logins_per_seat",
                 "utilisation_change_3m", "tickets_90d", "csat_90d", "last_nps", "payment_issues_6m",
                 "months_to_renewal", "tenure_months", "company_size", "industry", "region", "acquisition_channel",
                 "contract_type", "churn_probability", "risk_tier", "arr_at_risk",
                 "driver_1", "driver_1_impact", "driver_2", "driver_2_impact", "driver_3", "driver_3_impact"]
    risk = score[risk_cols].copy()
    for c in CATEGORICAL:
        risk[c] = risk[c].astype(str)

    con.execute("create schema if not exists ml")
    for name, frame in [("account_risk", risk), ("churn_drivers", drivers), ("model_performance", perf)]:
        con.register("frame", frame)
        con.execute(f"create or replace table ml.{name} as select * from frame")
        con.unregister("frame")
    con.close()

    model.save_model(MODELS / "churn_xgb.json")
    (MODELS / "metrics.json").write_text(json.dumps(metrics, indent=2))
    tiers = risk.groupby("risk_tier").agg(accounts=("account_id", "size"), arr=("arr", "sum"),
                                          arr_at_risk=("arr_at_risk", "sum"))
    log.info("risk book as of %s:\n%s", as_of, tiers.round(0).to_string())
    log.info("top drivers: %s", ", ".join(drivers["feature"].head(5)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:                      # noqa: BLE001 - CLI boundary: log and fail loudly
        log.exception("churn model failed")
        sys.exit(1)
