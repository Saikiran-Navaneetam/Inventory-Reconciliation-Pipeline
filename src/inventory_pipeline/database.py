
import duckdb

from inventory_pipeline.config import DATABASE_PATH


def get_connection():
    """
    Create or open the inventory DuckDB database.
    """
    return duckdb.connect(str(DATABASE_PATH))


def create_tables():
    """
    Create all source, transformation, target,
    data-quality and operational tables.
    """

    connection = get_connection()

    try:

        # 1. Product master
        connection.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id VARCHAR PRIMARY KEY,
                product_name VARCHAR NOT NULL,
                unit_of_measure VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Location master
        connection.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                location_id VARCHAR PRIMARY KEY,
                location_name VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Pipeline execution history
        connection.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id VARCHAR PRIMARY KEY,
                pipeline_name VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                input_count BIGINT DEFAULT 0,
                output_count BIGINT DEFAULT 0,
                rejected_count BIGINT DEFAULT 0,
                error_message VARCHAR
            );
        """)

        # 4. Original source records
        connection.execute("""
            CREATE TABLE IF NOT EXISTS raw_inventory_events (
                ingestion_id VARCHAR PRIMARY KEY,
                event_id VARCHAR,
                source_file VARCHAR NOT NULL,
                source_row_number INTEGER NOT NULL,
                run_id VARCHAR NOT NULL,
                raw_payload VARCHAR NOT NULL,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. Validated inventory events
        connection.execute("""
            CREATE TABLE IF NOT EXISTS inventory_events (
                event_id VARCHAR PRIMARY KEY,
                event_type VARCHAR NOT NULL,
                product_id VARCHAR NOT NULL,
                quantity DECIMAL(18,3) NOT NULL,
                location_id VARCHAR,
                from_location_id VARCHAR,
                to_location_id VARCHAR,
                effective_at TIMESTAMP NOT NULL,
                source_file VARCHAR NOT NULL,
                source_row_number INTEGER NOT NULL,
                run_id VARCHAR NOT NULL,
                payload_hash VARCHAR NOT NULL,

                CHECK (
                    event_type IN (
                        'RECEIPT',
                        'ISSUE',
                        'TRANSFER',
                        'ADJUSTMENT'
                    )
                ),

                CHECK (quantity > 0 OR event_type = 'ADJUSTMENT')
            );
        """)

        # 6. Signed inventory movements
        connection.execute("""
            CREATE TABLE IF NOT EXISTS inventory_movements (
                movement_id VARCHAR PRIMARY KEY,
                event_id VARCHAR NOT NULL,
                product_id VARCHAR NOT NULL,
                location_id VARCHAR NOT NULL,
                movement_type VARCHAR NOT NULL,
                quantity DECIMAL(18,3) NOT NULL,
                effective_at TIMESTAMP NOT NULL,
                source_file VARCHAR NOT NULL,
                run_id VARCHAR NOT NULL
            );
        """)

        # 7. Invalid or quarantined records
        connection.execute("""
            CREATE TABLE IF NOT EXISTS rejected_records (
                reject_id VARCHAR PRIMARY KEY,
                event_id VARCHAR,
                source_file VARCHAR NOT NULL,
                source_row_number INTEGER NOT NULL,
                run_id VARCHAR NOT NULL,
                raw_payload VARCHAR NOT NULL,
                rejection_reason VARCHAR NOT NULL,
                rejected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 8. Daily inventory balances
        connection.execute("""
            CREATE TABLE IF NOT EXISTS daily_inventory_balances (
                business_date DATE NOT NULL,
                product_id VARCHAR NOT NULL,
                location_id VARCHAR NOT NULL,

                opening_quantity DECIMAL(18,3) NOT NULL,
                receipts_quantity DECIMAL(18,3) NOT NULL,
                issues_quantity DECIMAL(18,3) NOT NULL,
                transfer_in_quantity DECIMAL(18,3) NOT NULL,
                transfer_out_quantity DECIMAL(18,3) NOT NULL,
                adjustment_quantity DECIMAL(18,3) NOT NULL,
                net_movement_quantity DECIMAL(18,3) NOT NULL,
                closing_quantity DECIMAL(18,3) NOT NULL,

                negative_stock_flag BOOLEAN NOT NULL,
                run_id VARCHAR NOT NULL,

                PRIMARY KEY (
                    business_date,
                    product_id,
                    location_id
                )
            );
        """)

        print("All database tables created successfully.")

    finally:
        connection.close()


if __name__ == "__main__":
    create_tables()
