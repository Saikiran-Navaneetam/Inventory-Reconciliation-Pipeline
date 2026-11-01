
import duckdb

print("Executing transfer reconciliation script...")

connection = duckdb.connect("data/inventory.duckdb")

total_transfers = connection.execute("""
    SELECT COUNT(DISTINCT event_id)
    FROM inventory_movements
    WHERE movement_type = 'TRANSFER_OUT'
""").fetchone()[0]

invalid_transfers = connection.execute("""
    SELECT COUNT(*)
    FROM (
        SELECT event_id
        FROM inventory_movements
        WHERE movement_type IN (
            'TRANSFER_IN',
            'TRANSFER_OUT'
        )
        GROUP BY event_id
        HAVING
            COUNT(*) != 2
            OR SUM(quantity) != 0
    ) AS invalid_events
""").fetchone()[0]

print("\nTRANSFER RECONCILIATION REPORT")
print("-" * 40)
print(f"Total transfers  : {total_transfers}")
print(f"Invalid transfers: {invalid_transfers}")

if invalid_transfers == 0:
    print("Status           : SUCCESS")
else:
    print("Status           : FAILED")

connection.close()
