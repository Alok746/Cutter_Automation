from flask import render_template
import pandas as pd
import re
from utils import apply_global_filters
import os

def get_nps_data(filepath, sheet, column, filters):
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

    return {
        "question_text":question_text,
        "row_labels":row_labels,
        "col_labels":col_labels,
        "result_matrix":result_matrix,
        "col_totals":[int(x) for x in col_totals],
        "promoters": [int(x) for x in promoters],
        "neutrals": [int(x) for x in neutrals],
        "detractors": [int(x) for x in detractors],
        "nps_scores": [float(x) for x in nps_scores],
        "average_scores": [float(x) for x in average_scores],
        "question_code": base_prefix,
        "all_columns": question_columns
    }

def process_nps_question(filepath, sheet, column, filters):
    data = get_nps_data(filepath, sheet, column, filters)
    data.update({
        "filename": os.path.basename(filepath),
        "sheet": sheet
    })
    return render_template("results_nps.html", **data)

def process_nps_question_qualtrics(filepath, sheet, column, filters):
    # Read necessary sheets
    df       = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key   = pd.read_excel(filepath, sheet_name="Answer key", header=None)
    varinfo  = pd.read_excel(filepath, sheet_name="Variable information", header=None)

    # Apply any global filters (your existing function)
    df = apply_global_filters(df, df_key, filters)

    # Step 1: pick up any columns exactly == column or ending in _{column}
    relevant_cols = [
        col for col in df.columns
        if col == column or col.endswith(f"_{column}")
    ]
    if not relevant_cols:
        return f"No NPS columns found for base '{column}'"

    # Step 2: grab full text per column from varinfo
    col_to_text    = {}
    question_texts = []
    for col in relevant_cols:
        match = varinfo[varinfo[0] == col]
        if not match.empty and pd.notna(match.iloc[0][2]):
            full_text = str(match.iloc[0][2])
        else:
            full_text = col
        col_to_text[col] = full_text
        question_texts.append(full_text)

    # Step 3: find common prefix
    def get_common_prefix(strings):
        prefix = strings[0]
        for s in strings[1:]:
            while not s.startswith(prefix):
                prefix = prefix[:-1]
        return prefix.strip()

    common_prefix = get_common_prefix(question_texts)
    question_text = common_prefix or f"NPS Summary for {column}"
    col_labels    = [
        col_to_text[col].replace(common_prefix, "").strip(" :-")
        for col in relevant_cols
    ]

    # Step 4: calculate NPS stats
    promoters      = []
    neutrals       = []
    detractors     = []
    nps_scores     = []
    average_scores = []
    col_totals     = []
    score_range    = list(range(0, 11))
    result_matrix  = []

    for col in relevant_cols:
        scores = pd.to_numeric(df[col], errors='coerce').dropna().astype(int)
        total  = int(len(scores))

        prom  = int((scores >= 9).sum())
        neut  = int(((scores >= 7) & (scores <= 8)).sum())
        detr  = int((scores <= 6).sum())

        nps = float(round((prom - detr) / total * 100, 2)) if total else 0.0
        avg = float(round(scores.mean(), 2))              if total else 0.0

        promoters.append(prom)
        neutrals.append(neut)
        detractors.append(detr)
        nps_scores.append(nps)
        average_scores.append(avg)
        col_totals.append(total)

    # Step 5: build distribution matrix as (score_str, [counts…])
    for score in score_range:
        row = [int((df[col] == score).sum()) for col in relevant_cols]
        result_matrix.append((str(score), row))

    filename_only = os.path.basename(filepath)

    # Sidebar: list all Q-codes from the answer key
    question_columns = []
    for _, row in df_key.iterrows():
        if pd.notna(row[0]):
            code = str(row[0]).strip()
            if re.match(r'^Q\d+$', code):
                question_columns.append(code)
    question_columns = list(dict.fromkeys(question_columns))

    return render_template("results_nps.html",
        filename          = filename_only,
        sheet             = sheet,
        question_text     = question_text,
        col_labels        = col_labels,
        promoters         = promoters,
        neutrals          = neutrals,
        detractors        = detractors,
        nps_scores        = nps_scores,
        average_scores    = average_scores,
        result_matrix     = result_matrix,
        col_totals        = col_totals,
        question_code     = column,
        all_columns       = question_columns
    )