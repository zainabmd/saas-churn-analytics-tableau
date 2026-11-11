"""
Synthetic B2B SaaS operating data, Jan-2022 → Jun-2024 (the "extract" step).

Simulates a subscription business month by month:

* **6,000 accounts** sign up on a growing curve. Each has a company size,
  industry, region, acquisition channel, contract type (monthly or annual),
  plan (Starter / Growth / Business / Enterprise) and seats.
* **Hidden product fit** (0–1) per account drives everything observable:
  seat utilisation, feature adoption, logins, support tickets, CSAT, NPS and
  payment reliability. Data scientists never see it directly. They must infer
  it, as in real life.
* **Lifecycle events** come from monthly hazards:
  - *expansion* (seats or upgrade) is likelier with high utilisation;
  - *contraction* is likelier with low utilisation;
  - *churn* rises with low fit, falling usage, failed payments and bad support,
    peaks in the first 90 days, and for annual contracts can only happen at
    renewal;
  - *reactivation* sometimes follows churn.
* **Pre-churn decay:** usage starts sliding 1–3 months before a churn, which is
  the early-warning signal a churn model should detect.

Outputs (landing CSVs, like a SaaS billing + product-analytics export):
    accounts, plans, subscription_events, invoices, usage_monthly, support_tickets, nps_responses

    python -m src.generate
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from src.config import END, LANDING, SEED, START, get_logger

log = get_logger("generate")

PLANS = pd.DataFrame([
    {"plan": "Starter", "tier": 1, "price_per_seat": 15, "min_seats": 3, "max_seats": 20},
    {"plan": "Growth", "tier": 2, "price_per_seat": 29, "min_seats": 8, "max_seats": 60},
    {"plan": "Business", "tier": 3, "price_per_seat": 49, "min_seats": 20, "max_seats": 200},
    {"plan": "Enterprise", "tier": 4, "price_per_seat": 79, "min_seats": 60, "max_seats": 600},
])
SIZES = {"1-10": 0.28, "11-50": 0.32, "51-200": 0.22, "201-1000": 0.13, "1000+": 0.05}
SIZE_PLAN = {"1-10": [0.80, 0.18, 0.02, 0.0], "11-50": [0.35, 0.52, 0.12, 0.01], "51-200": [0.06, 0.50, 0.39, 0.05],
             "201-1000": [0.0, 0.20, 0.58, 0.22], "1000+": [0.0, 0.05, 0.45, 0.50]}
INDUSTRIES = {"Software": 0.22, "Financial Services": 0.12, "Healthcare": 0.10, "Retail & E-commerce": 0.14,
              "Manufacturing": 0.10, "Professional Services": 0.14, "Education": 0.08, "Media": 0.10}
REGIONS = {"North America": 0.46, "EMEA": 0.32, "APAC": 0.15, "LATAM": 0.07}
CHANNELS = {"Organic Search": 0.24, "Paid Search": 0.18, "Partner": 0.12, "Outbound Sales": 0.16, "Referral": 0.14,
            "Events": 0.06, "Product-led (free trial)": 0.10}
CHANNEL_FIT = {"Referral": 0.10, "Partner": 0.06, "Outbound Sales": 0.03, "Organic Search": 0.0, "Events": 0.0,
               "Product-led (free trial)": -0.02, "Paid Search": -0.07}
FEATURES = 12


def _choice(rng, d: dict, n: int):
    k = list(d)
    p = np.array(list(d.values()), dtype=float)
    return rng.choice(k, size=n, p=p / p.sum())


def run(seed: int = SEED, n_accounts: int = 6000) -> dict[str, int]:
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    months = pd.date_range(START, END, freq="MS")
    M = len(months)

    # ---------------- accounts ----------------
    # Signup weights grow ~45%/yr with a December dip and a January budget bump.
    w = (1.45 ** (np.arange(M) / 12)) * np.where(months.month == 12, 0.75, 1.0) * np.where(months.month == 1, 1.15, 1.0)
    signup_m = rng.choice(M, size=n_accounts, p=w / w.sum())
    size = _choice(rng, SIZES, n_accounts)
    plan_idx = np.array([rng.choice(4, p=SIZE_PLAN[s]) for s in size])
    channel = _choice(rng, CHANNELS, n_accounts)
    contract = np.where(rng.random(n_accounts) < np.array([0.15, 0.35, 0.6, 0.9])[plan_idx], "Annual", "Monthly")
    fit = np.clip(rng.beta(3.2, 2.0, n_accounts) + np.vectorize(CHANNEL_FIT.get)(channel)
                  + np.where(contract == "Annual", 0.05, 0.0), 0.02, 0.98)
    lo, hi = PLANS["min_seats"].to_numpy()[plan_idx], PLANS["max_seats"].to_numpy()[plan_idx]
    seats = np.round(np.exp(rng.uniform(np.log(lo), np.log(np.maximum(hi * 0.4, lo + 1))))).astype(int)
    accounts = pd.DataFrame({
        "account_id": [f"ACC-{i:05d}" for i in range(1, n_accounts + 1)],
        "account_name": [f"{a} {b}" for a, b in zip(rng.choice(["Apex", "Blue", "Cedar", "Delta", "Echo", "Falcon", "Granite", "Harbor",
                                                                  "Iris", "Juniper", "Kite", "Lumen", "Maple", "Nimbus", "Orbit",
                                                                  "Pioneer", "Quartz", "Ridge", "Summit", "Tidal"], n_accounts),
                                                     rng.choice(["Labs", "Group", "Systems", "Partners", "Health", "Logistics",
                                                                 "Capital", "Studio", "Works", "Retail", "Learning", "Media"], n_accounts))],
        "signup_date": [months[m] + pd.Timedelta(days=int(d)) for m, d in zip(signup_m, rng.integers(0, 28, n_accounts))],
        "company_size": size, "industry": _choice(rng, INDUSTRIES, n_accounts), "region": _choice(rng, REGIONS, n_accounts),
        "acquisition_channel": channel, "contract_type": contract,
        "initial_plan": PLANS["plan"].to_numpy()[plan_idx], "initial_seats": seats,
        # CAC = gross-margin-adjusted first-month MRR x CAC-payback months: ~18 for sales-led and
        # paid channels, ~9 for organic / referral / product-led (typical B2B SaaS benchmarks)
        "cac_usd": np.round(seats * PLANS["price_per_seat"].to_numpy()[plan_idx] * 0.80
                            * np.where(np.isin(channel, ["Referral", "Organic Search", "Product-led (free trial)"]), 9.0, 18.0)
                            * rng.lognormal(0, 0.30, n_accounts), 0),
    })

    # ---------------- monthly simulation ----------------
    ev, inv, use, tickets, nps = [], [], [], [], []
    tid = 0
    for i in range(n_accounts):
        a_id, m0 = accounts.at[i, "account_id"], signup_m[i]
        p, s, f = plan_idx[i], seats[i], fit[i]
        active, churn_month, decay_start = True, None, None
        mrr = s * PLANS.at[p, "price_per_seat"] * (0.85 if contract[i] == "Annual" else 1.0)
        ev.append((a_id, months[m0], "new", 0.0, mrr, PLANS.at[p, "plan"], s))
        util_trend = 0.0
        for m in range(m0, M):
            tenure = m - m0
            if not active:
                # Win-back: 1.5%/month for decent-fit accounts
                if f > 0.5 and rng.random() < 0.015:
                    active, s = True, max(PLANS.at[p, "min_seats"], int(s * 0.7))
                    mrr = s * PLANS.at[p, "price_per_seat"]
                    ev.append((a_id, months[m], "reactivation", 0.0, mrr, PLANS.at[p, "plan"], s))
                    decay_start, util_trend = None, 0.0
                else:
                    continue
            # ----- observable behaviour driven by fit (with pre-churn decay) -----
            decay = 0.0 if decay_start is None else 0.12 * (m - decay_start + 1)
            util = float(np.clip(0.25 + 0.65 * f + util_trend - decay + rng.normal(0, 0.06), 0.02, 1.0))
            active_users = max(0, int(round(s * util)))
            adoption = int(np.clip(round(FEATURES * (0.2 + 0.7 * f) - 6 * decay + rng.normal(0, 1.2)), 1, FEATURES))
            logins = int(active_users * rng.uniform(14, 26) * (0.6 + 0.6 * f))
            t_rate = (0.4 + 0.012 * s ** 0.85) * (1.6 - f) * (1.8 if tenure < 3 else 1.0)
            n_t = rng.poisson(t_rate)
            for _ in range(n_t):
                tid += 1
                sev = rng.choice(["Low", "Medium", "High", "Urgent"], p=[0.45, 0.35, 0.15, 0.05])
                hours = float(rng.lognormal(np.log({"Low": 30, "Medium": 18, "High": 8, "Urgent": 3}[sev]), 0.6))
                csat = int(np.clip(round(rng.normal(3.2 + 1.6 * f - 0.15 * (hours > 48), 0.8)), 1, 5))
                tickets.append((f"TCK-{tid:06d}", a_id, months[m] + pd.Timedelta(days=int(rng.integers(0, 28))), sev,
                                rng.choice(["Billing", "Bug", "How-to", "Integration", "Performance", "Feature request"]),
                                round(hours, 1), csat))
            if tenure % 3 == 2 and rng.random() < 0.35:
                score = int(np.clip(round(rng.normal(3 + 6.5 * f - 4 * decay, 1.6)), 0, 10))
                nps.append((a_id, months[m] + pd.Timedelta(days=int(rng.integers(0, 28))), score))

            # ----- billing -----
            billed_this_month = contract[i] == "Monthly" or tenure % 12 == 0
            failed = False
            if billed_this_month:
                amount = mrr * (12 if contract[i] == "Annual" else 1)
                p_fail = (0.02 + 0.10 * (s < 10) + 0.06 * (1 - f)) * (0.4 if contract[i] == "Annual" else 1.0)
                failed = rng.random() < p_fail
                recovered = failed and rng.random() < 0.6
                inv.append((f"INV-{len(inv) + 1:07d}", a_id, months[m], round(amount, 2),
                            "paid" if not failed else ("recovered" if recovered else "failed")))
                failed = failed and not recovered

            use.append((a_id, months[m], s, active_users, round(util, 3), adoption, logins, round(mrr, 2)))

            # ----- lifecycle hazards -----
            renewal = contract[i] == "Monthly" or (tenure > 0 and tenure % 12 == 11)
            h_churn = (0.002 + 0.07 * (1 - f) ** 2.2) * (2.2 if tenure < 3 else 1.0) * (3.0 if failed else 1.0) \
                * (1.6 if n_t >= 4 else 1.0) * np.array([1.4, 1.0, 0.8, 0.5])[p]
            if contract[i] == "Annual":
                h_churn = h_churn * 6 if renewal else 0.0
            if decay_start is None and active and rng.random() < min(h_churn * 1.6, 0.9):
                decay_start = m      # the account starts disengaging...
                churn_month = m + int(rng.integers(1, 4))   # ...and leaves 1-3 months later
            if churn_month is not None and m >= churn_month and (renewal or contract[i] == "Monthly"):
                ev.append((a_id, months[m] + pd.Timedelta(days=27), "churn", mrr, 0.0, PLANS.at[p, "plan"], s))
                active, churn_month, mrr = False, None, 0.0
                continue
            if decay_start is not None and churn_month is None:
                decay_start = None
            if decay_start is None:
                if util > 0.75 and rng.random() < 0.05 + 0.08 * f:            # expansion
                    old = mrr
                    if p < 3 and s * 1.4 > PLANS.at[p, "max_seats"] * 0.7 and rng.random() < 0.5:
                        p += 1
                    s = int(min(PLANS.at[p, "max_seats"], max(s * rng.uniform(1.1, 1.5), PLANS.at[p, "min_seats"])))
                    mrr = s * PLANS.at[p, "price_per_seat"] * (0.85 if contract[i] == "Annual" else 1.0)
                    ev.append((a_id, months[m] + pd.Timedelta(days=15), "expansion", old, mrr, PLANS.at[p, "plan"], s))
                    util_trend += 0.02
                elif util < 0.45 and renewal and rng.random() < 0.12:           # contraction (seat cut)
                    old = mrr
                    s = max(PLANS.at[p, "min_seats"], int(s * rng.uniform(0.6, 0.85)))
                    mrr = s * PLANS.at[p, "price_per_seat"] * (0.85 if contract[i] == "Annual" else 1.0)
                    if mrr < old:
                        ev.append((a_id, months[m] + pd.Timedelta(days=15), "contraction", old, mrr, PLANS.at[p, "plan"], s))

    tables = {
        "plans": PLANS,
        "accounts": accounts,
        "subscription_events": pd.DataFrame(ev, columns=["account_id", "event_date", "event_type", "mrr_before", "mrr_after", "plan", "seats"]),
        "invoices": pd.DataFrame(inv, columns=["invoice_id", "account_id", "invoice_month", "amount_usd", "status"]),
        "usage_monthly": pd.DataFrame(use, columns=["account_id", "month", "seats", "active_users", "seat_utilisation",
                                                    "features_adopted", "logins", "mrr"]),
        "support_tickets": pd.DataFrame(tickets, columns=["ticket_id", "account_id", "opened_at", "severity", "category",
                                                          "resolution_hours", "csat"]),
        "nps_responses": pd.DataFrame(nps, columns=["account_id", "responded_at", "score"]),
    }
    tables["subscription_events"].insert(0, "event_id", [f"EVT-{i:06d}" for i in range(1, len(ev) + 1)])
    tables["_ground_truth"] = accounts[["account_id"]].assign(product_fit=fit.round(4))
    LANDING.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, df in tables.items():
        df.to_csv(LANDING / f"{name}.csv", index=False)
        counts[name] = len(df)
    (LANDING / "_manifest.json").write_text(json.dumps({"rows": counts, "seed": seed, "window": [str(START), str(END)],
                                                         "seconds": round(time.perf_counter() - t0, 1)}, indent=2))
    log.info("Landing written: %s rows in %.1fs · %s", f"{sum(counts.values()):,}", time.perf_counter() - t0, counts)
    return counts


if __name__ == "__main__":
    run()
