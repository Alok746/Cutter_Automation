from flask import render_template
import pandas as pd
import re
import os

def process_ranked_question(filepath, sheet, column, filters):
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

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

    return render_template("results_ranked.html",
        question_text=f"Ranked Summary for {base_prefix}",
        rank_labels=rank_labels,
        result_matrix=result_matrix,
        percent_matrix=percent_matrix,
        col_totals=col_totals,
        overall_total=total_respondents,
        total_respondents=total_respondents,
        sort_order="none",
        sort_column="Overall",
        sort_column_options=["Overall"] + rank_labels,
        filename=filename_only,
        sheet=sheet,
        question_code=base_prefix,
        all_columns=question_columns
    )
