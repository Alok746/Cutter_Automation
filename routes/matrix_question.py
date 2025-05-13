from flask import render_template
import pandas as pd
import re

def process_matrix_question(filepath, sheet, column, filters):
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

    base_prefix = column.split(":")[0].strip()
    relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix}:")]

    # Build row label map
    option_map = {}
    capture = False
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip() == base_prefix:
            capture = True
            continue
        if capture and pd.isna(row[0]):
            break
        if capture and pd.notna(row[0]) and pd.notna(row[1]):
            option_map[str(int(float(row[0]))) if str(row[0]).replace('.', '', 1).isdigit() else str(row[0]).strip()] = str(row[1]).strip()

    row_labels = list(option_map.values())
    col_labels = [col.split(":")[1].strip() for col in relevant_cols]
    col_totals = [df[col].notna().sum() for col in relevant_cols]

    count_matrix = []
    percent_matrix = []
    for code, label in option_map.items():
        row_counts = []
        row_percents = []
        for i, col in enumerate(relevant_cols):
            count = (df[col].dropna().astype(str).str.strip() == code).sum()
            row_counts.append(count)
            percent = (count / col_totals[i]) * 100 if col_totals[i] else 0
            row_percents.append(percent)
        count_matrix.append(row_counts)
        percent_matrix.append(row_percents)

    return render_template("results_matrix.html", question_text=column, row_labels=row_labels, col_labels=col_labels,
                           count_matrix=count_matrix, percent_matrix=percent_matrix, col_totals=col_totals,
                           cut_headers=col_labels, sort_order="none", sort_column="", filename=filepath.split('/')[-1],
                           sheet=sheet, question_code=column, all_columns=[], sort_column_options=col_labels)