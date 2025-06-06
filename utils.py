import pandas as pd
import re

def apply_global_filters(df: pd.DataFrame, df_key: pd.DataFrame, filters: dict) -> pd.DataFrame:
    f_questions = filters.get("filter_questions", [])
    f_values = filters.get("filter_values", [])

    for q, v in zip(f_questions, f_values):
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

        if code is not None and q in df.columns:
            df = df[df[q] == code]
    return df

def is_valid_data_column(col_name: str) -> bool:
    """
    Returns False if the column is marked as a user input column (e.g., ends with ':: user input').
    """
    return ":: user input" not in col_name.lower()

def detect_nps_questions(df: pd.DataFrame, df_key: pd.DataFrame) -> list:
    """
    Detect NPS-style questions:
    - Columns must follow 'Qx | Label' format
    - Use Answer Key column B (index 1) to extract option labels
    - All values must be in the range 0–10
    """
    prefix_map = {}

    for col in df.columns:
        if isinstance(col, str) and "|" in col and is_valid_data_column(col):
            prefix = col.split("|")[0].strip()
            prefix_map.setdefault(prefix, []).append(col)

    nps_questions = []

    for qid, cols in prefix_map.items():
        capture = False
        option_labels = []

        for _, row in df_key.iterrows():
            key = str(row[0]).strip() if pd.notna(row[0]) else ""
            val = str(row[1]).strip() if pd.notna(row[1]) else ""

            if key == qid:
                capture = True
                continue
            if capture and key.startswith("Q"):
                break
            if capture and val:
                option_labels.append(val)

        numeric_vals = []
        for v in option_labels:
            try:
                numeric_vals.append(int(str(v).strip()))
            except:
                pass

        if numeric_vals and all(0 <= val <= 10 for val in numeric_vals):
            nps_questions.append(qid)

    return nps_questions

def detect_single_choice_questions(df: pd.DataFrame, df_key: pd.DataFrame) -> list:
    """
    Detect single choice questions:
    - Must appear in the dataset as a single column (e.g., 'Q5')
    - Must have numeric codes (1, 2, ...) in the raw data
    - Option codes must be defined in Answer Key column A
    """
    single_choice_qs = []

    for col in df.columns:
        if not is_valid_data_column(col):
            continue
        if not isinstance(col, str):
            continue
        if not re.match(r"^Q\d+$", col):
            continue

        series = pd.to_numeric(df[col], errors='coerce').dropna().astype(int)
        if series.empty:
            continue

        # ✅ Now check if answer key for this column has numeric codes in col A
        capture = False
        valid_codes = []

        for _, row in df_key.iterrows():
            key = str(row[0]).strip() if pd.notna(row[0]) else ""

            if key == col:
                capture = True
                continue
            if capture and key.startswith("Q"):
                break
            if capture and row[0] is not None:
                try:
                    valid_codes.append(int(row[0]))
                except:
                    continue

        if valid_codes and series.isin(valid_codes).any():
            single_choice_qs.append(col)

    return single_choice_qs

def detect_multi_select_questions(df: pd.DataFrame) -> list:
    """
    Detect multi-select questions:
    - Columns start with the same prefix like 'Qx:'
    - All values are binary (0, 1 or NaN)
    """
    prefix_map = {}

    for col in df.columns:
        if isinstance(col, str) and ":" in col and is_valid_data_column(col):
            prefix = col.split(":")[0].strip()
            prefix_map.setdefault(prefix, []).append(col)

    multi_select_qs = []

    for qid, cols in prefix_map.items():
        if len(cols) < 2:
            continue

        binary = True
        for col in cols:
            values = df[col].dropna().unique()
            if not all(v in [0, 1] for v in values):
                binary = False
                break

        if binary:
            multi_select_qs.append(qid)

    return multi_select_qs