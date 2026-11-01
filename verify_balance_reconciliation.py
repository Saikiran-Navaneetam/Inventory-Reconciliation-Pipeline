
import duckdb

con = duckdb.connect("data/inventory.duckdb")

print("\nINVENTORY BALANCE RECONCILIATION")
print("=" * 55)

# 1. Compare source movements with daily balances

source = con.execute("""
    SELECT
        SUM(CASE WHEN movement_type = 'RECEIPT'
            THEN ABS(quantity) ELSE 0 END),
        SUM(CASE WHEN movement_type = 'ISSUE'
            THEN ABS(quantity) ELSE 0 END),
        SUM(CASE WHEN movement_type = 'TRANSFER_IN'
            THEN ABS(quantity) ELSE 0 END),
        SUM(CASE WHEN movement_type = 'TRANSFER_OUT'
            THEN ABS(quantity) ELSE 0 END),
        SUM(CASE WHEN movement_type = 'ADJUSTMENT'
            THEN quantity ELSE 0 END)
    FROM inventory_movements
""").fetchone()

target = con.execute("""
    SELECT
        SUM(receipts_quantity),
        SUM(issues_quantity),
        SUM(transfer_in_quantity),
        SUM(transfer_out_quantity),
        SUM(adjustment_quantity)
    FROM daily_inventory_balances
""").fetchone()

labels = [
    "Receipts",
    "Issues",
    "Transfer In",
    "Transfer Out",
    "Adjustments"
]

print("\nSOURCE VS TARGET MOVEMENT TOTALS")

all_passed = True

for label, src, tgt in zip(labels, source, target):

    src = src or 0
    tgt = tgt or 0

    passed = abs(float(src - tgt)) < 0.001

    if not passed:
        all_passed = False

    print(
        f"{label:15} | "
        f"Source: {src:>14} | "
        f"Target: {tgt:>14} | "
        f"{'PASS' if passed else 'FAIL'}"
    )

# 2. Check balance arithmetic

arithmetic_errors = con.execute("""
    SELECT COUNT(*)
    FROM daily_inventory_balances
    WHERE ABS(
        closing_quantity -
        opening_quantity -
        net_movement_quantity
    ) > 0.001
""").fetchone()[0]

print("\nBALANCE ARITHMETIC ERRORS:", arithmetic_errors)

if arithmetic_errors > 0:
    all_passed = False

# 3. Check opening/closing continuity

continuity_errors = con.execute("""
    WITH ordered AS (
        SELECT
            product_id,
            location_id,
            business_date,
            opening_quantity,

            LAG(closing_quantity) OVER (
                PARTITION BY product_id, location_id
                ORDER BY business_date
            ) AS previous_closing

        FROM daily_inventory_balances
    )

    SELECT COUNT(*)
    FROM ordered

    WHERE previous_closing IS NOT NULL
      AND ABS(
          opening_quantity - previous_closing
      ) > 0.001
""").fetchone()[0]

print("BALANCE CONTINUITY ERRORS:", continuity_errors)

if continuity_errors > 0:
    all_passed = False

# 4. Check duplicate balance keys

duplicate_keys = con.execute("""
    SELECT COUNT(*)
    FROM (
        SELECT
            business_date,
            product_id,
            location_id

        FROM daily_inventory_balances

        GROUP BY
            business_date,
            product_id,
            location_id

        HAVING COUNT(*) > 1
    ) duplicates
""").fetchone()[0]

print("DUPLICATE BALANCE KEYS:", duplicate_keys)

if duplicate_keys > 0:
    all_passed = False

# 5. Negative inventory report

negative_count = con.execute("""
    SELECT COUNT(*)
    FROM daily_inventory_balances
    WHERE negative_stock_flag = TRUE
""").fetchone()[0]

print("NEGATIVE INVENTORY ROWS:", negative_count)

# 6. Final result

print("\n" + "=" * 55)

if all_passed:
    print("RECONCILIATION STATUS: SUCCESS")
else:
    print("RECONCILIATION STATUS: FAILED")

con.close()
