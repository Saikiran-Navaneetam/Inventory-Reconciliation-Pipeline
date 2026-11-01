
import duckdb

con = duckdb.connect("data/inventory.duckdb")

print("\nDAILY INVENTORY BALANCE REPORT")
print("=" * 50)

print("\nTOTAL BALANCE RECORDS")

print(
    con.execute("""
        SELECT COUNT(*)
        FROM daily_inventory_balances
    """).fetchone()[0]
)

print("\nSAMPLE DAILY BALANCES")

rows = con.execute("""
    SELECT
        business_date,
        product_id,
        location_id,
        opening_quantity,
        receipts_quantity,
        issues_quantity,
        transfer_in_quantity,
        transfer_out_quantity,
        adjustment_quantity,
        closing_quantity,
        negative_stock_flag

    FROM daily_inventory_balances

    ORDER BY business_date, product_id, location_id

    LIMIT 10
""").fetchall()

for row in rows:
    print(row)

print("\nNEGATIVE INVENTORY REPORT")

rows = con.execute("""
    SELECT
        product_id,
        location_id,
        business_date,
        closing_quantity

    FROM daily_inventory_balances

    WHERE negative_stock_flag = TRUE

    LIMIT 10
""").fetchall()

for row in rows:
    print(row)

print("\nBALANCE RECONCILIATION")

result = con.execute("""
    SELECT COUNT(*)
    FROM daily_inventory_balances

    WHERE ABS(
        closing_quantity -
        (
            opening_quantity +
            net_movement_quantity
        )
    ) > 0.001
""").fetchone()[0]

print("Invalid balances:", result)

con.close()
