
import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATED_DIR = PROJECT_ROOT / "data" / "generated"

EVENT_COLUMNS = [
    "event_id",
    "event_type",
    "product_id",
    "quantity",
    "location_id",
    "from_location_id",
    "to_location_id",
    "effective_at",
]


def generate_products(count=100):
    return [
        {
            "product_id": f"P{i:04d}",
            "product_name": f"Product {i:04d}",
            "unit_of_measure": "EA",
        }
        for i in range(1, count + 1)
    ]


def generate_locations(count=10):
    return [
        {
            "location_id": f"WH{i:03d}",
            "location_name": f"Warehouse {i:03d}",
        }
        for i in range(1, count + 1)
    ]


def generate_event(event_number, products, locations, rng):
    event_type = rng.choices(
        ["RECEIPT", "ISSUE", "TRANSFER", "ADJUSTMENT"],
        weights=[35, 35, 15, 15],
        k=1,
    )[0]

    product = rng.choice(products)["product_id"]
    quantity = rng.randint(1, 100)

    event_date = datetime(2026, 10, 1) + timedelta(
        days=rng.randint(0, 29)
    )

    effective_at = event_date.replace(
        hour=rng.randint(0, 23),
        minute=rng.randint(0, 59),
        second=0,
    ).isoformat()

    location = rng.choice(locations)["location_id"]

    record = {
        "event_id": f"EVT{event_number:09d}",
        "event_type": event_type,
        "product_id": product,
        "quantity": quantity,
        "location_id": location,
        "from_location_id": "",
        "to_location_id": "",
        "effective_at": effective_at,
    }

    if event_type == "ADJUSTMENT":
        record["quantity"] = rng.choice([-1, 1]) * quantity

    elif event_type == "TRANSFER":
        destinations = [
            item["location_id"]
            for item in locations
            if item["location_id"] != location
        ]

        record["location_id"] = ""
        record["from_location_id"] = location
        record["to_location_id"] = rng.choice(destinations)

    return record


def write_csv(file_path, records, columns):
    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)


def generate_dataset(row_count, seed, include_anomalies):
    rng = random.Random(seed)

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    products = generate_products()
    locations = generate_locations()

    events = [
        generate_event(i, products, locations, rng)
        for i in range(1, row_count + 1)
    ]

    if include_anomalies and events:
        # Exact duplicate of an existing event
        duplicate = events[0].copy()
        events.append(duplicate)

        # Invalid product reference
        invalid_product = events[1].copy()
        invalid_product["event_id"] = "INVALID_PRODUCT"
        invalid_product["product_id"] = "P999999"
        events.append(invalid_product)

        # Missing required product ID
        missing_product = events[2].copy()
        missing_product["event_id"] = "MISSING_PRODUCT"
        missing_product["product_id"] = ""
        events.append(missing_product)

    write_csv(
        GENERATED_DIR / "products.csv",
        products,
        ["product_id", "product_name", "unit_of_measure"],
    )

    write_csv(
        GENERATED_DIR / "locations.csv",
        locations,
        ["location_id", "location_name"],
    )

    write_csv(
        GENERATED_DIR / "inventory_events.csv",
        events,
        EVENT_COLUMNS,
    )

    print("Synthetic dataset generated successfully.")
    print(f"Seed: {seed}")
    print(f"Requested valid events: {row_count}")
    print(f"Total event rows: {len(events)}")
    print(f"Products: {len(products)}")
    print(f"Locations: {len(locations)}")
    print(f"Output directory: {GENERATED_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic inventory events."
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=1000,
        help="Number of valid inventory events",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )

    parser.add_argument(
        "--include-anomalies",
        action="store_true",
        help="Add duplicate and invalid records",
    )

    args = parser.parse_args()

    if args.rows < 3:
        parser.error("--rows must be at least 3")

    generate_dataset(
        row_count=args.rows,
        seed=args.seed,
        include_anomalies=args.include_anomalies,
    )
