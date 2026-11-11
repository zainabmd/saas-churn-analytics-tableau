"""End-to-end pipeline: synthetic billing/product data -> dbt warehouse -> churn model -> Tableau data export.

    python run_pipeline.py                 # everything
    python run_pipeline.py --from dbt      # skip data generation
    python run_pipeline.py --only model    # one stage

Stages run in order and stop at the first failure (each stage exits non-zero on error).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from src.config import get_logger

ROOT = Path(__file__).resolve().parent
log = get_logger("pipeline")

STAGES = {
    "generate": [sys.executable, "-m", "src.generate"],
    # dbt runs from its project folder so the relative landing path in _sources.yml resolves
    "dbt": [sys.executable, "-c", "from dbt.cli.main import cli; cli()", "build", "--profiles-dir", "."],
    "model": [sys.executable, "-m", "src.churn_model"],
    "extracts": [sys.executable, "-m", "src.export_tableau"],
}
CWD = {"dbt": ROOT / "dbt"}


def run(stage: str) -> None:
    t0 = time.perf_counter()
    log.info("▶ %s", stage)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT)}
    res = subprocess.run(STAGES[stage], cwd=CWD.get(stage, ROOT), env=env)
    if res.returncode != 0:
        log.error("✖ %s failed (exit %s)", stage, res.returncode)
        sys.exit(res.returncode)
    log.info("✔ %s in %.1fs", stage, time.perf_counter() - t0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--from", dest="start", choices=STAGES, help="start at this stage")
    g.add_argument("--only", choices=STAGES, help="run a single stage")
    args = ap.parse_args()
    names = list(STAGES)
    todo = [args.only] if args.only else names[names.index(args.start):] if args.start else names
    for stage in todo:
        run(stage)
    log.info("done · open tableau/SaaS Revenue and Churn.twbx in Tableau and refresh its data sources")


if __name__ == "__main__":
    main()
