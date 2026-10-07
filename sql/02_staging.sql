-- 02_staging.sql — internal stage + raw orders table.
-- After running this, upload the CSV, then run the COPY in 03's load step:
--   PUT file://data/orders.csv @PORTFOLIO_DB.ANALYTICS.orders_stage AUTO_COMPRESS=TRUE;

USE WAREHOUSE PORTFOLIO_WH;
USE SCHEMA PORTFOLIO_DB.ANALYTICS;

CREATE STAGE IF NOT EXISTS orders_stage
  FILE_FORMAT = CSV_FF;

CREATE OR REPLACE TABLE stg_orders (
    order_id    NUMBER NOT NULL,
    customer_id NUMBER NOT NULL,
    order_date  DATE NOT NULL,
    product_sku VARCHAR NOT NULL,
    quantity    NUMBER NOT NULL,
    unit_price  NUMBER(10, 2) NOT NULL,
    line_total  NUMBER(10, 2) NOT NULL
);
