import pandas as pd
import re

def apply_global_filters(df: pd.DataFrame, df_key: pd.DataFrame, filters: dict) -> pd.DataFrame:
    f_questions = filters.get("filter_questions", [])
    f_values = filters.get("filter_values", [])
    mode = filters.get("data_format", "inquery")

    df_key = df_key.copy()
    df_key[0] = df_key[0].ffill()  # Ensures every row has a QID

    for q, v in zip(f_questions, f_values):
        code = None

        if mode == "qualtrics":
            # For Qualtrics, match row[0] == q (every row has QID)
            label_col = 2
            code_col = 1

            for _, row in df_key.iterrows():
                qid = str(row[0]).strip() if pd.notna(row[0]) else ""
                if qid != q:
                    continue

                label_val = str(row[label_col]).strip() if pd.notna(row[label_col]) else ""
                if label_val == v:
                    raw_code = row[code_col]
                    if pd.notna(raw_code):
                        try:
                            # Convert "1.0" → 1
                            code = int(float(str(raw_code).strip()))
                        except:
                            code = str(raw_code).strip()
                    break

        else:  # InQuery
            # For InQuery, capture block below QID row
            label_col = 1
            code_col = 0
            capture = False

            for _, row in df_key.iterrows():
                qid_or_code = str(row[0]).strip() if pd.notna(row[0]) else ""

                if qid_or_code == q:
                    capture = True
                    continue

                if capture and qid_or_code.startswith("Q"):
                    break

                if capture and pd.notna(row[label_col]) and str(row[label_col]).strip() == v:
                    raw_code = row[code_col]
                    if pd.notna(raw_code):
                        try:
                            code = int(float(str(raw_code).strip()))
                        except:
                            code = str(raw_code).strip()
                    break
                
        # Apply filtering to main or subcolumns
        if code is not None:
            if q in df.columns:
                df = df[df[q].astype(str).str.strip() == str(code)]
            else:
                matching_cols = [col for col in df.columns if col.startswith(q + "_")]
                if matching_cols:
                    mask = df[matching_cols].astype(str).eq(str(code)).any(axis=1)
                    df = df[mask]

    return df

def extract_answer_values(df_key, question_code: str, data_format: str):
    """
    Extracts question text and option labels from the answer key.
    Handles both InQuery and Qualtrics formats.

    Returns:
        List[str] — list of option labels
    """
    values = []
    capture = False

    for _, row in df_key.iterrows():
        cell_qid = str(row[0]).strip() if pd.notna(row[0]) else ""

        # Column C (index 2) for Qualtrics, B (index 1) for InQuery
        cell_label = ""
        if data_format == "qualtrics":
            cell_label = str(row[2]).strip() if pd.notna(row[2]) else ""
        else:
            cell_label = str(row[1]).strip() if pd.notna(row[1]) else ""

        if cell_qid == question_code:
            capture = True
            if data_format == "qualtrics" and cell_label:
                values.append(cell_label)  # ✅ include first row for qualtrics
            continue

        if capture and cell_qid.startswith("Q"):
            break

        if capture and cell_label:
            values.append(cell_label)

    return values


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

def detect_nps_questions_qualtrics(df: pd.DataFrame) -> list:
    """
    In a Qualtrics‐style dataframe (header row = Q‐codes), find any column
    whose name contains '_NPS_' (case‐insensitive) and return the base QID.
    E.g. 'Q9_NPS_GROUP' → 'Q9'.

    Returns a sorted list of unique QIDs.
    """
    qids = set()
    for col in df.columns:
        if isinstance(col, str) and re.search(r"_NPS_", col, re.IGNORECASE):
            m = re.search(r"(Q\d+)", col, re.IGNORECASE)
            if m:
                qids.add(m.group(1).upper())
    return sorted(qids)

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

def detect_single_choice_questions_qualtrics(df: pd.DataFrame) -> list:
    """
    Detect “single‐choice” questions in a Qualtrics dump:
      1. Column name must be exactly 'Q<digits>' (no suffixes).
      2. Exclude any QID that also shows up in an '_NPS_' column.

    Returns:
      A sorted list of QIDs (e.g. ['Q1','Q2', ...]) that look like single‐choice.
    """
    # 1) Find all pure-Q columns:
    pure_qs = {col for col in df.columns
               if isinstance(col, str) and re.fullmatch(r"Q\d+", col)}

    # 2) Find all QIDs that appear in an NPS column (e.g. 'Q9_NPS_GROUP')
    nps_qs = set()
    for col in df.columns:
        if isinstance(col, str) and re.search(r"_NPS_", col, re.IGNORECASE):
            m = re.match(r"(Q\d+)", col, re.IGNORECASE)
            if m:
                nps_qs.add(m.group(1).upper())

    # 3) Exclude the NPS ones
    singles = sorted(pure_qs - nps_qs,
                     key=lambda q: int(q[1:]))

    return singles
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

def detect_multi_select_questions_qualtrics(df: pd.DataFrame) -> list:
    """
    Detect Qualtrics multi‑select questions:
      1. Look for columns named Q<digits>_<digits>.
      2. Group by base QID (before the underscore).
      3. Must have at least two sub‑columns.
      4. Across all sub‑columns, values (after dropping NaNs) must be only 0 or 1.
    Returns a sorted list of base QIDs, e.g. ['Q2','Q5',…].
    """
    # 1) find all sub‑columns of the form Q<digits>_<digits>
    subs = [col for col in df.columns if isinstance(col, str) and re.fullmatch(r"Q\d+_\d+", col)]
    
    # 2) group by base
    groups = {}
    for col in subs:
        base = col.split("_")[0]
        groups.setdefault(base, []).append(col)

    result = []
    for base, cols in groups.items():
        if len(cols) < 2:
            continue
        # check that every non‑null entry across those cols is 0 or 1
        vals = (
            df[cols]
            .apply(pd.to_numeric, errors="coerce")
            .stack()
            .dropna()
            .unique()
        )
        if set(vals).issubset({0, 1}):
            result.append(base)

    return sorted(result, key=lambda q: int(q[1:]))


def detect_matrix_questions_qualtrics(df: pd.DataFrame) -> list:
    """
    Detect Qualtrics matrix questions:
      1. Reuse the same Q<digits>_<digits> pattern.
      2. Exclude any bases already flagged as multi‑select.
      3. Must have at least two sub‑columns.
      4. Across all sub‑columns, numeric values (after dropna) must lie between 0 and 10,
         and there should be more than two distinct values (to distinguish from a binary multi‑select).
    Returns a sorted list of base QIDs, e.g. ['Q3','Q7',…].
    """
    # first find all candidate sub‑columns
    subs = [col for col in df.columns if isinstance(col, str) and re.fullmatch(r"Q\d+_\d+", col)]
    # group by base
    groups = {}
    for col in subs:
        base = col.split("_")[0]
        groups.setdefault(base, []).append(col)

    # compute multi‑select so we can exclude
    multi = set(detect_multi_select_questions_qualtrics(df))

    matrices = []
    for base, cols in groups.items():
        if base in multi or len(cols) < 2:
            continue
        # pull all numeric values
        ser = (
            df[cols]
            .apply(pd.to_numeric, errors="coerce")
            .stack()
            .dropna()
        )
        if ser.empty:
            continue
        # check all between 0 and 10
        if not ser.between(0, 10).all():
            continue
        # ensure more than two distinct values (so it's not just binary)
        if ser.nunique() <= 2:
            continue

        matrices.append(base)

    return sorted(matrices, key=lambda q: int(q[1:]))
