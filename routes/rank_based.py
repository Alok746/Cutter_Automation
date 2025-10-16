from flask import render_template
import pandas as pd
import re
from utils import apply_global_filters
import os

def get_ranked_data(filepath, sheet, column, filters):
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

    df = apply_global_filters(df, df_key, filters)
    base_prefix = column.split(":")[0].strip()
    relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix}:")]

    actual_max = 0
    for col in relevant_cols:
        col_max = pd.to_numeric(df[col], errors='coerce').max()
        if pd.notna(col_max) and col_max > actual_max:
            actual_max = int(col_max)

    try:
        max_rank = int(filters.get('max_rank', actual_max))
        max_rank = min(max_rank, actual_max)
    except (ValueError, TypeError):
        max_rank = actual_max

    rank_labels = [f"Rank {i}" for i in range(1, max_rank + 1)]
    total_respondents = df[relevant_cols].notna().any(axis=1).sum()

    result_matrix = []
    col_totals = [0] * max_rank
    for col in relevant_cols:
        label = col.split(":")[1].strip() if ":" in col else col
        counts = []
        for i in range(1, max_rank + 1):
            count = (df[col] == i).sum()
            counts.append(count)
            col_totals[i - 1] += count
        row_total = sum(counts)
        result_matrix.append((label, row_total, counts))
        
    row_labels = [label for label, _, _ in result_matrix]
    count_matrix = [counts for _, _, counts in result_matrix]

    percent_matrix = []
    for label, row_total, counts in result_matrix:
        rank_percents = [(count / row_total * 100 if row_total > 0 else 0) for count in counts]
        overall_pct = (row_total / total_respondents * 100) if total_respondents > 0 else 0
        percent_matrix.append((label, overall_pct, rank_percents))

    filename_only = os.path.basename(filepath)

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
        
    question_text = f"Ranked Summary for {base_prefix}"
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip() == base_prefix:
            if pd.notna(row[1]):
                question_text = f"{base_prefix}: {str(row[1]).strip()}"
            break

    return {
        "question_text": question_text,
        "rank_labels": rank_labels,
        "result_matrix": result_matrix,
        "percent_matrix": percent_matrix,
        "col_totals": col_totals,
        "overall_total": total_respondents,
        "total_respondents": total_respondents,
        "sort_column_options": ["Overall"] + rank_labels,
        "question_code": base_prefix,
        "all_columns": question_columns
    }
    
def process_ranked_question(filepath, sheet, column, filters):
    data = get_ranked_data(filepath, sheet, column, filters)
    data.update({
        "sort_order":"none",
        "sort_column":"Overall",
        "filename": os.path.basename(filepath),
        "sheet": sheet
    })
    return render_template("results_ranked.html", **data)

def process_ranked_question_qualtrics(filepath, sheet, column, filters):
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)
    varinfo = pd.read_excel(filepath, sheet_name="Variable information", header=None)

    df = apply_global_filters(df, df_key, filters)

    base_prefix = column.split("_")[0].strip()
    relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix}_")]

    col_to_text = {}
    question_texts = []
    for col in relevant_cols:
        row_match = varinfo[varinfo[0] == col]
        if not row_match.empty:
            full_text = str(row_match.iloc[0][2])
            col_to_text[col] = full_text
            question_texts.append(full_text)
        else:
            col_to_text[col] = col
            question_texts.append(col)

    def get_common_prefix(strings):
        prefix = strings[0]
        for s in strings[1:]:
            while not s.startswith(prefix):
                prefix = prefix[:-1]
        return prefix.strip()

    common_prefix = get_common_prefix(question_texts)

    row_labels = [
        col_to_text[col].replace(common_prefix, '').strip(" :-") for col in relevant_cols
    ]
    actual_max = 0
    for col in relevant_cols:
        col_max = pd.to_numeric(df[col], errors='coerce').max()
        if pd.notna(col_max) and col_max > actual_max:
            actual_max = int(col_max)

    try:
        max_rank = int(filters.get('max_rank', actual_max))
        max_rank = min(max_rank, actual_max)
    except (ValueError, TypeError):
        max_rank = actual_max

    rank_labels = [f"Rank {i}" for i in range(1, max_rank + 1)]
    total_respondents = df[relevant_cols].notna().any(axis=1).sum()

    result_matrix = []
    col_totals = [0] * max_rank
    for i, col in enumerate(relevant_cols):
        label = row_labels[i]
        counts = [(df[col] == r).sum() for r in range(1, max_rank + 1)]
        row_total = sum(counts)
        result_matrix.append((label, row_total, counts))
        for j, c in enumerate(counts):
            col_totals[j] += c

    percent_matrix = []
    for label, row_total, counts in result_matrix:
        rank_percents = [(count / row_total * 100 if row_total else 0) for count in counts]
        overall_pct = (row_total / total_respondents * 100) if total_respondents else 0
        percent_matrix.append((label, overall_pct, rank_percents))

    filename_only = os.path.basename(filepath)

    question_columns = []
    for _, row in df_key.iterrows():
        if pd.notna(row[0]):
            code = str(row[0]).strip()
            if re.match(r'^Q\d+$', code):
                question_columns.append(code)
    question_columns = list(dict.fromkeys(question_columns))
    
    sort_order = filters.get("sort_column", "")
    if sort_order in ("asc", "desc") and percent_matrix:
        reverse = sort_order == "desc"
        combined = list(zip(percent_matrix, result_matrix))
        combined.sort(key=lambda x: x[0][1], reverse=reverse)  # sort by overall %
        percent_matrix, result_matrix = zip(*combined)
        percent_matrix, result_matrix = list(percent_matrix), list(result_matrix)

    return render_template("results_ranked.html",
        question_text=common_prefix,
        rank_labels=rank_labels,
        result_matrix=result_matrix,
        percent_matrix=percent_matrix,
        col_totals=col_totals,
        overall_total=total_respondents,
        total_respondents=total_respondents,
        sort_order=sort_order,
        sort_column="Overall",
        sort_column_options=["Overall"] + rank_labels,
        filename=filename_only,
        sheet=sheet,
        question_code=base_prefix,
        all_columns=question_columns
    )