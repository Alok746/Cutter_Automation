from flask import render_template
import pandas as pd
from utils import apply_global_filters
import os

BUCKETS = [(0, 10), (11, 20), (21, 30), (31, 40), (41, 50),
           (51, 60), (61, 70), (71, 80), (81, 90), (91, 100)]

def bucket_label(low, high):
    return f"{low}–{high}"

def get_bucket(val):
    try:
        val = float(val)
        for low, high in BUCKETS:
            if low <= val <= high:
                return bucket_label(low, high)
    except:
        return None
    return None

def get_sow_data(filepath, sheet, question_prefix, filters):
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)
    df = apply_global_filters(df, df_key, filters)

    relevant_cols = [col for col in df.columns if isinstance(col, str) and col.startswith(f"{question_prefix}:")]
    brands = [col.split(":", 1)[1].strip() for col in relevant_cols]

    # Build bucket map
    bucket_counts = {bucket_label(l, h): [0] * len(brands) for l, h in BUCKETS}
    col_totals = [0] * len(brands)

    for col_idx, col in enumerate(relevant_cols):
        series = pd.to_numeric(df[col], errors='coerce').dropna()
        col_totals[col_idx] = len(series)

        for val in series:
            bucket = get_bucket(val)
            if bucket:
                bucket_counts[bucket][col_idx] += 1

    bucket_labels = list(bucket_counts.keys())
    count_matrix = [bucket_counts[label] for label in bucket_labels]

    filename_only = os.path.basename(filepath)

    return {
        "question_text":f"{question_prefix}: Share of Wallet Distribution",
        "row_labels":bucket_labels,
        "col_labels":brands,
        "count_matrix":count_matrix,
        "col_totals":col_totals,
        "question_code": question_prefix,
        "all_columns": [],
        "sort_column_options": []
    }
    
def process_share_of_wallet(filepath, sheet, column, filters):
    data = get_sow_data(filepath, sheet, column, filters)
    data.update({
        "filename": os.path.basename(filepath),
        "sheet": sheet
    })
    return render_template("results_sow.html", **data)