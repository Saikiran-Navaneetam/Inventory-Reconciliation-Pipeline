
import duckdb

con = duckdb.connect("data/inventory.duckdb")

print("\nCOMPLETE BALANCE TABLE SCHEMA")

for row in con.execute(
    "DESCRIBE daily_inventory_balances"
).fetchall():
    print(row[0], "|", row[1])

print("\nMOVEMENT TYPE SUMMARY")

result = con.execute("""
    SELECT
        movement_type,
        COUNT(*) AS record_count,
        SUM(quantity) AS total_quantity
    FROM inventory_movements
    GROUP BY movement_type
    ORDER BY movement_type
""").fetchall()

for row in result:
    print(row)

print("\nSAMPLE MOVEMENTS")

result = con.execute("""
    SELECT
        movement_type,
        quantity,
        effective_at,
        product_id,
        location_id
    FROM inventory_movements
    ORDER BY effective_at
    LIMIT 10
""").fetchall()

for row in result:
    print(row)

con.close()
