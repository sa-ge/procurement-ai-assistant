"""Schema description given to the LLM.

The static part documents every field and its business meaning; the dynamic part
is computed from the live collection (date range, allowed categorical values) so
the model filters on values that actually exist instead of guessing spellings.
"""
from functools import lru_cache

from app.db import get_collection

FIELDS = """\
Collection `purchases` — one document per purchase-order LINE ITEM (346k docs).
Several line items can share the same `po_number`; an "order" means a distinct po_number.

| field | type | meaning |
|---|---|---|
| creation_date | date | date the PO was created in the system — the PRIMARY date for all time questions |
| purchase_date | date or missing | date of purchase entered by the user (often missing; less reliable) |
| year, month, quarter | int | calendar parts of creation_date (quarter 1-4) |
| year_month | string | "YYYY-MM" of creation_date |
| year_quarter | string | "YYYY-Qn" of creation_date, e.g. "2014-Q3" |
| fiscal_year | string | California fiscal year (Jul 1 - Jun 30), e.g. "2013-2014" |
| fiscal_quarter | int | fiscal quarter 1-4 (FQ1 = Jul-Sep, FQ2 = Oct-Dec, FQ3 = Jan-Mar, FQ4 = Apr-Jun) |
| po_number | string | purchase order number (group key for "orders") |
| requisition_number | string | requisition number (mostly missing) |
| lpa_number | string | leveraged procurement agreement / contract number used (missing if none) |
| acquisition_type | string | IT vs non-IT, goods vs services |
| sub_acquisition_type | string | finer sub-type (mostly missing) |
| acquisition_method | string | procurement method, e.g. "Informal Competitive", "Statewide Contract" |
| sub_acquisition_method | string | finer method (mostly missing) |
| department_name | string | purchasing state department, e.g. "Corrections and Rehabilitation, Department of" |
| supplier_code | string | supplier id |
| supplier_name | string | supplier name (inconsistent casing — use case-insensitive regex when matching names) |
| supplier_qualifications | array of strings | certifications: "CA-SB" small business, "CA-MB" micro business, "CA-DVBE"/"CDVBE" disabled veteran, "DBE", "WBE"... |
| supplier_zip_code | string | supplier ZIP code |
| location | GeoJSON Point | supplier location |
| calcard | bool | true if paid with the state credit card (CalCard) |
| item_name | string | free-text line item name (inconsistent casing/spelling) |
| item_description | string | free-text line item description |
| quantity | number | quantity ordered |
| unit_price | number | price per unit in USD |
| total_price | number | line total in USD (= spending). A few lines are negative (credits/adjustments) |
| unspsc_code | string | normalized UNSPSC commodity code |
| commodity_title | string | UNSPSC commodity title (standardized product name — best for "what items/products") |
| class_code, class_title | string | UNSPSC class (one level above commodity) |
| family_code, family_title | string | UNSPSC family |
| segment_code, segment_title | string | UNSPSC segment (top level category, e.g. "Medical Equipment and Accessories and Supplies") |
"""

CATEGORICAL = ["acquisition_type", "acquisition_method", "fiscal_year", "sub_acquisition_type",
               "sub_acquisition_method", "segment_title"]


@lru_cache
def schema_prompt() -> str:
    coll = get_collection()
    parts = [FIELDS]
    bounds = list(coll.aggregate([{"$group": {"_id": None, "min": {"$min": "$creation_date"},
                                             "max": {"$max": "$creation_date"}}}]))
    if bounds:
        parts.append(f"creation_date range: {bounds[0]['min']:%Y-%m-%d} to {bounds[0]['max']:%Y-%m-%d}.")
    for field in CATEGORICAL:
        values = sorted(v for v in coll.distinct(field) if v)
        parts.append(f"Allowed values of `{field}`: {values}")
    departments = sorted(v for v in coll.distinct("department_name") if v)
    parts.append(f"`department_name` values ({len(departments)}): {departments}")
    return "\n\n".join(parts)
