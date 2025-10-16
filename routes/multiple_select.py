from flask import render_template
import pandas as pd
from utils import apply_global_filters
import re
import os

def get_multi_select_data(filepath, sheet, column, filters):
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

    question_columns = []
    for _, row in df_key.iterrows():
        if pd.notna(row[0]):
            code = str(row[0]).strip()
            if re.match(r'^Q\\d+$', code):
                question_columns.append(code)
    question_columns = list(dict.fromkeys(question_columns))

    return {
        "question_text": question_text,
        "response_summary": final_data,
        "total_responses": total_responses,
        "total_respondents": total_respondents,
        "total_pct_response": 100,
        "total_pct_respondent": 100,
        "question_code": column,
        "filename": os.path.basename(filepath),
        "sheet": sheet,
        "all_columns": question_columns,
    }
    
def process_multi_select(filepath, sheet, column, filters):
    data = get_multi_select_data(filepath, sheet, column, filters)
    return render_template("results_multiple_select.html", **data)

def process_multi_select_qualtrics(filepath, sheet, column, filters):
    import pandas as pd
    import os
    from flask import render_template
    from utils import apply_global_filters

    # ✅ Read data and drop label row if present
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df.drop(index=0, inplace=True)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)
    df_key[0] = df_key[0].ffill()

    df = apply_global_filters(df, df_key, filters)
    base_qid = column.strip()

    # ✅ Find sub-question columns like Q7_1, Q7_2, ...
    relevant_cols = [col for col in df.columns if str(col).startswith(base_qid)]
    print(f"[DEBUG] Relevant cols for {base_qid}: {relevant_cols}")
    for col in relevant_cols:
        print(f"[DEBUG] {col} → {df[col].dropna().unique().tolist()}")

    # ✅ Extract option labels from answer key
    option_labels = {}
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip().startswith(base_qid + "_"):
            try:
                qid = str(row[0]).strip()
                label = str(row[2]).strip() if len(row) > 2 and pd.notna(row[2]) else str(row[1]).strip()
                option_labels[qid] = label
            except:
                continue

    # ✅ Count selections using .notna()
    response_counts = []
    for qid, label in option_labels.items():
        col = next((c for c in relevant_cols if c.startswith(qid)), None)
        if col:
            count = df[col].notna().sum()
            response_counts.append((label, count))

    total_respondents = df[relevant_cols].notna().any(axis=1).sum()
    total_responses = sum(count for _, count in response_counts)

    response_summary = []
    for label, count in response_counts:
        pct_respondent = (count / total_respondents * 100) if total_respondents else 0
        pct_response = (count / total_responses * 100) if total_responses else 0
        response_summary.append((label, count, round(pct_respondent, 2), round(pct_response, 2)))

    # ✅ Extract common question text from variable info
    question_text = base_qid
    try:
        df_varinfo = pd.read_excel(filepath, sheet_name="Variable information", header=None)
        grouped_texts = []
        for _, row in df_varinfo.iterrows():
            if pd.notna(row[0]):
                qid = str(row[0]).strip()
                if qid.startswith(base_qid + "_") and pd.notna(row[2]):
                    grouped_texts.append(str(row[2]).strip())

        def longest_common_prefix(strings):
            if not strings:
                return ""
            shortest = min(strings, key=len)
            for i, ch in enumerate(shortest):
                for other in strings:
                    if i >= len(other) or other[i] != ch:
                        return shortest[:i].strip(" :-–")
            return shortest.strip(" :-–")

        if grouped_texts:
            question_text = f"{base_qid}: {longest_common_prefix(grouped_texts)}"
    except:
        pass

    filename_only = os.path.basename(filepath)
    all_columns = list(set(df_key[0].dropna().astype(str)))

    return render_template("results_multiple_select.html",
        question_text=question_text,
        response_summary=response_summary,
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
        question_code=base_qid,
        all_columns=all_columns
    )