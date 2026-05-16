-- ============================================================
-- FILE: 02_queries.sql
-- PURPOSE: Analytical queries showcasing advanced SQL concepts
-- CONCEPTS COVERED:
--   1. Complex Multi-table JOINs
--   2. Window Functions
--   3. CTEs
--   4. CTEs + Window Functions combined
-- ============================================================

USE supply_chain_dw;

-- ============================================================
-- QUERY 1: COMPLEX MULTI-TABLE JOIN
-- BUSINESS QUESTION: Give a full order summary joining all
-- 4 tables — customer, product, supplier, and fact.
-- CONCEPTS: INNER JOIN across 4 tables, column aliasing,
--           CASE WHEN for readable labels
-- ============================================================
SELECT
    fo.order_id,
    -- Customer details
    CONCAT(dc.customer_fname, ' ', dc.customer_lname)   AS customer_name,
    dc.customer_segment,
    dc.customer_country,
    -- Product details
    dp.product_name,
    dp.product_category,
    dp.department_name,
    -- Supplier details
    ds.market,
    ds.order_region,
    ds.shipping_mode,
    -- Order metrics
    fo.order_date,
    fo.scheduled_ship_days,
    fo.actual_ship_days,
    fo.sales_per_order,
    fo.order_profit_per_order,
    fo.order_item_discount,
    -- Human readable delay label using CASE WHEN
    CASE
        WHEN fo.is_delayed = 1 THEN 'Late'
        ELSE 'On Time'
    END                                                 AS delivery_flag,
    fo.delivery_status
FROM fact_orders fo
INNER JOIN dim_customer dc ON fo.customer_id = dc.customer_id
INNER JOIN dim_product  dp ON fo.product_id  = dp.product_id
INNER JOIN dim_supplier ds ON fo.supplier_id = ds.supplier_id
ORDER BY fo.order_date DESC
LIMIT 100;


-- ============================================================
-- QUERY 2: WINDOW FUNCTIONS — Running totals & rankings
-- BUSINESS QUESTION: For each order show running revenue
-- total, rank by profit, and compare to market average.
-- CONCEPTS: SUM() OVER, RANK() OVER, AVG() OVER,
--           PARTITION BY, ORDER BY inside window
-- ============================================================
SELECT
    fo.order_id,
    fo.order_date,
    ds.market,
    ds.shipping_mode,
    fo.sales_per_order,
    fo.order_profit_per_order,

    -- Running total revenue per market
    -- Resets for each market partition
    ROUND(SUM(fo.sales_per_order) OVER (
        PARTITION BY ds.market
        ORDER BY fo.order_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 2)                                               AS running_revenue_by_market,

    -- Rank orders by profit within each market
    -- Rank 1 = most profitable order in that market
    RANK() OVER (
        PARTITION BY ds.market
        ORDER BY fo.order_profit_per_order DESC
    )                                                   AS profit_rank_in_market,

    -- Average profit for ALL orders in same shipping mode
    -- Lets us see if this order is above or below average
    ROUND(AVG(fo.order_profit_per_order) OVER (
        PARTITION BY ds.shipping_mode
    ), 2)                                               AS avg_profit_by_shipping_mode,

    -- Difference between this order and shipping mode average
    ROUND(fo.order_profit_per_order - AVG(fo.order_profit_per_order) OVER (
        PARTITION BY ds.shipping_mode
    ), 2)                                               AS profit_vs_mode_avg,

    -- Dense rank of order by sales across entire dataset
    DENSE_RANK() OVER (
        ORDER BY fo.sales_per_order DESC
    )                                                   AS global_sales_rank

FROM fact_orders fo
INNER JOIN dim_supplier ds ON fo.supplier_id = ds.supplier_id
ORDER BY ds.market, fo.order_date
LIMIT 200;


-- ============================================================
-- QUERY 3: WINDOW FUNCTIONS — LAG/LEAD for trend analysis
-- BUSINESS QUESTION: How does each month's revenue compare
-- to the previous month? Is the business growing?
-- CONCEPTS: LAG(), LEAD(), DATE_FORMAT, revenue growth %
-- ============================================================
WITH monthly_revenue AS (
    SELECT
        DATE_FORMAT(fo.order_date, '%Y-%m-01')          AS order_month,
        ds.market,
        ROUND(SUM(fo.sales_per_order), 2)               AS total_revenue,
        ROUND(SUM(fo.order_profit_per_order), 2)        AS total_profit,
        COUNT(DISTINCT fo.order_id)                     AS total_orders
    FROM fact_orders fo
    INNER JOIN dim_supplier ds ON fo.supplier_id = ds.supplier_id
    WHERE fo.order_date IS NOT NULL
    GROUP BY DATE_FORMAT(fo.order_date, '%Y-%m-01'), ds.market
)
SELECT
    order_month,
    market,
    total_revenue,
    total_profit,
    total_orders,

    -- Previous month revenue using LAG
    ROUND(LAG(total_revenue) OVER (
        PARTITION BY market
        ORDER BY order_month
    ), 2)                                               AS prev_month_revenue,

    -- Next month revenue using LEAD (forecasting view)
    ROUND(LEAD(total_revenue) OVER (
        PARTITION BY market
        ORDER BY order_month
    ), 2)                                               AS next_month_revenue,

    -- Month over month growth percentage
    ROUND(
        (total_revenue - LAG(total_revenue) OVER (
            PARTITION BY market ORDER BY order_month
        )) /
        NULLIF(LAG(total_revenue) OVER (
            PARTITION BY market ORDER BY order_month
        ), 0) * 100
    , 2)                                                AS mom_revenue_growth_pct

FROM monthly_revenue
ORDER BY market, order_month;


-- ============================================================
-- QUERY 4: CTE + JOIN — Customer lifetime value analysis
-- BUSINESS QUESTION: Who are our most valuable customers
-- and which segment do they belong to?
-- CONCEPTS: CTE, aggregation, JOIN, NTILE window function
-- ============================================================
WITH customer_orders AS (
    -- Step 1: Aggregate all orders per customer
    SELECT
        fo.customer_id,
        COUNT(DISTINCT fo.order_id)             AS total_orders,
        ROUND(SUM(fo.sales_per_order), 2)       AS lifetime_revenue,
        ROUND(SUM(fo.order_profit_per_order), 2) AS lifetime_profit,
        ROUND(AVG(fo.order_item_discount), 2)   AS avg_discount,
        SUM(fo.is_delayed)                      AS total_delayed_orders,
        MIN(fo.order_date)                      AS first_order_date,
        MAX(fo.order_date)                      AS last_order_date
    FROM fact_orders fo
    GROUP BY fo.customer_id
),
customer_segments AS (
    -- Step 2: Join with dim_customer to get segment info
    SELECT
        co.*,
        dc.customer_fname,
        dc.customer_lname,
        dc.customer_segment,
        dc.customer_country,
        -- Days between first and last order = customer tenure
        DATEDIFF(co.last_order_date, co.first_order_date) AS tenure_days
    FROM customer_orders co
    INNER JOIN dim_customer dc ON co.customer_id = dc.customer_id
)
SELECT
    customer_id,
    CONCAT(customer_fname, ' ', customer_lname)     AS customer_name,
    customer_segment,
    customer_country,
    total_orders,
    lifetime_revenue,
    lifetime_profit,
    avg_discount,
    total_delayed_orders,
    tenure_days,
    -- Divide customers into 4 tiers by lifetime revenue
    -- Tier 1 = top 25% most valuable customers
    NTILE(4) OVER (
        ORDER BY lifetime_revenue DESC
    )                                               AS revenue_tier,
    -- Rank within their segment
    RANK() OVER (
        PARTITION BY customer_segment
        ORDER BY lifetime_revenue DESC
    )                                               AS rank_in_segment
FROM customer_segments
ORDER BY lifetime_revenue DESC
LIMIT 50;


-- ============================================================
-- QUERY 5: CTE + WINDOW — Product category performance
-- BUSINESS QUESTION: Which product categories drive the most
-- revenue and how do they rank within each department?
-- CONCEPTS: Multiple CTEs, JOIN, PERCENT_RANK, NTILE
-- ============================================================
WITH category_metrics AS (
    -- Step 1: Revenue and profit per category
    SELECT
        dp.department_name,
        dp.product_category,
        COUNT(fo.order_item_id)                         AS total_orders,
        ROUND(SUM(fo.sales_per_order), 2)               AS total_revenue,
        ROUND(SUM(fo.order_profit_per_order), 2)        AS total_profit,
        ROUND(AVG(fo.order_item_discount), 2)           AS avg_discount,
        ROUND(AVG(fo.is_delayed) * 100, 2)              AS delay_rate_pct,
        ROUND(
            SUM(fo.order_profit_per_order)
            / NULLIF(SUM(fo.sales_per_order), 0) * 100
        , 2)                                            AS profit_margin_pct
    FROM fact_orders fo
    INNER JOIN dim_product dp ON fo.product_id = dp.product_id
    GROUP BY dp.department_name, dp.product_category
),
category_ranked AS (
    -- Step 2: Add window functions on top of aggregated data
    SELECT
        *,
        -- Rank category within its department by revenue
        RANK() OVER (
            PARTITION BY department_name
            ORDER BY total_revenue DESC
        )                                               AS revenue_rank_in_dept,

        -- What % of total revenue does this category represent
        ROUND(
            total_revenue / SUM(total_revenue) OVER () * 100
        , 2)                                            AS pct_of_total_revenue,

        -- Running revenue total within department
        ROUND(SUM(total_revenue) OVER (
            PARTITION BY department_name
            ORDER BY total_revenue DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ), 2)                                           AS dept_running_revenue,

        -- Percentile rank by profit margin
        ROUND(
            PERCENT_RANK() OVER (
                ORDER BY profit_margin_pct
            ) * 100
        , 1)                                            AS margin_percentile
    FROM category_metrics
)
SELECT *
FROM category_ranked
ORDER BY department_name, revenue_rank_in_dept;


-- ============================================================
-- QUERY 6: FULL COMPLEXITY — Supplier risk scorecard
-- BUSINESS QUESTION: Build a complete supplier risk score
-- combining delay rate, volume, and revenue at risk.
-- CONCEPTS: CTE chain, 3-table JOIN, multiple window functions,
--           CASE WHEN risk classification
-- ============================================================
WITH supplier_metrics AS (
    -- Step 1: Core metrics per supplier route
    SELECT
        ds.supplier_id,
        ds.market,
        ds.order_region,
        ds.shipping_mode,
        COUNT(fo.order_item_id)                         AS total_shipments,
        SUM(fo.is_delayed)                              AS delayed_shipments,
        ROUND(AVG(fo.is_delayed) * 100, 2)              AS delay_rate_pct,
        ROUND(AVG(fo.actual_ship_days
            - fo.scheduled_ship_days), 2)               AS avg_days_late,
        ROUND(SUM(fo.sales_per_order), 2)               AS total_revenue,
        ROUND(SUM(fo.order_profit_per_order), 2)        AS total_profit
    FROM fact_orders fo
    INNER JOIN dim_supplier ds ON fo.supplier_id = ds.supplier_id
    GROUP BY
        ds.supplier_id, ds.market,
        ds.order_region, ds.shipping_mode
),
supplier_scored AS (
    -- Step 2: Add risk score and window rankings
    SELECT
        *,
        -- Risk score formula: delay rate × log(volume)
        -- Penalises high-volume delays more than low-volume ones
        ROUND(
            delay_rate_pct * LOG(total_shipments)
        , 2)                                            AS risk_score,

        -- Rank by risk within each market
        RANK() OVER (
            PARTITION BY market
            ORDER BY delay_rate_pct DESC
        )                                               AS risk_rank_in_market,

        -- Revenue this supplier puts at risk
        ROUND(
            total_revenue * (delay_rate_pct / 100)
        , 2)                                            AS revenue_at_risk,

        -- Compare to market average delay rate
        ROUND(AVG(delay_rate_pct) OVER (
            PARTITION BY market
        ), 2)                                           AS market_avg_delay_rate
    FROM supplier_metrics
    WHERE total_shipments > 100
)
SELECT
    market,
    order_region,
    shipping_mode,
    total_shipments,
    delayed_shipments,
    delay_rate_pct,
    market_avg_delay_rate,
    -- How much worse than market average?
    ROUND(delay_rate_pct - market_avg_delay_rate, 2)    AS vs_market_avg,
    avg_days_late,
    total_revenue,
    revenue_at_risk,
    risk_score,
    risk_rank_in_market,
    -- Classify supplier into risk tiers
    CASE
        WHEN delay_rate_pct >= 70 THEN 'Critical'
        WHEN delay_rate_pct >= 50 THEN 'High'
        WHEN delay_rate_pct >= 30 THEN 'Medium'
        ELSE                           'Low'
    END                                                 AS risk_category
FROM supplier_scored
ORDER BY risk_score DESC;
