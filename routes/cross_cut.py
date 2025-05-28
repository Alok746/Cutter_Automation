from flask import render_template
import pandas as pd
import os
import re
from utils import apply_global_filters

def process_cross_cut(filepath, sheet, column, filters):
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)
    df = apply_global_filters(df, df_key, filters)

    base_prefix = column.split(":")[0].strip()
    cut_col = filters.get("cut_column", "")
    cut_prefix = cut_col.split(":")[0].strip() if cut_col else ""

    # ✅ Use multi-column format if available, else fallback to single-column
    relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix}:")]
    is_single_column = False
    if not relevant_cols and base_prefix in df.columns:
        relevant_cols = [base_prefix]
        is_single_column = True

    # ✅ Get base options from answer key
    base_options = []
    base_option_code_map = {}
    capture = False
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip() == base_prefix:
            capture = True
            continue
        if capture and pd.isna(row[0]):
            break
        if capture and pd.notna(row[0]) and pd.notna(row[1]):
            label = str(row[1]).strip()
            code = row[0]
            base_options.append(label)
            base_option_code_map[label] = code

    # ✅ Get cut column value labels
    cut_value_map = {}
    capture = False
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip() == cut_prefix:
            capture = True
            continue
        if capture and pd.isna(row[0]):
            break
        if capture and pd.notna(row[0]) and pd.notna(row[1]):
            cut_value_map[row[0]] = str(row[1]).strip()

    cut_codes = list(cut_value_map.keys())
    cut_labels = list(cut_value_map.values())
    total_respondents = df[cut_col].notna().sum() if cut_col else 0

    # ✅ Compute count matrix
    cut_totals = [df[df[cut_col] == code].shape[0] for code in cut_codes]
    result_matrix = []

    for base_option in base_options:
        row_counts = []
        base_code = base_option_code_map.get(base_option)

        for cut_val in cut_codes:
            filtered = df[df[cut_col] == cut_val]

            if is_single_column:
                match_col = relevant_cols[0]
                count = (filtered[match_col] == base_code).sum() if base_code is not None else 0
            else:
                match_col = next((col for col in relevant_cols if base_option in col), None)
                count = filtered[match_col].notna().sum() if match_col else 0

            row_counts.append(count)

        row_total = sum(row_counts)
        result_matrix.append((base_option, row_total, row_counts))

    # ✅ Compute percentage matrix
    percent_matrix = []
    for label, row_total, counts in result_matrix:
        row_percents = [(v / cut_totals[i] * 100 if cut_totals[i] > 0 else 0) for i, v in enumerate(counts)]
        overall_pct = (row_total / total_respondents * 100) if total_respondents > 0 else 0
        percent_matrix.append((label, overall_pct, row_percents))

    # ✅ Sorting
    sort_order = filters.get("sort_column")
    if sort_order in ["asc", "desc"] and percent_matrix:
        reverse = sort_order == "desc"
        combined = list(zip(percent_matrix, result_matrix))
        combined.sort(key=lambda x: x[0][1], reverse=reverse)
        percent_matrix, result_matrix = zip(*combined)
        percent_matrix = list(percent_matrix)
        result_matrix = list(result_matrix)

    filename_only = os.path.basename(filepath)

    return render_template("results_cross_cut.html",
        question_text=f"Cross cut {column} x {cut_prefix}",
        cut_headers=cut_labels,
        result_matrix=result_matrix,
        percent_matrix=percent_matrix,
        total_respondents=total_respondents,
        cut_totals=cut_totals,
        sort_order=sort_order,
        sort_column="Overall",
        sort_column_options=["Overall"] + cut_labels,
        filename=filename_only,
        sheet=sheet,
        question_code=base_prefix,
        cut_column=cut_prefix,
        all_columns=[]
    )