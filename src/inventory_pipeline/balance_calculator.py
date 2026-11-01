
"""
Daily Inventory Balance Calculator

Responsibilities:
1. Aggregate inventory movements by date, product and location.
2. Calculate daily opening and closing balances.
3. Handle backdated corrections through full recalculation.
4. Safely replace previous balance outputs.
5. Record negative inventory flags.
"""

import uuid
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "data" / "inventory.duckdb"


def calculate_daily_balances(database_path=DATABASE_PATH):

    run_id = str(uuid.uuid4())

    connection = duckdb.connect(str(database_path))

    try:
        print("\nDAILY INVENTORY BALANCE CALCULATION")
        print("=" * 50)

        connection.execute("BEGIN TRANSACTION")

        # 1. Check source records
        movement_count = connection.execute("""
            SELECT COUNT(*)
            FROM inventory_movements
        """).fetchone()[0]

        if movement_count == 0:
            raise ValueError("No inventory movements available")

        print(f"Source movements : {movement_count}")

        # 2. Remove previous calculated balances.
        # Full rebuild makes reruns idempotent and handles
        # backdated corrections.

        connection.execute("""
            DELETE FROM daily_inventory_balances
        """)

        # 3. Generate daily balances
        connection.execute("""
            INSERT INTO daily_inventory_balances (
                business_date,
                product_id,
                location_id,
                opening_quantity,
                receipts_quantity,
                issues_quantity,
                transfer_in_quantity,
                transfer_out_quantity,
                adjustment_quantity,
                net_movement_quantity,
                closing_quantity,
                negative_stock_flag,
                run_id
            )

            WITH movement_daily AS (

                SELECT
                    CAST(effective_at AS DATE) AS business_date,
                    product_id,
                    location_id,

                    SUM(
                        CASE
                            WHEN movement_type = 'RECEIPT'
                            THEN ABS(quantity)
                            ELSE 0
                        END
                    ) AS receipts_quantity,

                    SUM(
                        CASE
                            WHEN movement_type = 'ISSUE'
                            THEN ABS(quantity)
                            ELSE 0
                        END
                    ) AS issues_quantity,

                    SUM(
                        CASE
                            WHEN movement_type = 'TRANSFER_IN'
                            THEN ABS(quantity)
                            ELSE 0
                        END
                    ) AS transfer_in_quantity,

                    SUM(
                        CASE
                            WHEN movement_type = 'TRANSFER_OUT'
                            THEN ABS(quantity)
                            ELSE 0
                        END
                    ) AS transfer_out_quantity,

                    SUM(
                        CASE
                            WHEN movement_type = 'ADJUSTMENT'
                            THEN quantity
                            ELSE 0
                        END
                    ) AS adjustment_quantity

                FROM inventory_movements

                GROUP BY
                    CAST(effective_at AS DATE),
                    product_id,
                    location_id
            ),

            date_ranges AS (

                SELECT
                    product_id,
                    location_id,
                    MIN(business_date) AS min_date,
                    MAX(business_date) AS max_date

                FROM movement_daily

                GROUP BY
                    product_id,
                    location_id
            ),

            date_spine AS (

                SELECT
                    r.product_id,
                    r.location_id,
                    CAST(d.business_date AS DATE) AS business_date

                FROM date_ranges r

                CROSS JOIN UNNEST(
                    generate_series(
                        r.min_date,
                        r.max_date,
                        INTERVAL 1 DAY
                    )
                ) AS d(business_date)
            ),

            daily_data AS (

                SELECT
                    s.business_date,
                    s.product_id,
                    s.location_id,

                    COALESCE(m.receipts_quantity, 0)
                        AS receipts_quantity,

                    COALESCE(m.issues_quantity, 0)
                        AS issues_quantity,

                    COALESCE(m.transfer_in_quantity, 0)
                        AS transfer_in_quantity,

                    COALESCE(m.transfer_out_quantity, 0)
                        AS transfer_out_quantity,

                    COALESCE(m.adjustment_quantity, 0)
                        AS adjustment_quantity

                FROM date_spine s

                LEFT JOIN movement_daily m
                    ON s.business_date = m.business_date
                    AND s.product_id = m.product_id
                    AND s.location_id = m.location_id
            ),

            net_movements AS (

                SELECT
                    *,

                    (
                        receipts_quantity
                        - issues_quantity
                        + transfer_in_quantity
                        - transfer_out_quantity
                        + adjustment_quantity
                    ) AS net_movement_quantity

                FROM daily_data
            ),

            running_balances AS (

                SELECT
                    *,

                    SUM(net_movement_quantity) OVER (
                        PARTITION BY product_id, location_id
                        ORDER BY business_date
                        ROWS BETWEEN UNBOUNDED PRECEDING
                        AND CURRENT ROW
                    ) AS cumulative_closing

                FROM net_movements
            )

            SELECT
                business_date,
                product_id,
                location_id,

                CAST(
                    cumulative_closing - net_movement_quantity
                    AS DECIMAL(18,3)
                ) AS opening_quantity,

                CAST(receipts_quantity AS DECIMAL(18,3)),
                CAST(issues_quantity AS DECIMAL(18,3)),
                CAST(transfer_in_quantity AS DECIMAL(18,3)),
                CAST(transfer_out_quantity AS DECIMAL(18,3)),
                CAST(adjustment_quantity AS DECIMAL(18,3)),
                CAST(net_movement_quantity AS DECIMAL(18,3)),

                CAST(
                    cumulative_closing AS DECIMAL(18,3)
                ) AS closing_quantity,

                cumulative_closing < 0 AS negative_stock_flag,

                ? AS run_id

            FROM running_balances
        """, [run_id])

        # 4. Validate output
        balance_count = connection.execute("""
            SELECT COUNT(*)
            FROM daily_inventory_balances
        """).fetchone()[0]

        negative_count = connection.execute("""
            SELECT COUNT(*)
            FROM daily_inventory_balances
            WHERE negative_stock_flag = TRUE
        """).fetchone()[0]

        # 5. Validate arithmetic
        invalid_balances = connection.execute("""
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

        if invalid_balances > 0:
            raise ValueError(
                f"Found {invalid_balances} incorrect balances"
            )

        connection.execute("COMMIT")

        print("\nBALANCE CALCULATION COMPLETED")
        print("=" * 50)

        print(f"Run ID             : {run_id}")
        print(f"Source movements   : {movement_count}")
        print(f"Daily balance rows : {balance_count}")
        print(f"Negative balances  : {negative_count}")
        print(f"Invalid balances   : {invalid_balances}")
        print("Status             : SUCCESS")

    except Exception as error:

        connection.execute("ROLLBACK")

        print("\nBALANCE CALCULATION FAILED")
        print(f"Error: {error}")

        raise

    finally:
        connection.close()


if __name__ == "__main__":
    calculate_daily_balances()
