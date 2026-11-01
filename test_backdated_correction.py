
import duckdb
import shutil
import uuid

from pathlib import Path

from inventory_pipeline.balance_calculator import (
    calculate_daily_balances
)


PROJECT_ROOT = Path(__file__).resolve().parent

SOURCE_DB = PROJECT_ROOT / "data" / "inventory.duckdb"

TEST_DB = PROJECT_ROOT / "outputs" / "backdated_test.duckdb"


def test_backdated_correction():

    print("\nBACKDATED CORRECTION TEST")
    print("=" * 50)

    # 1. Copy original database

    TEST_DB.parent.mkdir(parents=True, exist_ok=True)

    if TEST_DB.exists():
        TEST_DB.unlink()

    shutil.copy2(SOURCE_DB, TEST_DB)

    con = duckdb.connect(str(TEST_DB))

    try:

        # 2. Select a product/location with at least
        # three existing daily balances.

        selected = con.execute("""
            SELECT product_id, location_id
            FROM daily_inventory_balances
            GROUP BY product_id, location_id
            HAVING COUNT(*) >= 3
            ORDER BY product_id, location_id
            LIMIT 1
        """).fetchone()

        if not selected:
            raise ValueError("No suitable product/location found")

        product_id, location_id = selected

        # 3. Select the second available business date.

        dates = con.execute("""
            SELECT business_date
            FROM daily_inventory_balances
            WHERE product_id = ?
              AND location_id = ?
            ORDER BY business_date
            LIMIT 2
        """, [product_id, location_id]).fetchall()

        correction_date = dates[1][0]

        # 4. Capture balances BEFORE correction date.
        # These balances must remain unchanged.

        earlier_before = con.execute("""
            SELECT business_date, closing_quantity
            FROM daily_inventory_balances
            WHERE product_id = ?
              AND location_id = ?
              AND business_date < ?
            ORDER BY business_date
        """, [
            product_id,
            location_id,
            correction_date
        ]).fetchall()

        # 5. Capture balances ON and AFTER correction date.

        before = con.execute("""
            SELECT business_date, closing_quantity
            FROM daily_inventory_balances
            WHERE product_id = ?
              AND location_id = ?
              AND business_date >= ?
            ORDER BY business_date
        """, [
            product_id,
            location_id,
            correction_date
        ]).fetchall()

        print("Product        :", product_id)
        print("Location       :", location_id)
        print("Correction date:", correction_date)

        # 6. Insert a late-arriving adjustment.
        # The movement is inserted today but has
        # an earlier effective_at timestamp.

        test_id = str(uuid.uuid4())

        con.execute("""
            INSERT INTO inventory_movements (
                movement_id,
                event_id,
                product_id,
                location_id,
                movement_type,
                quantity,
                effective_at,
                source_file,
                run_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "BACKDATE_" + test_id,
            "BACKDATE_" + test_id,
            product_id,
            location_id,
            "ADJUSTMENT",
            7,
            str(correction_date) + " 12:00:00",
            "backdated_test.csv",
            "BACKDATED_TEST"
        ])

    finally:
        con.close()

    # 7. Recalculate all daily balances.

    calculate_daily_balances(TEST_DB)

    # 8. Reconnect to test database.

    con = duckdb.connect(str(TEST_DB))

    try:

        # 9. Capture balances BEFORE correction date
        # AFTER recalculation.

        earlier_after = con.execute("""
            SELECT business_date, closing_quantity
            FROM daily_inventory_balances
            WHERE product_id = ?
              AND location_id = ?
              AND business_date < ?
            ORDER BY business_date
        """, [
            product_id,
            location_id,
            correction_date
        ]).fetchall()

        # 10. Capture balances ON and AFTER correction date.

        after = con.execute("""
            SELECT business_date, closing_quantity
            FROM daily_inventory_balances
            WHERE product_id = ?
              AND location_id = ?
              AND business_date >= ?
            ORDER BY business_date
        """, [
            product_id,
            location_id,
            correction_date
        ]).fetchall()

    finally:
        con.close()

    # 11. Verify earlier balances remain unchanged.

    if earlier_before != earlier_after:
        raise AssertionError(
            "Balances before correction date were unexpectedly changed!"
        )

    # 12. Verify balance row counts.

    if len(before) != len(after):
        raise AssertionError(
            "Balance row count changed unexpectedly"
        )

    # 13. Verify all balances on and after correction date
    # increase by exactly 7.

    for old, new in zip(before, after):

        if old[0] != new[0]:
            raise AssertionError(
                f"Business date mismatch: {old[0]} vs {new[0]}"
            )

        difference = float(new[1] - old[1])

        if abs(difference - 7) > 0.001:
            raise AssertionError(
                f"Incorrect correction on {old[0]}: "
                f"expected +7, got {difference}"
            )

    # 14. Print final test report.

    print("\nBACKDATED CORRECTION RESULTS")
    print("=" * 50)

    print("Original balance rows       :", len(before))
    print("Updated balance rows        :", len(after))
    print("Earlier balance rows        :", len(earlier_before))
    print("Correction quantity         : +7")

    print("\nVERIFICATION RESULTS")
    print("=" * 50)

    print("Historical recalculation   : PASS")
    print("Subsequent balances        : PASS")
    print("Earlier balances unchanged : PASS")
    print("Balance row count          : PASS")
    print("Original database          : UNCHANGED")

    print("\nBACKDATED CORRECTION TEST: SUCCESS")


if __name__ == "__main__":
    test_backdated_correction()
