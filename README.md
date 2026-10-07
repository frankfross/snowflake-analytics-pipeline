# snowflake-analytics-pipeline

An end-to-end analytics pipeline on Snowflake: raw order CSVs → staged table →
SQL-built marts → data-contract checks, all orchestrated by a small Python
runner. Same retail-orders domain as my other portfolio projects, so the set
reads as one story. Portfolio project.

## What it does

1. `sql/01_setup.sql` — warehouse (XSMALL, auto-suspend), database, schema, CSV
   file format
2. `sql/02_staging.sql` — internal stage + `stg_orders`, `COPY INTO` from the
   uploaded CSV
3. `sql/03_marts.sql` — `mart_monthly_revenue`, `mart_customer_ltv` built in
   pure SQL
4. `sql/04_checks.sql` — assertion queries; every one must return zero rows
5. `sf_pipeline/run.py` — runs the steps in order, executes the checks,
   exits non-zero on any violation

## Quickstart

You need a Snowflake account (the 30-day free trial is plenty — this uses an
XSMALL warehouse that suspends after 60 idle seconds).

```bash
pip install -r requirements.txt

# 1. Fill in config.yaml (account, user) and export your password:
export SNOWFLAKE_PASSWORD='...'

# 2. Run the pipeline (setup -> staging tables; stops before COPY):
python -m sf_pipeline.run --config config.yaml --steps setup

# 3. Upload the CSV (SnowSQL):
# PUT file://data/orders.csv @PORTFOLIO_DB.ANALYTICS.orders_stage AUTO_COMPRESS=TRUE;

# 4. Load + build marts + run checks:
python -m sf_pipeline.run --config config.yaml --steps load,checks
```

Sample run output:

```
[step] setup          OK (4 statements)
[step] staging        OK (3 statements)
[step] load           OK (1 statement, 60 rows copied)
[step] marts          OK (2 statements)
[check] null keys                    PASS (0 rows)
[check] duplicate keys               PASS (0 rows)
[check] invalid quantities           PASS (0 rows)
[check] marts reconcile to staging   PASS (0 rows)
pipeline succeeded: 4/4 checks passed
```

## Design notes

- **SQL files are the transform layer.** The Python runner is deliberately
  thin — connect, execute in order, report. Logic lives in versioned `.sql`
  files you can read in a PR, not buried in Python strings.
- **Checks are queries, not code.** Each assertion in `04_checks.sql` is
  written so that *any returned row is a violation*. Adding a contract means
  adding a query, not a deploy.
- **Cost-aware by default.** XSMALL warehouse, `AUTO_SUSPEND = 60`,
  `INITIALLY_SUSPENDED = TRUE` — nothing runs (or bills) unless the pipeline
  does.
- The live Snowflake run needs your own account, so CI covers the runner
  logic (statement splitting, check evaluation, config validation) with a
  mocked connection — see `tests/`.
