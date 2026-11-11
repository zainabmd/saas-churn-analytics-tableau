# Data dictionary

Tables in the warehouse (`data/saas.duckdb`). Each section gives the grain, then the columns.

## `marts.fct_saas_metrics_monthly`
*Grain:* one row per month · 30 rows

| Column | Type | Description |
|---|---|---|
| `month` | DATE | First day of the calendar month |
| `mrr` | DOUBLE | Monthly recurring revenue billed that month (USD) |
| `arr` | DOUBLE | MRR × 12 |
| `customers` | BIGINT | Accounts with MRR > 0 |
| `new_mrr` | DOUBLE | MRR from first-ever paying accounts |
| `expansion_mrr` | DOUBLE | MRR increase from accounts already paying |
| `reactivation_mrr` | DOUBLE | MRR from returning churned accounts |
| `contraction_mrr` | DOUBLE | MRR decrease from accounts that keep paying (positive number) |
| `churned_mrr` | DOUBLE | MRR lost from accounts that stopped paying (positive number) |
| `net_new_mrr` | DOUBLE | new + expansion + reactivation − contraction − churned |
| `new_customers` | BIGINT | Accounts paying for the first time |
| `churned_customers` | BIGINT | Accounts that stopped paying this month |
| `reactivated_customers` | BIGINT | Churned accounts paying again |
| `logo_churn_rate` | DOUBLE | churned_customers ÷ accounts paying at the start of the month |
| `gross_mrr_churn_rate` | DOUBLE | (churned + contraction MRR) ÷ opening MRR |
| `expansion_rate` | DOUBLE | expansion MRR ÷ opening MRR |
| `arpa` | DOUBLE | Average revenue per paying account (MRR ÷ customers) |
| `quick_ratio` | DOUBLE | (new + expansion + reactivation) ÷ (contraction + churn) |
| `nrr_ttm` | DOUBLE | Net revenue retention: today's MRR from accounts that paid 12 months ago ÷ their MRR then |
| `grr_ttm` | DOUBLE | Gross revenue retention: as NRR, each account capped at its MRR 12 months ago |
| `cac_spend` | DOUBLE | Acquisition cost of accounts that signed up this month |
| `cac_per_customer` | DOUBLE | cac_spend ÷ new_customers |
| `ltv` | DOUBLE | ARPA × 80% gross margin ÷ 3-month average logo churn |

## `marts.fct_mrr_movements`
*Grain:* month × movement × segment · 8,858 rows

| Column | Type | Description |
|---|---|---|
| `month` | DATE | First day of the calendar month |
| `movement` | VARCHAR | new · expansion · contraction · churn · reactivation |
| `company_size` | VARCHAR | Employees band |
| `region` | VARCHAR | Sales region |
| `industry` | VARCHAR | Industry vertical |
| `acquisition_channel` | VARCHAR | First-touch acquisition channel |
| `contract_type` | VARCHAR | Monthly or Annual billing |
| `accounts` | BIGINT | Number of account-months in the group |
| `mrr_delta` | DOUBLE | MRR change for the movement (signed) |

## `marts.fct_cohort_retention`
*Grain:* cohort month × months since start × size × contract · 4,547 rows

| Column | Type | Description |
|---|---|---|
| `cohort_month` | DATE | Month of first payment |
| `months_since_start` | BIGINT | Months since the cohort month (0 = first month) |
| `company_size` | VARCHAR | Employees band |
| `contract_type` | VARCHAR | Monthly or Annual billing |
| `cohort_customers` | BIGINT | Cohort accounts observable at this age |
| `active_customers` | BIGINT | Cohort accounts paying at this age |
| `cohort_start_mrr` | DOUBLE | Cohort accounts' MRR in their first month |
| `mrr` | DOUBLE | Cohort MRR at this age (USD) |

## `marts.dim_accounts`
*Grain:* one row per account · 6,000 rows

| Column | Type | Description |
|---|---|---|
| `account_id` | VARCHAR | Account key (ACC-#####) |
| `account_name` | VARCHAR | Company name |
| `signup_date` | DATE | Date the account signed up |
| `signup_month` | DATE | Signup date truncated to month |
| `company_size` | VARCHAR | Employees band |
| `industry` | VARCHAR | Industry vertical |
| `region` | VARCHAR | Sales region |
| `acquisition_channel` | VARCHAR | First-touch acquisition channel |
| `contract_type` | VARCHAR | Monthly or Annual billing |
| `initial_plan` | VARCHAR | Plan at signup |
| `initial_seats` | BIGINT | Seats at signup |
| `cac_usd` | DOUBLE | Customer acquisition cost (USD) |
| `first_paid_month` | DATE | First month with MRR > 0 |
| `last_paid_month` | DATE | Last month with MRR > 0 |
| `active_months` | BIGINT | Months with MRR > 0 |
| `lifetime_revenue` | DOUBLE | Sum of billed MRR to date |
| `current_mrr` | DOUBLE | MRR in the as-of month |
| `current_seats` | BIGINT | Seats in the as-of month |
| `current_plan` | VARCHAR | Plan of the latest subscription event |
| `status` | VARCHAR | Active · Churned · Never paid |
| `mrr_band` | VARCHAR | Current MRR band |

## `marts.fct_churn_features`
*Grain:* one row per paying account-month · 70,848 rows

| Column | Type | Description |
|---|---|---|
| `account_id` | VARCHAR | Account key (ACC-#####) |
| `month` | DATE | First day of the calendar month |
| `mrr` | DOUBLE | Monthly recurring revenue billed that month (USD) |
| `seats` | BIGINT | Licensed seats |
| `seat_utilisation` | DOUBLE | Active users ÷ seats |
| `features_adopted` | BIGINT | Distinct features used (0–12) |
| `logins_per_seat` | DOUBLE | Monthly logins ÷ seats |
| `utilisation_change_3m` | DOUBLE | Seat utilisation − utilisation 3 months earlier |
| `logins_trend_3m` | DOUBLE | Logins per seat vs the prior 3-month average (−0.2 = 20% lower) |
| `mrr_change_3m` | DOUBLE | MRR − MRR 3 months earlier |
| `tenure_months` | BIGINT | Paying months to date |
| `churned_next_3m` | INTEGER | Label: 1 if the account stops paying within 3 months; null when not yet observable |
| `company_size` | VARCHAR | Employees band |
| `industry` | VARCHAR | Industry vertical |
| `region` | VARCHAR | Sales region |
| `acquisition_channel` | VARCHAR | First-touch acquisition channel |
| `contract_type` | VARCHAR | Monthly or Annual billing |
| `tickets_90d` | BIGINT | Support tickets opened in the last 3 months |
| `severe_tickets_90d` | BIGINT | High / Critical tickets in the last 3 months |
| `csat_90d` | DOUBLE | Average CSAT (1–5) of recent tickets |
| `last_nps` | BIGINT | Latest NPS score (0–10) |
| `payment_issues_6m` | BIGINT | Failed or recovered invoices in the last 6 months |
| `months_to_renewal` | BIGINT | Months until the next annual renewal (0 for monthly contracts) |

## `ml.account_risk`
*Grain:* one row per active account, as of the latest month · 5,105 rows

| Column | Type | Description |
|---|---|---|
| `account_id` | VARCHAR | Account key (ACC-#####) |
| `month` | DATE | First day of the calendar month |
| `mrr` | DOUBLE | Monthly recurring revenue billed that month (USD) |
| `arr` | DOUBLE | MRR × 12 |
| `seats` | BIGINT | Licensed seats |
| `seat_utilisation` | DOUBLE | Active users ÷ seats |
| `logins_per_seat` | DOUBLE | Monthly logins ÷ seats |
| `utilisation_change_3m` | DOUBLE | Seat utilisation − utilisation 3 months earlier |
| `tickets_90d` | BIGINT | Support tickets opened in the last 3 months |
| `csat_90d` | DOUBLE | Average CSAT (1–5) of recent tickets |
| `last_nps` | BIGINT | Latest NPS score (0–10) |
| `payment_issues_6m` | BIGINT | Failed or recovered invoices in the last 6 months |
| `months_to_renewal` | BIGINT | Months until the next annual renewal (0 for monthly contracts) |
| `tenure_months` | BIGINT | Paying months to date |
| `company_size` | VARCHAR | Employees band |
| `industry` | VARCHAR | Industry vertical |
| `region` | VARCHAR | Sales region |
| `acquisition_channel` | VARCHAR | First-touch acquisition channel |
| `contract_type` | VARCHAR | Monthly or Annual billing |
| `churn_probability` | FLOAT | Model probability of churning within 3 months |
| `risk_tier` | VARCHAR | Critical ≥ 30% · High ≥ 15% · Medium ≥ 7% · Low |
| `arr_at_risk` | DOUBLE | ARR × churn_probability |
| `driver_1` | VARCHAR | Feature pushing this account's risk up the most (SHAP) |
| `driver_1_impact` | FLOAT | SHAP value of driver 1 (log-odds) |
| `driver_2` | VARCHAR | 2nd strongest risk driver (SHAP) |
| `driver_2_impact` | FLOAT | SHAP value of driver 2 |
| `driver_3` | VARCHAR | 3rd strongest risk driver (SHAP) |
| `driver_3_impact` | FLOAT | SHAP value of driver 3 |

## `ml.churn_drivers`
*Grain:* one row per model feature · 20 rows

| Column | Type | Description |
|---|---|---|
| `feature` | VARCHAR | Model feature (business name) |
| `feature_key` | VARCHAR | Model column name of the feature |
| `mean_abs_shap` | FLOAT | Mean absolute SHAP value across scored accounts |
| `share_raising_risk` | DOUBLE | Share of accounts where the feature raises risk |
| `kind` | VARCHAR | Feature family: Behaviour · Support & billing · Firmographic |
| `rank` | BIGINT | Importance rank (1 = most important) |

## `ml.model_performance`
*Grain:* decile lift and calibration buckets on the Q1-2024 test window · 20 rows

| Column | Type | Description |
|---|---|---|
| `bucket` | BIGINT | Decile (1 = highest risk) or calibration bin |
| `accounts` | BIGINT | Number of account-months in the group |
| `churners` | DOUBLE | Accounts that churned within 3 months |
| `avg_pred` | FLOAT | Mean predicted probability in the decile |
| `churned_mrr` | DOUBLE | MRR of accounts that churned within 3 months |
| `churn_rate` | DOUBLE | Observed churn rate in the decile |
| `lift` | DOUBLE | Decile churn rate ÷ overall churn rate |
| `cum_capture` | DOUBLE | Share of all churners captured from the top decile down |
| `cum_mrr_capture` | DOUBLE | Share of churned MRR captured from the top decile down |
| `kind` | VARCHAR | Row type: `decile` (lift table) or `calibration` (reliability bins) |
| `predicted` | FLOAT | Mean predicted probability (calibration bin) |
| `observed` | DOUBLE | Observed churn rate (calibration bin) |

## Landing zone (`data/landing/*.csv`)
| File | Grain | Notes |
|---|---|---|
| plans | plan | price per seat and seat limits |
| accounts | account | firmographics, contract, acquisition channel, CAC |
| subscription_events | event | new / expansion / contraction / churn / reactivation with MRR before → after |
| invoices | account × month | paid · recovered · failed |
| usage_monthly | account × active month | seats, active users, utilisation, features, logins, billed MRR |
| support_tickets | ticket | severity, category, resolution hours, CSAT |
| nps_responses | response | quarterly NPS score |
| _ground_truth | account | hidden product-fit score (evaluation only, never a model feature) |
