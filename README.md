# Inventory Reconciliation Pipeline & Inventory Control Tower

An end-to-end data engineering project that processes inventory events, validates data quality, transforms inventory movements, calculates daily inventory balances, and identifies inventory risks through SQL analytics and an interactive Streamlit dashboard.

## 1. Business Problem

Inventory data is generated through receipts, issues, transfers, and adjustments. Without a reliable reconciliation process, businesses can experience:

- Inaccurate inventory balances.
- Duplicate transaction records.
- Untracked or invalid inventory movements.
- Incorrect balances after historical corrections.
- Negative inventory positions.
- Limited visibility into warehouse operations.

This project addresses these challenges by building a reproducible inventory data pipeline with validation, reconciliation, historical recalculation, and monitoring.

## 2. Solution Overview

The pipeline processes inventory data through five main stages:

1. **Bronze ingestion:** Loads inventory event records into the raw data layer.
2. **Reference data loading:** Loads product and location information.
3. **Data validation:** Checks inventory records and quarantines invalid records.
4. **Movement transformation:** Converts validated events into signed inventory movements.
5. **Daily balance calculation:** Calculates opening balances, closing balances, and inventory risk indicators.

The processed data is stored in DuckDB and used by SQL analysis scripts and the Streamlit dashboard.

## 3. Architecture

```text
Synthetic Inventory Data
          |
          v
    Bronze Ingestion
          |
          v
    Raw Inventory Events
          |
          v
    Reference Data Loading
          |
          v
    Data Validation
       /       \
      v         v
  Accepted   Rejected
      |
      v
Movement Transformation
      |
      v
Inventory Movements
      |
      v
Daily Balance Calculation
      |
      v
DuckDB Analytics Database
      |
      +------------------+
      |                  |
      v                  v
  SQL Analysis     Streamlit Dashboard
```

## 4. Technology Stack

- Python
- DuckDB
- SQL
- Pandas
- Streamlit
- Plotly
- Pytest
- Docker
- Git and GitHub

## 5. Key Engineering Features

### Reliable ingestion
- SHA-256 source file hashing.
- Deterministic ingestion identifiers.
- Batch-based processing.
- Duplicate prevention.
- Pipeline run tracking.

### Data quality
- Product and location reference validation.
- Invalid record quarantine.
- Accepted and rejected record tracking.
- Data quality monitoring.

### Inventory transformation
- Receipt and issue processing.
- Transfer-in and transfer-out generation.
- Inventory adjustments.
- Signed movement quantities.

### Historical correction support
- Recalculates balances after backdated changes.
- Preserves balances before the correction date.
- Rebuilds daily balance outputs safely.

### Reconciliation
- Source-to-target movement reconciliation.
- Transfer integrity checks.
- Daily balance arithmetic checks.
- Balance continuity checks.
- Duplicate balance key detection.

## 6. Project Results

Results from the generated inventory dataset and completed verification runs:

| Metric | Result |
|---|---:|
| Input inventory records | 100,003 |
| Accepted inventory records | 100,000 |
| Rejected inventory records | 3 |
| Inventory products | 100 |
| Locations | 10 |
| Inventory movement records | 114,879 |
| Daily inventory balance records | 29,948 |
| Transfers reconciled | 14,879 |
| Invalid transfers | 0 |
| Balance arithmetic errors | 0 |
| Balance continuity errors | 0 |
| Duplicate balance keys | 0 |

### Reliability test results

- Idempotency test: PASS.
- Backdated correction test: PASS.
- Transfer reconciliation test: PASS.
- Balance reconciliation test: PASS.

The dataset also contains negative inventory positions. These are retained as operational risk indicators for investigation rather than silently discarded.

## 7. Inventory Control Tower Dashboard

The Streamlit dashboard provides an interactive view of inventory operations.

Dashboard sections include:

- Executive Overview
- Inventory Explorer
- Warehouse Analysis
- Movement Intelligence
- Alerts Center
- Data Quality Center
- Pipeline Monitoring
- Reconciliation Center

Key visualizations include inventory health, receipts versus issues, negative inventory trends, operational coverage, and pipeline monitoring.

## 8. SQL Analytics

The `sql/` directory contains:

- `01_inspect_database.sql` — database inspection and table exploration.
- `02_inventory_overview.sql` — inventory overview and operational summaries.
- `03_inventory_risk_analysis.sql` — negative inventory and risk analysis.

## 9. Project Structure

```text
inventory-reconciliation-pipeline/
│
├── data/
│   ├── generated/
│   ├── sample/
│   └── inventory.duckdb
│
├── docs/
├── logs/
├── outputs/
├── sql/
│   ├── 01_inspect_database.sql
│   ├── 02_inventory_overview.sql
│   └── 03_inventory_risk_analysis.sql
│
├── src/
│   └── inventory_pipeline/
│       ├── balance_calculator.py
│       ├── config.py
│       ├── database.py
│       ├── generate_data.py
│       ├── ingestion.py
│       ├── main.py
│       ├── monitoring.py
│       ├── reconciliation.py
│       ├── transformation.py
│       └── validation.py
│
├── dashboard.py
├── run_pipeline.py
├── test_idempotency.py
├── test_backdated_correction.py
├── verify_transfers.py
├── verify_balance_reconciliation.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
└── .gitignore
```

## 10. Run Locally

### Clone the repository

```bash
git clone https://github.com/Saikiran-Navaneetnam/Inventory-Reconciliation-Pipeline.git
cd Inventory-Reconciliation-Pipeline
```

### Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the pipeline

```bash
python run_pipeline.py
```

### Launch the dashboard

```bash
streamlit run dashboard.py
```

## 11. Run with Docker

Build the image:

```bash
docker build -t inventory-control-tower .
```

Start the container:

```bash
docker run -d --name inventory-control-tower -p 8501:8501 inventory-control-tower
```

Open the dashboard:

`http://localhost:8501`

Stop the container:

```bash
docker stop inventory-control-tower
```

## 12. Future Improvements

- Automated scheduled ingestion.
- Incremental balance recalculation.
- CI/CD integration with GitHub Actions.
- Cloud data warehouse deployment.
- Automated alerts for negative inventory.
- More extensive automated test coverage.

## 13. Author

**Saikiran Navaneetnam**

GitHub: https://github.com/Saikiran-Navaneetnam/Inventory-Reconciliation-Pipeline

---

*This project was developed as a practical data engineering portfolio project to demonstrate ingestion, transformation, data quality, reconciliation, analytical SQL, dashboarding, and containerization.*