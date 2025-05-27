from flask import render_template
import pandas as pd
from utils import apply_global_filters
import re
import os

def process_multi_select(filepath, sheet, column, filters):
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)
    df = apply_global_filters(df, df_key, filters)
    base_prefix = column.split(":")[0].strip()
    relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix}:")]

    answer_labels = []
    capture = False
    question_text = base_prefix
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip() == base_prefix:
            capture = True
            if pd.notna(row[1]):
                question_text = f"{base_prefix}: {str(row[1]).strip()}"
            continue
        if capture and pd.isna(row[0]):
            break
        if capture and pd.notna(row[1]):
            answer_labels.append(str(row[1]).strip())

    total_respondents = df[relevant_cols[0]].notna().sum() if relevant_cols else 0
    response_summary = []
    total_responses = 0

    for label in answer_labels:
        col_match = next((col for col in relevant_cols if label in col), None)
        count = (df[col_match] == 1).sum() if col_match else 0
        total_responses += count
        response_summary.append((label, count))

    final_data = []
    for label, count in response_summary:
        pct_respondent = (count / total_respondents * 100) if total_respondents else 0
        pct_response = (count / total_responses * 100) if total_responses else 0
        final_data.append((label, count, pct_respondent, pct_response))

    filename_only = os.path.basename(filepath)

    question_columns = []
    for _, row in df_key.iterrows():
        if pd.notna(row[0]):
            code = str(row[0]).strip()
            if re.match(r'^Q\d+$', code):
                question_columns.append(code)
    question_columns = list(dict.fromkeys(question_columns))
    
    if filters.get("sort_column") == "asc":
        final_data.sort(key=lambda x: x[2])
    elif filters.get("sort_column") == "desc":
        final_data.sort(key=lambda x: x[2], reverse=True)

    return render_template("results_multiple_select.html",
        question_text=question_text,
        response_summary=final_data,
        total_responses=total_responses,
        total_respondents=total_respondents,
        total_pct_response=100,
        total_pct_respondent=100,
        min_pct=0,
        max_pct=100,
        sort_order="none",
        sort_column="",
        sort_column_options=[],
        filename=filename_only,
        sheet=sheet,
        question_code=column,
        all_columns=question_columns
    )
