
import csv


from inventory_pipeline.config import GENERATED_DATA_DIR
from inventory_pipeline.database import get_connection


import hashlib
import json
import uuid

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


def load_reference_data():
    """
    Load product and warehouse master data into DuckDB.
    """

    connection = get_connection()

    try:
        products_file = GENERATED_DATA_DIR / "products.csv"
        locations_file = GENERATED_DATA_DIR / "locations.csv"

        with open(products_file, encoding="utf-8-sig") as file:
            products = list(csv.DictReader(file))

        with open(locations_file, encoding="utf-8-sig") as file:
            locations = list(csv.DictReader(file))

        for product in products:
            connection.execute(
                """
                INSERT INTO products (
                    product_id,
                    product_name,
                    unit_of_measure
                )
                VALUES (?, ?, ?)
                ON CONFLICT (product_id) DO UPDATE SET
                    product_name = EXCLUDED.product_name,
                    unit_of_measure = EXCLUDED.unit_of_measure
                """,
                [
                    product["product_id"],
                    product["product_name"],
                    product["unit_of_measure"],
                ],
            )

        for location in locations:
            connection.execute(
                """
                INSERT INTO locations (
                    location_id,
                    location_name
                )
                VALUES (?, ?)
                ON CONFLICT (location_id) DO UPDATE SET
                    location_name = EXCLUDED.location_name
                """,
                [
                    location["location_id"],
                    location["location_name"],
                ],
            )

        print("REFERENCE DATA LOADED")
        print(f"Products : {len(products)}")
        print(f"Locations: {len(locations)}")

    finally:
        connection.close()



REQUIRED_COLUMNS = {
    "event_id",
    "event_type",
    "product_id",
    "quantity",
    "location_id",
    "from_location_id",
    "to_location_id",
    "effective_at",
}

VALID_EVENT_TYPES = {
    "RECEIPT",
    "ISSUE",
    "TRANSFER",
    "ADJUSTMENT",
}


def reject_record(connection, record, reason, run_id):
    """
    Store an invalid record with its original payload.
    """

    reject_id = hashlib.sha256(
        f"{record['ingestion_id']}|{reason}".encode()
    ).hexdigest()

    connection.execute(
        """
        INSERT INTO rejected_records (
            reject_id,
            event_id,
            source_file,
            source_row_number,
            run_id,
            raw_payload,
            rejection_reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (reject_id) DO NOTHING
        """,
        [
            reject_id,
            record["event_id"],
            record["source_file"],
            record["source_row_number"],
            run_id,
            record["raw_payload"],
            reason,
        ],
    )


def validate_event(event, products, locations):
    """
    Apply schema and business-rule validation.
    Returns an error message or None.
    """

    if set(event.keys()) != REQUIRED_COLUMNS:
        return "UNEXPECTED_SCHEMA"

    event_id = event["event_id"]
    event_type = event["event_type"]
    product_id = event["product_id"]

    if not event_id or not event_id.strip():
        return "MISSING_EVENT_ID"

    if not product_id or not product_id.strip():
        return "MISSING_PRODUCT_ID"

    if event_type not in VALID_EVENT_TYPES:
        return "INVALID_EVENT_TYPE"

    if product_id not in products:
        return "INVALID_PRODUCT_REFERENCE"

    try:
        quantity = Decimal(event["quantity"])
    except (InvalidOperation, TypeError):
        return "INVALID_QUANTITY"

    if not quantity.is_finite():
        return "INVALID_QUANTITY"

    if event_type in {"RECEIPT", "ISSUE", "TRANSFER"}:
        if quantity <= 0:
            return "QUANTITY_MUST_BE_POSITIVE"

    if event_type == "ADJUSTMENT":
        if quantity == 0:
            return "ZERO_ADJUSTMENT"

    try:
        effective_at = datetime.fromisoformat(
            event["effective_at"]
        )
    except (ValueError, TypeError):
        return "INVALID_EFFECTIVE_TIMESTAMP"

    if effective_at.tzinfo is not None:
        return "TIMEZONE_NOT_NORMALIZED"

    location_id = event["location_id"]
    from_location = event["from_location_id"]
    to_location = event["to_location_id"]

    if event_type == "TRANSFER":

        if location_id:
            return "TRANSFER_LOCATION_ID_NOT_ALLOWED"

        if not from_location:
            return "MISSING_TRANSFER_SOURCE"

        if not to_location:
            return "MISSING_TRANSFER_DESTINATION"

        if from_location == to_location:
            return "SAME_TRANSFER_SOURCE_AND_DESTINATION"

        if from_location not in locations:
            return "INVALID_TRANSFER_SOURCE"

        if to_location not in locations:
            return "INVALID_TRANSFER_DESTINATION"

    else:

        if not location_id:
            return "MISSING_LOCATION_ID"

        if location_id not in locations:
            return "INVALID_LOCATION_REFERENCE"

        if from_location or to_location:
            return "UNEXPECTED_TRANSFER_FIELDS"

    return None


def validate_inventory_events():
    """
    Validate Bronze records and publish accepted events
    to the Silver inventory_events table.
    """

    connection = get_connection()

    run_id = str(uuid.uuid4())

    start_time = datetime.now(timezone.utc).replace(
        tzinfo=None
    )

    input_count = 0
    accepted_count = 0
    rejected_count = 0

    try:

        connection.execute(
            """
            INSERT INTO pipeline_runs (
                run_id,
                pipeline_name,
                status,
                start_time
            )
            VALUES (?, ?, 'RUNNING', ?)
            """,
            [
                run_id,
                "inventory_validation",
                start_time,
            ],
        )

        products = {
            row[0]
            for row in connection.execute(
                "SELECT product_id FROM products"
            ).fetchall()
        }

        locations = {
            row[0]
            for row in connection.execute(
                "SELECT location_id FROM locations"
            ).fetchall()
        }

        raw_records = connection.execute(
            """
            SELECT
                ingestion_id,
                event_id,
                source_file,
                source_row_number,
                raw_payload
            FROM raw_inventory_events
            ORDER BY source_file, source_row_number
            """
        ).fetchall()

        seen_events = {}

        for record in raw_records:

            input_count += 1

            ingestion_id, event_id, source_file, row_number, raw_payload = record

            metadata = {
                "ingestion_id": ingestion_id,
                "event_id": event_id,
                "source_file": source_file,
                "source_row_number": row_number,
                "raw_payload": raw_payload,
            }

            try:
                event = json.loads(raw_payload)
            except (ValueError, TypeError):
                reject_record(
                    connection,
                    metadata,
                    "MALFORMED_JSON",
                    run_id,
                )
                rejected_count += 1
                continue

            if not isinstance(event, dict):
                reject_record(
                    connection,
                    metadata,
                    "INVALID_RECORD_FORMAT",
                    run_id,
                )
                rejected_count += 1
                continue

            error = validate_event(
                event,
                products,
                locations,
            )

            if error:
                reject_record(
                    connection,
                    metadata,
                    error,
                    run_id,
                )
                rejected_count += 1
                continue

            event_id = event["event_id"]

            payload_hash = hashlib.sha256(
                json.dumps(
                    event,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()

            # Check duplicate IDs within this batch
            if event_id in seen_events:

                reason = (
                    "DUPLICATE_EVENT"
                    if seen_events[event_id] == payload_hash
                    else "CONFLICTING_DUPLICATE_EVENT_ID"
                )

                reject_record(
                    connection,
                    metadata,
                    reason,
                    run_id,
                )

                rejected_count += 1
                continue

            
            # Check whether the event already exists in Silver
            existing = connection.execute(
                """
                SELECT payload_hash
                FROM inventory_events
                WHERE event_id = ?
                """,
                [event_id],
            ).fetchone()

            if existing:

                if existing[0] == payload_hash:
                    # Already processed successfully in an earlier run.
                    # This is a safe replay, not a new rejection.
                    seen_events[event_id] = payload_hash
                    continue

                else:
                    # Same event ID but different business content.
                    reject_record(
                        connection,
                        metadata,
                        "CONFLICTING_DUPLICATE_EVENT_ID",
                        run_id,
                    )

                    rejected_count += 1
                    seen_events[event_id] = existing[0]
                    continue


            quantity = Decimal(event["quantity"])

            connection.execute(
                """
                INSERT INTO inventory_events (
                    event_id,
                    event_type,
                    product_id,
                    quantity,
                    location_id,
                    from_location_id,
                    to_location_id,
                    effective_at,
                    source_file,
                    source_row_number,
                    run_id,
                    payload_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    event_id,
                    event["event_type"],
                    event["product_id"],
                    quantity,
                    event["location_id"] or None,
                    event["from_location_id"] or None,
                    event["to_location_id"] or None,
                    datetime.fromisoformat(
                        event["effective_at"]
                    ),
                    source_file,
                    row_number,
                    run_id,
                    payload_hash,
                ],
            )

            seen_events[event_id] = payload_hash
            accepted_count += 1

        connection.execute(
            """
            UPDATE pipeline_runs
            SET
                status = 'SUCCESS',
                end_time = ?,
                input_count = ?,
                output_count = ?,
                rejected_count = ?
            WHERE run_id = ?
            """,
            [
                datetime.now(timezone.utc).replace(
                    tzinfo=None
                ),
                input_count,
                accepted_count,
                rejected_count,
                run_id,
            ],
        )

        print("\nVALIDATION COMPLETED")
        print("-" * 40)
        print(f"Run ID          : {run_id}")
        print(f"Input records   : {input_count}")
        print(f"Accepted records: {accepted_count}")
        print(f"Rejected records: {rejected_count}")
        print("Status          : SUCCESS")

        return run_id

    except Exception as error:

        connection.execute(
            """
            UPDATE pipeline_runs
            SET
                status = 'FAILED',
                end_time = ?,
                input_count = ?,
                output_count = ?,
                rejected_count = ?,
                error_message = ?
            WHERE run_id = ?
            """,
            [
                datetime.now(timezone.utc).replace(
                    tzinfo=None
                ),
                input_count,
                accepted_count,
                rejected_count,
                str(error),
                run_id,
            ],
        )

        raise

    finally:
        connection.close()

if __name__ == "__main__":
    load_reference_data()
    validate_inventory_events()