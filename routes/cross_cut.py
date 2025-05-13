from flask import render_template
import pandas as pd
import os
import re

def process_cross_cut(filepath, sheet, column, filters):
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

    base_prefix = column.split(":")[0].strip()
    cut_col = filters.get("cut_column", "")
    cut_prefix = cut_col.split(":")[0].strip() if cut_col else ""

    relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix}:")]

    base_options = []
    cut_value_map = {}
    capture = False

    # Extract base options from answer key
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip() == base_prefix:
            capture = True
            continue
        if capture and pd.isna(row[0]):
            break
        if capture and pd.notna(row[1]):
            base_options.append(str(row[1]).strip())

    # Extract cut filter options from answer key
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

    cut_totals = [df[df[cut_col] == code].shape[0] for code in cut_codes]
    result_matrix = []

    for base_option in base_options:
        row_counts = []
        match_col = next((col for col in relevant_cols if base_option in col), None)
        for cut_val in cut_codes:
            filtered = df[df[cut_col] == cut_val]
            count = filtered[match_col].notna().sum() if match_col else 0
            row_counts.append(count)
        row_total = sum(row_counts)
        result_matrix.append((base_option, row_total, row_counts))

    percent_matrix = []
    for label, row_total, counts in result_matrix:
        row_percents = [(v / cut_totals[i] * 100 if cut_totals[i] > 0 else 0) for i, v in enumerate(counts)]
        overall_pct = (row_total / total_respondents * 100) if total_respondents > 0 else 0
        percent_matrix.append((label, overall_pct, row_percents))

    # ✅ Clean filename for safe HTML use
    filename_only = os.path.basename(filepath)

    # ✅ Extract question list for filter dropdown
    question_columns = []
    for _, row in df_key.iterrows():
        if pd.notna(row[0]):
            code = str(row[0]).strip()
            if re.match(r'^Q\d+$', code):
                question_columns.append(code)
    question_columns = list(dict.fromkeys(question_columns))

    return render_template("results_cross_cut.html",
        question_text=f"Cross cut {column} x {cut_prefix}",
        cut_headers=cut_labels,
        result_matrix=result_matrix,
        percent_matrix=percent_matrix,
        total_respondents=total_respondents,
        cut_totals=cut_totals,
        sort_order="none",
        sort_column="Overall",
        sort_column_options=["Overall"] + cut_labels,
        filename=filename_only,
        sheet=sheet,
        question_code=base_prefix,
        cut_column=cut_prefix,
        all_columns=question_columns
    )
