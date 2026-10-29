"""Evaluation cases: natural-language question + hand-written ground-truth pipeline.

`expect` extracts the value(s) that must appear in the agent's answer from the
ground-truth result rows. Numbers are matched with a relative tolerance and
strings case-insensitively (see run_eval.py).
"""

CASES = [
    {
        "id": "orders_month",
        "category": "time-period count",
        "question": "How many orders were created in March 2014?",
        "truth": [{"$match": {"year_month": "2014-03"}}, {"$group": {"_id": "$po_number"}}, {"$count": "n"}],
        "expect": lambda rows: [rows[0]["n"]],
    },
    {
        "id": "orders_quarter",
        "category": "time-period count",
        "question": "What is the total number of purchase orders created in Q1 2015?",
        "truth": [{"$match": {"year_quarter": "2015-Q1"}}, {"$group": {"_id": "$po_number"}}, {"$count": "n"}],
        "expect": lambda rows: [rows[0]["n"]],
    },
    {
        "id": "orders_fiscal_year",
        "category": "time-period count",
        "question": "How many distinct purchase orders were there in fiscal year 2012-2013?",
        "truth": [{"$match": {"fiscal_year": "2012-2013"}}, {"$group": {"_id": "$po_number"}}, {"$count": "n"}],
        "expect": lambda rows: [rows[0]["n"]],
    },
    {
        "id": "top_quarter",
        "category": "highest spending",
        "question": "Which quarter had the highest spending?",
        "truth": [{"$group": {"_id": "$year_quarter", "s": {"$sum": "$total_price"}}}, {"$sort": {"s": -1}}, {"$limit": 1}],
        "expect": lambda rows: [rows[0]["_id"].split("-")[1], rows[0]["_id"].split("-")[0]],
    },
    {
        "id": "top_fiscal_quarter",
        "category": "highest spending",
        "question": "Which fiscal quarter of fiscal year 2013-2014 had the highest total spend?",
        "truth": [{"$match": {"fiscal_year": "2013-2014"}},
                  {"$group": {"_id": "$fiscal_quarter", "s": {"$sum": "$total_price"}}}, {"$sort": {"s": -1}}, {"$limit": 1}],
        "expect": lambda rows: [rows[0]["s"]],
    },
    {
        "id": "top_items",
        "category": "frequent items",
        "question": "What is the most frequently ordered commodity?",
        "truth": [{"$match": {"commodity_title": {"$ne": None}}},
                  {"$group": {"_id": "$commodity_title", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 1}],
        "expect": lambda rows: [rows[0]["_id"]],
    },
    {
        "id": "top_department",
        "category": "ranking",
        "question": "Which department spent the most money overall?",
        "truth": [{"$group": {"_id": "$department_name", "s": {"$sum": "$total_price"}}}, {"$sort": {"s": -1}}, {"$limit": 1}],
        "expect": lambda rows: [rows[0]["_id"].split(",")[0]],
    },
    {
        "id": "top_supplier_count",
        "category": "ranking",
        "question": "Which supplier appears on the most purchase order line items?",
        "truth": [{"$group": {"_id": "$supplier_name", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 1}],
        "expect": lambda rows: [rows[0]["_id"]],
    },
    {
        "id": "calcard_share",
        "category": "filter count",
        "question": "How many line items were paid with CalCard?",
        "truth": [{"$match": {"calcard": True}}, {"$count": "n"}],
        "expect": lambda rows: [rows[0]["n"]],
    },
    {
        "id": "it_goods_spend_2014",
        "category": "filter + sum",
        "question": "What was the total spending on IT Goods in calendar year 2014?",
        "truth": [{"$match": {"year": 2014, "acquisition_type": "IT Goods"}},
                  {"$group": {"_id": None, "s": {"$sum": "$total_price"}}}],
        "expect": lambda rows: [rows[0]["s"]],
    },
    {
        "id": "small_business",
        "category": "array filter",
        "question": "How many line items went to certified small businesses (CA-SB)?",
        "truth": [{"$match": {"supplier_qualifications": "CA-SB"}}, {"$count": "n"}],
        "expect": lambda rows: [rows[0]["n"]],
    },
    {
        "id": "multi_step",
        "category": "multi-step",
        "question": "In the calendar quarter with the highest spending, which department spent the most?",
        "truth": [{"$match": {"year_quarter": "2015-Q2"}},
                  {"$group": {"_id": "$department_name", "s": {"$sum": "$total_price"}}}, {"$sort": {"s": -1}}, {"$limit": 1}],
        "expect": lambda rows: [rows[0]["_id"].split(",")[0]],
    },
    {
        "id": "follow_up",
        "category": "follow-up (context)",
        "question": ["How many orders were created in January 2014?", "And in February?"],
        "truth": [{"$match": {"year_month": "2014-02"}}, {"$group": {"_id": "$po_number"}}, {"$count": "n"}],
        "expect": lambda rows: [rows[0]["n"]],
    },
    {
        "id": "arabic",
        "category": "multilingual",
        "question": "كم عدد أوامر الشراء في شهر يونيو 2013؟",
        "truth": [{"$match": {"year_month": "2013-06"}}, {"$group": {"_id": "$po_number"}}, {"$count": "n"}],
        "expect": lambda rows: [rows[0]["n"]],
    },
]
