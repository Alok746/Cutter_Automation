from flask import render_template
import pandas as pd
import os
import re
from utils import apply_global_filters

def get_cross_cut_data(filepath, sheet, column, filters):
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

    return {
        "question_text":f"Cross cut {column} x {cut_prefix}",
        "result_matrix":result_matrix,
        "percent_matrix": percent_matrix,
        "total_respondents":total_respondents,
        "cut_totals":cut_totals,
        "sort_order":sort_order,
        "sort_column_options": ["Overall"] + cut_labels,
        "question_code": base_prefix,
        "cut_column":cut_prefix,
        "all_columns": [],
        "cut_headers": cut_labels
    }
    
def process_cross_cut(filepath, sheet, column, filters):
    data = get_cross_cut_data(filepath, sheet, column, filters)
    data.update({
        "sort_column": "Overall",
        "filename": os.path.basename(filepath),
        "sheet": sheet
    })
    return render_template("results_cross_cut.html", **data)

def process_cross_cut_qualtrics(filepath, sheet, column, filters):
    # 1) Load the “full” sheet (so we can drop the question‑text row)
    df_full = pd.read_excel(filepath, sheet_name=sheet, header=2)
    # drop the text row so row 0 of `df` is the first respondent
    df = df_full.iloc[1:].reset_index(drop=True)

    # 2) Load & prepare the Answer Key
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)
    # Qualtrics key often repeats the QID down the column
    df_key[0] = df_key[0].ffill()

    # 3) Apply any global filters
    df = apply_global_filters(df, df_key, filters)

    # 4) Identify base (row) question and “cut” question prefixes
    base_qid = column.strip()                         # e.g. "Q2"
    cut_qid  = filters.get("cut_column", "").strip()  # e.g. "Q5"
    
    # 5) Find all sub‑columns for each
    base_cols = [c for c in df.columns if isinstance(c, str) and c.startswith(base_qid + "_")]
    cut_cols  = [c for c in df.columns if isinstance(c, str) and c.startswith(cut_qid  + "_")]

    # If no underscored columns, fall back to single‐column (Qualtrics single‐choice)
    if not base_cols and base_qid in df.columns:
        base_cols = [base_qid]
    if not cut_cols and cut_qid in df.columns:
        cut_cols = [cut_qid]

    # 6) Build label maps from the Variable information sheet
    #    (col0 = raw column name, col1 = code, col2 = label text)
    try:
        df_var = pd.read_excel(filepath, sheet_name="Variable information", header=None)
    except:
        df_var = pd.DataFrame([], columns=[0,1,2])

    # helper: look up label for a (col, code) pair in varinfo
    def lookup_label(col, code):
        m = df_var[(df_var[0]==col) & (df_var[1].notna()) & (df_var[2].notna())]
        # prefer matching on the code column
        m = m[m[1].astype(str).str.strip()==str(code).strip()]
        if not m.empty:
            return str(m.iloc[0,2]).strip()
        return str(code)

    # 7) Build the “row” options (base question) labels
    row_options = []
    for col in base_cols:
        # single‐ or multi‐select base: pull all distinct codes actually used
        codes = pd.to_numeric(df[col], errors="coerce").dropna().unique()
        for code in sorted(codes):
            lbl = lookup_label(col, code)
            row_options.append((col, code, lbl))
    # dedupe by code
    seen = set()
    row_options = [o for o in row_options if not (o[1] in seen or seen.add(o[1]))]

    # 8) Build the “cut” buckets (column headers)
    cut_codes = []
    for col in cut_cols:
        codes = pd.to_numeric(df[col], errors="coerce").dropna().unique()
        for code in sorted(codes):
            lbl = lookup_label(col, code)
            cut_codes.append((col, code, lbl))
    seen = set()
    cut_codes = [o for o in cut_codes if not (o[1] in seen or seen.add(o[1]))]

    # 9) Count & assemble the result matrix
    total_respondents = df[cut_cols[0]].notna().sum() if cut_cols else 0
    cut_totals = []
    for _, cut_code, _ in cut_codes:
        # count how many rows have that code in ANY of the cut columns
        mask = pd.concat([df[c].astype(str).eq(str(cut_code)) for c,_,_ in cut_codes], axis=1).any(axis=1)
        cut_totals.append(int(mask.sum()))

    result_matrix = []
    for base_col, base_code, base_lbl in row_options:
        row_counts = []
        for cut_col, cut_code, _ in cut_codes:
            sub = df[df[cut_col].astype(str)==str(cut_code)]
            cnt = int((sub[base_col].astype(str)==str(base_code)).sum())
            row_counts.append(cnt)
        row_total = sum(row_counts)
        result_matrix.append((base_lbl, row_total, row_counts))

    # 10) Build percent matrix
    percent_matrix = []
    for base_lbl, row_total, counts in result_matrix:
        row_pcts = [
            (counts[i]/cut_totals[i]*100 if cut_totals[i] else 0)
            for i in range(len(counts))
        ]
        overall = (row_total/total_respondents*100) if total_respondents else 0
        percent_matrix.append((base_lbl, overall, row_pcts))

    # 11) Optional sorting
    sort_order = filters.get("sort_column")
    if sort_order in ("asc","desc") and percent_matrix:
        rev = (sort_order=="desc")
        combined = list(zip(percent_matrix, result_matrix))
        combined.sort(key=lambda x: x[0][1], reverse=rev)
        percent_matrix, result_matrix = zip(*combined)
        percent_matrix, result_matrix = list(percent_matrix), list(result_matrix)

    # 12) Render
    filename = os.path.basename(filepath)
    return render_template(
        "results_cross_cut.html",
        question_text    = f"{base_qid}: Cross‑cut by {cut_qid}",
        cut_headers      = [lbl for _,_,lbl in cut_codes],
        result_matrix    = result_matrix,
        percent_matrix   = percent_matrix,
        total_respondents= total_respondents,
        cut_totals       = cut_totals,
        sort_order       = sort_order,
        sort_column      = "Overall",
        sort_column_options = ["Overall"] + [lbl for _,_,lbl in cut_codes],
        filename         = filename,
        sheet            = sheet,
        question_code    = base_qid,
        cut_column       = cut_qid,
        all_columns      = [column]  # you can adjust if you want the full Q‑list
    )