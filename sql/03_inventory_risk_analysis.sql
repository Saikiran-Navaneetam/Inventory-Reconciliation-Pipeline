
-- =====================================================
-- INVENTORY RECONCILIATION PIPELINE
-- SQL BUSINESS ANALYSIS - 02: INVENTORY RISK
-- =====================================================

-- 1. Latest inventory position for every product/location
WITH latest_inventory AS (
    SELECT *
    FROM daily_inventory_balances
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY product_id, location_id
        ORDER BY business_date DESC
    ) = 1
)
SELECT
    product_id,
    location_id,
    business_date,
    closing_quantity,
    negative_stock_flag
FROM latest_inventory
ORDER BY closing_quantity ASC
LIMIT 20;


-- 2. Negative inventory by location
WITH latest_inventory AS (
    SELECT *
    FROM daily_inventory_balances
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY product_id, location_id
        ORDER BY business_date DESC
    ) = 1
)
SELECT
    location_id,
    COUNT(*) AS product_count,
    SUM(CASE WHEN negative_stock_flag
        THEN 1 ELSE 0 END) AS negative_stock_products,
    ROUND(
        100.0 * SUM(CASE WHEN negative_stock_flag
            THEN 1 ELSE 0 END) / COUNT(*), 2
    ) AS negative_stock_percentage
FROM latest_inventory
GROUP BY location_id
ORDER BY negative_stock_percentage DESC;


-- 3. Products with the most negative inventory days
SELECT
    product_id,
    location_id,
    COUNT(*) AS negative_inventory_days,
    MIN(closing_quantity) AS lowest_closing_quantity
FROM daily_inventory_balances
WHERE negative_stock_flag = TRUE
GROUP BY product_id, location_id
ORDER BY negative_inventory_days DESC
LIMIT 20;


-- 4. Daily receipts versus issues
SELECT
    business_date,
    SUM(receipts_quantity) AS receipts,
    SUM(issues_quantity) AS issues,
    SUM(receipts_quantity) - SUM(issues_quantity)
        AS receipt_issue_difference
FROM daily_inventory_balances
GROUP BY business_date
ORDER BY business_date;
