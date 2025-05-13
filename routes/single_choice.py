from flask import render_template
import pandas as pd
import re
import os

def process_single_choice(filepath, sheet, column, filters):
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

    # Get full list of question columns (those present in the answer key)
    question_columns = []
    seen = set()

    for _, row in df_key.iterrows():
        if pd.notna(row[0]):
            code = str(row[0]).strip()
            if re.match(r'^Q\d+$', code) and code not in seen:
                seen.add(code)
                question_columns.append(code)  # remove duplicates while preserving order

    print("set", question_columns)
    # Apply filters (if any)
    if filters:
        f_questions = filters.get("filter_questions", [])
        f_values = filters.get("filter_values", [])
        for q, v in zip(f_questions, f_values):
            if not q or v == "__all__":
                continue
            code = None
            capture = False
            for _, row in df_key.iterrows():
                if pd.notna(row[0]) and str(row[0]).strip() == q:
                    capture = True
                    continue
                if capture and pd.isna(row[0]):
                    break
                if capture and pd.notna(row[1]):
                    if str(row[1]).strip() == v:
                        code = row[0]
                        break
            df = df[df[q] == code] if code is not None else df[0:0]

    selected_values = df[column].dropna()

    # Map codes to labels
    mapping_dict = {}
    question_text = column
    capture = False
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip() == column:
            capture = True
            if pd.notna(row[1]):
                question_text = f"{column}: {str(row[1]).strip()}"
            continue
        if capture and pd.isna(row[0]):
            break
        if capture and pd.notna(row[0]) and pd.notna(row[1]):
            mapping_dict[str(int(float(row[0]))).strip()] = str(row[1]).strip()

    def normalize(val):
        try:
            return mapping_dict.get(str(int(float(val))).strip(), "Unknown")
        except:
            return "Unknown"

    mapped_values = selected_values.apply(normalize)
    value_counts = mapped_values.value_counts().to_dict()
    total = sum(value_counts.values())

    summary = []
    for label in mapping_dict.values():
        count = value_counts.get(label, 0)
        pct = (count / total * 100) if total else 0
        summary.append((label, count, round(pct, 2)))

    filename_only = os.path.basename(filepath)

    return render_template('results.html',
        question_text=question_text,
        response_summary=summary,
        total_count=total,
        total_pct=100,
        min_pct=0,
        max_pct=100,
        sort_order='none',
        filename=filename_only,
        sheet=sheet,
        question_code=column,
        all_columns=question_columns,  # ✅ Pass full list of questions here
        sort_column_options=[]
    )
