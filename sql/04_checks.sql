-- 04_checks.sql — data-contract assertions.
-- Convention: EVERY query must return zero rows. Any row = contract violated.
-- The runner reports each query by the comment above it.

USE SCHEMA PORTFOLIO_DB.ANALYTICS;

-- null keys
SELECT order_id FROM stg_orders WHERE order_id IS NULL;

-- duplicate keys
SELECT order_id, COUNT(*) AS n FROM stg_orders GROUP BY 1 HAVING COUNT(*) > 1;

-- invalid quantities
SELECT order_id, quantity FROM stg_orders WHERE quantity <= 0;

-- negative prices
SELECT order_id, unit_price FROM stg_orders WHERE unit_price < 0;

-- marts reconcile to staging
SELECT diff FROM (
    SELECT (SELECT SUM(revenue) FROM mart_monthly_revenue)
         - (SELECT SUM(line_total) FROM stg_orders) AS diff
) WHERE diff != 0;
