# Tableau workbook

## What's in it
`tableau/SaaS Revenue and Churn.twbx` is a packaged workbook. It contains 4 dashboards and a snapshot of the data.

| Dashboard | What it shows |
|---|---|
| Revenue Overview | KPI tiles, ARR trend, MRR gained vs lost, NRR vs GRR |
| Growth & Segments | MRR by region, industry and channel, with shared filters |
| Cohort Retention | retention heatmap and curves by contract and company size |
| Churn Risk | ARR at risk, risk tiers, SHAP drivers, accounts to save (click a tier to filter) |

## Open it
Double-click the `.twbx`, or open it from Tableau Desktop or Tableau Public (2024.3 or newer).
Dashboard tabs are at the bottom. Press **F7** for presentation mode.

## Refresh the data
1. Run the pipeline: `python run_pipeline.py`. It writes new CSVs to `tableau/data/`.
2. In Tableau, go to **Data → Edit Data Source** (or **Replace Data Source**) for each data source.
3. Point it at the matching CSV in `tableau/data/`, then refresh the extract if Tableau asks.
4. Save the workbook as a packaged `.twbx`.

## Publish to Tableau Public
1. **File → Save to Tableau Public As…** and sign in.
2. Name it, for example *SaaS Revenue & Churn Analytics*.
3. On the web page, add a short description and choose a thumbnail.
4. Copy the share link into the README.
