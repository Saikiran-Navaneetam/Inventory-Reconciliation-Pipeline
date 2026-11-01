
import duckdb
import shutil

from pathlib import Path

import inventory_pipeline.ingestion as ingestion

from inventory_pipeline.config import GENERATED_DATA_DIR


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

SOURCE_DB = PROJECT_ROOT / "data" / "inventory.duckdb"

TEST_DB = PROJECT_ROOT / "outputs" / "idempotency_test.duckdb"

SOURCE_CSV = GENERATED_DATA_DIR / "inventory_events.csv"


# --------------------------------------------------
# IDEMPOTENCY TEST
# --------------------------------------------------

def test_idempotency():

    print("\nINVENTORY INGESTION IDEMPOTENCY TEST")
    print("=" * 55)

    # 1. Verify source files exist

    if not SOURCE_DB.is_file():
        raise FileNotFoundError(
            f"Original database not found: {SOURCE_DB}"
        )

    if not SOURCE_CSV.is_file():
        raise FileNotFoundError(
            f"Generated CSV not found: {SOURCE_CSV}"
        )

    # 2. Create isolated test database

    TEST_DB.parent.mkdir(parents=True, exist_ok=True)

    if TEST_DB.exists():
        TEST_DB.unlink()

    shutil.copy2(SOURCE_DB, TEST_DB)

    # Capture original database record count

    original_con = duckdb.connect(
        str(SOURCE_DB),
        read_only=True
    )

    try:
        original_count = original_con.execute("""
            SELECT COUNT(*)
            FROM raw_inventory_events
        """).fetchone()[0]

    finally:
        original_con.close()

    print("\nTEST DATABASE CREATED")
    print("-" * 40)

    print("Original database records:", original_count)

    # 3. Redirect ingestion to test database

    original_get_connection = ingestion.get_connection

    ingestion.get_connection = lambda: duckdb.connect(
        str(TEST_DB)
    )

    try:

        con = duckdb.connect(str(TEST_DB))

        try:

            # Start with an empty raw events table
            # in the copied test database.

            con.execute("""
                DELETE FROM raw_inventory_events
            """)

            initial_count = con.execute("""
                SELECT COUNT(*)
                FROM raw_inventory_events
            """).fetchone()[0]

        finally:
            con.close()

        print("Initial test records:", initial_count)

        # 4. FIRST INGESTION

        print("\nEXECUTING FIRST INGESTION")
        print("-" * 40)

        first_run_id = ingestion.ingest_inventory_events(
            source_path=SOURCE_CSV
        )

        con = duckdb.connect(str(TEST_DB))

        try:

            first_count = con.execute("""
                SELECT COUNT(*)
                FROM raw_inventory_events
            """).fetchone()[0]

            first_run = con.execute("""
                SELECT input_count, output_count, status
                FROM pipeline_runs
                WHERE run_id = ?
            """, [first_run_id]).fetchone()

        finally:
            con.close()

        first_input = first_run[0]
        first_inserted = first_run[1]
        first_status = first_run[2]

        print("\nFIRST INGESTION RESULTS")
        print("Input records   :", first_input)
        print("Inserted records:", first_inserted)
        print("Total raw records:", first_count)

        if first_status != "SUCCESS":
            raise AssertionError(
                "First ingestion did not complete successfully"
            )

        if first_inserted != first_input:
            raise AssertionError(
                "First ingestion did not insert all source records"
            )

        if first_count != first_input:
            raise AssertionError(
                "Unexpected raw record count after first ingestion"
            )

        # 5. SECOND INGESTION
        # Process exactly the same CSV again.

        print("\nEXECUTING SECOND INGESTION")
        print("-" * 40)

        second_run_id = ingestion.ingest_inventory_events(
            source_path=SOURCE_CSV
        )

        con = duckdb.connect(str(TEST_DB))

        try:

            second_count = con.execute("""
                SELECT COUNT(*)
                FROM raw_inventory_events
            """).fetchone()[0]

            second_run = con.execute("""
                SELECT input_count, output_count, status
                FROM pipeline_runs
                WHERE run_id = ?
            """, [second_run_id]).fetchone()

            duplicate_count = con.execute("""
                SELECT COUNT(*) - COUNT(DISTINCT ingestion_id)
                FROM raw_inventory_events
            """).fetchone()[0]

        finally:
            con.close()

        second_input = second_run[0]
        second_inserted = second_run[1]
        second_status = second_run[2]

        print("\nSECOND INGESTION RESULTS")
        print("Input records   :", second_input)
        print("Inserted records:", second_inserted)
        print("Total raw records:", second_count)

        # 6. VERIFY IDEMPOTENCY

        if second_status != "SUCCESS":
            raise AssertionError(
                "Second ingestion did not complete successfully"
            )

        if second_input != first_input:
            raise AssertionError(
                "Input record counts differ between ingestion runs"
            )

        if second_inserted != 0:
            raise AssertionError(
                f"Idempotency FAILED: {second_inserted} "
                "duplicate records were inserted"
            )

        if first_count != second_count:
            raise AssertionError(
                "Raw record count changed after second ingestion"
            )

        if duplicate_count != 0:
            raise AssertionError(
                f"Duplicate ingestion IDs detected: {duplicate_count}"
            )

        # 7. VERIFY ORIGINAL DATABASE IS UNCHANGED

        original_con = duckdb.connect(
            str(SOURCE_DB),
            read_only=True
        )

        try:

            final_original_count = original_con.execute("""
                SELECT COUNT(*)
                FROM raw_inventory_events
            """).fetchone()[0]

        finally:
            original_con.close()

        if final_original_count != original_count:
            raise AssertionError(
                "Original database was unexpectedly modified!"
            )

        # 8. FINAL REPORT

        print("\nIDEMPOTENCY TEST RESULTS")
        print("=" * 55)

        print("Original database records :", original_count)
        print("Initial test records      :", initial_count)
        print("First ingestion records   :", first_inserted)
        print("Second ingestion records  :", second_inserted)
        print("Final raw records         :", second_count)
        print("Duplicate records         :", duplicate_count)

        print("\nVERIFICATION RESULTS")
        print("=" * 55)

        print("First ingestion          : PASS")
        print("Second ingestion         : PASS")
        print("Duplicate prevention     : PASS")
        print("Record count consistency : PASS")
        print("Original database        : UNCHANGED")

        print("\nIDEMPOTENCY TEST: SUCCESS")

    finally:

        # Restore original connection function.

        ingestion.get_connection = original_get_connection


if __name__ == "__main__":

    test_idempotency()
