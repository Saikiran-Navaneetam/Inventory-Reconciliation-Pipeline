
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Main directories
DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_DATA_DIR = DATA_DIR / "sample"
GENERATED_DATA_DIR = DATA_DIR / "generated"

OUTPUT_DIR = PROJECT_ROOT / "outputs"
LOG_DIR = PROJECT_ROOT / "logs"

# Database configuration
DATABASE_PATH = DATA_DIR / "inventory.duckdb"

# Pipeline configuration
PIPELINE_NAME = "inventory_reconciliation_pipeline"

# Data configuration
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_QUANTITY_PRECISION = 3

# Ensure required directories exist
for directory in [
    DATA_DIR,
    SAMPLE_DATA_DIR,
    GENERATED_DATA_DIR,
    OUTPUT_DIR,
    LOG_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)
