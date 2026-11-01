
import csv
import hashlib
import json
import uuid
import duckdb

from datetime import datetime, timezone
from pathlib import Path

from inventory_pipeline.config import GENERATED_DATA_DIR
from inventory_pipeline.database import get_connection


BATCH_SIZE = 5000


# --------------------------------------------------
# FILE HASH GENERATION
# --------------------------------------------------

def generate_file_hash(file_path):
    """Generate a SHA256 hash for the source file."""

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        for chunk in iter(
            lambda: file.read(1024 * 1024), b""
        ):
            sha256.update(chunk)

    return sha256.hexdigest()


# --------------------------------------------------
# DETERMINISTIC INGESTION ID
# --------------------------------------------------

def generate_ingestion_id(file_path, file_hash, row_number):
    """
    Generate a deterministic ID for each source row.

    Reprocessing the same file does not create
    another copy of the same raw source row.
    """

    unique_value = (
        f"{file_path.resolve()}|{file_hash}|{row_number}"
    )

    return hashlib.sha256(
        unique_value.encode("utf-8")
    ).hexdigest()


# --------------------------------------------------
# INVENTORY EVENT INGESTION
# --------------------------------------------------

def ingest_inventory_events(source_path=None, database_path=None):
    """
    Ingest inventory events into the Bronze layer.

    Features:
    - Unique pipeline run ID
    - Source file tracking
    - Source row tracking
    - Deterministic ingestion IDs
    - Batch insertion
    - Duplicate prevention
    - Safe retries
    - Run status tracking
    - Optional test database support
    """

    # 1. Resolve source file

    if source_path is None:

        source_path = (
            GENERATED_DATA_DIR / "inventory_events.csv"
        )

    source_path = Path(source_path)

    if not source_path.is_file():

        raise FileNotFoundError(
            f"Source file not found: {source_path}"
        )

    # 2. Connect to database

    if database_path is None:

        connection = get_connection()

    else:

        database_path = Path(database_path)

        if not database_path.is_file():

            raise FileNotFoundError(
                f"Database not found: {database_path}"
            )

        connection = duckdb.connect(
            str(database_path)
        )

    # 3. Initialize ingestion tracking

    run_id = str(uuid.uuid4())

    start_time = datetime.now(
        timezone.utc
    ).replace(tzinfo=None)

    file_hash = generate_file_hash(source_path)

    input_count = 0
    inserted_count = 0

    try:

        # 4. Create pipeline run record

        connection.execute(
            """
            INSERT INTO pipeline_runs (
                run_id,
                pipeline_name,
                status,
                start_time
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                run_id,
                "inventory_reconciliation_pipeline",
                "RUNNING",
                start_time,
            ],
        )

        # 5. Read source CSV records

        with open(
            source_path,
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            reader = csv.DictReader(file)

            if not reader.fieldnames:

                raise ValueError(
                    "CSV file has no header."
                )

            batch = []

            for row_number, row in enumerate(
                reader,
                start=2,
            ):

                input_count += 1

                # Generate deterministic ingestion ID

                ingestion_id = generate_ingestion_id(
                    source_path,
                    file_hash,
                    row_number,
                )

                # Convert source record into JSON

                raw_payload = json.dumps(
                    row,
                    sort_keys=True,
                )

                batch.append(
                    (
                        ingestion_id,
                        row.get("event_id"),
                        source_path.name,
                        row_number,
                        run_id,
                        raw_payload,
                    )
                )

                # 6. Insert records in batches

                if len(batch) >= BATCH_SIZE:

                    connection.executemany(
                        """
                        INSERT INTO raw_inventory_events (
                            ingestion_id,
                            event_id,
                            source_file,
                            source_row_number,
                            run_id,
                            raw_payload
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT (ingestion_id) DO NOTHING
                        """,
                        batch,
                    )

                    batch.clear()

            # 7. Insert remaining records

            if batch:

                connection.executemany(
                    """
                    INSERT INTO raw_inventory_events (
                        ingestion_id,
                        event_id,
                        source_file,
                        source_row_number,
                        run_id,
                        raw_payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (ingestion_id) DO NOTHING
                    """,
                    batch,
                )

        # 8. Count records inserted by this run

        inserted_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM raw_inventory_events
            WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()[0]

        # 9. Update pipeline run status

        end_time = datetime.now(
            timezone.utc
        ).replace(tzinfo=None)

        connection.execute(
            """
            UPDATE pipeline_runs
            SET
                status = 'SUCCESS',
                end_time = ?,
                input_count = ?,
                output_count = ?,
                rejected_count = 0
            WHERE run_id = ?
            """,
            [
                end_time,
                input_count,
                inserted_count,
                run_id,
            ],
        )

        # 10. Display ingestion report

        print("\nINGESTION COMPLETED SUCCESSFULLY")
        print("-" * 45)

        print(f"Run ID       : {run_id}")
        print(f"Source file  : {source_path.name}")
        print(f"Input rows   : {input_count}")
        print(f"Inserted rows: {inserted_count}")
        print(f"Skipped rows : {input_count - inserted_count}")
        print(f"Status       : SUCCESS")

        return run_id

    except Exception as error:

        # 11. Record failed ingestion

        end_time = datetime.now(
            timezone.utc
        ).replace(tzinfo=None)

        connection.execute(
            """
            UPDATE pipeline_runs
            SET
                status = 'FAILED',
                end_time = ?,
                input_count = ?,
                output_count = ?,
                error_message = ?
            WHERE run_id = ?
            """,
            [
                end_time,
                input_count,
                inserted_count,
                str(error),
                run_id,
            ],
        )

        print(f"INGESTION FAILED: {error}")

        raise

    finally:

        connection.close()


# --------------------------------------------------
# MAIN EXECUTION
# --------------------------------------------------

if __name__ == "__main__":

    ingest_inventory_events()
