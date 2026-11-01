
"""
Inventory Reconciliation Pipeline
Runs all processing stages in the correct order.
"""

import sys
import logging
from pathlib import Path

# Make the src package available when running this file directly.
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from inventory_pipeline.ingestion import ingest_inventory_events
from inventory_pipeline.validation import (
    load_reference_data,
    validate_inventory_events,
)
from inventory_pipeline.transformation import transform_inventory_movements
from inventory_pipeline.balance_calculator import calculate_daily_balances


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("inventory_pipeline")


def run_pipeline():
    """Execute the complete inventory pipeline."""

    logger.info("=" * 65)
    logger.info("STARTING INVENTORY RECONCILIATION PIPELINE")
    logger.info("=" * 65)

    stages = [
        ("1. BRONZE INGESTION", ingest_inventory_events),
        ("2. LOAD REFERENCE DATA", load_reference_data),
        ("3. DATA VALIDATION", validate_inventory_events),
        ("4. MOVEMENT TRANSFORMATION", transform_inventory_movements),
        ("5. DAILY BALANCE CALCULATION", calculate_daily_balances),
    ]

    try:
        for stage_name, stage_function in stages:
            logger.info("STARTED: %s", stage_name)
            stage_function()
            logger.info("COMPLETED: %s", stage_name)

        logger.info("=" * 65)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 65)

    except Exception:
        logger.exception("PIPELINE FAILED")
        raise


if __name__ == "__main__":
    run_pipeline()
