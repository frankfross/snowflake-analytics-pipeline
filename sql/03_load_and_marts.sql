-- 03_load_and_marts.sql — load staged CSV, then build marts in pure SQL.

USE WAREHOUSE PORTFOLIO_WH;
USE SCHEMA PORTFOLIO_DB.ANALYTICS;

COPY INTO stg_orders
FROM @orders_stage
ON_ERROR = 'ABORT_STATEMENT';

CREATE OR REPLACE TABLE mart_monthly_revenue AS
SELECT DATE_TRUNC('month', order_date) AS month,
       COUNT(*) AS orders,
       SUM(line_total) AS revenue
FROM stg_orders
GROUP BY 1;

CREATE OR REPLACE TABLE mart_customer_ltv AS
SELECT customer_id,
       COUNT(*) AS orders,
       SUM(line_total) AS lifetime_value,
       MIN(order_date) AS first_order,
       MAX(order_date) AS last_order
FROM stg_orders
GROUP BY 1;
