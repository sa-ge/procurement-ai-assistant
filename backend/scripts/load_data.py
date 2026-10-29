"""Clean the California procurement CSV and load it into MongoDB.

Usage (from the backend/ folder):
    python -m scripts.load_data [path/to/csv]

Each CSV row is one *line item*; several line items can share one purchase order
number. Fields are renamed to snake_case and typed (dates -> datetime, money ->
float) so the LLM can write simple, correct aggregation pipelines. Derived time
fields (calendar + fiscal year/quarter/month) are precomputed to avoid fragile
date arithmetic inside generated queries.
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from pymongo import ASCENDING, MongoClient

from app.config import settings

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "archive" / "PURCHASE ORDER DATA EXTRACT 2012-2015_0.csv"

RENAME = {
    "Creation Date": "creation_date",
    "Purchase Date": "purchase_date",
    "Fiscal Year": "fiscal_year",
    "LPA Number": "lpa_number",
    "Purchase Order Number": "po_number",
    "Requisition Number": "requisition_number",
    "Acquisition Type": "acquisition_type",
    "Sub-Acquisition Type": "sub_acquisition_type",
    "Acquisition Method": "acquisition_method",
    "Sub-Acquisition Method": "sub_acquisition_method",
    "Department Name": "department_name",
    "Supplier Code": "supplier_code",
    "Supplier Name": "supplier_name",
    "Supplier Qualifications": "supplier_qualifications",
    "Supplier Zip Code": "supplier_zip_code",
    "CalCard": "calcard",
    "Item Name": "item_name",
    "Item Description": "item_description",
    "Quantity": "quantity",
    "Unit Price": "unit_price",
    "Total Price": "total_price",
    "Classification Codes": "classification_codes",
    "Normalized UNSPSC": "unspsc_code",
    "Commodity Title": "commodity_title",
    "Class": "class_code",
    "Class Title": "class_title",
    "Family": "family_code",
    "Family Title": "family_title",
    "Segment": "segment_code",
    "Segment Title": "segment_title",
    "Location": "location",
}

# Purchase Date contains impossible values (e.g. 1911, 6070); keep only plausible ones.
PLAUSIBLE_DATES = (datetime(2000, 1, 1), datetime(2020, 12, 31))


def money(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.str.replace(r"[$,]", "", regex=True), errors="coerce")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=RENAME)
    for col in df.columns:
        df[col] = df[col].str.strip()

    df["creation_date"] = pd.to_datetime(df["creation_date"], format="%m/%d/%Y", errors="coerce")
    pd_dates = pd.to_datetime(df["purchase_date"], format="%m/%d/%Y", errors="coerce")
    df["purchase_date"] = pd_dates.where(pd_dates.between(*PLAUSIBLE_DATES))

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = money(df["unit_price"])
    df["total_price"] = money(df["total_price"])

    cd = df["creation_date"]
    df["year"] = cd.dt.year
    df["month"] = cd.dt.month
    df["quarter"] = cd.dt.quarter
    df["year_month"] = cd.dt.strftime("%Y-%m")
    df["year_quarter"] = cd.dt.year.astype(str) + "-Q" + cd.dt.quarter.astype(str)
    # California fiscal year runs July 1 - June 30; FQ1 = Jul-Sep.
    df["fiscal_quarter"] = ((cd.dt.month - 7) % 12) // 3 + 1

    df["calcard"] = df["calcard"].eq("YES")
    df["supplier_qualifications"] = df["supplier_qualifications"].str.split()

    # Location is "ZIP\n(lat, lon)" -> GeoJSON point.
    coords = df["location"].str.extract(r"\(([-\d.]+),\s*([-\d.]+)\)").astype(float)
    df["location"] = [
        {"type": "Point", "coordinates": [lon, lat]} if pd.notna(lat) else None
        for lat, lon in zip(coords[0], coords[1])
    ]
    return df


def to_documents(df: pd.DataFrame):
    for rec in df.to_dict("records"):
        doc = {}
        for key, value in rec.items():
            if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
                continue
            if isinstance(value, pd.Timestamp):
                value = value.to_pydatetime()
            elif hasattr(value, "item"):  # numpy scalar -> python
                value = value.item()
            doc[key] = value
        yield doc


def main(csv_path: Path) -> None:
    print(f"Reading {csv_path} ...")
    df = clean(pd.read_csv(csv_path, dtype=str, low_memory=False))
    print(f"Rows: {len(df):,}  distinct POs: {df['po_number'].nunique():,}")

    client = MongoClient(settings.mongo_uri)
    coll = client[settings.mongo_db][settings.mongo_collection]
    coll.drop()

    batch, inserted = [], 0
    for doc in to_documents(df):
        batch.append(doc)
        if len(batch) == 10_000:
            coll.insert_many(batch, ordered=False)
            inserted += len(batch)
            batch.clear()
            print(f"  inserted {inserted:,}", end="\r")
    if batch:
        coll.insert_many(batch, ordered=False)
        inserted += len(batch)
    print(f"\nInserted {inserted:,} documents into {settings.mongo_db}.{settings.mongo_collection}")

    for field in ["creation_date", "po_number", "department_name", "supplier_name",
                  "acquisition_type", "acquisition_method", "fiscal_year", "year_quarter",
                  "segment_title", "item_name"]:
        coll.create_index([(field, ASCENDING)])
    coll.create_index([("item_name", "text"), ("item_description", "text"), ("commodity_title", "text")])
    print("Indexes created.")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV)
