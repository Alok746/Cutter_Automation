from flask import render_template
import pandas as pd
import re
from utils import apply_global_filters
import os

def process_nps_question(filepath, sheet, column, filters):
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)
    df = apply_global_filters(df, df_key, filters)
    base_prefix = column.split("|")[0].strip()
    relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix} |")]
    col_labels = [col.split("|")[1].strip() for col in relevant_cols]

    row_labels = [str(i) for i in range(11)]
    result_matrix = []
    for score in row_labels:
        row = []
        value_to_count = int(score) + 1
        for col in relevant_cols:
            count = (df[col] == value_to_count).sum()
            row.append(count)
        result_matrix.append((score, row))

    brand_columns = list(zip(*[row[1] for row in result_matrix]))
    col_totals = [sum(col) for col in brand_columns]
    promoters = [sum(col[9:11]) for col in brand_columns]
    neutrals = [sum(col[7:9]) for col in brand_columns]
    detractors = [sum(col[0:7]) for col in brand_columns]
    nps_scores = [round(((p - d) / t) * 100, 1) if t else 0 for p, d, t in zip(promoters, detractors, col_totals)]
    average_scores = [
        round(sum(i * col[i] for i in range(11)) / sum(col), 2) if sum(col) > 0 else 0
        for col in brand_columns
    ]

    filename_only = os.path.basename(filepath)

    question_columns = []
    for _, row in df_key.iterrows():
        if pd.notna(row[0]):
            code = str(row[0]).strip()
            if re.match(r'^Q\d+$', code):
                question_columns.append(code)
    question_columns = list(dict.fromkeys(question_columns))
    
    question_text = f"NPS Summary for {base_prefix}"
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip() == base_prefix:
            if pd.notna(row[1]):
                question_text = f"{base_prefix}: {str(row[1]).strip()}"
            break

    return render_template("results_nps.html",
        question_text=question_text,
        row_labels=row_labels,
        col_labels=col_labels,
        result_matrix=result_matrix,
        col_totals=[int(x) for x in col_totals],
        promoters=[int(x) for x in promoters],
        neutrals=[int(x) for x in neutrals],
        detractors=[int(x) for x in detractors],
        nps_scores=[float(x) for x in nps_scores],
        average_scores=[float(x) for x in average_scores],
        filename=filename_only,
        sheet=sheet,
        question_code=base_prefix,
        all_columns=question_columns
    )
