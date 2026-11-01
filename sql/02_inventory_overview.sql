
-- =====================================================
-- INVENTORY RECONCILIATION PIPELINE
-- SQL BUSINESS ANALYSIS - 01: INVENTORY OVERVIEW
-- =====================================================

-- 1. Overall inventory movement summary
SELECT
    COUNT(*) AS total_balance_records,
    COUNT(DISTINCT product_id) AS total_products,
    COUNT(DISTINCT location_id) AS total_locations,
    MIN(business_date) AS first_business_date,
    MAX(business_date) AS last_business_date
FROM daily_inventory_balances;


-- 2. Daily inventory movement summary
SELECT
    business_date,
    SUM(receipts_quantity) AS total_receipts,
    SUM(issues_quantity) AS total_issues,
    SUM(transfer_in_quantity) AS total_transfer_in,
    SUM(transfer_out_quantity) AS total_transfer_out,
    SUM(adjustment_quantity) AS total_adjustments,
    SUM(net_movement_quantity) AS total_net_movement
FROM daily_inventory_balances
GROUP BY business_date
ORDER BY business_date;


-- 3. Negative inventory analysis
SELECT
    COUNT(*) AS negative_inventory_records,
    COUNT(DISTINCT product_id) AS affected_products,
    COUNT(DISTINCT location_id) AS affected_locations
FROM daily_inventory_balances
WHERE negative_stock_flag = TRUE;


-- 4. Products and locations with the lowest closing inventory
SELECT
    product_id,
    location_id,
    business_date,
    closing_quantity
FROM daily_inventory_balances
ORDER BY closing_quantity ASC
LIMIT 10;


-- 5. Inventory movement by movement type
SELECT
    movement_type,
    COUNT(*) AS movement_records,
    SUM(ABS(quantity)) AS total_movement_quantity
FROM inventory_movements
GROUP BY movement_type
ORDER BY movement_type;
