"""Publish the dbt marts and model outputs as flat CSV extracts for the Tableau workbook.

Tableau Public cannot connect to DuckDB, so the warehouse is the system of record and these CSVs are a
read-only publication layer (one file per Tableau data source, column names already business-friendly
where the workbook shows them). Re-run after `dbt build` and `python -m src.churn_model`.
"""
from __future__ import annotations

import json
import sys

import duckdb

from src.config import TABLEAU, WAREHOUSE, get_logger

log = get_logger("tableau")

EXTRACTS = {
    # company KPIs, one row per month
    "saas_metrics_monthly": "select * from marts.fct_saas_metrics_monthly order by month",
    # MRR bridge by movement and segment; sign kept (+ growth, - losses) for waterfalls
    "mrr_movements": """
        select month, movement,
               case movement when 'new' then '1 New' when 'expansion' then '2 Expansion'
                             when 'reactivation' then '3 Reactivation' when 'contraction' then '4 Contraction'
                             else '5 Churn' end as movement_order,
               company_size, region, industry, acquisition_channel, contract_type, accounts, mrr_delta
        from marts.fct_mrr_movements order by month, movement_order""",
    # cohort grid; logo and revenue retention computed in Tableau from the additive columns
    "cohort_retention": "select * from marts.fct_cohort_retention order by cohort_month, months_since_start",
    # one row per account: lifecycle + (for active accounts) the latest churn score and drivers
    "accounts": """
        select d.account_id, d.account_name, d.signup_date, d.signup_month, d.company_size, d.industry, d.region,
               d.acquisition_channel, d.contract_type, d.current_plan, d.status, d.mrr_band,
               d.current_mrr, d.current_mrr * 12 as current_arr, d.current_seats, d.active_months,
               d.lifetime_revenue, d.cac_usd,
               r.churn_probability, r.risk_tier,
               case r.risk_tier when 'Critical' then 1 when 'High' then 2 when 'Medium' then 3 when 'Low' then 4 end
                   as risk_tier_order,
               r.arr_at_risk, r.seat_utilisation, r.logins_per_seat, r.utilisation_change_3m, r.tickets_90d,
               r.csat_90d, r.last_nps, r.payment_issues_6m, r.months_to_renewal, r.tenure_months,
               r.driver_1, r.driver_1_impact, r.driver_2, r.driver_2_impact, r.driver_3, r.driver_3_impact
        from marts.dim_accounts d
        left join ml.account_risk r using (account_id)
        order by r.arr_at_risk desc nulls last""",
    "churn_drivers": "select * from ml.churn_drivers order by rank",
    "model_performance": "select * from ml.model_performance order by kind, bucket",
}


def main() -> int:
    if not WAREHOUSE.exists():
        log.error("warehouse %s not found - run the generator and `dbt build` first", WAREHOUSE)
        return 1
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    manifest = {}
    try:
        for name, sql in EXTRACTS.items():
            out = TABLEAU / f"{name}.csv"
            rel = con.sql(sql)
            # write to a temp file then swap, so an open Tableau workbook never sees a half-written CSV
            tmp = out.with_suffix(".tmp")
            rel.write_csv(str(tmp), header=True)
            tmp.replace(out)
            n = con.sql(f"select count(*) from ({sql})").fetchall()[0][0]
            manifest[name] = n
            log.info("%-22s %8s rows -> %s", name, f"{n:,}", out.name)
    except duckdb.CatalogException as exc:
        log.error("missing table (%s) - run `dbt build` and `python -m src.churn_model` first", exc)
        return 1
    finally:
        con.close()
    (TABLEAU / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
