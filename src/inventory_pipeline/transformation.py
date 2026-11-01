
import hashlib
import uuid

from datetime import datetime, timezone
from decimal import Decimal

from inventory_pipeline.database import get_connection


BATCH_SIZE = 5000


def generate_movement_id(
    event_id,
    product_id,
    location_id,
    movement_type,
):
    """
    Generate a deterministic movement ID.

    The same business event always produces
    the same movement identifier.
    """

    unique_key = (
        f"{event_id}|{product_id}|"
        f"{location_id}|{movement_type}"
    )

    return hashlib.sha256(
        unique_key.encode("utf-8")
    ).hexdigest()


def build_movements(event):
    """
    Convert one validated business event into
    one or two signed inventory movements.
    """

    event_id = event[0]
    event_type = event[1]
    product_id = event[2]
    quantity = Decimal(str(event[3]))

    location_id = event[4]
    from_location = event[5]
    to_location = event[6]

    effective_at = event[7]
    source_file = event[8]
    source_row_number = event[9]

    movements = []

    def create_movement(location, movement_type, signed_quantity):

        movement_id = generate_movement_id(
            event_id,
            product_id,
            location,
            movement_type,
        )

        movements.append(
            (
                movement_id,
                event_id,
                product_id,
                location,
                movement_type,
                signed_quantity,
                effective_at,
                source_file,
            )
        )

    if event_type == "RECEIPT":

        create_movement(
            location_id,
            "RECEIPT",
            quantity,
        )

    elif event_type == "ISSUE":

        create_movement(
            location_id,
            "ISSUE",
            -quantity,
        )

    elif event_type == "ADJUSTMENT":

        create_movement(
            location_id,
            "ADJUSTMENT",
            quantity,
        )

    elif event_type == "TRANSFER":

        # Reduce stock at the source warehouse
        create_movement(
            from_location,
            "TRANSFER_OUT",
            -quantity,
        )

        # Increase stock at the destination warehouse
        create_movement(
            to_location,
            "TRANSFER_IN",
            quantity,
        )

    return movements


def transform_inventory_movements():
    """
    Transform validated inventory events into
    signed warehouse-level stock movements.

    Features:
    - Transfer expansion
    - Signed quantities
    - Deterministic movement IDs
    - Duplicate movement prevention
    - Transaction handling
    - Pipeline execution monitoring
    """

    connection = get_connection()

    run_id = str(uuid.uuid4())

    start_time = datetime.now(timezone.utc).replace(
        tzinfo=None
    )

    input_count = 0
    inserted_count = 0

    try:

        # Record pipeline execution
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
                "inventory_movement_transformation",
                "RUNNING",
                start_time,
            ],
        )

        # Read validated events in deterministic order
        events = connection.execute(
            """
            SELECT
                event_id,
                event_type,
                product_id,
                quantity,
                location_id,
                from_location_id,
                to_location_id,
                effective_at,
                source_file,
                source_row_number
            FROM inventory_events
            ORDER BY effective_at, event_id
            """
        ).fetchall()

        input_count = len(events)

        # Begin atomic movement processing
        connection.execute("BEGIN TRANSACTION")

        batch = []

        for event in events:

            movements = build_movements(event)

            for movement in movements:

                batch.append(
                    movement + (run_id,)
                )

            if len(batch) >= BATCH_SIZE:

                connection.executemany(
                    """
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
                    ON CONFLICT (movement_id) DO NOTHING
                    """,
                    batch,
                )

                batch.clear()

        # Insert remaining records
        if batch:

            connection.executemany(
                """
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
                ON CONFLICT (movement_id) DO NOTHING
                """,
                batch,
            )

        # Count movements inserted by this run
        inserted_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM inventory_movements
            WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()[0]

        # Commit all movement changes together
        connection.execute("COMMIT")

        # Update pipeline execution status
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
                datetime.now(timezone.utc).replace(
                    tzinfo=None
                ),
                input_count,
                inserted_count,
                run_id,
            ],
        )

        print("\nMOVEMENT TRANSFORMATION COMPLETED")
        print("-" * 45)
        print(f"Run ID          : {run_id}")
        print(f"Input events    : {input_count}")
        print(f"Inserted movements: {inserted_count}")
        print("Status          : SUCCESS")

        return run_id

    except Exception as error:

        # Undo partial movement processing
        try:
            connection.execute("ROLLBACK")
        except Exception:
            pass

        connection.execute(
            """
            UPDATE pipeline_runs
            SET
                status = 'FAILED',
                end_time = ?,
                input_count = ?,
                output_count = 0,
                error_message = ?
            WHERE run_id = ?
            """,
            [
                datetime.now(timezone.utc).replace(
                    tzinfo=None
                ),
                input_count,
                str(error),
                run_id,
            ],
        )

        print(f"TRANSFORMATION FAILED: {error}")

        raise

    finally:
        connection.close()


if __name__ == "__main__":
    transform_inventory_movements()
