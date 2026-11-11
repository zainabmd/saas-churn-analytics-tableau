"""Shared configuration for the SaaS revenue & churn analytics project."""
from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("SAAS_DATA_DIR", ROOT / "data"))
LANDING = DATA / "landing"                      # extract output (CSV, like a billing / product-analytics export)
WAREHOUSE = Path(os.getenv("SAAS_WAREHOUSE", DATA / "saas.duckdb"))
TABLEAU = ROOT / "tableau" / "data"              # extracts consumed by the Tableau workbook
MODELS = ROOT / "models"
for d in (LANDING, TABLEAU, MODELS):
    d.mkdir(parents=True, exist_ok=True)

SEED = int(os.getenv("SAAS_SEED", "11"))
START, END = date(2022, 1, 1), date(2024, 6, 30)  # 30 months of history; the "as of" date is mid-2024
CHURN_HORIZON_MONTHS = 3                           # predict churn in the next 90 days


def get_logger(name: str) -> logging.Logger:
    lg = logging.getLogger(name)
    if not lg.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)-10s | %(message)s"))
        lg.addHandler(h)
    lg.setLevel(os.getenv("SAAS_LOG_LEVEL", "INFO"))
    lg.propagate = False
    return lg
