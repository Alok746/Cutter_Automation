from flask import render_template
import pandas as pd
import re
from utils import apply_global_filters
import os

def get_matrix_question_data(filepath, sheet, column, filters):
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)
    df = apply_global_filters(df, df_key, filters)
    base_prefix = re.split(r"[:|]", column)[0].strip()

    relevant_cols = [
        col for col in df.columns
        if isinstance(col, str)
        and (col.startswith(f"{base_prefix}:") or col.startswith(f"{base_prefix} |"))
    ]

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

    # ✅ Get clean filename
    filename_only = os.path.basename(filepath)

    # ✅ Extract all question codes from Answer Key
    question_columns = []
    for _, row in df_key.iterrows():
        if pd.notna(row[0]):
            code = str(row[0]).strip()
            if re.match(r'^Q\d+$', code):
                question_columns.append(code)
    question_columns = list(dict.fromkeys(question_columns))
    
    if filters.get("sort_column") == "asc":
        percent_matrix, count_matrix, row_labels = zip(*sorted(
            zip(percent_matrix, count_matrix, row_labels), key=lambda x: x[0][0]
        ))
    elif filters.get("sort_column") == "desc":
        percent_matrix, count_matrix, row_labels = zip(*sorted(
            zip(percent_matrix, count_matrix, row_labels), key=lambda x: x[0][0], reverse=True
        ))
        
    question_text = column
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip() == base_prefix:
            if pd.notna(row[1]):
                question_text = f"{base_prefix}: {str(row[1]).strip()}"
            break

    return{
        "question_text": question_text,
        "row_labels": row_labels,
        "col_labels": col_labels,
        "count_matrix": [[int(x) for x in row] for row in count_matrix],
        "percent_matrix": [[float(x) for x in row] for row in percent_matrix],
        "col_totals": col_totals,
        "question_code":column,
        "all_columns":question_columns,
        "sort_column_options":col_labels
    }
    
def process_matrix_question(filepath, sheet, column, filters):
    data = get_matrix_question_data(filepath, sheet, column, filters)
    data.update({
        "cut_headers": data["col_labels"],
        "sort_order": "none",
        "sort_column": "",
        "filename": os.path.basename(filepath),
        "sheet": sheet
    })
    return render_template("results_matrix.html", **data)

def process_matrix_question_qualtrics(filepath, sheet, column, filters):
    # Load data
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df.drop(index=0, inplace=True)

    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)
    df_key[0] = df_key[0].ffill()
    df = apply_global_filters(df, df_key, filters)

    base_qid = column.strip()
    relevant_cols = [col for col in df.columns if col.startswith(base_qid + "_")]

    # Extract column labels (sub-question text)
    col_labels = []
    try:
        df_varinfo = pd.read_excel(filepath, sheet_name="Variable information", header=None)
        raw_labels = []
        for col in relevant_cols:
            label = col
            for _, row in df_varinfo.iterrows():
                if pd.notna(row[0]) and str(row[0]).strip() == col and pd.notna(row[2]):
                    label = str(row[2]).strip()
                    break
            raw_labels.append(label)

        def longest_common_prefix(strings):
            if not strings:
                return ""
            shortest = min(strings, key=len)
            for i, ch in enumerate(shortest):
                for other in strings:
                    if i >= len(other) or other[i] != ch:
                        return shortest[:i].strip(" :-–")
            return shortest.strip(" :-–")

        prefix = longest_common_prefix(raw_labels)
        col_labels = [label[len(prefix):].strip(" :-–") for label in raw_labels]
    except Exception as e:
        col_labels = relevant_cols

    # Get question text
    question_text = base_qid
    try:
        texts = []
        for _, row in df_varinfo.iterrows():
            if pd.notna(row[0]) and str(row[0]).startswith(base_qid + "_") and pd.notna(row[2]):
                texts.append(str(row[2]).strip())
        if texts:
            question_text = f"{base_qid}: {longest_common_prefix(texts)}"
    except Exception as e:
        print("Question text fallback error:", e)

    # Build row (scale) labels from answer key
    option_map = {}

    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip().startswith(base_qid + "_") and pd.notna(row[1]):
            try:
                code = str(int(float(row[1]))).strip()
                label = str(row[2]).strip() if len(row) > 2 and pd.notna(row[2]) else str(row[1]).strip()
                if code not in option_map:
                    option_map[code] = label
            except Exception as e:
                print(f"Error parsing code-label from row: {row.tolist()} → {e}")

    row_labels = list(option_map.values())
    # col_totals = [df[col].notna().sum() for col in relevant_cols]
    col_totals = [int(df[col].notna().sum()) for col in relevant_cols]
    count_matrix = []
    percent_matrix = []

    for code, row_label in option_map.items():
        row_counts = []
        row_percents = []

        for i, col in enumerate(relevant_cols):
            # Normalize all values to string and compare
            df_col_normalized = df[col].astype(str).str.strip()
            match_series = df_col_normalized == str(code)

            match_count = match_series.sum()

            row_counts.append(match_count)
            pct = (match_count / col_totals[i] * 100) if col_totals[i] else 0
            row_percents.append(pct)

        count_matrix.append(row_counts)
        percent_matrix.append(row_percents)
        
    sort_order = filters.get("sort_column", "")
    if sort_order in ("asc", "desc"):
        reverse = sort_order == "desc"
        combined = list(zip(percent_matrix, count_matrix, row_labels))
        combined.sort(key=lambda x: x[0][0], reverse=reverse)  # Sort by first column %
        percent_matrix, count_matrix, row_labels = zip(*combined)
        percent_matrix = list(percent_matrix)
        count_matrix = list(count_matrix)
        row_labels = list(row_labels)

    filename_only = os.path.basename(filepath)
    all_columns = list(set(df_key[0].dropna().astype(str)))

    return render_template("results_matrix.html",
        question_text=question_text,
        row_labels=row_labels,
        col_labels=col_labels,
        # count_matrix=count_matrix,
        count_matrix=[[int(x) for x in row] for row in count_matrix],
        percent_matrix=[[float(x) for x in row] for row in percent_matrix],
        col_totals=[int(x) for x in col_totals],
        # percent_matrix=percent_matrix,
        # col_totals=col_totals,
        cut_headers=col_labels,
        sort_order=sort_order,
        sort_column="Overall",
        filename=filename_only,
        sheet=sheet,
        question_code=base_qid,
        all_columns=all_columns,
        sort_column_options=col_labels
    )